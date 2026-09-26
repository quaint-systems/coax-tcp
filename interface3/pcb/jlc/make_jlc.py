#!/usr/bin/env python3
"""Generate the JLCPCB fabrication and assembly files for the Liz 4174 board.

Writes, next to this script:
  liz4174-v1-gerbers.zip  Gerbers and Excellon drill files for the PCB order
  liz4174-v1-bom.csv      Assembly BOM, one row per LCSC part
  liz4174-v1-cpl.csv      Placement file for the parts JLC fits

Every footprint on the board must be listed in parts.csv, so a part cannot
fall off the order without the script saying so.  Needs kicad-cli from
KiCad 10; set KICAD_CLI to use a different one.
"""
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent / "pcb.kicad_pcb"
NAME = "liz4174-v1"
KICAD_CLI = os.environ.get(
    "KICAD_CLI",
    shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
)

GERBER_LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"

# JLC's library may hold a part at a different zero orientation than KiCad's
# footprint.  Leave this empty until JLC's placement preview shows otherwise,
# then add the correction in degrees here rather than editing the CPL by hand.
ROTATION_FIX = {}


def run(*args):
    subprocess.run([KICAD_CLI, *args], check=True, capture_output=True, text=True)


def load_parts():
    parts = {}
    with open(HERE / "parts.csv", newline="") as f:
        for row in csv.DictReader(f):
            for ref in row["refs"].split():
                if ref in parts:
                    sys.exit(f"parts.csv lists {ref} twice")
                parts[ref] = row
    return parts


def board_refs():
    refs = set()
    for line in BOARD.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith('(property "Reference" "'):
            refs.add(line.split('"')[3])
    return refs


def gerbers(tmp):
    out = tmp / "gerbers"
    out.mkdir()
    run("pcb", "export", "gerbers", "--output", str(out), "--layers", GERBER_LAYERS,
        "--no-x2", "--no-netlist", "--subtract-soldermask", "--check-zones", str(BOARD))
    run("pcb", "export", "drill", "--output", str(out), "--format", "excellon",
        "--excellon-units", "mm", "--excellon-zeros-format", "decimal",
        "--excellon-oval-format", "alternate", "--drill-origin", "absolute",
        "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", str(BOARD))
    zpath = HERE / f"{NAME}-gerbers.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.iterdir()):
            z.write(p, p.name)
    return zpath, sorted(p.name for p in out.iterdir())


def placements(tmp):
    pos = tmp / "pos.csv"
    run("pcb", "export", "pos", "--output", str(pos), "--format", "csv", "--units", "mm",
        "--side", "front", "--exclude-dnp", str(BOARD))
    with open(pos, newline="") as f:
        return {row["Ref"]: row for row in csv.DictReader(f)}


def main():
    parts = load_parts()
    on_board = board_refs()
    missing = sorted(on_board - parts.keys())
    extra = sorted(parts.keys() - on_board)
    if missing or extra:
        sys.exit(f"parts.csv does not match the board: missing {missing}, not on board {extra}")

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        zpath, files = gerbers(tmp)
        pos = placements(tmp)

    fitted = {r: p for r, p in parts.items() if p["assembly"] in ("smt", "tht")}
    absent = sorted(r for r in fitted if r not in pos)
    if absent:
        sys.exit(f"parts JLC should fit are missing from the placement export: {absent}")

    with open(HERE / f"{NAME}-cpl.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref in sorted(fitted, key=lambda r: (r.rstrip("0123456789"), int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")))):
            p = pos[ref]
            rot = (float(p["Rot"]) + ROTATION_FIX.get(ref, 0)) % 360
            w.writerow([ref, p["PosX"], p["PosY"], "Top", f"{rot:g}"])

    groups = {}
    for ref, p in fitted.items():
        groups.setdefault(p["lcsc"], (p, []))[1].append(ref)
    with open(HERE / f"{NAME}-bom.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for lcsc, (p, refs) in sorted(groups.items(), key=lambda g: g[1][1][0]):
            refs.sort(key=lambda r: (r.rstrip("0123456789"), int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))))
            w.writerow([p["comment"], ",".join(refs), pos[refs[0]]["Package"], lcsc])

    print(f"{zpath.name}: {len(files)} files")
    for name in files:
        print(f"  {name}")
    print(f"{NAME}-bom.csv: {len(groups)} lines, {len(fitted)} parts")
    print(f"{NAME}-cpl.csv: {len(fitted)} placements")
    left = sorted(r for r, p in parts.items() if p["assembly"] == "none")
    print(f"not fitted by JLC: {' '.join(left)}")


if __name__ == "__main__":
    main()
