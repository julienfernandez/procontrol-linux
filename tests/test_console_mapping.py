# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise mapping isolation and persistence without hardware or OSC output."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from console_layout import layout, elements, button_id
from console_presets import PresetStore, validate_preset, validate_protocol
from console_mapping import MappingRuntime, suspend_plugin_window
from mapping_inventory import mapper_for, MODES
from surface_feedback import SurfaceFeedback, button_led, motor, meter, scribble
from surface_routing import SurfaceRouting
from console_indicators import ConsoleIndicators
from pointer_x11 import FreshPointer
from datetime import datetime, timezone


class LayoutTests(unittest.TestCase):
    def test_reference_coverage_and_unique_physical_ids(self):
        m=layout();ids=elements();self.assertEqual(len(m['elements']),len(ids))
        from procontrol_mapping import mapping_tree
        groups=[(z,mapping_tree()[0x90]['Children'][0]['Children']) for z in range(8)]
        groups += [(z,g['Children']) for z,g in mapping_tree()[0x90]['Children'][8]['Children'].items()]
        for z,keys in groups:
            for k in keys:self.assertIn(button_id(z,k),set(ids))
        for n in range(1,9):
            self.assertIn(f'dsp.{n}.encoder',ids)
            self.assertEqual(ids[f'dsp.{n}.display']['output']['address'],44+n)
            for k in range(3):self.assertIn(button_id(12+n,k),ids)
        self.assertEqual(sum(x['id'].startswith('master.meter.') for x in ids.values()),6)
        for n in range(1,7):self.assertIsNone(ids[f'master.meter.{n}']['output'])
        self.assertEqual(ids['button.18.00']['validation']['input'],'confirmed')
        self.assertEqual(ids['button.18.00']['validation']['function'],'unknown')
        for i in m['elements']:
            x,y,w,h=i['box'];self.assertGreater(w,0);self.assertGreater(h,0)
            self.assertLessEqual(x+w,1440);self.assertLessEqual(y+h,1024)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.store=PresetStore(self.temp.name)
    def op(self,action,**kw):return self.store.mutate(dict(action=action,revision=self.store.read()['revision'],**kw))
    def test_protected_duplicate_edit_activate_rollback_and_restart(self):
        with self.assertRaises(ValueError):self.op('save',preset='ardour-current',data={})
        s=self.op('duplicate',preset='ardour-current');id=next(iter(s['presets']))
        p=s['presets'][id];p['bindings']['button.1c.10']={'normal':{'kind':'disabled'}}
        self.op('save',preset=id,data=p)
        self.assertEqual(self.store.read()['active']['bindings'],{})
        self.op('activate',preset=id);self.assertIn('button.1c.10',self.store.read()['active']['bindings'])
        self.assertEqual(PresetStore(self.temp.name).read(),self.store.read())
        self.op('rollback');self.assertEqual(self.store.read()['active']['bindings'],{})
    def test_concurrent_revision_rejected_and_file_unchanged(self):
        self.op('duplicate');before=self.store.path.read_bytes()
        with self.assertRaises(ValueError):self.store.mutate(dict(action='duplicate',revision=0))
        self.assertEqual(self.store.path.read_bytes(),before)
    def test_import_is_draft_logic_is_inactive_and_validation_is_separate(self):
        s=self.op('import',data={'version':1,'preset':{'name':'Test','adapter':'ardour','bindings':{}}})
        self.assertEqual(s['active']['preset'],'ardour-current')
        before=set(s['presets']);s=self.op('logic');id=(set(s['presets'])-before).pop()
        with self.assertRaises(ValueError):self.op('activate',preset=id)
        with self.assertRaises(ValueError):self.op('validation',element='clock',dimension='output',level='confirmed')
        self.op('validation',element='clock',dimension='output',level='confirmed',confirmed=True,note='Vu sur la console')
        self.assertEqual(self.store.read()['validations']['clock']['output']['level'],'confirmed')
        self.assertNotIn('function',self.store.read()['validations']['clock'])
    def test_conflicting_protocol_and_motor_remap_rejected(self):
        with self.assertRaises(ValueError):validate_protocol({'button.1c.10':{'input':dict(family='button',zone=28,key=15)}})
        with self.assertRaises(ValueError):validate_protocol({'strip.1.fader':{'output':dict(family='motor',channel=2)}})
        validate_protocol({'master.meter.1':{'output':dict(family='meter',address=10)}})
    def test_expert_validation_blocks_invalid_types_addresses_and_nonfinite(self):
        base={'name':'Test','adapter':'ardour','bindings':{'button.1c.10':{'normal':dict(kind='osc',path='/transport_play',trigger='press',args=[{'type':'i','value':1}])}}}
        validate_preset(base)
        for path in ('http://host','/set_surface','/refresh','/strip/list','/foo *'):
            p=copy.deepcopy(base);p['bindings']['button.1c.10']['normal']['path']=path
            with self.assertRaises(ValueError):validate_preset(p)
        p=copy.deepcopy(base);p['bindings']['button.1c.10']['normal']['args']=[dict(type='f',value=float('nan'))]
        with self.assertRaises(ValueError):validate_preset(p)
    def test_function_confirmation_is_scoped_to_preset_context_and_revision(self):
        s=self.op('duplicate');id=next(iter(s['presets']))
        self.op('validation',element='button.1c.10',dimension='function',level='confirmed',confirmed=True,preset=id,mode='normal')
        saved=self.store.read();record=saved['validations']['button.1c.10']['functions'][id]['normal']
        self.assertEqual(record['preset_revision'],1)
        self.assertNotIn('modifier',saved['validations']['button.1c.10']['functions'][id])
        self.op('save',preset=id,data=saved['presets'][id])
        self.assertNotEqual(record['preset_revision'],self.store.read()['presets'][id]['revision'])

    def test_position_bounded(self):
        self.op('position',element='clock',box=[790,56,218,55])
        with self.assertRaises(ValueError):self.op('position',element='clock',box=[1400,900,200,55])


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=100.;self.mapper=mapper_for('normal');self.feedback=self.mapper.eq.feedback
        self.routing=self.mapper.eq.routing;self.indicators=ConsoleIndicators(self.mapper,self.feedback,lambda:self.now)
        self.reset=Mock();self.guard=Mock()
        self.runtime=MappingRuntime(self.temp.name,self.mapper,self.feedback,self.routing,self.indicators,self.reset,self.guard,lambda:self.now)
        self.runtime.online=True;self.refresh_transport()
    def refresh_transport(self,speed=0,record=0):
        self.runtime.feed('/transport_speed',[speed],self.now)
        self.indicators.feed('/procontrol/transport/state',[1,0,0,0,0,record,0],self.now)
    def start(self):return self.runtime.request(dict(action='learn_start',seconds=60))['token']
    def test_dsp_window_suspend_preserves_native_show_clear_negotiation(self):
        from plugin_window import PluginWindowFollower
        f=PluginWindowFollower();f.feed('/procontrol/plugin_ui/version',[1]);f.target=('session','174',1,'EQ')
        self.assertEqual(suspend_plugin_window(f),[('osc','/procontrol/plugin_ui/clear',[])])
        self.assertTrue(f.supported);self.assertIsNone(f.target)
        editor=SimpleNamespace(active=True,mode='eq',error=None,usable=lambda:True,valid_target=lambda:True,sid=1,plugin=1,plugin_name='EQ')
        routing=SimpleNamespace(ready=True,identities={1:'174'},session='session')
        self.assertEqual(f.update(editor,routing,100),[('osc','/procontrol/plugin_ui/show',['session','174',1,'EQ'])])

    def test_builtin_exact_parity_all_inventory_modes(self):
        rows=json.loads((Path(__file__).resolve().parents[1]/'docs/mapping-coverage.json').read_text())
        for mode in MODES:
            for row in rows:
                left=mapper_for(mode);right=mapper_for(mode)
                r=MappingRuntime(self.temp.name,right,right.eq.feedback,right.eq.routing,self.indicators,clock=lambda:100.)
                c=bytes([0x90,row['button'],row['zone']|64])
                self.assertEqual(left.route(1,c,100.),r.route(1,c,100.),(mode,row['label']))
                self.assertEqual(left.alpha,right.alpha)
                self.assertEqual(left.route(2,bytes([0x90,row['button'],row['zone']]),100.1),r.route(2,bytes([0x90,row['button'],row['zone']]),100.1))
    def test_learning_isolation_duplicates_capture_and_held_release(self):
        token=self.start();self.guard.assert_called_once_with(True)
        for seq,body in enumerate([bytes.fromhex('90 10 5c'),motor(1,.42),bytes.fromhex('b0 5c 45'),bytes.fromhex('f0 13 00 60 01 20 0a 00 f7')]):
            self.assertEqual(self.runtime.route(seq,body),[])
            self.assertEqual(self.runtime.route(seq,body),[])
        self.assertEqual(self.runtime.counters['duplicates'],4)
        self.assertEqual(len(self.runtime.candidates),5)
        self.assertTrue(self.runtime.suppress_pointer())
        self.runtime.request(dict(action='learn_stop',token=token))
        self.assertEqual(self.runtime.route(5,bytes.fromhex('90 10 5c')),[]) # still held
        self.assertEqual(self.runtime.route(6,bytes.fromhex('90 10 1c')),[]) # release, no replay
        self.assertTrue(self.runtime.route(7,bytes.fromhex('90 10 5c')))
    def test_gate_unknown_stale_playing_recording(self):
        for speed,record in [(1,0),(0,1),(0,2)]:
            self.refresh_transport(speed,record)
            with self.assertRaises(ValueError):self.start()
        self.refresh_transport();self.now+=3
        with self.assertRaises(ValueError):self.start()
        self.refresh_transport();self.runtime.online=False
        with self.assertRaises(ValueError):self.start()
    def test_lease_timeout_reconnect_and_owner(self):
        token=self.start()
        with self.assertRaises(ValueError):self.runtime.request(dict(action='learn_heartbeat',token='wrong'))
        self.now+=8;self.refresh_transport();self.runtime.tick(self.now,True)
        self.assertIsNone(self.runtime.learning);self.assertIn('déconnectée',self.runtime.last_learning)
        self.start();self.runtime.reconnect();self.assertIsNone(self.runtime.learning)
        self.start();self.now+=61;self.runtime.tick(self.now,True);self.assertIsNone(self.runtime.learning)
    def test_transport_change_cancels_and_pointer_ack_failure_prevents_capture(self):
        self.guard.side_effect=OSError('absent')
        with self.assertRaises(OSError):self.start()
        self.assertIsNone(self.runtime.learning)
        self.guard.side_effect=None;self.start();self.refresh_transport(1);self.runtime.tick(self.now,True)
        self.assertIsNone(self.runtime.learning)
    def test_fader_capture_extremes_and_explicit_association(self):
        token=self.start()
        for seq,v in enumerate([.1,.9,.3]):self.runtime.route(seq,motor(1,v))
        c=list(self.runtime.candidates.values())[0]
        self.assertEqual(c['min'],102);self.assertEqual(c['max'],921)
        with self.assertRaises(ValueError):self.runtime.request(dict(action='associate',token=token,element='strip.1.fader',candidate_id=c['candidate_id'],revision=0,confirmed=False))
        self.runtime.request(dict(action='associate',token=token,element='strip.1.fader',candidate_id=c['candidate_id'],revision=0,confirmed=True))
        self.assertEqual(self.runtime.config['protocol'],{}) # saved calibration is not active yet
    def test_custom_button_modes_pair_release_and_typed_osc(self):
        self.runtime.config['bindings']={'button.1c.10':{'normal':dict(kind='osc',path='/custom',trigger='both',args=[dict(type='f',source='pressed'),dict(type='s',value='ok')]),'modifier':{'kind':'disabled'}}}
        self.assertEqual(self.runtime.route(1,bytes.fromhex('90 10 5c')),[('direct_osc','/custom',[1.,'ok'])])
        self.mapper.modifiers.add('Shift_L')
        self.assertEqual(self.runtime.route(2,bytes.fromhex('90 10 1c')),[('direct_osc','/custom',[0.,'ok'])])
    def test_guided_dsp_uses_existing_mode_handler(self):
        self.runtime.config['bindings']={'button.1c.10':{'normal':dict(kind='guided',action='eq')}}
        self.assertEqual(self.runtime.route(1,bytes.fromhex('90 10 5c')),[('eq','enter',[1])])
    def test_probe_restores_latest_feedback_not_old_value(self):
        key=('led',28,16);self.feedback.put(key,button_led(28,16,False))
        self.runtime.start_probe(dict(element='button.1c.10'))
        self.feedback.put(key,button_led(28,16,True))
        self.now+=3;self.runtime.tick(self.now,True)
        self.assertEqual(self.feedback.queue[key],button_led(28,16,True))
        self.feedback.put(key,button_led(28,16,False))
        self.assertEqual(self.feedback.queue[key],button_led(28,16,False))
    def test_output_remap_and_unknown_meter_restore(self):
        self.runtime.config['protocol']={'master.meter.1':{'output':dict(family='meter',address=10)}}
        self.runtime.start_probe(dict(element='master.meter.1'))
        self.assertEqual(self.feedback.queue[('meter',10)],meter(10,-13))
        self.runtime.cancel_probe();self.assertEqual(self.feedback.queue[('meter',10)],meter(10,-193))
    def test_motor_guard_bounded_travel_touch_and_stale_position(self):
        with self.assertRaises(ValueError):self.runtime.start_probe(dict(element='strip.1.fader',motor_confirmed=True))
        self.feedback.active[1]=True;self.feedback.put(('motor',1),motor(1,.4))
        with self.assertRaises(ValueError):self.runtime.start_probe(dict(element='strip.1.fader',motor_confirmed=True,delta=.5))
        self.runtime.start_probe(dict(element='strip.1.fader',motor_confirmed=True))
        self.mapper.touched.add(1);self.runtime.tick(self.now,True)
        self.assertIsNone(self.runtime.probe);self.assertNotIn(('motor',1),self.feedback.queue)
        self.mapper.touched.clear();self.start();self.assertTrue(self.feedback.motor_blocked(('motor',1),self.now))
    def test_remapped_input_disables_old_address_and_pointer_clicks_are_editable(self):
        self.runtime.config['protocol']={'button.1c.10':{'input':dict(family='button',zone=12,key=50)}}
        self.runtime.build_indexes()
        self.assertEqual(self.runtime.route(1,bytes.fromhex('90 10 5c')),[])
        self.assertTrue(self.runtime.route(2,bytes.fromhex('90 32 4c')))
        self.runtime.config['bindings']={'pointer.left':{'normal':dict(kind='guided',action='eq')}}
        self.assertEqual(self.runtime.route(3,bytes.fromhex('f0 13 00 60 01 20 00 00 f7')),[('eq','enter',[1])])
        self.assertEqual(self.runtime.route(4,bytes.fromhex('f0 13 00 60 01 00 00 00 f7')),[])
    def test_unknown_meter_column_acquires_live_state_after_calibration(self):
        self.runtime.config['protocol']={'master.meter.1':{'output':dict(family='meter',address=10)}}
        self.runtime.build_indexes();self.feedback.meter_address(10,-13)
        self.assertGreater(self.runtime.outputs['master.meter.1']['value'],0)
    def test_apply_preparation_failure_does_not_commit_active_preset(self):
        s=self.runtime.store.mutate(dict(action='duplicate',revision=0));id=next(iter(s['presets']))
        self.reset.side_effect=OSError('OSC down')
        with self.assertRaises(OSError):self.runtime.request(dict(action='activate',preset=id,revision=1))
        self.assertEqual(self.runtime.store.read()['active']['preset'],'ardour-current')
        self.assertEqual(self.runtime.config['preset'],'ardour-current')
    def test_expert_selected_uses_known_single_route_only(self):
        self.runtime.config['bindings']={'button.1c.10':{'normal':dict(kind='osc',path='/strip/mute',trigger='press',args=[dict(type='i',source='selected'),dict(type='i',value=1)])}}
        self.assertEqual(self.runtime.route(1,bytes.fromhex('90 10 5c')),[])
        self.routing.rows={17:{}};self.routing.cache[('/strip/select',17)]=[17,1]
        self.assertEqual(self.runtime.route(2,bytes.fromhex('90 10 5c')),[('direct_osc','/strip/mute',[17,1])])

    def test_snapshot_bounded_coalesces_continuous_and_reports_gap(self):
        for i in range(600):self.runtime.route(i,bytes([0xb0,0x5c,65]))
        self.assertLess(len(self.runtime.events),10);self.assertEqual(self.runtime.counters['coalesced'],600)
        for i in range(200):self.runtime.route(i,bytes([0x90,16,28|(64 if i%2 else 0)]))
        data=self.runtime.snapshot(1);self.assertTrue(data['gap']);self.assertLess(len(json.dumps(data).encode()),65535)
    def test_fresh_pointer_rejects_isolated_packet(self):
        now=100.;parser=FreshPointer(.58);h=dict(event='ethernet_rx',utc=datetime.fromtimestamp(now,timezone.utc).isoformat(),command_field=0,body_sum16_match=True,sequence_candidate=1,body_hex='f0 13 00 60 01 00 0a 00 f7',mapping_suppressed=True)
        parser.feed(h,now);self.assertIsNone(parser.feed(dict(event='controls'),now))


if __name__=='__main__':unittest.main()
