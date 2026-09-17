#!/usr/bin/env python3
"""Exercise native OSC page changes on an already open disposable Ardour session.

This changes the selected track and OSC feedback settings. It does not change
plugin parameters, start playback, save the session, or send Ethernet packets.
Run with the gateway stopped and a COPY of an eight-track test session open.
For memory diagnostics, instrument the OSC module with AddressSanitizer first.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import json
from pathlib import Path
import socket
import time

from ardour_transport import decode, message


def probe(port, reply_port, cycles, pid=None):
    packets = 0
    samples = []
    start = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', reply_port))
        sock.connect(('127.0.0.1', port))
        sock.settimeout(.2)

        def receive_until(address, timeout):
            nonlocal packets
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    messages = decode(sock.recv(65535))
                except socket.timeout:
                    continue
                packets += 1
                for path, values in messages:
                    if path == address:
                        return values
            raise TimeoutError('No Ardour reply for ' + address)

        sock.send(message('/transport_speed'))
        receive_until('/transport_speed', 10)
        try:
            for cycle in range(cycles):
                page_size = (0, 1, 8, 16)[cycle % 4]
                sock.send(message('/set_surface', 0, 63, 8307, 2, page_size, 8, 0))
                sock.send(message('/strip/select', cycle % 8 + 1, 0))
                sock.send(message('/strip/plugin/descriptor', cycle % 8 + 1, cycle % 2 + 1))
                sock.send(message('/set_surface'))
                config = receive_until('/set_surface', 5)
                if len(config) != 9 or config[4] != page_size:
                    raise RuntimeError('Unexpected OSC surface configuration: ' + repr(config))
                if pid and cycle % 10 == 0:
                    status = dict(line.split(':', 1) for line in
                                  Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
                    samples.append({'cycle': cycle,
                                    'rss_kib': int(status['VmRSS'].split()[0]),
                                    'threads': int(status['Threads'])})
                # Allow periodic feedback ticks, including send-name timeouts.
                time.sleep(.12)
        finally:
            try:
                sock.send(message('/set_surface/feedback', 0))
            except OSError:
                pass
    return {'cycles': cycles, 'received_datagrams': packets,
            'elapsed_seconds': round(time.monotonic() - start, 3), 'samples': samples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=3819)
    parser.add_argument('--reply-port', type=int, default=3822)
    parser.add_argument('--cycles', type=int, default=100)
    parser.add_argument('--pid', type=int, help='Ardour PID, for Linux memory samples')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 1000:
        parser.error('cycles must be in 1..1000')
    result = probe(args.port, args.reply_port, args.cycles, args.pid)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
