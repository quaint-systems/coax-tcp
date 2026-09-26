# Ordering the Liz 4174 board from JLCPCB

The Liz 4174 Terminal Controller v1 is interface3 Rev 3, the layout with the second port's transmit path corrected, built with a socketed Pico. It has the following changes:

- quaint-systems silkscreen
- the Pico left off the assembly
- USB-B and the NET LED not fitted
- a yellow PWR LED

JLC machine-places the SMD parts and hand-solders the two BNC jacks. The Pico sockets are fitted by hand.

## Files

| File | Use |
| --- | --- |
| `liz4174-v1-gerbers.zip` | PCB order: Gerbers plus Excellon drill files (PTH and NPTH separate) |
| `liz4174-v1-bom.csv` | PCBA BOM, one line per LCSC part |
| `liz4174-v1-cpl.csv` | PCBA placement file, top side |
| `parts.csv` | Source of truth: every footprint on the board, with how it is fitted and its LCSC part |
| `make_jlc.py` | Regenerates the three order files from `../pcb.kicad_pcb` and `parts.csv` |

Regenerate after any board or `parts.csv` change:

```bash
python3 make_jlc.py
```

The script refuses to run if a footprint on the board is missing from `parts.csv`, or if a part marked for assembly is missing from the placement export.

## PCB options

| Option | Setting |
| --- | --- |
| Layers | 2 |
| Size | 107.47 x 65.97 mm (JLC reads it from the Gerbers) |
| Thickness | 1.6 mm |
| Surface finish | HASL lead-free or ENIG |
| Mark on PCB | "Specify position": the `JLCJLCJLCJLC` text on the top silkscreen, under the Pico's outline, marks the spot, so the order number ends up hidden beneath the Pico |

## Assembly options

| Option | Setting |
| --- | --- |
| Type | Economic, top side |
| Quantity | at least 2 boards |
| Upload | `liz4174-v1-bom.csv` and `liz4174-v1-cpl.csv` |

Parts and fees:

- **Extended-part fees:** the Economic quote on 2026-09-26 (T1/T2 not placed) charged three Extended-part fees at $3.09, most likely for U1, U2 and SW1. The yellow LED is labelled Extended but carried no fee, and neither did the hand-soldered BNC. The whole order came to $89.77 for 5 assembled boards, before shipping.
- **Hand-soldered through-hole:** J1 and J2 need JLC's through-hole hand soldering.
- **U2 stock:** LCSC had only 100 of U2 (C1543778) on 2026-09-26. Buy them into your JLC parts library before ordering. The fallback is C2672589, the DS34LV87TMX/NOPB reel part.
- **T1 and T2 (Murata 78602/8JC, C7040198):** LCSC had none on 2026-09-26.
  - At the BOM matching step, look them up under **Global Sourcing**.
  - If Global Sourcing does not offer them, set T1 and T2 to "do not place" and fit them by hand. DigiKey stocks 78602/8JC. The 786J package is J-lead on a 2.54 mm pitch.
  - Do not substitute another 786J variant: the transmit waveform depends on this transformer.

### Check the placement preview

Before paying, check the placement preview:

- **U1 and U2:** the pin-1 dot sits at the silkscreen dot.
- **LEDs (D1–D9, D11, D12):** the cathode is on the correct side.
- **T1 and T2:** the pin-1 marking matches the silkscreen, if they were sourced.
- **SW1:** the legs lie on the four pads. Either 0° or 180° is electrically fine.

If JLC's library holds a part at a different zero orientation, record the correction in `ROTATION_FIX` in `make_jlc.py` and regenerate, rather than editing the CPL.

## Fitted by hand

| Part | Notes |
| --- | --- |
| Pico sockets | 2 x 1x20 female header, 2.54 mm, standard 8.5 mm height, in U3's through-holes |
| Pico 2 | With male headers. Its own micro-USB carries power and data. |
| T1, T2 | Only if Global Sourcing did not supply them |

## Not fitted

| Ref | Why |
| --- | --- |
| J4 (USB-B) | A socketed Pico cannot reach the data pads under it, and the jack would tie two hosts' VBUS together through the Pico |
| D10, R22 (NET LED) | `LED_NET` has no driver since the second port's signals were rerouted |
| J3 (ports 3/4 header) | Not needed; fit a 2x6 2.54 mm header if the TTL ports are wanted |
| TP2, TP3 | USB test pads for a Pico soldered flat; unused with a socket |
