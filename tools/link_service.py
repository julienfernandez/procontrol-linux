#!/usr/bin/env python3
"""Build and manage the optional Ardour -> Ableton Link bridge (systemd user)."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REVISION = '902aef95bf94af49746fdda5369b42cdcfa1e6d2'
UNIT = 'procontrol-link.service'
BINARY = ROOT / 'build/procontrol-link'
STATUS = ROOT / 'run/link-status.json'

def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'

def build(sdk):
    sdk = Path(sdk).resolve() if sdk else ROOT / 'work/ableton-link'
    if not sdk.exists():
        sdk.parent.mkdir(parents=True, exist_ok=True)
        run('git', 'clone', 'https://github.com/Ableton/link.git', str(sdk))
        run('git', '-C', str(sdk), 'checkout', '--detach', REVISION)
    revision = subprocess.check_output(['git', '-C', str(sdk), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise RuntimeError('SDK revision mismatch; expected ' + REVISION)
    if subprocess.check_output(['git', '-C', str(sdk), 'status', '--porcelain', '--untracked-files=no'], text=True).strip():
        raise RuntimeError('SDK contains tracked modifications')
    run('git', '-C', str(sdk), 'submodule', 'update', '--init', '--recursive', '--depth', '1')
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    # Replace atomically, never overwrite the inode of a running executable.
    temporary = BINARY.with_suffix('.new')
    run('c++', '-O2', '-std=c++17', '-Wall', '-Wextra', '-Wno-multichar', '-DLINK_PLATFORM_LINUX=1',
        '-DASIO_STANDALONE=1', '-I' + str(sdk / 'include'),
        '-I' + str(sdk / 'modules/asio-standalone/asio/include'),
        str(ROOT / 'native/ardour_link.cc'), '-ljack', '-lpthread', '-o', str(temporary))
    temporary.replace(BINARY)
    (BINARY.parent / 'link-provenance.json').write_text(json.dumps({
        'sdk': 'https://github.com/Ableton/link', 'commit': REVISION,
        'license': 'GPL-2.0-or-later', 'binary': str(BINARY),
    }, indent=2) + '\n')
    print('Link bridge built:', BINARY)

def install(library):
    if not BINARY.is_file():
        raise RuntimeError('Build first: ./link build')
    if library:
        library = Path(library).resolve()
        if not (library / 'libjack.so.0').exists():
            raise RuntimeError('--jack-library must be a directory containing libjack.so.0')
    directory = Path.home() / '.config/systemd/user'
    directory.mkdir(parents=True, exist_ok=True)
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    environment = 'Environment=' + quote('LD_LIBRARY_PATH=' + str(library)) + '\n' if library else ''
    (directory / UNIT).write_text(
        '[Unit]\nDescription=Ardour transport and tempo to Ableton Link\n'
        'After=pipewire.service\nStartLimitIntervalSec=0\n\n'
        '[Service]\nType=simple\n' + environment +
        'ExecStart=' + quote(BINARY) + ' ' + quote(STATUS) + '\n'
        'Restart=on-failure\nRestartSec=5\nTimeoutStopSec=5\nUMask=0077\n\n'
        '[Install]\nWantedBy=default.target\n')
    run('systemctl', '--user', 'daemon-reload')
    print('User service installed; start with ./link start')

def status():
    active = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', UNIT]).returncode == 0
    try:
        data = json.loads(STATUS.read_text())
        fresh = time.time() - STATUS.stat().st_mtime < 4
        pid = int(data['pid'])
        same_process = Path('/proc', str(pid), 'exe').resolve() == BINARY
        data['running'] = bool(active and fresh and same_process)
    except (OSError, ValueError, KeyError):
        data = {'running': False}
    data['service_active'] = active
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'install', 'start', 'stop', 'status'])
    parser.add_argument('--sdk', help='Existing clean checkout of the pinned Ableton Link SDK')
    parser.add_argument('--jack-library', help='JACK library directory; use the same backend as Ardour')
    args = parser.parse_args()
    if args.command == 'build': build(args.sdk)
    elif args.command == 'install': install(args.jack_library)
    elif args.command == 'status': status()
    else:
        run('systemctl', '--user', args.command, UNIT)
        if args.command == 'start':
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if STATUS.exists() and time.time() - STATUS.stat().st_mtime < 2: break
                time.sleep(.1)
            if not status()['running']: raise RuntimeError('Link did not start; inspect journalctl --user -u ' + UNIT)

if __name__ == '__main__':
    try: main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
