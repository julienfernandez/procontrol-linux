#!/usr/bin/env python3
"""Exercise real PBD queued callbacks with a built, patched Ardour source tree."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import os
from pathlib import Path
import shlex
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--library-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = args.source.resolve()
    lib = args.library_dir.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'glibmm-2.4', 'sigc++-2.0', 'libxml-2.0'], text=True))
    includes = [source, source/'build'] + [source/p for p in (
        'libs/pbd', 'build/libs/pbd', 'libs/temporal', 'build/libs/temporal', 'libs/surfaces/osc')]
    subprocess.run([
        'g++', '-std=c++17', '-O1', '-g', '-pthread', '-DPLATFORM_LINUX', '-DCOMPILER_GCC',
        str(root/'native/tests/osc-observer-lifetime.cc'), '-o', str(output),
        *['-I'+str(p) for p in includes], '-L'+str(lib), '-Wl,-rpath,'+str(lib), '-lpbd', *flags,
    ], check=True)
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(lib) + (':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    return subprocess.run([str(output)], env=env, timeout=60).returncode


if __name__ == '__main__':
    raise SystemExit(main())
