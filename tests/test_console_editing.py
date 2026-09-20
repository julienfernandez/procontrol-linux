# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from jog_scheduler import JogScheduler


def press(m,z,n):
    result=m.command(bytes([0x90,n,z|64]),0)
    m.command(bytes([0x90,n,z]),0)
    return result


def names(result):
    return [a[2][0] for a in result if a[:2]==('osc','/access_action')]


class ConsoleEditingTests(unittest.TestCase):
    def test_editing_targets_main_editor_not_mouse_or_obsolete_osc_undo(self):
        m=SurfaceMap()
        for n,op in ((4,'cut'),(5,'copy'),(6,'paste'),(7,'delete')):
            a=names(press(m,0x1b,n))
            self.assertLess(a.index('Editor/edit-at-playhead'),a.index('EditorEditing/editor-'+op))
        self.assertEqual(names(press(m,0x19,6)),['EditorEditing/undo'])
        m.modifiers.add('Shift_L')
        self.assertEqual(names(press(m,0x19,6)),['EditorEditing/redo'])
        self.assertEqual(names(press(m,0x19,7)),['Common/Save'])

    def test_edit_pressed_once_across_release_retry_and_reconnect(self):
        m=SurfaceMap();c=bytes.fromhex('90 04 5b')
        self.assertTrue(m.route(1,c))
        self.assertEqual(m.route(1,c),[])
        self.assertEqual(m.route(2,c),[])
        self.assertEqual(m.route(3,bytes.fromhex('90 04 1b')),[])
        self.assertTrue(m.route(4,c))
        m.reset_inputs();self.assertTrue(m.route(1,c))

    def test_in_resets_old_endpoint_then_out_finishes_without_record_arm(self):
        m=SurfaceMap();a=names(press(m,0x1c,2))
        self.assertEqual(a[-2:],['Common/finish-range-from-playhead','Common/start-range-from-playhead'])
        self.assertEqual(names(press(m,0x1c,3))[-1],'Common/finish-range-from-playhead')
        for n in (2,3,9,10):
            self.assertFalse(any('rec_enable' in a[1] for a in press(m,0x1c,n)))

    def test_loop_uses_gui_order_and_feedback_for_second_press(self):
        m=SurfaceMap()
        self.assertEqual(names(press(m,0x1c,9))[-2:],['Editor/set-loop-from-edit-range','Transport/Loop'])
        m.feedback('/loop_toggle',[1.])
        self.assertEqual(names(press(m,0x1c,9)),['Transport/Loop'])
        m.feedback('/loop_toggle',[0.]);m.modifiers.add('Shift_L')
        self.assertEqual(names(press(m,0x1c,9)),['Transport/Loop'])

    def test_shift_moves_loop_bounds_control_preserves_punch_controls(self):
        m=SurfaceMap();m.modifiers.add('Shift_L')
        self.assertEqual(names(press(m,0x1c,2))[-2:],['Common/start-loop-range','Editor/select-loop-range'])
        self.assertEqual(names(press(m,0x1c,3))[-2:],['Common/finish-loop-range','Editor/select-loop-range'])
        m.modifiers={'Control_L'}
        self.assertEqual(press(m,0x1c,2),[('osc','/toggle_punch_in',[1.])])
        self.assertEqual(press(m,0x1c,3),[('osc','/toggle_punch_out',[1.])])

    def test_musical_jumps_fine_jog_and_scheduler_barrier(self):
        m=SurfaceMap();m.jog_gain=.2
        self.assertEqual(press(m,0x1c,4),[('osc','/jump_bars',[1.])])
        m.modifiers.add('Shift_L')
        self.assertEqual(press(m,0x1c,1),[('osc','/jump_bars',[-4.])])
        self.assertAlmostEqual(m.command(bytes.fromhex('b0 5c 41'),0)[0][2][0],.02)
        m.jog_mode=2
        self.assertAlmostEqual(m.command(bytes.fromhex('b0 5c 41'),0)[0][2][0],.2)
        q=JogScheduler();q.actions([('osc','/jog',[.2])],0)
        q.actions([('osc','/jog',[.3])],.001)
        a=q.actions(press(m,0x1c,2),.002)
        self.assertEqual(a[0],('osc','/jog',[.3]));self.assertEqual(q.pending,0.)

    def test_nudge_preserves_banking_and_plugin_browser(self):
        m=SurfaceMap()
        self.assertEqual(press(m,0x1b,10),[('bank','delta',[-1])])
        press(m,0x1b,11)
        self.assertEqual(names(press(m,0x1b,12))[-1],'Editor/nudge-forward')
        m.eq=SimpleNamespace(active=True,command=lambda c:[('eq','bank',[1])])
        self.assertEqual(m.command(bytes.fromhex('90 0c 5b'),0),[('eq','bank',[1])])

    def test_editor_button_exits_plugin_and_monitor_views(self):
        m=SurfaceMap()
        m.eq=SimpleNamespace(active=True,exit=Mock())
        m.monitor=SimpleNamespace(active=True,exit=Mock())
        self.assertEqual(names(press(m,0x19,1)),['Common/show-editor','Editor/edit-at-playhead'])
        m.eq.exit.assert_called_once();m.monitor.exit.assert_called_once()

    def test_region_selection_repeat_align_and_grid(self):
        m=SurfaceMap()
        self.assertIn('Editor/select-all-between-cursors',names(press(m,0x1b,15)))
        self.assertIn('Region/align-regions-start-relative',names(press(m,0x1b,2)))
        self.assertIn('EditorSnap/grid-type-bar',names(press(m,0x1b,3)))
        m.modifiers={'Shift_L'}
        self.assertIn('Region/align-regions-end-relative',names(press(m,0x1b,2)))
        self.assertIn('Editor/duplicate',names(press(m,0x1b,5)))
        self.assertIn('EditorSnap/grid-type-beat',names(press(m,0x1b,3)))
        m.modifiers={'Alt_L'}
        self.assertIn('EditorEditing/snap-off',names(press(m,0x1b,3)))

    def test_unknown_navigation_is_not_guessed(self):
        m=SurfaceMap()
        self.assertIsNone(m.command(bytes.fromhex('90 00 58'),0))


if __name__=='__main__':unittest.main()
