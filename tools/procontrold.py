#!/usr/bin/env python3
"""Démon continu ProControl : start, status, stop. Aucun arrêt minuté."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import array
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time

from ardour_transport import ArdourTransport, message
from surface_map import SurfaceMap
from dsp_display_probe import DSPDisplayProbe
from surface_feedback import SurfaceFeedback
from surface_osc import ArdourSurface
from surface_routing import SurfaceRouting
from eq_editor import EQEditor
from plugin_window import PluginWindowFollower
from stereo_bridge import StereoBridge
from surface_settings import load as load_settings, validate as validate_settings
from audit_diginet import candidate_header
from inspect_pcap import CaptureError, mac_address
from procontrol_mapping import decode_body, mapping_tree
from session_probe import Session, drop_privileges, mac_bytes

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'run'


def utc():
    return datetime.now(timezone.utc).isoformat()


def running(runtime):
    if not (runtime / 'daemon.lock').exists():
        return False
    with (runtime / 'daemon.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def status(runtime):
    try:
        result = json.loads((runtime / 'status.json').read_text())
    except (OSError, ValueError):
        result = {}
    result['running'] = running(runtime)
    return result


class ConsoleSession:
    """Réutilise la session validée ; rouvre seulement après une annonce e0."""
    def __init__(self, host, peer):
        self.host, self.peer = host, peer
        self.session = Session(host, peer, duration=None)
        self.phase = 'waiting_console'
        self.announcement = None
        self.last_seen = None
        self.connections = 0

    def reset(self):
        self.session = Session(self.host, self.peer, duration=None)
        self.phase = 'waiting_console'
        self.announcement = None

    def receive(self, frame, now):
        s = self.session
        if (len(frame) < 30 or frame[6:12] != s.peer or frame[12:14] != b'\x88\x5f'
                or frame[:6] not in (s.host, b'\xff' * 6)):
            return [], None
        h = candidate_header(frame[14:])
        if not h['body_sum16_match']:
            raise CaptureError('Checksum candidat non concordant')
        self.last_seen = now
        if h['command_field'] in (0xe0, 0xe1) and frame[:6] == b'\xff' * 6:
            if h.get('device_candidate') != 'MAINUNIT':
                return [], None
            if h['command_field'] == 0xe0 and s.started is not None and now - s.started >= 10:
                self.reset()
                s = self.session
            self.announcement = h['command_field']
            if self.announcement == 0xe1 and s.started is None:
                if h.get('announced_host_candidate') == self.host:
                    # Our process lock excludes a second local daemon. Reopen
                    # the console session left by our previous process only.
                    s.started = s.last_heartbeat = now
                    self.connections += 1; self.phase = 'connecting'
                    return [s.frame(0xe2, sequence=1)], h
                self.phase = 'waiting_existing_session'
                return [], h
        frames = s.receive(frame, now)
        if any(f[28] == 0xe2 for f in frames):
            self.connections += 1
            self.phase = 'connecting'
        if s.online_acked and self.announcement == 0xe1:
            self.phase = 'online'
        return frames, h

    def tick(self, now):
        if self.last_seen is not None and now - self.last_seen > 45:
            self.reset()
            self.last_seen = None
        return self.session.tick(now)


def spawn_worker(args, rx, tx, lock):
    """Les sockets déjà ouvertes sont transmises à un processus détaché non root."""
    runtime = Path(args.runtime)
    command = [sys.executable, str(Path(__file__).resolve()), '_run',
               '--interface', args.interface, '--mac', args.mac, '--host', args.host,
               '--osc-port', str(args.osc_port), '--runtime', str(runtime),
               '--rx-fd', str(rx.fileno()), '--tx-fd', str(tx.fileno()), '--lock-fd', str(lock.fileno())]
    with (runtime / 'launcher.log').open('w') as output:
        return subprocess.Popen(command, pass_fds=(rx.fileno(), tx.fileno(), lock.fileno()),
                                start_new_session=True, stdin=subprocess.DEVNULL,
                                stdout=output, stderr=subprocess.STDOUT, cwd=ROOT)


NET_HELPER = Path('/usr/local/libexec/procontrol-net')

def packet_sockets(interface):
    if os.geteuid() == 0:
        return (socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x885f)),
                socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x885f)))
    parent,child = socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
    fds=array.array('i')
    try:
        parent.settimeout(3)
        proc=subprocess.Popen([str(NET_HELPER),interface,str(child.fileno())],pass_fds=(child.fileno(),),stderr=subprocess.PIPE)
        child.close()
        try:
            data,ancillary,flags,_=parent.recvmsg(1,socket.CMSG_SPACE(2*fds.itemsize))
            for level,kind,payload in ancillary:
                if level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS:
                    fds.frombytes(payload[:len(payload)-(len(payload)%fds.itemsize)])
            _,error=proc.communicate(timeout=3)
            if proc.returncode or data!=b'P' or len(fds)!=2 or flags & socket.MSG_CTRUNC:
                raise RuntimeError('Lanceur Ethernet : '+error.decode(errors='replace').strip())
            rx=socket.socket(fileno=fds[0]);tx=socket.socket(fileno=fds[1]);fds=array.array('i')
            return rx,tx
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
    finally:
        parent.close();child.close()
        for fd in fds:os.close(fd)


def bootstrap(args):
    interface = Path('/sys/class/net') / args.interface
    if '/' in args.interface or not (interface / 'type').exists() or (interface / 'type').read_text().strip() != '1' or (interface / 'wireless').exists():
        raise RuntimeError('Interface Ethernet filaire requise')
    args.host = (interface / 'address').read_text().strip()
    peer = mac_bytes(args.mac)
    if peer[0] & 1 or not any(peer) or peer == mac_bytes(args.host):
        raise RuntimeError('MAC console unicast distincte requise')
    rx,tx = packet_sockets(args.interface)
    with rx,tx:
        rx.bind((args.interface, 0)); tx.bind((args.interface, 0))
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        drop_privileges()
        os.umask(0o077)
        runtime = Path(args.runtime)
        runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (runtime / 'daemon.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print('Le démon tourne déjà.'); return 0
            child = spawn_worker(args, rx, tx, lock)
            # Pas de déverrouillage explicite : le fils conserve le même descripteur.
            for _ in range(100):
                state = status(runtime)
                if state.get('pid') == child.pid and state.get('running'):
                    print(json.dumps(state, ensure_ascii=False, indent=2)); return 0
                if child.poll() is not None:
                    raise RuntimeError('Échec de démarrage : ' + (runtime / 'launcher.log').read_text()[-2000:])
                time.sleep(0.05)
            raise RuntimeError('Démarrage sans état publié : consulter run/launcher.log et status')


def worker(args):
    if os.geteuid() == 0:
        raise RuntimeError('Le processus continu doit fonctionner sans root')
    runtime = Path(args.runtime)
    # Conserver le verrou transmis jusqu'à la fin du processus.
    lock = os.fdopen(args.lock_fd, 'a')
    rx = socket.socket(fileno=args.rx_fd); tx = socket.socket(fileno=args.tx_fd)
    control = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    # Le chemin absolu du projet dépasse la limite Linux AF_UNIX ; cwd privé court.
    os.chdir(runtime)
    control_path = Path('control.sock')
    control_path.unlink(missing_ok=True)
    control.bind(str(control_path)); control_path.chmod(0o600)
    logger = logging.getLogger('procontrold'); logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(runtime / 'events.jsonl', maxBytes=8*1024*1024, backupCount=3)
    handler.setFormatter(logging.Formatter('%(message)s')); logger.addHandler(handler)
    def event(kind, **details):
        logger.info(json.dumps({'utc': utc(), 'event': kind, **details}, ensure_ascii=False))
    flow = ConsoleSession(args.host, args.mac)
    surface = SurfaceMap()
    feedback = SurfaceFeedback(surface)
    feedback.initialize()
    settings_path = runtime.parent / 'settings.json'
    settings = load_settings(settings_path)
    surface.jog_gain = settings['jog_gain']
    routing = SurfaceRouting(surface, feedback)
    eq = EQEditor(routing, feedback)
    plugin_window = PluginWindowFollower()
    display_probe = DSPDisplayProbe(feedback)
    stereo = StereoBridge(routing, feedback, settings, port=0 if args.interface.startswith('test') else 3820)
    next_catalog = 0; next_meter_render = 0
    mapping_tree()
    counts = Counter(); alive = True; osc = None
    last_osc = None; next_osc = 0; next_query = 0; next_status = 0; last_action = None
    started = utc(); phase = flow.phase; error = None
    def stop_signal(*_):
        nonlocal alive
        alive = False
    signal.signal(signal.SIGTERM, stop_signal); signal.signal(signal.SIGINT, stop_signal)
    def publish():
        state = {'pid': os.getpid(), 'uid': os.geteuid(), 'started_utc': started,
                 'updated_utc': utc(), 'running': alive, 'console': flow.phase if alive else 'stopped',
                 'interface': args.interface, 'host': args.host, 'peer': args.mac,
                 'connections': flow.connections, 'counts': dict(counts), 'last_action': last_action,
                 'surface': {'alpha': surface.alpha, 'encoder_mode': surface.encoder_mode,
                             'jog_mode': surface.jog_mode, 'bank_start': surface.bank_start,
                             'feedback': dict(feedback.counts), 'output_error': feedback.error,
                             'output_timing': feedback.status(),
                             'queued_outputs': len(feedback.queue)},
                 'settings_revision': settings['revision'], 'settings': settings,
                 'routing': routing.status(), 'stereo': stereo.status(), 'dsp': eq.status(),
                 'plugin_window': plugin_window.status(),
                 'jog': osc.jog.status() if osc else None,
                 'ardour': 'responding' if last_osc is not None and time.monotonic()-last_osc < 20 else 'waiting',
                 'osc_target': f'127.0.0.1:{args.osc_port}', 'error': error}
        temp = runtime / 'status.tmp'; temp.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n')
        temp.replace(runtime / 'status.json')
    def send(frames):
        for frame in frames:
            if frame[28] == 0xa0:
                time.sleep(0.0008)
            if tx.send(frame) != len(frame):
                raise OSError('Émission Ethernet incomplète')
            counts['tx'] += 1
            if frame[28] == 0xe2: counts['online_sent'] += 1
            elif frame[28] == 0xa0: counts['ack_sent'] += 1
            elif frame[30:] == b'\x00' * (len(frame)-30): counts['keepalive_sent'] += 1
            else: counts['feedback_sent'] += 1
            event('ethernet_tx', command=frame[28], hex=frame.hex(' '))
    def osc_failed(exc):
        nonlocal osc, next_osc, last_osc
        event('ardour_waiting', detail=str(exc))
        if osc: osc.close()
        routing.disconnect()
        plugin_window.reset()
        osc = None; last_osc = None; next_osc = time.monotonic()+5
    event('started', pid=os.getpid(), uid=os.geteuid(), interface=args.interface, peer=args.mac)
    publish()
    try:
        while alive:
            now = time.monotonic()
            if osc is None and now >= next_osc:
                try:
                    routing.begin_catalog()
                    osc = ArdourSurface(args.osc_port, surface); next_query = now+10; next_catalog = now+2
                except OSError as exc: osc_failed(exc)
            if osc:
                try:
                    for address, values in osc.poll():
                        last_osc = now
                        plugin_window.feed(address, values)
                        routing.feed(address, values)
                        if address in ('/transport_play', '/transport_stop', '/transport_speed'):
                            event('osc_feedback', address=address, values=values)
                    deferred = routing.drain() + eq.tick(now) + plugin_window.update(eq, routing, now)
                    if deferred:
                        addresses = osc.actions(deferred)
                        counts['osc_sent'] += len(addresses)
                        event('osc_sent', addresses=addresses, actions=deferred)
                    addresses = osc.flush_jog(now)
                    if addresses:
                        counts['osc_sent'] += len(addresses)
                        event('osc_sent', addresses=addresses)
                    if routing.catalog_due(now, next_catalog):
                        routing.begin_catalog(); osc.request_catalog()
                        routing.need_catalog = False; next_catalog = now+2
                    if now >= next_query:
                        osc.socket.send(message('/transport_speed')); next_query = now+10
                except OSError as exc: osc_failed(exc)
            display_probe.tick(now)
            stereo.poll()
            if now >= next_meter_render:
                stereo.render(now); next_meter_render = now + .020
            try:
                send(flow.tick(now))
                if flow.phase == 'online':
                    output_frame = feedback.next_frame(flow.session, now)
                    if feedback.needs_refresh:
                        feedback.needs_refresh=False
                        event('feedback_recovery', counts=dict(feedback.counts))
                        if osc:
                            try:osc.refresh()
                            except OSError as exc:osc_failed(exc)
                    if output_frame is not None: send([output_frame])
            except OSError as exc:
                event('ethernet_waiting', detail=str(exc)); flow.reset()
            # Wake on OSC/Lua too; a fixed 50 ms wait throttled output to ~19 fps.
            watched = [rx, control]
            if osc: watched.append(osc.socket)
            if stereo.socket: watched.append(stereo.socket)
            timeout = feedback.wait_timeout(time.monotonic()) if flow.phase == 'online' else 0.05
            if osc: timeout = osc.jog.wait_timeout(time.monotonic(), timeout)
            timeout = min(timeout, max(0., next_meter_render-time.monotonic()))
            readable = select.select(watched, [], [], timeout)[0]
            if control in readable:
                data, client = control.recvfrom(65535)
                if data == b'stop': alive = False
                else:
                    try:
                        request = json.loads(data)
                        if request.get('command') == 'configure':
                            new_settings = validate_settings(request['settings'])
                            stereo.configure(new_settings); settings = new_settings
                            surface.jog_gain = settings['jog_gain']; publish()
                            reply = {'ok':True,'revision':settings['revision']}
                        elif request.get('command') == 'dsp_display_test':
                            reply=display_probe.start();event('dsp_display_test', **reply)
                        elif request.get('command') == 'meter_test':
                            stereo.test_address(request['address']);reply={'ok':True}
                        elif request.get('command') == 'status':
                            publish();reply=status(runtime)
                        else:raise ValueError('Commande inconnue')
                    except (ValueError,KeyError,TypeError) as exc:reply={'ok':False,'error':str(exc)}
                    if client:
                        try:control.sendto(json.dumps(reply).encode(),client)
                        except OSError:pass
            if alive and rx in readable:
                frame = rx.recv(65535)
                try:
                    connections = flow.connections
                    frames, h = flow.receive(frame, time.monotonic())
                    if h is not None:
                        counts['rx'] += 1
                        if h['command_field'] == 0xa0: counts['ack_received'] += 1
                        event('ethernet_rx', **h)
                        feedback.acknowledge(h)
                        if connections != flow.connections:
                            if osc: osc.jog.cancel()
                            event('input_events', actions=surface.reset_inputs())
                            feedback.resync()
                            routing.render_matrix()
                            if osc:
                                try: osc.refresh()
                                except OSError as exc: osc_failed(exc)
                        send(frames)
                        if h['command_field'] == 0 and frame[:6] == flow.session.host:
                            decoded = decode_body(bytes.fromhex(h['body_hex']))
                            counts['control_frames'] += 1
                            event('controls', decoded=decoded)
                            if flow.session.online_acked:
                                actions = surface.route(h['sequence_candidate'], bytes.fromhex(h['body_hex']))
                                for action in actions: feedback.local(action)
                                routed_actions = routing.actions(actions)
                                inputs = [a for a in actions if a[0] in ('key','text','button','release_all')]
                                if inputs: event('input_events', actions=inputs)
                                if actions: event('surface_actions', actions=actions)
                                if surface.last_unknown: event('unmapped_surface', commands=surface.last_unknown)
                                if osc:
                                    try:
                                        addresses = osc.actions(routed_actions)
                                        if addresses:
                                            counts['osc_sent'] += len(addresses)
                                            last_action = {'utc': utc(), 'address': addresses[-1]}
                                            event('osc_sent', addresses=addresses)
                                    except OSError as exc: osc_failed(exc)
                except CaptureError as exc:
                    counts['malformed'] += 1; event('malformed', detail=str(exc))
                except OSError as exc:
                    event('ethernet_waiting', detail=str(exc)); flow.reset()
            if phase != flow.phase:
                phase = flow.phase; event('console_state', state=phase); next_status = 0
                if phase != 'online':
                    if osc: osc.jog.cancel()
                    event('input_events', actions=[('release_all','',[])])
            if now >= next_status:
                publish(); next_status = now+2
    except Exception as exc:
        error = str(exc); event('fatal', detail=error)
        raise
    finally:
        alive = False
        event('input_events', actions=[('release_all','',[])])
        if osc: osc.close()
        stereo.close()
        rx.close(); tx.close(); control.close(); control_path.unlink(missing_ok=True)
        event('stopped', counts=dict(counts), error=error); publish()
        handler.close(); lock.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('start', 'status', 'stop', '_start', '_run'))
    p.add_argument('--interface', default='enp0s25')
    p.add_argument('--mac', default='00:a0:7e:a0:ad:9c', type=mac_address)
    p.add_argument('--osc-port', default=3819, type=int)
    p.add_argument('--runtime', default=str(RUNTIME))
    p.add_argument('--host', help=argparse.SUPPRESS)
    for name in ('rx-fd', 'tx-fd', 'lock-fd'):
        p.add_argument('--'+name, type=int, help=argparse.SUPPRESS)
    args = p.parse_args(); runtime = Path(args.runtime).resolve(); args.runtime = str(runtime)
    if not 1024 < args.osc_port < 65536: p.error('Port OSC invalide')
    if args.action == 'status':
        print(json.dumps(status(runtime), ensure_ascii=False, indent=2)); return 0
    if args.action == 'stop':
        if not running(runtime): print('Démon déjà arrêté.'); return 0
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as control:
            os.chdir(runtime); control.sendto(b'stop', 'control.sock')
        for _ in range(100):
            if not running(runtime): print('Démon arrêté proprement.'); return 0
            time.sleep(0.05)
        raise RuntimeError('Arrêt demandé ; vérifier status et events.jsonl')
    if args.action == 'start':
        if running(runtime): print(json.dumps(status(runtime), ensure_ascii=False, indent=2)); return 0
        if NET_HELPER.exists():return bootstrap(args)
        print('Ouverture Ethernet : authentification Linux si nécessaire.', flush=True)
        return subprocess.call(['pkexec', sys.executable, str(Path(__file__).resolve()), '_start',
                                '--interface', args.interface, '--mac', args.mac,
                                '--osc-port', str(args.osc_port), '--runtime', str(runtime)])
    if args.action == '_start': return bootstrap(args)
    return worker(args)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (OSError, RuntimeError) as exc: raise SystemExit(str(exc))
