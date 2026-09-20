#!/usr/bin/env python3
"""Stress normal OSC jog on an ALREADY OPEN DISPOSABLE COPY of an Ardour session.

Starts/stops playback and moves its playhead. Never enable recording here.
Use the same JACK/external-sync settings as the session being investigated.
The Link bridge may control connected peers while this test plays.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import json
from pathlib import Path
import socket
import time

from ardour_transport import decode, message


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-session', action='store_true', required=True)
    parser.add_argument('--duration', type=float, default=60)
    parser.add_argument('--hz', type=float, default=50)
    parser.add_argument('--pattern', choices=('alternating', 'start-boundary'), default='alternating')
    parser.add_argument('--port', type=int, default=3819)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.duration <= 3600 or not 1 <= args.hz <= 100:
        parser.error('duration: 1..3600 seconds; hz: 1..100')
    link_path = Path(__file__).resolve().parents[1]/'run/link-status.json'
    result = {'requested_seconds': args.duration, 'requested_hz': args.hz, 'pattern': args.pattern, 'samples': []}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        sock.settimeout(.1)

        def send(path, *values):
            sock.sendto(message(path, *values), ('127.0.0.1', args.port))

        def query(path, timeout=3):
            send(path)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    for address, values in decode(sock.recv(65535)):
                        if address == path:
                            return values
                except socket.timeout:
                    pass
            raise TimeoutError('Ardour stopped replying to '+path)

        def link_status():
            try:
                return json.loads(link_path.read_text())
            except (OSError, ValueError):
                return None

        # Checking before PLAY prevents an armed global transport from recording.
        if query('/record_enabled')[0] or query('/is_recording')[0]:
            raise RuntimeError('Disarm recording in the disposable session before testing')
        send('/set_surface', 0, 0, 16, 0, 0, 0, 0)
        send('/transport_stop')
        send('/jog/mode', 0.)
        send('/goto_start')
        time.sleep(.5)
        result['link_before'] = link_status()
        sent = 0
        try:
            send('/transport_play')
            time.sleep(1)
            result['initial_speed'] = query('/transport_speed')[0]
            if result['initial_speed'] != 1:
                raise RuntimeError('Playback did not start')
            start = time.monotonic()
            next_send = start
            next_probe = start + 1
            while time.monotonic() - start < args.duration:
                now = time.monotonic()
                if now >= next_send:
                    send('/jog', -1.0 if args.pattern == 'start-boundary' else
                         (1.0 if int((now-start)/2) % 2 == 0 else -1.0))
                    sent += 1
                    # No catch-up burst after a slow response.
                    next_send = now + 1/args.hz
                if now >= next_probe:
                    result['samples'].append({'seconds': now-start,
                        'frame': query('/transport_frame')[0], 'link': link_status()})
                    next_probe = time.monotonic()+1
                time.sleep(max(0, min(.01, next_send-time.monotonic())))
            result['jog_seconds'] = time.monotonic()-start
            result['jog_commands'] = sent
            # Release the jog and check that ordinary playback recovers.
            time.sleep(1)
            frame1 = query('/transport_frame')[0]
            time.sleep(1)
            frame2 = query('/transport_frame')[0]
            result['resume'] = {'frame1': frame1, 'frame2': frame2,
                                'speed': query('/transport_speed')[0]}
            if frame2 <= frame1 or result['resume']['speed'] != 1:
                raise RuntimeError('Playback did not recover after the jog')
            result['passed'] = True
        except Exception as exc:
            result.update(passed=False, error=str(exc), jog_commands=sent)
            raise
        finally:
            send('/transport_stop')
            time.sleep(1.2)
            try:
                result['final_speed'] = query('/transport_speed', 1)[0]
                result['link_after'] = link_status()
                if result['final_speed'] != 0:
                    result['passed'] = False
            except Exception as exc:
                result['passed'] = False
                result['stop_error'] = str(exc)
            finally:
                send('/set_surface/feedback', 0)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k != 'samples'}, indent=2))
        return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
