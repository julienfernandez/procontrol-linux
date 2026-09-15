import socket, sys, unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from jog_scheduler import JogScheduler
from surface_osc import ArdourSurface
from surface_map import SurfaceMap
from ardour_transport import decode


class JogTests(unittest.TestCase):
    def test_fast_turn_preserves_delta_and_flushes_tail(self):
        j=JogScheduler();sent=[]
        for i in range(200):
            sent+=j.actions([('osc','/jog',[.2])],100+i*.001)
        sent+=j.flush(100.221)
        self.assertLessEqual(len(sent),11)
        self.assertAlmostEqual(sum(a[2][0] for a in sent),40.)
        self.assertEqual(j.pending,0.)
        self.assertEqual(j.flush(101),[])
    def test_first_move_immediate_and_reverse_cancels_pending(self):
        j=JogScheduler()
        self.assertEqual(j.actions([('osc','/jog',[1.])],100),[('osc','/jog',[1.])])
        self.assertEqual(j.actions([('osc','/jog',[2.])],100.001),[])
        self.assertAlmostEqual(j.wait_timeout(100.005),.015)
        self.assertEqual(j.actions([('osc','/jog',[-2.])],100.010),[])
        self.assertEqual(j.flush(100.021),[])
        self.assertEqual(j.wait_timeout(100.021),.05)
    def test_transport_and_mode_are_ordering_barriers(self):
        j=JogScheduler();j.actions([('osc','/jog',[1.])],100)
        j.actions([('osc','/jog',[2.])],100.001)
        stop=('osc','/transport_stop',[1.])
        self.assertEqual(j.actions([stop],100.002),[('osc','/jog',[2.]),stop])
        j.actions([('osc','/jog',[3.])],100.003)
        mode=('osc','/jog/mode',[2.])
        self.assertEqual(j.actions([mode],100.004),[('osc','/jog',[3.]),mode])
        for i in range(5):
            action=('osc','/jog',[float(i)])
            self.assertEqual(j.actions([action],100.005+i*.001),[action])
    def test_slow_jog_is_unchanged(self):
        j=JogScheduler()
        for i in range(10):
            action=('osc','/jog',[.2])
            self.assertEqual(j.actions([action],100+i*.1),[action])
    def test_disconnect_cancels_pending_movement(self):
        j=JogScheduler();j.actions([('osc','/jog',[1.])],100)
        j.actions([('osc','/jog',[2.])],100.001);j.cancel()
        self.assertEqual(j.flush(101),[])
        self.assertEqual(j.cancelled_delta,2.)
    def test_udp_client_emits_pending_tail_without_another_gesture(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as server:
            server.bind(('127.0.0.1',0));server.settimeout(.05)
            client=ArdourSurface(server.getsockname()[1],SurfaceMap())
            try:
                for _ in range(4):server.recv(65535)
                with patch('jog_scheduler.time.monotonic',return_value=100):
                    client.actions([('osc','/jog',[.2])])
                self.assertEqual(decode(server.recv(65535))[0][0],'/jog')
                with patch('jog_scheduler.time.monotonic',return_value=100.001):
                    self.assertEqual(client.actions([('osc','/jog',[.3])]),[])
                self.assertEqual(client.flush_jog(100.021),['/jog'])
                path,values=decode(server.recv(65535))[0]
                self.assertEqual(path,'/jog');self.assertAlmostEqual(values[0],.3)
                with self.assertRaises(socket.timeout):server.recv(65535)
            finally:client.close()
