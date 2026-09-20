#!/usr/bin/env python3
"""Inspect a ProControl personality resource fork offline. Never communicates with hardware.

Extracts CODE resources containing Intel HEX into separate contiguous segments,
without filling unrepresented addresses or treating these images as a ROM backup.
Only Python's standard library is required. Proprietary input/output stays local.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct


class FirmwareError(ValueError):
    pass


def bounded(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise FirmwareError(f'Out-of-bounds region: offset={offset}, size={size}')
    return data[offset:offset + size]


def resources(data):
    """Read classic resource-fork records with offsets checked within each region."""
    data_offset, map_offset, data_size, map_size = struct.unpack('>4I', bounded(data, 0, 16))
    if min(data_offset, map_offset) < 16:
        raise FirmwareError('Resource regions overlap the header')
    if max(data_offset, map_offset) < min(data_offset + data_size, map_offset + map_size):
        raise FirmwareError('Resource data and map overlap')
    area = bounded(data, data_offset, data_size)
    table = bounded(data, map_offset, map_size)
    type_offset, name_offset = struct.unpack('>HH', bounded(table, 24, 4))
    if type_offset < 28 or name_offset < 28:
        raise FirmwareError('Resource list overlaps map header')
    types = bounded(table, type_offset, len(table) - type_offset)
    names = bounded(table, name_offset, len(table) - name_offset)
    last_type = struct.unpack('>H', bounded(types, 0, 2))[0]
    count = 0 if last_type == 0xffff else last_type + 1
    bounded(types, 2, count * 8)
    found, identities = [], set()
    for i in range(count):
        kind, last, refs = struct.unpack('>4sHH', bounded(types, 2 + i * 8, 8))
        for j in range(last + 1):
            ident, name_at, attributes_offset, _ = struct.unpack('>hHII', bounded(types, refs + j * 12, 12))
            if (kind, ident) in identities:
                raise FirmwareError('Duplicate resource type/id')
            identities.add((kind, ident))
            offset = attributes_offset & 0xffffff
            length = struct.unpack('>I', bounded(area, offset, 4))[0]
            body = bounded(area, offset + 4, length)
            name = None
            if name_at != 0xffff:
                length_name = bounded(names, name_at, 1)[0]
                name = bounded(names, name_at + 1, length_name).decode('mac_roman')
            found.append({'type': kind.decode('ascii', errors='replace'), 'id': ident,
                          'name': name, 'offset': data_offset + offset + 4,
                          'size': length, 'data': body})
    return found


def intel_hex(data):
    """Validate every record and retain only addressed bytes, rejecting overlaps."""
    try:
        lines = data.decode('ascii').splitlines()
    except UnicodeError as exc:
        raise FirmwareError('Non-ASCII Intel HEX') from exc
    memory, types, starts = {}, Counter(), []
    base, ended, records = 0, False, 0
    for line_number, line in enumerate(lines, 1):
        if not line:
            continue
        if ended:
            raise FirmwareError(f'Line {line_number}: record after EOF')
        if not re.fullmatch(r':[0-9a-fA-F]+', line) or len(line) % 2 != 1:
            raise FirmwareError(f'Line {line_number}: invalid HEX syntax')
        raw = bytes.fromhex(line[1:])
        if len(raw) < 5 or len(raw) != raw[0] + 5:
            raise FirmwareError(f'Line {line_number}: inconsistent byte count')
        if sum(raw) & 0xff:
            raise FirmwareError(f'Line {line_number}: checksum mismatch')
        size, address, kind = raw[0], int.from_bytes(raw[1:3], 'big'), raw[3]
        payload = raw[4:-1]
        records += 1
        types[f'{kind:02x}'] += 1
        if kind == 0:
            if address + size > 0x10000 or base + address + size > 0x100000000:
                raise FirmwareError(f'Line {line_number}: address overflow')
            for i, value in enumerate(payload):
                target = base + address + i
                if target in memory:
                    raise FirmwareError(f'Line {line_number}: overlapping data at {target:#x}')
                memory[target] = value
        elif kind in (1, 2, 3, 4, 5):
            required = {1: 0, 2: 2, 3: 4, 4: 2, 5: 4}[kind]
            if address != 0 or size != required:
                raise FirmwareError(f'Line {line_number}: invalid type {kind:02x} record')
            if kind == 1:
                ended = True
            elif kind in (2, 4):
                base = int.from_bytes(payload, 'big') << (4 if kind == 2 else 16)
            else:
                starts.append({'type': f'{kind:02x}', 'raw_hex': payload.hex()})
        else:
            raise FirmwareError(f'Line {line_number}: unsupported type {kind:02x}')
    if not ended or not memory:
        raise FirmwareError('Missing EOF or empty firmware')
    segments, start, previous, values = [], None, None, bytearray()
    for address in sorted(memory):
        if previous is not None and address != previous + 1:
            segments.append((start, bytes(values)))
            values = bytearray()
            start = None
        if start is None:
            start = address
        values.append(memory[address])
        previous = address
    segments.append((start, bytes(values)))
    return {'records': records, 'record_types': dict(types), 'checksums_valid': records,
            'start_records': starts, 'addressed_bytes': len(memory)}, segments


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect(path, output=None):
    if path.stat().st_size > 16 * 1024 * 1024:
        raise FirmwareError('Resource fork exceeds the 16 MiB inspection limit')
    data = path.read_bytes()
    report = {'source': str(path), 'source_sha256': digest(data), 'resources': [],
              'scope': 'Offline installer image inspection; no network or hardware access; '
                       'not a dump of installed flash, boot ROM, calibration or EEPROM.'}
    pending = {}
    for entry in resources(data):
        body = entry['data']
        item = {k: v for k, v in entry.items() if k != 'data'}
        item['sha256'] = digest(body)
        if entry['type'] == 'TEXT':
            item['text'] = body.decode('ascii', errors='replace')
        if entry['type'] == 'CODE' and body.startswith(b':'):
            details, segments = intel_hex(body)
            item['intel_hex'] = details
            item['segments'] = []
            name = f"CODE-{entry['id']}.hex"
            pending[name] = body
            item['hex_file'] = name
            for address, segment in segments:
                name = f"CODE-{entry['id']}-{address:08x}.bin"
                pending[name] = segment
                item['segments'].append({'start': address, 'end_exclusive': address + len(segment),
                                         'size': len(segment), 'sha256': digest(segment), 'file': name})
            item['strings'] = [{'address': address + match.start(),
                               'text': match.group().decode('ascii')}
                              for address, segment in segments
                              for match in re.finditer(rb'[\x20-\x7e]{6,}', segment)]
        report['resources'].append(item)
    # Fully validate first; require a fresh output directory, never overwrite evidence.
    if output is not None:
        output.mkdir(parents=True, exist_ok=False)
        for name, body in pending.items():
            (output / name).write_bytes(body)
        (output / 'manifest.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resource_fork', type=Path)
    parser.add_argument('--extract', type=Path, help='New local directory for HEX, segments and manifest')
    args = parser.parse_args()
    try:
        result = inspect(args.resource_fork, args.extract)
    except (OSError, FirmwareError, struct.error) as exc:
        parser.exit(1, f'Error: {exc}\n')
    # Full strings and segmentation are retained in the manifest, not terminal noise.
    for entry in result['resources']:
        print(json.dumps({k: v for k, v in entry.items() if k not in ('strings', 'segments')}, ensure_ascii=False))
    print(result['scope'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
