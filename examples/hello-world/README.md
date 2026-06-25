How to build this PlatformIO based project
==========================================

A minimal smoke test for the **Meshtasticd WASM** platform: compile a bare C
program to WebAssembly with the emcc/em++ toolchain.

1. [Install PlatformIO Core](https://docs.platformio.org/page/core.html)
2. Install an [Emscripten SDK](https://emscripten.org/docs/getting_started/downloads.html)
   and put `emcc` on `PATH` — `source <emsdk>/emsdk_env.sh` (or `export EMSDK=<path>`).
3. Download [the platform with examples](https://github.com/meshtastic/platform-wasm/archive/master.zip)
4. Extract the ZIP archive
5. Run these commands:

```shell
# Change directory to example
$ cd platform-wasm/examples/hello-world

# Build project (emits meshnode.{mjs,wasm} under .pio/build/wasm/)
$ pio run

# Run the ES module under Node.js
$ pio run --target exec

# Clean build files
$ pio run --target clean
```
