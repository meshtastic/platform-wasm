# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
    Builder for the Meshtastic WASM platform (Emscripten).

    Mirrors platform-native's main.py, but swaps the host GCC toolchain for
    Emscripten's emcc/em++. We let env.Tool("gcc")/("g++") install the standard
    SCons compile/link command templates ($CCCOM/$CXXCOM/$LINKCOM/...), then
    env.Replace the actual binaries with emcc/em++/emar/emranlib so those
    templates drive Emscripten. The "program" links to <progname>.mjs and emcc
    emits the companion <progname>.wasm.

    Prerequisite: emcc must be reachable. Either `source <emsdk>/emsdk_env.sh`
    so it's on PATH, or set $EMSDK to your emsdk checkout.
"""

import os
import shutil

from SCons.Script import (
    AlwaysBuild,
    COMMAND_LINE_TARGETS,
    Default,
    DefaultEnvironment,
)

env = DefaultEnvironment()

#
# Locate the Emscripten toolchain
#
emcc = shutil.which("emcc")
if not emcc and os.getenv("EMSDK"):
    cand = os.path.join(os.getenv("EMSDK"), "upstream", "emscripten", "emcc")
    if os.path.isfile(cand):
        emcc = cand
if not emcc:
    raise SystemExit(
        "platform-wasm: emcc not found. Install the Emscripten SDK and run "
        "`source <emsdk>/emsdk_env.sh` (or export EMSDK=<path>) before building."
    )
EMSDK_BIN = os.path.dirname(emcc)


def _tool(name):
    p = os.path.join(EMSDK_BIN, name)
    return p if os.path.isfile(p) else name


#
# Install the standard host-compiler command templates, then point the actual
# toolchain binaries at Emscripten. (Following platform-native: env.Tool sets up
# $CCCOM/$CXXCOM/$LINKCOM/$ARCOM and the object/program suffixes; we keep those
# and only swap which compiler they invoke.)
#
for k in ("CC", "CXX"):
    if k in env:
        del env[k]

backup_cflags = env.get("CFLAGS", [])
backup_cxxflags = env.get("CXXFLAGS", [])

env.Tool("gcc")
env.Tool("g++")

if "compiledb" in COMMAND_LINE_TARGETS:
    env.Tool("compilation_db")

env.Append(CFLAGS=backup_cflags, CXXFLAGS=backup_cxxflags)

env.Replace(
    AR=_tool("emar"),
    AS=_tool("emcc"),
    CC=_tool("emcc"),
    CXX=_tool("em++"),
    LINK=_tool("em++"),
    RANLIB=_tool("emranlib"),
    PROGSUFFIX=".mjs",  # emcc -o x.mjs emits x.mjs + x.wasm (ES module loader)
    PROGNAME="meshnode",  # consumers (CI, companion) expect meshnode.{mjs,wasm}
)

# Core Emscripten/Asyncify settings that define a "wasm node" image. App- and
# firmware-specific link flags (EXPORTED_FUNCTIONS, ASYNCIFY_IMPORTS, the radio
# backend's import names, EXPORT_NAME) belong in the project's build_flags.
env.Append(
    LINKFLAGS=[
        "-fexceptions",
        "-sASYNCIFY=1",
        "-sALLOW_MEMORY_GROWTH=1",
        "-sINITIAL_MEMORY=64MB",
        "-sSTACK_SIZE=5MB",
        "-sMODULARIZE=1",
        "-sEXPORT_ES6=1",
        "-sINVOKE_RUN=0",
        "-sERROR_ON_UNDEFINED_SYMBOLS=1",
        "-lidbfs.js",
        "-lnodefs.js",
    ]
)

#
# Target: Build program -> <progname>.mjs + <progname>.wasm
#
target_bin = env.BuildProgram()

# `pio run -t exec` runs the headless node under Node.js (INVOKE_RUN=0 means
# callMain must be driven by the host, so this is mostly a smoke hook).
exec_action = env.VerboseAction("node $SOURCE $PROGRAM_ARGS", "Executing $SOURCE")
AlwaysBuild(env.Alias("exec", target_bin, exec_action))
AlwaysBuild(env.Alias("upload", target_bin, exec_action))

Default([target_bin])
