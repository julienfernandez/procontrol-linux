"""Persistent validated settings shared by the daemon, pointer and local UI."""
# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
import math
import os
from pathlib import Path
import secrets
import socket

DEFAULTS = {'version': 1, 'revision': 0, 'pointer_gain': .24, 'jog_gain': 1.,
            'meter_assignments': [{'source': 'master', 'channel': 0},
                                  {'source': 'master', 'channel': 1}] +
                                 [{'source': '', 'channel': 0} for _ in range(4)],
            'meter_addresses': [None] * 6}


def validate(data):
    if not isinstance(data, dict) or set(data) - set(DEFAULTS):
        raise ValueError('Champs de configuration inconnus')
    result = copy.deepcopy(DEFAULTS); result.update(copy.deepcopy(data))
    if type(result['version']) is not int or result['version'] != 1:
        raise ValueError('Version de configuration inconnue')
    if type(result['revision']) is not int or result['revision'] < 0:
        raise ValueError('Révision invalide')
    for field, low, high in [('pointer_gain', .01, 1.), ('jog_gain', .05, 10.)]:
        value = result[field]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{field} doit être entre {low} et {high}')
        result[field] = float(value)
    rows = result['meter_assignments']
    if not isinstance(rows, list) or len(rows) != 6:
        raise ValueError('Six affectations requises')
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'source', 'channel'}:
            raise ValueError('Affectation invalide')
        if not isinstance(row['source'], str) or len(row['source']) > 512:
            raise ValueError('Source invalide')
        if type(row['channel']) is not int or not 0 <= row['channel'] <= 63:
            raise ValueError('Canal invalide')
    addresses = result['meter_addresses']
    if not isinstance(addresses, list) or len(addresses) != 6:
        raise ValueError('Six adresses requises')
    present = [a for a in addresses if a is not None]
    if any(type(a) is not int or not (8 <= a < 32 or 40 <= a < 64) for a in present) or len(set(present)) != len(present):
        raise ValueError('Adresses de grands vumètres invalides ou répétées')
    return result


def load(path):
    try: return validate(json.loads(Path(path).read_text()))
    except FileNotFoundError: return copy.deepcopy(DEFAULTS)


def save(path, data):
    result = validate(data); path = Path(path)
    temp = path.with_name(path.name + '.' + secrets.token_hex(4) + '.tmp')
    try:
        with temp.open('x') as f:
            os.chmod(temp, 0o600); json.dump(result, f, indent=2, ensure_ascii=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        temp.replace(path)
    finally: temp.unlink(missing_ok=True)
    return result


def rpc(runtime, name, request, timeout=1.):
    fd = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.bind('\0procontrol-' + secrets.token_hex(12)); sock.settimeout(timeout)
            sock.sendto(json.dumps(request).encode(), f'/proc/self/fd/{fd}/{name}')
            return json.loads(sock.recv(65535))
    finally: os.close(fd)
