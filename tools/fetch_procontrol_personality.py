#!/usr/bin/env python3
"""Retrieve only the three ProControl files from Avid's public PT 10.3.10 ZIP.

No installer execution and no console traffic. Requires curl. ZIP sizes, CRC32
and previously observed SHA-256 values are pinned; a changed download fails closed.
Files are proprietary and belong in an ignored local work directory.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zlib

URL = 'https://akmedia.digidesign.com/support/compressed/Pro_Tools_10_3_10_Win_84130.zip'
PAGE = 'https://kb.avid.com/pkb/articles/download/Pro-Tools-10-3-10-Downloads'
ZIP_SIZE = 1905248238
DIRECTORY_OFFSET = 1903261004
DIRECTORY_SIZE = 1987212
PREFIX = 'Pro Tools/Pro Tools Installer/program files/Avid/Pro Tools/DAE/Controllers/'
EXPECTED = {
    'Procontrol.dll': '222cad7e7abcf3f8f91bffc6ff9f3ea87ac2ee990328e93a20bda6770f43a903',
    'Procontrol.dll.rsr': '0603a032f3abf4af6e266ba05486d186e031a5e2448da86d0aacc2b1e1eb1a53',
    'Procontrol_M.dll': 'c05dc43a0e944bd1dae6e2ed9a04edb2ba8dcda2e40b61d772fb951a99baa4db',
}


def fetch_range(start, size):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        result = subprocess.run([
            'curl', '--silent', '--show-error', '--fail', '--location',
            '--proto', '=https', '--proto-redir', '=https',
            '--connect-timeout', '10', '--max-time', '55', '--max-filesize', str(size),
            '--range', f'{start}-{start + size - 1}', '--user-agent', 'Mozilla/5.0',
            '--dump-header', str(root / 'headers'), '--output', str(root / 'bytes'),
            '--write-out', '%{http_code}', URL,
        ], capture_output=True, text=True, check=True)
        data = (root / 'bytes').read_bytes()
        headers = (root / 'headers').read_text()
        ranges = re.findall(r'^content-range:\s*bytes\s+(\d+)-(\d+)/(\d+)\s*$',
                            headers, re.I | re.M)
        if result.stdout != '206' or len(data) != size or not ranges:
            raise ValueError('Server did not provide the exact requested range')
        if tuple(map(int, ranges[-1])) != (start, start + size - 1, ZIP_SIZE):
            raise ValueError('Archive range or size changed')
        return data


def retrieve(output):
    if output.exists():
        raise FileExistsError(f'Refusing existing destination: {output}')
    directory = fetch_range(DIRECTORY_OFFSET, DIRECTORY_SIZE + 22)
    end = struct.unpack_from('<4s4H2IH', directory, DIRECTORY_SIZE)
    if end != (b'PK\x05\x06', 0, 0, 12681, 12681, DIRECTORY_SIZE, DIRECTORY_OFFSET, 0):
        raise ValueError('Unexpected ZIP directory')
    offset, selected, count = 0, {}, 0
    while offset < DIRECTORY_SIZE:
        fields = struct.unpack_from('<4s6H3I5H2I', directory, offset)
        if fields[0] != b'PK\x01\x02':
            raise ValueError('Invalid ZIP directory entry')
        name = directory[offset + 46:offset + 46 + fields[10]].decode('utf-8')
        basename = name.removeprefix(PREFIX)
        if name.startswith(PREFIX) and basename in EXPECTED:
            if basename in selected or fields[3] & 1 or fields[4] != 8:
                raise ValueError('Duplicate, encrypted or unsupported member')
            selected[basename] = {'name': name, 'method': fields[4], 'crc32': fields[7],
                                  'compressed': fields[8], 'size': fields[9], 'offset': fields[-1]}
        offset += 46 + fields[10] + fields[11] + fields[12]
        count += 1
    if count != 12681 or offset != DIRECTORY_SIZE or set(selected) != set(EXPECTED):
        raise ValueError('Archive directory does not match the expected inventory')
    files, metadata = {}, []
    for name, entry in selected.items():
        header = fetch_range(entry['offset'], 30)
        fields = struct.unpack('<4s5H3I2H', header)
        if fields[0] != b'PK\x03\x04' or fields[2] & 1 or fields[3] != entry['method']:
            raise ValueError('Invalid ZIP local header')
        size = 30 + fields[-2] + fields[-1] + entry['compressed']
        if size > 1024 * 1024 or entry['size'] > 2 * 1024 * 1024:
            raise ValueError('Unexpected ProControl member size')
        raw = fetch_range(entry['offset'], size)
        if raw[30:30 + fields[-2]].decode('utf-8') != entry['name']:
            raise ValueError('ZIP member name mismatch')
        decoder = zlib.decompressobj(-15)
        body = decoder.decompress(raw[30 + fields[-2] + fields[-1]:], entry['size'] + 1)
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('Compressed member is truncated, oversized or has trailing data')
        sha = hashlib.sha256(body).hexdigest()
        if len(body) != entry['size'] or zlib.crc32(body) != entry['crc32'] or sha != EXPECTED[name]:
            raise ValueError(f'Integrity check failed: {name}')
        files[name] = body
        metadata.append({**entry, 'sha256': sha, 'zip_crc32_verified': True})
    output.mkdir(parents=True, exist_ok=False)
    for name, body in files.items():
        (output / name).write_bytes(body)
    manifest = {'source_url': URL, 'source_page': PAGE, 'zip_size': ZIP_SIZE,
                'central_directory_sha256': hashlib.sha256(directory).hexdigest(),
                'files': metadata}
    (output / 'personality-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New local directory, preferably under work/')
    args = parser.parse_args()
    try:
        result = retrieve(args.output)
    except (OSError, ValueError, struct.error, zlib.error, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    for item in result['files']:
        print(f"{Path(item['name']).name}: {item['size']} bytes; SHA-256 {item['sha256']}")
    print('Three local files verified. No installer executed. No console contacted.')


if __name__ == '__main__':
    main()
