"""Regressions for startup pw-dump failures and accidental track disconnection."""
import json
import sys
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from pipewire_graph import read_graph, unused_meter_links


def meter_fixture():
    def obj(i, kind, **props):
        return dict(id=i, type='PipeWire:Interface:'+kind, info=dict(props=props))
    def link(i, source, dest):
        return dict(id=i, type='PipeWire:Interface:Link', info={
            'output-node-id':source, 'input-node-id':1,
            'output-port-id':source+100, 'input-port-id':dest})
    return [obj(1,'Node',**{'node.name':'ardour'}),
            obj(2,'Node',**{'node.name':'alsa_input.pci-internal'}),
            obj(3,'Node',**{'node.name':'alsa_input.usb-MPC'}),
            obj(4,'Port',**{'node.id':'1','port.name':'physical_audio_input_monitor_enable'}),
            obj(5,'Port',**{'node.id':'1','port.name':'Behringer stereo/audio_in 1'}),
            link(10,2,4),link(11,3,4),link(12,2,5),link(13,3,5)]


class GraphRead(unittest.TestCase):
    @patch('pipewire_graph.time.sleep')
    def test_extra_document_is_retried_not_silently_truncated(self, sleep):
        expected=meter_fixture()
        with patch('pipewire_graph.subprocess.check_output', side_effect=['[]\n[]',json.dumps(expected)]) as run:
            self.assertEqual(read_graph(),expected)
        self.assertEqual(run.call_count,2)
        self.assertEqual(run.call_args.args[0],['pw-dump','--no-colors'])
    @patch('pipewire_graph.time.sleep')
    def test_bad_graph_never_becomes_empty_success(self, sleep):
        for bad in ('{', '{}', '[null]', '[{"id":1,"type":"PipeWire:Interface:Node","info":null}]', '[{"id":1,"type":"PipeWire:Interface:Link","info":{}}]', '[{"id":1,"type":"x","info":4}]'):
            with patch('pipewire_graph.subprocess.check_output',return_value=bad) as run:
                with self.assertRaisesRegex(ValueError,'après 3 lectures'):read_graph()
                self.assertEqual(run.call_count,3)
    @patch('pipewire_graph.time.sleep')
    def test_timeout_then_valid_empty_graph(self, sleep):
        with patch('pipewire_graph.subprocess.check_output', side_effect=[subprocess.TimeoutExpired('pw-dump',4),'[]']):
            self.assertEqual(read_graph(),[])
    @patch('pipewire_graph.time.sleep')
    def test_metadata_without_info_is_normalized_for_graph_consumers(self, sleep):
        with patch('pipewire_graph.subprocess.check_output', return_value='[{"id":1,"type":"PipeWire:Interface:Metadata","info":null}]'):
            self.assertEqual(read_graph()[0]['info'], {})

    def test_only_internal_dummy_meter_link_is_selected(self):
        self.assertEqual(unused_meter_links(meter_fixture()),({4},{(102,4)}))
    def test_port_disappearance_leaves_no_disconnect_target(self):
        self.assertEqual(unused_meter_links([o for o in meter_fixture() if o['id']!=4]),(set(),set()))


if __name__ == '__main__':unittest.main()
