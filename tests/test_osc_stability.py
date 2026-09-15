import socket
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from ardour_transport import decode
from surface_osc import ArdourSurface
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback, scribble, motor
from surface_routing import SurfaceRouting
from session_probe import Session

class OscStabilityTests(unittest.TestCase):
    def test_refresh_paths_do_not_rebuild_ardour_observers(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
            server.bind(('127.0.0.1',0));server.settimeout(.1)
            client=ArdourSurface(server.getsockname()[1], SurfaceMap())
            try:
                for _ in range(4): server.recv(65535)
                client.refresh()
                client.actions([('osc','/refresh',[1.0]),('osc','/transport_play',[1.0])])
                received=[decode(server.recv(65535))[0] for _ in range(3)]
                self.assertEqual(received,[('/transport_speed',[]),('/transport_speed',[]),('/transport_play',[1.0])])
                with self.assertRaises(socket.timeout):server.recv(65535)
            finally:client.close()

    def test_catalog_changes_and_missing_replies_but_no_idle_poll(self):
        mapping=SurfaceMap();routing=SurfaceRouting(mapping,SurfaceFeedback(mapping))
        self.assertTrue(routing.catalog_due(10,0))
        self.assertFalse(routing.catalog_due(10,12))
        routing.begin_catalog();routing.feed('#reply',['end_route_list'])
        self.assertFalse(routing.catalog_due(10000,12))
        routing.feed('/strip/list',[])
        self.assertTrue(routing.catalog_due(10000,12))
        routing.begin_catalog();routing.feed('#reply',['end_route_list'])
        self.assertFalse(routing.catalog_due(20000,12))
        routing.disconnect()
        self.assertTrue(routing.catalog_due(20000,12))

    def test_console_resync_keeps_current_labels_and_touched_motor_guard(self):
        mapping=SurfaceMap();feedback=SurfaceFeedback(mapping)
        feedback.initialize();feedback.feed('/strip/name',[1,'Current'])
        feedback.feed('/strip/fader',[1,.75]);feedback.queue.clear()
        mapping.touched.add(1);feedback.resync()
        self.assertEqual(feedback.queue[('name',1)],scribble(1,'Current'))
        session=Session('00:00:00:00:00:01','00:00:00:00:00:02');session.online_acked=True
        for i in range(100):
            frame=feedback.next_frame(session,100+i)
            if frame is not None:
                self.assertNotIn(motor(1,.75),frame)
                feedback.acknowledge({'command_field':160,'ack_candidate':session.sequence})
        self.assertIn(('motor',1),feedback.queue)

if __name__=='__main__':unittest.main()
