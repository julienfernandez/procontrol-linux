#!/usr/bin/env python3
"""Inspect classic Ethernet PCAPs without assuming a Digidesign payload layout."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
import struct
import sys


class CaptureError(ValueError):
    pass


def packets(path):
    """Yield (timestamp_ns, captured_bytes, original_length), bounded in memory."""
    formats = {
        b'\xd4\xc3\xb2\xa1': ('<', 1000), b'\xa1\xb2\xc3\xd4': ('>', 1000),
        b'\x4d\x3c\xb2\xa1': ('<', 1), b'\xa1\xb2\x3c\x4d': ('>', 1),
    }
    with open(path, 'rb') as stream:
        header = stream.read(24)
        if header[:4] == b'\x0a\x0d\x0d\x0a':
            raise CaptureError('PCAPNG : convertir avec editcap -F pcap entree.pcapng sortie.pcap')
        if len(header) != 24 or header[:4] not in formats:
            raise CaptureError('En-tête PCAP classique absent, incomplet ou non reconnu')
        endian, ns_factor = formats[header[:4]]
        major, minor, _, _, snaplen, network = struct.unpack(endian + 'HHIIII', header[4:])
        if (major, minor) != (2, 4):
            raise CaptureError(f'Version PCAP non prise en charge : {major}.{minor}')
        if network & 0xffff != 1:
            raise CaptureError(f'Linktype {network & 0xffff} : Ethernet (1) requis, éviter -i any')
        index = 0
        while True:
            record = stream.read(16)
            if not record:
                return
            index += 1
            if len(record) != 16:
                raise CaptureError(f'Trame {index} : en-tête de paquet incomplet')
            sec, fraction, caplen, wirelen = struct.unpack(endian + 'IIII', record)
            if fraction * ns_factor >= 1_000_000_000:
                raise CaptureError(f'Trame {index} : fraction temporelle invalide')
            if caplen > snaplen or caplen > wirelen or caplen > 16 * 1024 * 1024:
                raise CaptureError(f'Trame {index} : longueurs PCAP incohérentes ou excessives')
            data = stream.read(caplen)
            if len(data) != caplen:
                raise CaptureError(f'Trame {index} : données PCAP incomplètes')
            yield sec * 1_000_000_000 + fraction * ns_factor, data, wirelen


def ethernet(data):
    if len(data) < 14:
        raise CaptureError('En-tête Ethernet trop court')
    dst, src = data[:6].hex(':'), data[6:12].hex(':')
    field = int.from_bytes(data[12:14], 'big')
    offset, tags = 14, []
    while field in (0x8100, 0x88a8, 0x9100):
        if len(data) < offset + 4:
            raise CaptureError('En-tête VLAN incomplet')
        tags.append(int.from_bytes(data[offset:offset+2], 'big') & 0xfff)
        field = int.from_bytes(data[offset+2:offset+4], 'big')
        offset += 4
    kind = f'length:{field}' if field <= 1500 else f'0x{field:04x}'
    # Padding, LLC and an eventual captured FCS are left intact, unclassified.
    return src, dst, kind, tuple(tags), data[offset:]


def timestamp(ns):
    sec, fraction = divmod(ns, 1_000_000_000)
    return datetime.fromtimestamp(sec, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + f'.{fraction:09d}Z'


def nonnegative(value):
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError('Valeur positive ou nulle requise')
    return n


def mac_address(value):
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', value):
        raise argparse.ArgumentTypeError('MAC attendue : aa:bb:cc:dd:ee:ff')
    return value.lower()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcap', type=Path)
    parser.add_argument('--show', type=nonnegative, default=12, help='Nombre de trames affichées (défaut : 12)')
    parser.add_argument('--hex-bytes', type=nonnegative, default=96, help='Octets de payload affichés par trame')
    parser.add_argument('--mac', type=mac_address, help='Filtrer source OU destination, hors ligne')
    args = parser.parse_args(argv)
    flows, lengths = Counter(), Counter()
    total = selected = truncated = malformed = 0
    start = end = previous = None
    backwards = 0
    try:
        for index, (ts, data, wirelen) in enumerate(packets(args.pcap), 1):
            total += 1
            truncated += len(data) < wirelen
            if previous is not None and ts < previous:
                backwards += 1
            previous = ts
            start = ts if start is None else min(start, ts)
            end = ts if end is None else max(end, ts)
            try:
                src, dst, kind, tags, payload = ethernet(data)
            except CaptureError as exc:
                malformed += 1
                print(f'Attention, trame {index} : {exc}', file=sys.stderr)
                continue
            if args.mac and args.mac not in (src, dst):
                continue
            selected += 1
            flows[(src, dst, kind, tags)] += 1
            lengths[(len(data), wirelen)] += 1
            if selected <= args.show:
                print(f'#{index} {timestamp(ts)} {src} -> {dst} {kind} VLAN={tags or "-"} cap={len(data)} wire={wirelen}')
                preview = payload[:args.hex_bytes]
                print('  après Ethernet/VLAN :', preview.hex(' '))
                print('  ASCII :', ''.join(chr(b) if 32 <= b < 127 else '.' for b in preview))
        print(f'PCAP : {args.pcap.name}')
        print(f'Trames : {total} ; sélectionnées : {selected} ; capture tronquée : {truncated} ; Ethernet incomplet : {malformed}')
        if start is not None:
            print(f'Intervalle global : {timestamp(start)} / {timestamp(end)} ({(end-start)/1e9:.6f} s)')
        else:
            print('Aucune trame : vérifier le journal tcpdump et les conditions de capture.')
        if backwards:
            print(f'Attention : {backwards} retour(s) arrière des horodatages.')
        print('Flux sélectionnés (source -> destination, type/longueur, VLAN) :')
        for (src, dst, kind, tags), count in flows.most_common():
            print(f'  {count:7d}  {src} -> {dst}  {kind}  {tags or "-"}')
        print('Longueurs sélectionnées (capturée / originale) :')
        for (cap, wire), count in lengths.most_common():
            print(f'  {count:7d}  {cap} / {wire}')
        print('Aucun décodage applicatif : 0x885f seul ne prouve pas une identité ProControl.')
    except (OSError, CaptureError) as exc:
        print(f'Erreur : {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
