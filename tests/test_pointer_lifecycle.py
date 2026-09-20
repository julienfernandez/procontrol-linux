# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the real worker loop/locks/log tail without injecting desktop input."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKER = r'''
import json, sys
from pathlib import Path
from types import SimpleNamespace
import pointer_x11 as p
def record(kind, value):
    with Path('injected.jsonl').open('a') as out:
        out.write(json.dumps([kind, value]) + '\n')
class Pointer:
    def position(self): return (100, 100)
    def move(self, dx, dy): record('move', [dx, dy])
    def close(self): pass
class Inputs:
    def __init__(self, pointer): self.events = 0; self.held = False
    def apply(self, action):
        self.events += 1; self.held = True; record('input', action)
    def release_all(self):
        if self.held: record('release', None)
        self.held = False
p.XPointer = Pointer
p.XInput = Inputs
p.worker(SimpleNamespace(runtime=sys.argv[1], gain=0.58))
'''


class PointerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='procontrol-pointer-')
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        self.log = self.runtime / 'events.jsonl'
        self.lock = (self.runtime / 'daemon.lock').open('a')
        self.addCleanup(self.lock.close)
        self.process = None

    def daemon(self, pid):
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        target = self.runtime / 'status.json'
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps({'pid': pid, 'started_utc': str(pid), 'console': 'online'}))
        temp.replace(target)

    def start(self, log=True):
        self.daemon(111)
        if log: self.log.touch()
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'tools'))
        self.process = subprocess.Popen([sys.executable, '-c', WORKER, str(self.runtime)],
                                        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.cleanup_worker)
        return self.wait(lambda s: s.get('running') and s.get('console') == 'online')

    def cleanup_worker(self):
        if self.process.poll() is None: self.process.terminate()
        self.process.communicate(timeout=5)

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        state = {}
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                _, err = self.process.communicate()
                self.fail(f'Pointer exited ({self.process.returncode}): {err.decode()}')
            try: state = json.loads((self.runtime / 'pointer-status.json').read_text())
            except (FileNotFoundError, ValueError): pass
            if predicate(state): return state
            time.sleep(0.03)
        self.fail(f'Pointer did not reach expected state: {state}')

    def gesture(self, seq=7, *, age=0, button=False):
        stamp = datetime.fromtimestamp(time.time() - age, timezone.utc).isoformat()
        rows = [{'event': 'ethernet_rx', 'utc': stamp, 'command_field': 0,
                 'body_sum16_match': True, 'sequence_candidate': seq,
                 'body_hex': 'f0 13 00 60 01 00 0a 00 f7'}, {'event': 'controls'}]
        if button:
            rows.append({'event': 'input_events', 'utc': stamp,
                         'actions': [['button', 1, [1]]]})
        with self.log.open('a') as out:
            for row in rows: out.write(json.dumps(row) + '\n')

    def injected(self):
        path = self.runtime / 'injected.jsonl'
        return [json.loads(row) for row in path.read_text().splitlines()] if path.exists() else []

    def test_survives_restart_releases_inputs_and_resumes_same_sequence(self):
        initial = self.start()
        self.gesture(button=True)
        self.wait(lambda s: s.get('moves') == 1 and s.get('input_events') == 1)
        fcntl.flock(self.lock, fcntl.LOCK_UN)
        down = self.wait(lambda s: s.get('console') == 'waiting_daemon')
        self.assertTrue(down['running'])
        self.assertIsNone(down['error'])
        self.assertIn(['release', None], self.injected())
        # A stale status file saying online must not permit mouse or key input.
        self.gesture(seq=8, button=True)
        still_down = self.wait(lambda s: s.get('updated_utc', '') > down['updated_utc'])
        self.assertEqual(still_down['moves'], 1)
        self.assertEqual(still_down['input_events'], 1)
        self.log.rename(self.runtime / 'events.jsonl.1')
        self.log.touch()
        self.daemon(222)
        resumed = self.wait(lambda s: s.get('daemon_pid') == 222 and s.get('console') == 'online')
        self.assertEqual(resumed['pid'], initial['pid'])
        self.assertEqual(resumed['gain'], 0.58)
        self.gesture(button=True)
        self.wait(lambda s: s.get('moves') == 2 and s.get('input_events') == 2)
        self.assertEqual(sum(row[0] == 'move' for row in self.injected()), 2)
        # Explicit stop remains available even without a daemon.
        fcntl.flock(self.lock, fcntl.LOCK_UN)
        self.wait(lambda s: s.get('console') == 'waiting_daemon')
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as control:
            control.sendto(b'stop', str(self.runtime / 'pointer.sock'))
        self.assertEqual(self.process.wait(timeout=5), 0)
        self.assertFalse(json.loads((self.runtime / 'pointer-status.json').read_text())['running'])

    def test_mapping_guard_isolates_worker_releases_and_recovers_without_replay(self):
        self.start();self.gesture(button=True)
        self.wait(lambda s:s.get('moves')==1 and s.get('input_events')==1)
        import surface_settings
        response=surface_settings.rpc(self.runtime,'pointer.sock',{'command':'mapping_guard','active':True})
        self.assertTrue(response['ok'])
        self.assertIn(['release',None],self.injected())
        for seq in range(10,20):self.gesture(seq=seq,button=True)
        # Worker state publishes once a second; injected events would be recorded immediately.
        current=self.wait(lambda s:s.get('mapping_isolated'))
        self.wait(lambda s:s.get('updated_utc','')>current.get('updated_utc',''))
        self.assertEqual(sum(row[0]=='move' for row in self.injected()),1)
        self.assertEqual(sum(row[0]=='input' for row in self.injected()),1)
        surface_settings.rpc(self.runtime,'pointer.sock',{'command':'mapping_guard','active':False})
        self.gesture(seq=20,button=True)
        self.wait(lambda s:s.get('moves')==2 and s.get('input_events')==2)
        self.assertEqual(sum(row[0]=='move' for row in self.injected()),2)

    def test_rotation_gap_does_not_exit_or_replay_stale_events(self):
        initial = self.start()
        self.log.rename(self.runtime / 'events.jsonl.1')
        self.wait(lambda s: s.get('updated_utc', '') > initial['updated_utc'])
        self.gesture(seq=1, age=2, button=True)
        self.gesture(seq=2, button=True)
        state = self.wait(lambda s: s.get('moves') == 1)
        self.assertEqual(state['input_events'], 1)
        self.assertEqual(sum(row[0] == 'move' for row in self.injected()), 1)
        self.assertIsNone(state['error'])

    def test_log_absent_during_start_is_reopened(self):
        initial = self.start(log=False)
        self.assertTrue(initial['running'])
        self.gesture()
        state = self.wait(lambda s: s.get('moves') == 1)
        self.assertEqual(state['pid'], initial['pid'])


if __name__ == '__main__':
    unittest.main()
