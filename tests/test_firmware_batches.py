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

    def exchange(self, incomplete=False, experimental=False, state=None):
        data = bytes([0xf7, 0xf0, 0, 10, 13, 39, 255, 128, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        start, batch = (0x2a3d0, 32) if experimental else (0x20400, 16)
        if experimental: data = bytes(range(256))
        options=dict(address=start,length=len(data),batch_size=batch,experimental_batch32=experimental)
        if state:
            from firmware_probe import STATE_FIELDS
            start,size=STATE_FIELDS[state];data=bytes(i%256 for i in range(size))
            options=dict(state=state,batch_size=16)
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
                    for index, (address, expected) in enumerate(requests_for(**options)):
                        request = pending.pop(0) if pending else remote_rx.recv(65535)
                        self.assertEqual(request[30:30+len(expected)],expected)
                        remote_tx.send(peer.frame(0xa0,ack=int.from_bytes(request[18:22],'big')))
                        if address is None:
                            groups = [(1,PREFIX+EXPECTED_VERSION+b'\xf7')]
                        else:
                            positions = list(range(address,min(address+batch,start+len(data))))
                            if incomplete: positions.pop()
                            positions.reverse()  # responses need not arrive in address order
                            groups = [(1,PREFIX+b'\n\r\xf7')]
                            groups += [(len(positions[n:n+2]), b''.join(
                                memory_envelope(a,data[a-start]) for a in positions[n:n+2]))
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
                report = run_probe(rx,tx,ConsoleSession(HOST,PEER),out,
                                   connect_timeout=.5,reply_timeout=.2,**options)
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
                    self.assertEqual(len(report['transactions']),1+(len(data)+batch-1)//batch)
                    if state:
                        from audit_firmware_probe import audit_probe
                        checked=audit_probe(out,bytes.fromhex(HOST.replace(':','')),
                                             bytes.fromhex(PEER.replace(':','')))
                        self.assertEqual(bytes.fromhex(checked['data_hex']),data)
                    if experimental:
                        from audit_comm_archive import audit_chunk
                        actual, audited = audit_chunk(out/'traffic.pcap',start,len(data),
                            bytes.fromhex(HOST.replace(':','')),bytes.fromhex(PEER.replace(':','')),
                            expected_batch_size=batch)
                        self.assertEqual(actual,data)
                        self.assertEqual(audited['counts']['memory_requests'],8)
                        with self.assertRaises(ValueError):
                            audit_chunk(out/'traffic.pcap',start,len(data),
                                bytes.fromhex(HOST.replace(':','')),bytes.fromhex(PEER.replace(':','')),
                                expected_batch_size=16)
            finally:
                rx.close();tx.close();remote_tx.close();remote_rx.close()

    def test_real_socket_batches_assemble_addresses_and_deduplicate(self):
        self.exchange()

    def test_missing_byte_prevents_next_batch_and_complete_dump(self):
        self.exchange(incomplete=True)

    def test_experimental_32_preserves_all_byte_values_over_socket_and_independent_audit(self):
        self.exchange(experimental=True)

    def test_experimental_32_missing_byte_stops_without_retry(self):
        self.exchange(incomplete=True,experimental=True)

    def test_named_flash_gap_larger_than_256_bytes_over_socket(self):
        self.exchange(state='comm-app-gap-2fce4')

    def test_experimental_32_is_only_available_for_fixed_code_pilot(self):
        allowed=dict(address=0x2a3d0,length=256,batch_size=32,experimental_batch32=True)
        self.assertEqual(len(requests_for(**allowed)),9)
        for changes in ({'address':0x20400},{'length':255},{'batch_size':16},
                        {'experimental_batch32':False},{'state':'fader-rx-ring'},
                        {'ring_offset':0},{'target':'fader'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                requests_for(**{**allowed,**changes})


if __name__ == '__main__': unittest.main()
