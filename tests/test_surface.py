# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from surface_map import SurfaceMap,button_info,NUMPAD,OSC_BUTTONS,ACTION_BUTTONS
from surface_feedback import SurfaceFeedback,scribble,motor,meter
from session_probe import Session
from audit_diginet import candidate_header


class SurfaceTests(unittest.TestCase):
    def test_alpha_and_mouse_from_controlled_capture(self):
        fixtures=json.loads((ROOT/'tests/fixtures/alpha-keypad-clicks.json').read_text())
        m=SurfaceMap();keys=[];buttons=[]
        for index,row in enumerate(fixtures):
            result=m.route(index,bytes.fromhex(row['body']))
            self.assertEqual([list(a) for a in result],row['actions'])
            keys.extend(a[1] for a in result if a[0]=='key' and a[2]==[1])
            buttons.extend(a for a in result if a[0]=='button')
            self.assertEqual(m.route(index,bytes.fromhex(row['body'])),[])
        self.assertEqual(keys,['a','b','z','Shift_R','c','1','2','Return'])
        self.assertEqual([(a[1],a[2]) for a in buttons],[('1',[1]),('1',[0]),('3',[1]),('3',[0])])
        self.assertFalse(m.alpha);self.assertFalse(m.held_keys)

    def test_all_alpha_letters_and_mode_exit_release(self):
        m=SurfaceMap();m.command(bytes.fromhex('90 21 57'),0)
        for n in range(1,27):
            self.assertEqual(m.command(bytes([0x90,n,0x57]),0)[0],('key',chr(96+n),[1]))
            self.assertEqual(m.command(bytes([0x90,n,0x17]),0)[0],('key',chr(96+n),[0]))
        m.command(bytes.fromhex('90 1b 57'),0)
        self.assertEqual(m.command(bytes.fromhex('90 21 57'),0)[0][0],'release_all')
        self.assertFalse(m.held_keys)

    def test_source_zones_and_unknown_commands(self):
        self.assertEqual(button_info(bytes.fromhex('90 21 57'))['label'],'Alpha')
        self.assertEqual(button_info(bytes.fromhex('90 06 56'))['label'],'Dim')
        self.assertEqual(button_info(bytes.fromhex('90 00 55'))['label'],'CounterMode')
        m=SurfaceMap()
        self.assertEqual(m.route(1,bytes.fromhex('90 3f 7f')),[])
        self.assertTrue(m.last_unknown)

    def test_transport_jog_and_multiple_commands(self):
        m=SurfaceMap()
        self.assertEqual(m.route(1,bytes.fromhex('b0 5c 41')),[('osc','/jog',[1.0])])
        self.assertEqual(m.route(2,bytes.fromhex('b0 5c 3f')),[('osc','/jog',[-1.0])])
        actions=m.route(3,bytes.fromhex('90 10 5c 90 10 1c 90 0f 5c'))
        self.assertEqual([a[1] for a in actions],['/transport_play','/transport_stop'])

    def test_faders_toggles_and_touch(self):
        m=SurfaceMap();m.feedback('/strip/mute',[1,1.0])
        self.assertEqual(m.route(1,bytes.fromhex('90 08 40')),[('osc','/strip/mute',[1,0])])
        self.assertEqual(m.route(2,bytes.fromhex('b0 00 7f 20 70')),[('osc','/strip/fader',[1,1.0])])
        self.assertEqual(m.route(3,bytes.fromhex('b0 07 00 27 00')),[('osc','/strip/fader',[8,0.0])])
        m.route(4,bytes.fromhex('90 09 40'));self.assertIn(1,m.touched)
        m.route(5,bytes.fromhex('90 09 00'));self.assertNotIn(1,m.touched)

    def test_select_uses_ardour_zero_and_bank_actions_are_local(self):
        m=SurfaceMap()
        self.assertEqual(m.command(bytes.fromhex('90 06 40'),0),[('osc','/strip/select',[1,0])])
        self.assertEqual(m.command(bytes.fromhex('90 06 00'),0),[])
        self.assertEqual(m.command(bytes.fromhex('90 11 57'),0),[('matrix','select',[17])])
        self.assertEqual(m.command(bytes.fromhex('90 0a 5b'),0),[('bank','delta',[-1])])

    def test_hardware_output_formats_and_clamps(self):
        self.assertEqual(scribble(1,'Audio 1').hex(' '),'f0 13 00 40 20 00 41 75 64 69 6f 20 31 20 f7')
        self.assertEqual(motor(1,1),bytes.fromhex('b0 00 7f 20 70'))
        self.assertEqual(motor(8,-1),bytes.fromhex('b0 07 00 27 00'))
        self.assertEqual(meter(0,-193),bytes.fromhex('f0 13 00 10 00 00 00 f7'))
        self.assertEqual(meter(0,0),bytes.fromhex('f0 13 00 10 00 7f 7f f7'))

    def test_feedback_waits_for_ack_and_suspends_if_missing(self):
        m=SurfaceMap();f=SurfaceFeedback(m);s=Session('00:00:00:00:00:01','00:00:00:00:00:02')
        s.online_acked=True;f.initialize()
        a=f.next_frame(s,1);self.assertEqual(candidate_header(a[14:])['command_field'],0)
        self.assertIsNone(f.next_frame(s,1.1))
        f.acknowledge({'command_field':160,'ack_candidate':s.sequence})
        self.assertIsNotNone(f.next_frame(s,1.2))
        self.assertIsNone(f.next_frame(s,3.3));self.assertIsNotNone(f.error)

    def test_motor_never_fights_touched_fader(self):
        m=SurfaceMap();f=SurfaceFeedback(m);s=Session('00:00:00:00:00:01','00:00:00:00:00:02')
        s.online_acked=True;f.active[1]=True;m.touched.add(1)
        f.put(('motor',1),motor(1,.5))
        self.assertIsNone(f.next_frame(s,1))
        m.touched.clear();m.fader_moved[1]=1
        self.assertIsNone(f.next_frame(s,1.1));self.assertIsNotNone(f.next_frame(s,1.4))


if __name__=='__main__':unittest.main()
