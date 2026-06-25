# Meshtasticd WASM: development platform for PlatformIO

A PlatformIO [development platform](https://docs.platformio.org/en/latest/platforms/index.html)
that compiles the Meshtastic **portduino** node to **WebAssembly** with
[Emscripten](https://emscripten.org/), so `meshtasticd` runs in a browser tab (or
headless Node) and drives a LoRa radio over **WebUSB** through a CH341 USB→SPI
bridge.

It is the WASM sibling of
[meshtastic/platform-native](https://github.com/meshtastic/platform-native):
same portduino Arduino core and `framework-portduino` package, but the host
GCC/Clang toolchain is swapped for `emcc`/`em++` and the link is an
[Asyncify](https://emscripten.org/docs/porting/asyncify.html) ES module. The
firmware's setup()/loop() are unchanged; the radio HAL talks WebUSB and the
cooperative loop suspends via Asyncify while a USB transfer awaits.

## Usage

In a project's `platformio.ini`:

```ini
[env:wasm]
platform = https://github.com/meshtastic/platform-wasm/archive/<sha>.zip
framework = arduino
board = wasm
```

Then `pio run -e wasm`. An **Emscripten SDK must be on `PATH`** — `source
<emsdk>/emsdk_env.sh` (or `export EMSDK=<path>`) — so the builder can locate
`emcc`. The build emits `<progname>.mjs` + `<progname>.wasm` (ES module,
MODULARIZE/EXPORT_ES6, Asyncify, growable memory).

The canonical consumer is the firmware's `[env:wasm]` target
(`src/platform/portduino/wasm/`), which adds the app-specific link settings
(exported functions, the WebUSB Asyncify import seam, runtime methods).

## Layout

| path                            | role                                                                                |
| ------------------------------- | ----------------------------------------------------------------------------------- |
| `platform.json`                 | platform manifest: the `framework-portduino` package + the `arduino` framework hook |
| `builder/main.py`               | points the SCons toolchain at `emcc`/`em++`; the core Asyncify/MODULARIZE link flags |
| `builder/frameworks/arduino.py` | builds the emcc-safe portduino core subset (mirrors platform-native)                |
| `boards/wasm.json`              | the `wasm` board (`ARCH_PORTDUINO` / `ARCH_PORTDUINO_WASM`)                          |
| `examples/hello-world`          | minimal "compile C to wasm" smoke test                                              |

## License

GPL-3.0-or-later, matching the [Meshtastic firmware](https://github.com/meshtastic/firmware)
(see [LICENSE](LICENSE)). The `builder/` scripts are derived from PlatformIO's
platform-native scaffolding (Apache-2.0, which is GPL-compatible) and retain
their original file headers.
