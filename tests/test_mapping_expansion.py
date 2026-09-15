import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap

class MappingExpansionTests(unittest.TestCase):
    def test_automation_target_then_mode_and_release(self):
        m=SurfaceMap()
        for button,target in [(0x1a,'pan'),(0x1c,'mute'),(0x1d,'trimdB'),(0x18,'gain')]:
            actions=m.command(bytes([0x90,button,0x48]),0)
            self.assertEqual(sum(a[2][0] for a in actions),1)
            self.assertEqual(m.command(bytes([0x90,0x19,0x48]),0),[('osc','/select/'+target+'/automation',[3])])
            self.assertEqual(m.command(bytes([0x90,0x19,0x08]),0),[])
    def test_shift_zoom_does_not_replace_normal_markers(self):
        m=SurfaceMap()
        self.assertEqual(m.command(bytes.fromhex('90 02 48'),0)[0][1],'/add_marker')
        m.command(bytes.fromhex('90 23 48'),0)
        self.assertEqual(m.command(bytes.fromhex('90 02 48'),0)[0][2],['Editor/zoom-to-selection'])
        m.command(bytes.fromhex('90 23 08'),0)
        self.assertEqual(m.command(bytes.fromhex('90 02 48'),0)[0][1],'/add_marker')
    def test_new_actions_once_despite_retry_and_release(self):
        m=SurfaceMap();body=bytes.fromhex('90 01 5c')
        self.assertEqual(m.route(1,body),[('osc','/access_action',['Transport/PlayPreroll'])])
        self.assertEqual(m.route(1,body),[])
        self.assertEqual(m.route(2,bytes.fromhex('90 01 1c')),[])
    def test_previous_parameter_page_and_plugin_mode(self):
        m=SurfaceMap();m.command(bytes.fromhex('90 04 59'),0)
        self.assertEqual(m.encoder_mode,'plugin')
        m.modifiers.add('Shift_L')
        self.assertEqual(m.command(bytes.fromhex('90 2a 57'),0),[('osc','/select/plug_page',[-1.0])])
