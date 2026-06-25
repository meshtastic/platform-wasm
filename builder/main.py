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

    Prerequisite: an Emscripten SDK on the machine. The builder auto-locates it
    (PATH, $EMSDK, ~/emsdk, a project-local .emsdk, or a sibling Meshtastic
    companion checkout) and sources emsdk_env.sh, so `pio run` works even from a
    shell/IDE that didn't source it. Set $EMSDK_ENV to point at a specific
    emsdk_env.sh if it lives somewhere unusual.
"""

import os
import shutil
import subprocess

from SCons.Script import (
    AlwaysBuild,
    COMMAND_LINE_TARGETS,
    Default,
    DefaultEnvironment,
)

env = DefaultEnvironment()


#
# Locate (and if necessary bootstrap) the Emscripten toolchain.
#
# `emcc` just needs to be reachable. When `pio run` is invoked from a shell that
# didn't `source emsdk_env.sh` — a VS Code task, an IDE build button, a bare
# terminal — we probe the usual emsdk locations, source `emsdk_env.sh`, and
# import its environment (PATH / EMSDK / EM_CONFIG / ...) so the toolchain and
# emcc itself are set up. This keeps every consumer of the platform from having
# to carry their own bootstrap; it's a no-op when emcc is already on PATH (CI,
# or anyone who set it up in their shell).
#
def _emcc_on_path():
    return shutil.which("emcc")


def _prepend_path(directory):
    if directory and os.path.isdir(directory):
        os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")


def _source_emsdk_env(script):
    # Source emsdk_env.sh in a subshell and copy its environment back. A
    # newline-delimited `env` dump is portable across GNU/BSD; the emsdk vars
    # have no embedded newlines. Returns True if emcc became reachable.
    try:
        out = subprocess.check_output(
            ["bash", "-c", "source '%s' >/dev/null 2>&1 && env" % script],
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    for line in out.splitlines():
        key, sep, value = line.partition("=")
        if sep and key:
            os.environ[key] = value
    return bool(_emcc_on_path())


def _locate_emcc():
    if _emcc_on_path():
        return _emcc_on_path()

    emsdk = os.getenv("EMSDK")
    if emsdk:
        _prepend_path(os.path.join(emsdk, "upstream", "emscripten"))
        if _emcc_on_path():
            return _emcc_on_path()

    project_dir = env.subst("$PROJECT_DIR")
    home = os.path.expanduser("~")
    # Priority order: explicit override, $EMSDK, ~/emsdk, a project-local
    # checkout, then a sibling Meshtastic companion checkout (which bootstraps an
    # emsdk under ./emsdk via its tools/setup-emsdk.sh).
    candidates = [
        os.environ.get("EMSDK_ENV", ""),
        os.path.join(emsdk, "emsdk_env.sh") if emsdk else "",
        os.path.join(home, "emsdk", "emsdk_env.sh"),
        os.path.join(project_dir, ".emsdk", "emsdk_env.sh"),
        os.path.join(project_dir, "..", "meshtastic-web-node", "emsdk", "emsdk_env.sh"),
        os.path.join(project_dir, "..", "meshtasticd-wasm-node", "emsdk", "emsdk_env.sh"),
    ]
    for script in candidates:
        if script and os.path.isfile(script) and _source_emsdk_env(script):
            print("platform-wasm: emsdk environment loaded from %s" % script)
            return _emcc_on_path()

    return None


emcc = _locate_emcc()
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
