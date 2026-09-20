"""Regression checks for the observed fallback-routing and reopen failures."""
import copy
from pathlib import Path
import runpy
import unittest
import os
import tempfile
from unittest.mock import patch

with tempfile.TemporaryDirectory() as data_dir:
    with patch.dict(os.environ, MPC_STUDIO_ROOT=data_dir, MPC_HOST='192.0.2.1', MPC_STUDIO_SESSION='/music/studio/studio.ardour'):
        MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'integrations/mpc_usb/studio.py'))
PLAN = MODULE['keepalive_link_plan']

def fixture(playback=True):
    nodes = [dict(id=i, type='PipeWire:Interface:Node', info={'props':{'node.name':n}})
             for i,n in [(1,'keepalive'),(2,'mpc'),(3,'behringer')]]
    ports=[]; links=[]
    for c in range(16):
        src,dst=(1,2) if playback else (2,1)
        ports.extend([
            dict(id=100+c,type='PipeWire:Interface:Port',info={'props':{'node.id':str(src),'audio.channel':'AUX%d'%c,'port.direction':'out'}}),
            dict(id=200+c,type='PipeWire:Interface:Port',info={'props':{'node.id':str(dst),'audio.channel':'AUX%d'%c,'port.direction':'in'}})])
        links.append(dict(id=300+c,type='PipeWire:Interface:Link',info={'output-node-id':src,'input-node-id':dst,'output-port-id':100+c,'input-port-id':200+c,'state':'active'}))
    return nodes+ports+links

class Lifecycle(unittest.TestCase):
    def test_duplex_complete(self):
        for playback in [True,False]:
            self.assertEqual(PLAN(fixture(playback),'keepalive','mpc',playback),(set(),set()))
    def test_alive_but_routed_to_stereo_fallback(self):
        graph=fixture()[:-16]
        for c in range(2):
            graph.append(dict(id=400+c,type='PipeWire:Interface:Link',info={'output-node-id':1,'input-node-id':3,'output-port-id':100+c,'input-port-id':500+c,'state':'active'}))
        missing,wrong=PLAN(graph,'keepalive','mpc',True)
        self.assertEqual(missing,{(100+c,200+c) for c in range(16)})
        self.assertEqual(wrong,{(100,500),(101,501)})
    def test_one_lost_link_and_unrelated_graph(self):
        graph=fixture()[:-1]
        graph.append(dict(id=700,type='PipeWire:Interface:Link',info={'output-node-id':3,'input-node-id':4,'output-port-id':500,'input-port-id':600,'state':'active'}))
        self.assertEqual(PLAN(graph,'keepalive','mpc',True),({(115,215)},set()))
    def test_inactive_link_is_not_success_or_wrong_destination(self):
        graph=fixture(False);graph[-1]['info']['state']='paused'
        self.assertEqual(PLAN(graph,'keepalive','mpc',False),({(115,215)},set()))
    def test_missing_device_is_not_success(self):
        graph=[o for o in fixture() if o['id']!=2]
        with self.assertRaises(RuntimeError):PLAN(graph,'keepalive','mpc',True)
    def test_output_already_tuned_is_not_reopened(self):
        func=MODULE['tune_output'];g=func.__globals__
        nodes=[dict(id=70,type='PipeWire:Interface:Node',info={'state':'running','props':{'node.name':'alsa_output.usb-Burr-Brown_from_TI_USB_Audio_CODEC-00.analog-stereo-output'},'params':{'Props':[{'params':['api.alsa.period-size',128,'api.alsa.headroom',512]}]}})]
        with patch.dict(g,{'graph':lambda:nodes,'command':lambda *a,**kw:self.fail('unchanged device was reopened')}):func()

if __name__=='__main__':unittest.main()
