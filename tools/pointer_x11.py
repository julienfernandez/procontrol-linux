#!/usr/bin/env python3
"""Pont trackpad → pointeur X11, continu et sans root ; aucun clic ni clavier."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from surface_settings import load as load_settings, validate as validate_settings
from collections import deque
import ctypes as C
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from procontrol_pointer import decode_pointer
from surface_input import XInput
from procontrold import RUNTIME, status as daemon_status


class XPointer:
    def __init__(self):
        if os.environ.get('XDG_SESSION_TYPE') != 'x11':
            raise RuntimeError('Ce prototype nécessite une session X11')
        self.x = C.CDLL('libX11.so.6'); self.test = C.CDLL('libXtst.so.6')
        pointer = C.c_void_p; integer = C.c_int; ulong = C.c_ulong
        self.x.XOpenDisplay.argtypes = [C.c_char_p]; self.x.XOpenDisplay.restype = pointer
        self.x.XDefaultRootWindow.argtypes = [pointer]; self.x.XDefaultRootWindow.restype = ulong
        self.x.XQueryPointer.argtypes = [pointer, ulong, C.POINTER(ulong), C.POINTER(ulong),
                                       C.POINTER(integer), C.POINTER(integer), C.POINTER(integer),
                                       C.POINTER(integer), C.POINTER(C.c_uint)]
        self.x.XFlush.argtypes = [pointer]; self.x.XCloseDisplay.argtypes = [pointer]
        self.test.XTestQueryExtension.argtypes = [pointer] + [C.POINTER(integer)] * 4
        self.test.XTestFakeMotionEvent.argtypes = [pointer, integer, integer, integer, ulong]
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('Impossible d’ouvrir la session X11 courante')
        values = [integer() for _ in range(4)]
        if not self.test.XTestQueryExtension(self.display, *(C.byref(v) for v in values)):
            self.close(); raise RuntimeError('Extension XTEST absente')
        self.root = self.x.XDefaultRootWindow(self.display)

    def position(self):
        root, child = C.c_ulong(), C.c_ulong()
        x, y, wx, wy = (C.c_int() for _ in range(4)); mask = C.c_uint()
        if not self.x.XQueryPointer(self.display, self.root, C.byref(root), C.byref(child),
                                   C.byref(x), C.byref(y), C.byref(wx), C.byref(wy), C.byref(mask)):
            raise RuntimeError('Pointeur hors de l’écran X11 interrogé')
        return x.value, y.value

    def move(self, dx, dy):
        x, y = self.position()
        if not self.test.XTestFakeMotionEvent(self.display, -1, x + dx, y + dy, 0):
            raise RuntimeError('Mouvement XTEST refusé')
        self.x.XFlush(self.display)

    def close(self):
        if self.display:
            self.x.XCloseDisplay(self.display); self.display = None


class FreshPointer:
    """Uniquement des commandes unicast confirmées par le journal du démon.

    Refuse les relectures, messages vieux de plus de 250 ms et corps inconnus.
    La sélection de MAC et le checksum sont déjà vérifiés par procontrold.
    """
    def __init__(self, gain):
        self.gain = gain; self.pending = None; self.seen = deque(maxlen=256)
        self.remainder = [0.0, 0.0]

    def feed(self, row, now):
        if row.get('event') in ('started', 'console_state', 'stopped'):
            self.pending = None; self.seen.clear(); self.remainder = [0.0, 0.0]
        if row.get('event') == 'ethernet_rx':
            self.pending = row
            return None
        if row.get('event') != 'controls' or self.pending is None:
            return None
        h, self.pending = self.pending, None
        try:
            age = now - datetime.fromisoformat(h['utc']).timestamp()
            if not 0 <= age <= 0.25 or h.get('command_field') != 0 or not h.get('body_sum16_match'):
                return None
            key = (h['sequence_candidate'], h['body_hex'])
            if key in self.seen:
                return None
            decoded = decode_pointer(bytes.fromhex(h['body_hex']))
            if decoded is None:
                return None
        except (KeyError, ValueError, TypeError):
            return None
        self.seen.append(key)
        motion = []
        for axis, name in enumerate(('dx', 'dy')):
            value = self.remainder[axis] + decoded[name] * self.gain
            step = int(value); self.remainder[axis] = value - step
            motion.append(step)
        return tuple(motion)


def pointer_status(runtime):
    try: result = json.loads((runtime / 'pointer-status.json').read_text())
    except (OSError, ValueError): result = {}
    result['running'] = False
    if (runtime / 'pointer.lock').exists():
        with (runtime / 'pointer.lock').open('a') as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: result['running'] = True
    return result


def worker(args):
    runtime = Path(args.runtime); os.chdir(runtime); os.umask(0o077)
    with (runtime / 'pointer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pointer = XPointer(); inputs = XInput(pointer)
        control = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        Path('pointer.sock').unlink(missing_ok=True)
        control.bind('pointer.sock'); control.setblocking(False)
        path = runtime / 'events.jsonl'; log = path.open(); log.seek(0, 2)
        settings = load_settings(runtime.parent/'settings.json')
        parser = FreshPointer(args.gain); alive = True; next_status = 0
        state = {'pid': os.getpid(), 'started_utc': datetime.now(timezone.utc).isoformat(),
                 'gain': args.gain, 'mode': 'motion_clicks_alpha_keyboard', 'commands': 0, 'moves': 0,
                 'input_events': 0, 'settings_revision': settings['revision'],
                 'position': pointer.position(), 'error': None}
        def stop(*_):
            nonlocal alive
            alive = False
        signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
        def publish():
            state['running'] = alive
            state['updated_utc'] = datetime.now(timezone.utc).isoformat()
            temp = runtime / 'pointer-status.tmp'
            temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
            temp.replace(runtime / 'pointer-status.json')
        publish()
        try:
            while alive:
                try:
                    data, client = control.recvfrom(65535)
                    if data == b'stop': alive = False; continue
                    try:
                        request = json.loads(data)
                        if request.get('command') != 'configure':raise ValueError('Commande inconnue')
                        settings = validate_settings(request['settings'])
                        parser.gain = settings['pointer_gain']; parser.remainder = [0.,0.]
                        state['gain'] = parser.gain; state['settings_revision'] = settings['revision']; publish()
                        reply = {'ok':True,'revision':settings['revision']}
                    except (ValueError,KeyError,TypeError) as exc:reply={'ok':False,'error':str(exc)}
                    if client:
                        try:control.sendto(json.dumps(reply).encode(),client)
                        except OSError:pass
                except BlockingIOError: pass
                if time.monotonic() >= next_status:
                    daemon = daemon_status(runtime)
                    if not daemon.get('running'):
                        state['error'] = 'Démon Ethernet arrêté'; break
                    state['console'] = daemon.get('console')
                    state['alpha'] = daemon.get('surface',{}).get('alpha',False)
                    if state['console'] != 'online': inputs.release_all()
                    state['position'] = pointer.position(); publish(); next_status = time.monotonic() + 1
                offset = log.tell(); line = log.readline()
                if line and not line.endswith('\n'):
                    log.seek(offset); time.sleep(0.01); continue
                if line:
                    try: row = json.loads(line)
                    except ValueError: continue
                    if row.get('event') == 'input_events':
                        age = time.time() - datetime.fromisoformat(row['utc']).timestamp()
                        if 0 <= age <= 0.25:
                            try:
                                for action in row['actions']: inputs.apply(action)
                                state['input_events'] = inputs.events
                            except (ValueError, KeyError, IndexError) as exc:
                                inputs.release_all(); state['error'] = str(exc)
                        else: inputs.release_all()
                    if row.get('event') in ('stopped','started') or (row.get('event')=='console_state' and row.get('state')!='online'):
                        inputs.release_all()
                    motion = parser.feed(row, time.time())
                    if motion is not None and state.get('console') == 'online':
                        state['commands'] += 1
                        if any(motion): pointer.move(*motion); state['moves'] += 1
                else:
                    if os.fstat(log.fileno()).st_ino != path.stat().st_ino:
                        log.close(); log = path.open()
                        # Fichier nouvellement créé : la limite de fraîcheur reste appliquée.
                        parser.pending = None
                    time.sleep(0.01)
        except Exception as exc:
            state['error'] = str(exc); raise
        finally:
            alive = False; inputs.release_all(); publish(); log.close(); pointer.close(); control.close()
            Path('pointer.sock').unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('start', 'status', 'stop', '_run'))
    p.add_argument('--runtime', default=str(RUNTIME))
    p.add_argument('--gain', type=float)
    args = p.parse_args(); runtime = Path(args.runtime).resolve(); args.runtime = str(runtime)
    if args.gain is None: args.gain = load_settings(runtime.parent/'settings.json')['pointer_gain']
    if not .01 <= args.gain <= 1: p.error('Gain requis : 0 < gain <= 1')
    state = pointer_status(runtime)
    if args.action == 'status': print(json.dumps(state, indent=2)); return
    if args.action == 'stop':
        if state['running']:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as control:
                os.chdir(runtime); control.sendto(b'stop', 'pointer.sock')
            for _ in range(50):
                if not pointer_status(runtime)['running']: break
                time.sleep(0.05)
        print(json.dumps(pointer_status(runtime), indent=2)); return
    if args.action == '_run': return worker(args)
    if state['running']: print(json.dumps(state, indent=2)); return
    if not daemon_status(runtime).get('running'):
        raise RuntimeError('Démarrer procontrold avant le pointeur')
    with (runtime / 'pointer-launcher.log').open('w') as out:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '_run',
                                  '--runtime', str(runtime), '--gain', str(args.gain)],
                                 stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)
    for _ in range(50):
        state = pointer_status(runtime)
        if state.get('pid') == child.pid and state['running']:
            print(json.dumps(state, indent=2)); return
        if child.poll() is not None:
            raise RuntimeError((runtime / 'pointer-launcher.log').read_text()[-1000:])
        time.sleep(0.05)
    raise RuntimeError('Démarrage du pointeur sans état publié')


if __name__ == '__main__':
    try: main()
    except (OSError, RuntimeError) as exc: raise SystemExit(str(exc))
