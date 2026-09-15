"""Modèle de session testé sans socket ; ne simule pas le firmware."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from session_probe import Session

HOST = '02:00:00:00:00:01'
PEER = '00:a0:7e:a0:ad:9c'


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(HOST, PEER, 60)
        self.console = Session(PEER, HOST)

    def announcement(self, command=0xe0, name=b'MAINUNIT'):
        body = bytes(15) + b'1.37'.ljust(9, b'\0') + name.ljust(9, b'\0') + b'\0'
        return b'\xff' * 6 + self.console.frame(command, 1, 400, body=body)[6:]

    def test_online_reference_header_once(self):
        frames = self.session.receive(self.announcement(), 100)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0][14:30].hex(), '0010000000000001000000000000e200')
        self.assertEqual(len(frames[0]), 60)
        self.assertEqual(self.session.receive(self.announcement(), 101), [])

    def test_no_emission_before_identity(self):
        self.assertEqual(self.session.tick(100), [])
        self.assertEqual(self.session.receive(self.announcement(name=b'CONTROL24'), 100), [])
        bad = self.announcement()[:6] + bytes(6) + self.announcement()[12:]
        self.assertEqual(self.session.receive(bad, 100), [])

    def test_existing_session_rejected(self):
        with self.assertRaises(RuntimeError):
            self.session.receive(self.announcement(command=0xe1), 100)

    def test_ack_echoes_received_sequence_not_own(self):
        self.session.receive(self.announcement(), 100)
        frame = self.console.frame(0, 1, 456, body=b'\x90\x08\x01')
        ack = self.session.receive(frame, 102)[0]
        self.assertEqual(struct.unpack('>HHIIHBB', ack[14:30]), (16, 0, 0, 456, 0, 0xa0, 0))
        self.assertEqual(self.session.receive(self.console.frame(0xa0, ack=1), 103), [])

    def test_keepalive_cadence_sequence_and_ack_activity(self):
        self.session.receive(self.announcement(), 100)
        self.assertEqual(self.session.tick(109.9), [])
        keep = self.session.tick(110)[0]
        self.assertEqual(keep[14:31].hex(), '0011000000000002000000000000000100')
        self.session.receive(self.console.frame(0, 1, 10, body=b'\0'), 118)
        self.assertEqual(len(self.session.tick(120)), 1)
        self.assertEqual(self.session.tick(128), [])

    def test_continuous_gestures_do_not_starve_keepalive(self):
        self.session.receive(self.announcement(), 100)
        keepalives = []
        for elapsed in range(1, 60):
            frame = self.console.frame(0, 1, elapsed, body=b'\x90\x10\x5c')
            ack = self.session.receive(frame, 100 + elapsed)[0]
            self.assertEqual(int.from_bytes(ack[22:26], 'big'), elapsed)
            keepalives.extend(self.session.tick(100 + elapsed))
        self.assertEqual([int.from_bytes(f[18:22], 'big') for f in keepalives], [2, 3, 4, 5, 6])
        self.assertEqual(self.session.tick(160), [])

    def test_no_emission_at_or_after_deadline(self):
        self.session.receive(self.announcement(), 100)
        self.assertEqual(self.session.tick(160), [])
        self.assertEqual(self.session.receive(self.console.frame(0, 1, 10, body=b'\0'), 161), [])

    def test_clock_test_waits_for_online_ack_then_clears_display(self):
        from procontrol_display import clock_command
        session = Session(HOST, PEER, 80, clock_test=True)
        session.receive(self.announcement(), 100)
        self.assertEqual(session.tick(103), [])
        session.receive(self.console.frame(0xa0, ack=1), 103.1)
        for now, text in ((103.2, '12345678'), (133, '87654321'), (163, '        ')):
            frame = session.tick(now)[0]
            self.assertEqual(frame[30:45], clock_command(text))
            sequence = int.from_bytes(frame[18:22], 'big')
            session.receive(self.console.frame(0xa0, ack=sequence), now + 0.1)
        self.assertFalse(session.clock_steps)
        self.assertIsNone(session.clock_pending)
        self.assertEqual(session.tick(180), [])

    def test_clock_test_stops_on_missing_ack(self):
        session = Session(HOST, PEER, 80, clock_test=True)
        session.receive(self.announcement(), 100)
        session.receive(self.console.frame(0xa0, ack=1), 101)
        session.tick(103)
        session.receive(self.console.frame(0xa0, ack=99), 104)
        with self.assertRaises(RuntimeError):
            session.tick(105)


if __name__ == '__main__':
    unittest.main()
