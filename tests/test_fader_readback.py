from pathlib import Path
import json
import socket
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fader_readback as reader
from audit_diginet import candidate_header
from session_probe import Session


def serial_reply(data, address=0x8000):
    return b'\0\x20\x02\n\r'+b''.join(b'\0\x20\x12'+
        f"{address+i:08X}: {value:02X} '".encode()+bytes([value])+b"'\n\r"
        for i,value in enumerate(data))


class FaderReadbackTests(unittest.TestCase):
    def test_request_cannot_leave_vetted_vector_window(self):
        self.assertEqual(reader.request_for(0x8000,1),bytes.fromhex('f0 13 00 70 01')+b'U00008000q\xf7')
        self.assertTrue(reader.request_for(0x8000,8).endswith(b'Q'*8+b'\xf7'))
        for start,length in [(0,1),(0x8400,1),(0x8000,9),(0x8007,2),(0x8000,0),(0x8000071b,1)]:
            with self.assertRaises(ValueError):reader.request_for(start,length)

    def test_raw_serial_preserves_zero_high_bits_and_f7(self):
        data=bytes([0,4,0x53,0x84,0,0,0xa4,0xf7])
        self.assertEqual(reader.parse_serial(serial_reply(data),0x8000,8),data)
        with self.assertRaises(ValueError):reader.parse_serial(serial_reply(data)[:-1],0x8000,8)
        with self.assertRaises(ValueError):reader.parse_serial(serial_reply(data,0x8001),0x8000,8)
        bad=bytearray(serial_reply(b'\x80'));bad[-4]=0x81
        with self.assertRaises(ValueError):reader.parse_serial(bad,0x8000,1)

    def test_circular_windows_wrap_without_reading_ring_header(self):
        base=reader.RX_BUFFER_START
        self.assertEqual(reader.ring_windows(base+480,26),[(480,8),(0,18)])
        self.assertEqual(reader.ring_windows(base,341),[(0,256),(256,85)])
        for start,size in [(base-1,1),(base+488,1),(base,488),(base,0)]:
            with self.assertRaises(ValueError):reader.ring_windows(start,size)

    def test_changed_layout_and_invalid_pointers_are_rejected(self):
        base=reader.RX_BUFFER_START
        good=(base,base,base,512,0,0)
        self.assertEqual(reader.ring_header(struct.pack('>6I',*good))['producer'],base)
        for index,value in [(0,base-1),(1,base+1),(2,base+488),(3,488)]:
            bad=list(good);bad[index]=value
            with self.assertRaises(ValueError):reader.ring_header(struct.pack('>6I',*bad))

    def exercise_snapshot(self, changed=False, touched=False):
        base=reader.RX_BUFFER_START;before=base+478
        raw=serial_reply(b'\0');after=base+16
        ring=bytearray(488)
        for i,value in enumerate(raw):ring[(478+i)%488]=value
        sent=[]
        def save(folder,data=None):
            result={'error':None}
            (folder/'result.json').write_text(json.dumps(result))
            if data is not None:(folder/'memory.bin').write_bytes(data)
            return result
        def probe(rx,tx,flow,folder,**kwargs):
            state=kwargs.get('state');data=None
            if state=='fader-mode':data=b'\0'
            elif state=='fader-errors':data=bytes(4)
            elif state=='fader-touch-state':data=bytes([1 if touched else 0])+bytes(15)
            elif state=='fader-rx-ring':
                producer=before if folder.name=='rx-before' else after
                if changed and folder.name=='rx-final':producer+=1
                data=struct.pack('>6I',producer,base,producer,512,0,0)
            elif kwargs.get('ring_offset') is not None:
                offset=kwargs['ring_offset'];data=ring[offset:offset+kwargs['length']]
            return save(folder,data)
        def capture(rx,tx,flow,folder,address,length):
            sent.append((address,length));return save(folder)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            with patch.object(reader,'run_probe',side_effect=probe),\
                 patch.object(reader,'run_fader_version',side_effect=lambda a,b,c,d:save(d)),\
                 patch.object(reader,'capture_request',side_effect=capture):
                result=reader.acquire(None,None,None,out,0x8000,1)
            if touched:
                self.assertEqual(sent,[]);self.assertFalse(result['complete'])
            elif changed:
                self.assertFalse(result['complete']);self.assertIn('modifié',result['error'])
                self.assertFalse((out/'memory.bin').exists())
                self.assertTrue(result['recovery']['version_confirmed'])
            else:
                self.assertTrue(result['complete']);self.assertEqual((out/'memory.bin').read_bytes(),b'\0')
                self.assertEqual((out/'serial.bin').read_bytes(),raw)

    def test_complete_wrapped_snapshot_is_reconstructed(self):self.exercise_snapshot()
    def test_overwritten_snapshot_is_not_published_as_memory(self):self.exercise_snapshot(changed=True)
    def test_touched_faders_prevent_any_read_request(self):self.exercise_snapshot(touched=True)

    def test_socket_request_records_ack_without_claiming_memory_success(self):
        host='02:00:00:00:00:01';peer='00:a0:7e:a0:ad:9c'
        class Flow:
            phase='online'
            session=Session(host,peer)
            def tick(self,now):return []
            def receive(self,frame,now):return [],candidate_header(frame[14:])
        rx,remote_tx=socket.socketpair(socket.AF_UNIX,socket.SOCK_DGRAM)
        tx,remote_rx=socket.socketpair(socket.AF_UNIX,socket.SOCK_DGRAM)
        remote_rx.settimeout(1);failures=[]
        def console():
            try:
                request=remote_rx.recv(65535)
                self.assertEqual(request[30:46],reader.request_for(0x8000,1))
                remote_tx.send(Session(peer,host).frame(0xa0,ack=int.from_bytes(request[18:22],'big')))
            except Exception as exc:failures.append(exc)
        worker=threading.Thread(target=console);worker.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                report=reader.capture_request(rx,tx,Flow(),Path(tmp),0x8000,1,settle=.01)
                worker.join(2)
                self.assertFalse(worker.is_alive())
                if failures:raise failures[0]
                self.assertTrue(report['ack_received']);self.assertIsNone(report['error'])
                self.assertNotIn('complete',report)
                self.assertFalse((Path(tmp)/'memory.bin').exists())
        finally:rx.close();tx.close();remote_rx.close();remote_tx.close()


if __name__=='__main__':unittest.main()
