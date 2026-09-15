import socket
import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from ardour_transport import message, decode, TransportMap, ArdourTransport


class OscTests(unittest.TestCase):
    def test_wire_encoding_and_decode(self):
        self.assertEqual(message('/transport_play', 1), b'/transport_play\0,i\0\0\0\0\0\x01')
        self.assertEqual(decode(message('/test', 5, 0.5, 'OK')), [('/test', [5, 0.5, 'OK'])])
        self.assertEqual(decode(b'/test\0\0\0,h\0\0' + struct.pack('>q', 2**40)), [('/test', [2**40])])

    def test_malformed_and_bundle(self):
        packet = message('/transport_stop', 1)
        bundle = b'#bundle\0' + bytes(8) + struct.pack('>I', len(packet)) + packet
        self.assertEqual(decode(bundle), [('/transport_stop', [1])])
        for data in (b'bad', packet[:-1], bundle[:-1], b'#bundle\0'):
            with self.subTest(data=data), self.assertRaises(ValueError): decode(data)

    def test_release_unmapped_and_retries_do_not_start_transport(self):
        mapper = TransportMap()
        self.assertIsNone(mapper.route(1, bytes.fromhex('90 10 1c')))
        self.assertIsNone(mapper.route(2, bytes.fromhex('f0 13 00 70 00 55 f7')))
        self.assertEqual(mapper.route(3, bytes.fromhex('90 10 5c')), '/transport_play')
        self.assertIsNone(mapper.route(3, bytes.fromhex('90 10 5c')))
        self.assertEqual(mapper.route(4, bytes.fromhex('90 0f 5c')), '/transport_stop')

    def test_loopback_setup_forward_and_feedback(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as fake:
            fake.bind(('127.0.0.1', 0)); fake.settimeout(1)
            bridge = ArdourTransport(fake.getsockname()[1])
            self.addCleanup(bridge.close)
            setup, peer = fake.recvfrom(65535)
            self.assertEqual(decode(setup)[0][0], '/set_surface')
            self.assertEqual(decode(setup)[0][1][-1], 0)
            self.assertEqual(decode(fake.recvfrom(65535)[0]), [('/set_surface', [])])
            bridge.forward(1, bytes.fromhex('90 10 5c'))
            self.assertEqual(decode(fake.recvfrom(65535)[0]), [('/transport_play', [1])])
            fake.sendto(message('/transport_play', 1.0), peer)
            import select
            self.assertTrue(select.select([bridge.socket], [], [], 1)[0])
            self.assertEqual(bridge.poll(), [('/transport_play', [1.0])])

    def test_navigation_uses_reference_buttons_and_ignores_releases(self):
        mapper = TransportMap()
        for key, address in ((6, '/goto_start'), (7, '/goto_end'), (13, '/rewind'), (14, '/ffwd')):
            self.assertEqual(mapper.route(key, bytes([0x90, key, 0x5c])), address)
            self.assertIsNone(mapper.route(key, bytes([0x90, key, 0x5c])))
            self.assertIsNone(mapper.route(key+100, bytes([0x90, key, 0x1c])))
        self.assertIsNone(mapper.route(200, bytes.fromhex('90 11 5c')))


if __name__ == '__main__': unittest.main()
