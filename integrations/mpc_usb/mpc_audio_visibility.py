#!/usr/bin/env python3
"""Reversible RAM-only interoperability experiment for this exact MPC build.

The MPC 3.9.1 device enumerator skips ALSA longnames starting UAC2_Gadget.
Change its comparison literal in RAM, never the executable or project files.
The original binary, instruction sequence, map and literal are checked first.
"""
import json
import os
import re
from pathlib import Path
import subprocess as S
import sys

ROOT = Path(os.environ['MPC_STUDIO_ROOT']).resolve()
SSH = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
       '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=3', '-o', 'ServerAliveCountMax=1',
       '-o', 'UserKnownHostsFile=' + str(ROOT/'run/known_hosts'),
       'root@' + os.environ['MPC_HOST']]
OFFSET = 0x4abead4
ORIGINAL = b'UAC2_Gadget\0'
CHANGED = b'XAC2_Gadget\0'
EXPECTED_HASH = 'c8b33873cad5c4e5d069c6b28e98dab83d9badaa4a4c18976c58a15e326c11f6'

def run(cmd, data=None):
    return S.run(SSH+[cmd], input=data, stdout=S.PIPE, stderr=S.PIPE, check=True, timeout=15).stdout

def main(action):
    if action not in ('apply', 'restore', 'status'):
        raise SystemExit('Usage: mpc_audio_visibility.py apply|restore|status')
    actual_hash = run('sha256sum /usr/bin/MPC').decode().split()[0]
    if actual_hash != EXPECTED_HASH:
        raise RuntimeError('Different MPC executable: refusing the build-specific experiment')
    pid = int(run('systemctl show -p MainPID --value acvs').strip())
    if pid <= 1: raise RuntimeError('MPC application not running')
    card = run('for c in /proc/asound/card[0-9]*; do '
               'if [ "$(cat "$c/id" 2>/dev/null)" = UAC2Gadget ]; then echo "${c##*/}"; fi; done').decode().strip()
    if not re.fullmatch(r'card[0-9]+', card):
        raise RuntimeError('Unique UAC2 Gadget card not found')
    maps = run('cat /proc/%d/maps' % pid).decode().splitlines()
    candidates = []
    for line in maps:
        fields = line.split()
        start, end = (int(x, 16) for x in fields[0].split('-'))
        if fields[1] == 'r-xp' and fields[4] == '0' and end-start > OFFSET+len(ORIGINAL):
            address = start+OFFSET
            value = run('dd if=/proc/%d/mem bs=1 skip=%d count=12 2>/dev/null' % (pid,address))
            if value in (ORIGINAL, CHANGED): candidates.append((start,address,value))
    if len(candidates) != 1: raise RuntimeError('Unambiguous executable mapping not found')
    base, address, current = candidates[0]
    # ldr r1 literal; mov r0,r5; add r1,pc,r1; bl string constructor
    code = run('dd if=/proc/%d/mem bs=1 skip=%d count=16 2>/dev/null' % (pid,base+0x1f8231c))
    if code != bytes.fromhex('5c129fe50500a0e101108fe07bc4a6eb'):
        raise RuntimeError('Unexpected enumerator instructions; no modification made')
    desired = ORIGINAL if action == 'restore' else CHANGED
    changed = False
    if action != 'status' and current != desired:
        if action == 'restore':
            state = run('cat /proc/asound/'+card+'/pcm0p/sub0/status').strip()
            if state not in (b'', b'closed'):
                raise RuntimeError('Select Internal on MPC before restoring the filter')
        # GNU dd opens with O_LARGEFILE; BusyBox cannot write addresses beyond 2 GiB.
        run('/tmp/codex-dd of=/proc/%d/mem bs=1 seek=%d count=1 conv=notrunc status=none' % (pid,address), desired[:1])
        current = run('dd if=/proc/%d/mem bs=1 skip=%d count=12 2>/dev/null' % (pid,address))
        if current != desired: raise RuntimeError('RAM write verification failed')
        changed = True
        run('udevadm trigger --action=change /sys/class/sound/'+card+'; udevadm settle')
    result = {'pid':pid, 'binary_sha256':actual_hash, 'address':hex(address),
              'filter_bypassed':current==CHANGED, 'changed':changed,
              'scope':'One byte of comparison text in running MPC RAM only; on-disk firmware untouched'}
    (ROOT/'run/audio-visibility.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__ == '__main__': main(sys.argv[1] if len(sys.argv)>1 else 'status')
