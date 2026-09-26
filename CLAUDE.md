# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Hardware, firmware and host tools for driving real IBM 3270 coax terminals (CUT mode). The host side is normally [oec](https://github.com/lowobservable/oec) (or the TCP fork [oec-tcp](https://github.com/hanshuebner/oec-tcp)), which talks to one of the interfaces here through `pycoax`. `protocol/protocol.md` documents the coax wire protocol itself.

Independent subprojects, each with its own toolchain:

| Dir | What | Toolchain |
|-----|------|-----------|
| `interface1/` | Legacy DP8340/DP8341 board | PlatformIO (Arduino) |
| `interface2/` | iCE40 FPGA + STM32L443 | Verilog (iverilog tests, iCEcube2 synthesis), PlatformIO firmware |
| `interface3/` | Raspberry Pi Pico board, up to 4 coax ports | C firmware (pico-sdk) **and** older MicroPython firmware |
| `interface4/` | RP2350 Pi HAT board | KiCad only, no code |
| `pycoax/` | Python host library (`coax` package) | Python 3.8+ |

The active branch of work is `interface3` (its C firmware and tools).

## Commands

### interface3 C firmware (`interface3/firmware/`)

```bash
git submodule update --init interface3/firmware/pico-sdk   # vendored SDK; PICO_SDK_PATH overrides it
cd interface3
make                 # builds all four boards -> coax_interface-{pico,pico_w,pico2,pico2_w}.uf2
make pico2           # one board; build dir is firmware/build-<board>/ (CMake + Ninja)
make distclean
tools/flash-interface coax_interface-pico2.uf2   # Linux host: 1200-baud reset into bootloader, copy UF2, wait for re-enumeration
```

There are no unit tests for the C firmware. `interface3/confidence_test.py <port>` exercises RESET/INFO and polls a terminal over the serial protocol on real hardware.

### interface3 MicroPython firmware (`interface3/src/`)

```bash
cd interface3
./install.sh serial   # or wifi; uploads src/*.py via mpremote, installs main_<mode>.py as main.py
./config-wifi.sh      # WiFi mode: writes config.json on the device
./test-serial.sh      # run without installing
```

CI (`.github/workflows/interface3_build.yml`) builds only this MicroPython image (frozen into a `hanshuebner/micropython` rp2-dma build), not the C firmware.

### pycoax

```bash
cd pycoax
pip install -r requirements.txt
pylint -E coax                       # the lint CI runs
./run_unit_tests.sh                  # python -m unittest discover tests
python -m unittest tests.test_tcp_interface            # one module
python -m unittest tests.test_protocol.PollTestCase     # one class/method
```

### interface2 FPGA

```bash
cd interface2/fpga
make tests                           # iverilog testbenches in tests/
cd tests && ./run_tests.sh coax_rx_tb   # run one compiled testbench (fails on "[FAIL:" lines)
```
Bitstream synthesis (`make rtl`) needs the proprietary iCEcube2 Docker image; firmware (`interface2/firmware`, `pio run`) embeds the bitstream from `fpga/rtl/top.bin`.

## interface3 C firmware architecture

Single cooperative main loop in `main.c` (no RTOS): `tud_task()` → each command port → capture port → `tap_task()` → `leds_update()`. Nothing may block for long; waits must call `tud_task()`.

- **USB**: TinyUSB composite device with 5 CDC ports (`usb_descriptors.c`): CDC 0–3 are command ports, one per coax port; CDC 4 (`CAPTURE_CDC_PORT`) is `Coax Capture`. stdio over USB/UART is disabled. Opening any CDC at **1200 baud** reboots into the USB bootloader — the command protocol must never set a baud rate.
- **Command protocol** (`slip.c`, `command.c`): SLIP-framed, interface2-compatible messages (`[len16 BE][cmd][payload][00 00]`) so unmodified oec/pycoax `SerialInterface` works. Commands: RESET, TRANSMIT_RECEIVE, INFO (incl. counters), TEST, DFU. A single USB read can contain the tail of one frame and the start of the next — `slip_feed` returns how much it consumed and the caller re-feeds the rest.
- **Coax PHY** (`coax.pio`, `coax.c`): Manchester encode/decode in PIO at `12 × 2.3587 MHz`, frames moved by DMA. `coax_transact()` does one transmit-then-receive on the currently selected port (`coax_switch_port`), frames up to `MAX_FRAME_LENGTH` (8192) 10-bit words carried as 16-bit LE containers. PIO state machines are reset to program start on each transaction; TX DMA drain is bounded by a timeout.
- **Capture** (`capture.c`, `tools/coax-capture`, `tools/coax.lua`): records are SLIP-encoded into a 16 KB ring and drained opportunistically; capture must never delay a transaction (overflow → counted DROP records). Record format and pcapng layout are in `interface3/CAPTURE.md`.
- **Tap / forward** (`tap.c`, `forward.c`): passive listening on a port, or bit-level repeating between two ports. Both need PIO instruction memory, so they call `coax_release()` and transactions are refused until `coax_restore()`. On RP2040 (2 PIOs) a tap takes the RX program and blocks transactions on **all** ports (`tap_holds_all_ports()`); RP2350 has a third PIO. See `interface3/PASSIVE-CAPTURE.md`, and `PCB-REWORK.md` for boards that need rework to transmit on the second port.
- Constants shared with the host tools (capture record types/flags/commands, info queries) are duplicated in `capture.h`/`command.c` and `tools/coax-capture` / `pycoax` — change both sides together.

The MicroPython firmware (`src/`) is the original implementation of the same protocol; `coax.pio` was translated from `src/coax.py`, and `cmd_reset` deliberately matches its response bytes. WiFi mode (`src/tcpserver.py`, `TCP_PROTOCOL.md`) exists only in the MicroPython version.

## Host deployment

`interface3/systemd/` has user units running one oec per coax port, addressed by `/dev/serial/by-id/...-if00`/`-if02` (not `ttyACM*`, which shifts with the CDC count) and bound to the `.device` unit so they restart after reflashing. In unit files the dashes in device paths must be written `\x2d`.

## Conventions

Commit messages are a single imperative sentence describing the behavior change (e.g. "Bound the wait for the transmit DMA to drain"). Code comments explain *why* in full sentences, matching the existing style.
