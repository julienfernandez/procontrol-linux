from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from firmware_probe import PREFIX, EXPECTED_VERSION, requests_for, diagnostic_payloads, run_probe
from procontrold import ConsoleSession
from session_probe import Session

HOST = '02:00:00:00:00:01'
PEER = '00:a0:7e:a0:ad:9c'


def memory_envelope(address, value):
    return PREFIX + f"{address:08X}: {value:02X} '".encode() + bytes([value]) + b"'\n\r\xf7"


class BatchTests(unittest.TestCase):
    def test_batch_tail_never_reads_past_region(self):
        plan = requests_for(0x20064, 28, 16)
        self.assertEqual(plan[1][1], PREFIX+b'A00020064'+b'M'*16+b'\xf7')
        self.assertEqual(plan[2][1], PREFIX+b'A00020074'+b'M'*12+b'\xf7')
        for size in (0, 17):
            with self.assertRaises(ValueError): requests_for(0x20064, 28, size)
        with self.assertRaises(ValueError): requests_for(0x20064, 29, 16)

    def test_concatenated_envelopes_preserve_embedded_f7_and_newlines(self):
        for value in (0xf0, 0xf7, 0, 10, 13, 39, 255):
            frame = PREFIX+b'\n\r\xf7' + memory_envelope(0x20400, value) + memory_envelope(0x20401, 0)
            payloads = diagnostic_payloads(frame)
            self.assertEqual(len(payloads), 3)
            self.assertEqual(payloads[1][-4], value)
        with self.assertRaises(ValueError):
            diagnostic_payloads(memory_envelope(0x20400, 0)+b'\x90\x10\x5c')

    def exchange(self, incomplete=False):
        data = bytes([0xf7, 0xf0, 0, 10, 13, 39, 255, 128, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rx, remote_tx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            tx, remote_rx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            remote_rx.settimeout(1)
            peer = Session(PEER, HOST)
            failures = []

            def server():
                try:
                    pending = []
                    def expect_ack():
                        # A late duplicate can be ACKed after the next request
                        # was already transmitted. Preserve that request.
                        while True:
                            frame = remote_rx.recv(65535)
                            if frame[28] == 0xa0: return
                            self.assertEqual(frame[28],0)
                            pending.append(frame)
                            self.assertEqual(len(pending),1)
                    ident = bytes.fromhex(HOST.replace(':',''))+bytes(9)+b'1.37'.ljust(9,b'\0')+b'MAINUNIT\0\0'
                    remote_tx.send(b'\xff'*6+peer.frame(0xe1,1,100,body=ident)[6:])
                    self.assertEqual(remote_rx.recv(65535)[28],0xe2)
                    remote_tx.send(peer.frame(0xa0,ack=1))
                    seq = 1000
                    for index, (address, expected) in enumerate(requests_for(0x20400,len(data),16)):
                        request = pending.pop(0) if pending else remote_rx.recv(65535)
                        self.assertEqual(request[30:30+len(expected)],expected)
                        remote_tx.send(peer.frame(0xa0,ack=int.from_bytes(request[18:22],'big')))
                        if address is None:
                            groups = [(1,PREFIX+EXPECTED_VERSION+b'\xf7')]
                        else:
                            positions = list(range(address,min(address+16,0x20400+len(data))))
                            if incomplete: positions.pop()
                            positions.reverse()  # responses need not arrive in address order
                            groups = [(1,PREFIX+b'\n\r\xf7')]
                            groups += [(len(positions[n:n+2]), b''.join(
                                memory_envelope(a,data[a-0x20400]) for a in positions[n:n+2]))
                                for n in range(0,len(positions),2)]
                        for count, body in groups:
                            seq += 1
                            frame = peer.frame(0,count,seq,body=body)
                            remote_tx.send(frame)
                            expect_ack()
                            if count == 2:
                                remote_tx.send(frame)
                                expect_ack()
                        if incomplete and address is not None: break
                except Exception as exc: failures.append(exc)

            thread = threading.Thread(target=server);thread.start()
            try:
                report = run_probe(rx,tx,ConsoleSession(HOST,PEER),out,address=0x20400,
                                   length=len(data),batch_size=16,connect_timeout=.5,reply_timeout=.2)
                thread.join(2)
                self.assertFalse(thread.is_alive())
                if failures: raise failures[0]
                if incomplete:
                    self.assertIsNotNone(report['error'])
                    self.assertFalse((out/'memory.bin').exists())
                    self.assertEqual(len(report['transactions']),2)
                else:
                    self.assertIsNone(report['error'])
                    self.assertEqual((out/'memory.bin').read_bytes(),data)
                    self.assertEqual(len(report['transactions']),3)
            finally:
                rx.close();tx.close();remote_tx.close();remote_rx.close()

    def test_real_socket_batches_assemble_addresses_and_deduplicate(self):
        self.exchange()

    def test_missing_byte_prevents_next_batch_and_complete_dump(self):
        self.exchange(incomplete=True)


if __name__ == '__main__': unittest.main()
