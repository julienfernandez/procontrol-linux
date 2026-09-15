import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap

class DSPEncoderTests(unittest.TestCase):
    def test_eight_physical_encoders_both_directions(self):
        for index, address in enumerate(range(0x4d,0x55),1):
            m=SurfaceMap()
            m.feedback('/select/plugin/parameter',[index,.5])
            up=m.command(bytes([0xb0,address,0x41]),0)
            self.assertEqual(up[0][:2],('osc','/select/plugin/parameter'))
            self.assertEqual(up[0][2][0],index)
            self.assertAlmostEqual(up[0][2][1],.51)
            self.assertAlmostEqual(m.command(bytes([0xb0,address,0x3f]),1)[0][2][1],.5)
            self.assertEqual(m.encoder_mode,'pan')
    def test_unknown_and_invalidated_parameter_does_not_write(self):
        m=SurfaceMap();c=bytes.fromhex('b0 4d 41')
        self.assertEqual(m.command(c,0),[])
        m.feedback('/select/plugin/parameter',[1,.7])
        m.feedback('/select/plugin/name',['New plugin'])
        self.assertEqual(m.command(c,1),[])
        m.feedback('/select/plugin/parameter',[1,.2])
        m.feedback('/select/name',['New track'])
        self.assertEqual(m.command(c,2),[])
    def test_fine_and_bounds(self):
        m=SurfaceMap();m.modifiers.add('Shift_L')
        m.feedback('/select/plugin/parameter',[8,.5])
        self.assertAlmostEqual(m.command(bytes.fromhex('b0 54 42'),0)[0][2][1],.504)
        m.feedback('/select/plugin/parameter',[8,1.0])
        self.assertEqual(m.command(bytes.fromhex('b0 54 41'),0)[0][2][1],1.)
        m.feedback('/select/plugin/parameter',[8,0.0])
        self.assertEqual(m.command(bytes.fromhex('b0 54 3f'),0)[0][2][1],0.)
    def test_adjacent_unknown_and_strip_pan_direction(self):
        m=SurfaceMap()
        for address in (0x4c,0x55):self.assertIsNone(m.command(bytes([0xb0,address,0x41]),0))
        self.assertEqual(m.command(bytes.fromhex('b0 40 41'),0),[('osc','/strip/pan_stereo_position',[1,.49])])
        self.assertIsNone(m.command(bytes.fromhex('b0 4d 41 00'),0))
