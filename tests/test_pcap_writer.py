from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from inspect_pcap import packets
from pcap_writer import write_header, write_packet


class WriterTests(unittest.TestCase):
    def test_round_trip_keeps_microseconds_across_second_boundary(self):
        frames = [bytes.fromhex('ffffffffffff020000000001885f') + b'one',
                  bytes.fromhex('ffffffffffff020000000001885f') + b'two']
        times = [1_789_316_122_999_700_123, 1_789_316_123_001_200_999]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'roundtrip.pcap'
            with path.open('wb') as stream:
                write_header(stream)
                for ts, frame in zip(times, frames):
                    write_packet(stream, ts, frame)
            rows = list(packets(path))
        self.assertEqual([x[0] for x in rows], [t // 1000 * 1000 for t in times])
        self.assertEqual([x[1] for x in rows], frames)
        self.assertEqual(rows[1][0] - rows[0][0], 1_500_000)


if __name__ == '__main__':
    unittest.main()
