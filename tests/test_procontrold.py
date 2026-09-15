import argparse
import fcntl
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from procontrold import ConsoleSession, running, spawn_worker, status
from session_probe import Session
from ardour_transport import decode

HOST = '02:00:00:00:00:01'
PEER = '00:a0:7e:a0:ad:9c'
SCRIPT = str(Path(__file__).resolve().parents[1] / 'tools/procontrold.py')


def announcement(peer, command=0xe0):
    body = bytes(15) + b'1.37'.ljust(9, b'\0') + b'MAINUNIT\0' + b'\0'
    return b'\xff'*6 + peer.frame(command, 1, 400, body=body)[6:]


class DaemonTests(unittest.TestCase):
    def test_no_runtime_limit_and_reconnect_on_offline(self):
        flow = ConsoleSession(HOST, PEER); peer = Session(PEER, HOST)
        self.assertEqual(flow.receive(announcement(peer), 100)[0][0][28], 0xe2)
        flow.receive(peer.frame(0xa0, ack=1), 101)
        flow.receive(announcement(peer, 0xe1), 102)
        self.assertEqual(flow.phase, 'online')
        for now in range(110, 3711, 10):
            flow.receive(announcement(peer, 0xe1), now)
            self.assertEqual(flow.tick(now)[0][30], 0)
        self.assertEqual(flow.receive(announcement(peer), 3712)[0][0][28], 0xe2)
        self.assertEqual(flow.connections, 2)
        flow.tick(3800)
        self.assertEqual(flow.phase, 'waiting_console')

    def test_existing_session_is_waited_out_and_bad_checksum_rejected(self):
        from inspect_pcap import CaptureError
        flow = ConsoleSession(HOST, PEER); peer = Session(PEER, HOST)
        self.assertEqual(flow.receive(announcement(peer, 0xe1), 100)[0], [])
        self.assertEqual(flow.phase, 'waiting_existing_session')
        broken = bytearray(announcement(peer)); broken[16] ^= 1
        with self.assertRaises(CaptureError): flow.receive(bytes(broken), 101)

    def test_detached_worker_keeps_lock_bridges_play_and_stops_without_root(self):
        # De vraies sockets locales remplacent les deux sockets Ethernet : aucun
        # privilège, aucune émission vers la console. Le worker est un vrai processus.
        with tempfile.TemporaryDirectory(prefix='procontrold-test-') as temp:
            runtime = Path(temp)
            rx, console_send = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            tx, console_recv = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            fake = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            fake.bind(('127.0.0.1', 0)); fake.settimeout(3); console_recv.settimeout(3)
            lock = (runtime/'daemon.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX)
            args = argparse.Namespace(runtime=temp, interface='test', host=HOST, mac=PEER,
                                      osc_port=fake.getsockname()[1])
            child = spawn_worker(args, rx, tx, lock)
            rx.close(); tx.close(); lock.close()
            try:
                for _ in range(100):
                    if (runtime/'status.json').exists(): break
                    if child.poll() is not None: self.fail((runtime/'launcher.log').read_text())
                    time.sleep(.03)
                self.assertTrue(running(runtime))
                self.assertEqual(status(runtime)['pid'], child.pid)
                self.assertEqual(__import__('os').getsid(child.pid), child.pid)
                # Une deuxième ouverture ne peut prendre le verrou détenu par le fils.
                peer = Session(PEER, HOST)
                console_send.send(announcement(peer))
                self.assertEqual(console_recv.recv(65535)[28], 0xe2)
                console_send.send(peer.frame(0xa0, ack=1))
                console_send.send(announcement(peer, 0xe1))
                console_send.send(peer.frame(0, 1, 10, body=bytes.fromhex('90 10 5c')))
                # La surface commence aussi à initialiser les afficheurs. Le faux
                # matériel acquitte ces sorties pendant l'attente de l'ACK PLAY.
                for _ in range(24):
                    output = console_recv.recv(65535)
                    if output[28] == 0xa0: break
                    self.assertEqual(output[28], 0)
                    sequence = int.from_bytes(output[18:22], 'big')
                    console_send.send(peer.frame(0xa0, ack=sequence))
                else: self.fail('ACK du geste PLAY absent')
                messages = []
                while not any(a == '/transport_play' for a, _ in messages):
                    messages.extend(decode(fake.recvfrom(65535)[0]))
                self.assertIn(('/transport_play', [1.0]), messages)
                stop = subprocess.run([sys.executable, SCRIPT, 'stop', '--runtime', temp],
                                      capture_output=True, text=True, timeout=6)
                self.assertEqual(stop.returncode, 0, stop.stderr)
                self.assertEqual(child.wait(timeout=3), 0)
                self.assertFalse(running(runtime))
                self.assertEqual(status(runtime)['console'], 'stopped')
            finally:
                if child.poll() is None: child.terminate(); child.wait(timeout=3)
                console_send.close(); console_recv.close(); fake.close()


if __name__ == '__main__': unittest.main()
