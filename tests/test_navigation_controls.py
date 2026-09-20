# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from navigation_controls import navigation_button
from procontrol_mapping import decode_command
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback,button_led


class NavigationTests(unittest.TestCase):
    def test_captured_three_press_sequence_decodes_without_fictitious_track_25(self):
        capture=json.loads((Path(__file__).resolve().parents[1]/'docs/navigation-buttons-confirmed.json').read_text())
        labels=[]
        for event in capture['events']:
            command=bytes.fromhex(event['hex'])
            physical=navigation_button(command)
            decoded=decode_command(command)
            self.assertEqual(decoded['status'],'mapped_local')
            self.assertNotIn('track',decoded)
            self.assertEqual(physical['pressed'],event['pressed'])
            if physical['pressed']:labels.append(physical['label'])
        self.assertEqual(labels,capture['user_confirmed_order'])
        self.assertIsNone(navigation_button(bytes.fromhex('90 05 58')))
        self.assertNotIn('track',decode_command(bytes.fromhex('90 05 58')))

    def test_select_zoom_shortcuts_and_reset_keep_modes_consistent(self):
        m=SurfaceMap(); f=SurfaceFeedback(m);seq=0
        def press(n):
            nonlocal seq
            seq+=1;result=m.route(seq,bytes([0x90,n,0x58]))
            seq+=1;m.route(seq,bytes([0x90,n,0x18]))
            for a in result:f.local(a)
            return result
        self.assertEqual(press(0)[-1],('osc','/select/previous',[1.]))
        self.assertEqual(press(4)[-1],('osc','/select/next',[1.]))
        self.assertEqual(press(1)[-1][2],['Editor/playhead-to-previous-region-boundary'])
        self.assertEqual(press(3)[-1][2],['Editor/playhead-to-next-region-boundary'])
        self.assertEqual(press(2),[('led','24:2',[1])])
        for n,action in ((0,'Editor/expand-tracks'),(4,'Editor/shrink-tracks'),
                         (1,'EditorEditing/temporal-zoom-out'),(3,'EditorEditing/temporal-zoom-in')):
            self.assertEqual(press(n)[-1][2],[action])
        m.modifiers.add('Shift_L');self.assertEqual(press(2)[-1][2],['Editor/zoom-to-selection'])
        self.assertTrue(m.editing.zoom_navigation)
        m.modifiers.clear();m.modifiers.add('Alt_L')
        self.assertEqual(press(2)[-1][2],['Editor/zoom-to-session'])
        m.reset_inputs();f.resync()
        self.assertFalse(m.editing.zoom_navigation)
        self.assertEqual(f.desired['led',24,2],button_led(24,2,False))

    def test_holding_or_retransmitting_center_does_not_cycle_mode(self):
        m=SurfaceMap();c=bytes.fromhex('90 02 58')
        self.assertEqual(m.route(1,c),[('led','24:2',[1])])
        self.assertEqual(m.route(1,c),[]);self.assertEqual(m.route(2,c),[])
        self.assertTrue(m.editing.zoom_navigation)
        m.route(3,bytes.fromhex('90 02 18'))
        self.assertEqual(m.route(4,c),[('led','24:2',[0])])


if __name__=='__main__':unittest.main()
