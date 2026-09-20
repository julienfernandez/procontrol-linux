#!/usr/bin/env python3
"""Build/run a regression against a supplied, already built Ardour library."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--library-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source, lib = args.source.resolve(), args.library_dir.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    includes = [source/'libs'] + [source/'libs'/d for d in
                ('ardour', 'pbd', 'temporal', 'evoral', 'timecode', 'midi++2')]
    flags = subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'glibmm-2.4', 'sigc++-2.0', 'libxml-2.0'], text=True).split()
    subprocess.run(['g++', '-std=c++17', '-g', str(root/'native/tests/session-event-pool.cc'),
                    str(source/'libs/ardour/test/dummy_lxvst.cc'),
                    '-o', str(output)] + ['-I'+str(p) for p in includes] +
                   ['-L'+str(lib), '-Wl,-rpath,'+str(lib), '-lardour', '-lpbd'] + flags, check=True)
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(lib) + (':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    return subprocess.run([str(output)], env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())
