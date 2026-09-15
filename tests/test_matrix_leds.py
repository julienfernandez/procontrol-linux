import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback,button_led
from surface_routing import SurfaceRouting

class MatrixLedTests(unittest.TestCase):
    def setUp(self):
        self.m=SurfaceMap();self.f=SurfaceFeedback(self.m);self.f.initialize()
        self.r=SurfaceRouting(self.m,self.f)
        self.catalog(40)
    def catalog(self,count):
        self.r.begin_catalog()
        for i in range(1,count+1):self.r.feed('#reply',['AT',f'Track {i}',2,2,0,0,i,0])
        self.r.feed('#reply',['end_route_list'])
    def light(self,key):return self.f.desired[('led',23,key)]==button_led(23,key,True)
    def press(self,key):
        actions=self.m.command(bytes([0x90,key,0x57]),0)
        for action in actions:self.f.local(action)
        return self.r.actions(actions)
    def test_select_feedback_outside_eight_faders_and_no_optimistic_led(self):
        self.r.feed('/strip/select',[17,1])
        self.assertTrue(self.light(17));self.assertFalse(self.light(2))
        self.assertEqual(self.press(2),[('osc','/strip/select',[2,0])])
        self.assertFalse(self.light(2))
        self.r.feed('/strip/select',[17,0]);self.r.feed('/strip/select',[2,1])
        self.assertFalse(self.light(17));self.assertTrue(self.light(2))
    def test_mode_bank_and_empty_slots(self):
        self.r.feed('/strip/mute',[34,1]);self.r.feed('/strip/solo',[35,1]);self.r.feed('/strip/recenable',[36,1])
        self.press(0x2d);self.press(0x25)
        self.assertTrue(self.light(2));self.assertFalse(self.light(3));self.assertTrue(self.light(0x2d))
        self.press(0x26);self.assertFalse(self.light(2));self.assertTrue(self.light(3))
        self.press(0x27);self.assertFalse(self.light(3));self.assertTrue(self.light(4))
        self.assertFalse(any(self.light(i) for i in range(9,33)))
        self.catalog(2);self.assertFalse(any(self.light(i) for i in range(1,33)))
    def test_alpha_masks_track_feedback_and_restores_on_exit(self):
        self.r.feed('/strip/select',[1,1]);self.press(0x21)
        self.assertFalse(self.light(1));self.assertTrue(self.light(0x21));self.assertFalse(self.light(0x24))
        self.press(0x1c);self.assertTrue(self.light(0x1c))
        self.r.feed('/strip/select',[2,1]);self.assertFalse(self.light(2));self.assertTrue(self.light(0x1c))
        self.press(0x21);self.assertTrue(self.light(1));self.assertTrue(self.light(2));self.assertFalse(self.light(0x1c))
    def test_disconnect_clears_track_lights(self):
        self.r.feed('/strip/select',[1,1]);self.r.disconnect()
        self.assertFalse(any(self.light(i) for i in range(1,33)))

if __name__=='__main__':unittest.main()
