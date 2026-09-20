"""Recovery contracts: actual links, stale state, serialized writes, shutdown."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from studio_control import StudioBackend, StudioController, graph_health, pcm_info, write_json


def graph_fixture():
    objects=[]
    def node(i,name):
        objects.append(dict(id=i,type='PipeWire:Interface:Node',info={'props':{'node.name':name}}))
    def port(i,node,ch,direction,alias=''):
        objects.append(dict(id=i,type='PipeWire:Interface:Port',info={'props':{'node.id':str(node),'audio.channel':ch,'port.direction':direction,'port.alias':alias}}))
    def link(i,s,d,a,b):
        objects.append(dict(id=i,type='PipeWire:Interface:Link',info={'output-node-id':s,'input-node-id':d,'output-port-id':a,'input-port-id':b,'state':'active'}))
    for i,n in [(1,'alsa_input.usb-Akai_Professional_MPC_One_USB_Audio_16ch_test'),(2,'alsa_output.usb-Akai_Professional_MPC_One_USB_Audio_16ch_test'),(3,'codex-mpc-usb-silence-v3'),(4,'codex-mpc-usb-capture-keepalive-v3'),(5,'ardour'),(6,'alsa_output.usb-Burr-Brown_from_TI_USB_Audio_CODEC-test')]:node(i,n)
    for i in range(16):
        for base,n,d in [(100,1,'out'),(200,2,'in'),(300,3,'out'),(400,4,'in')]:port(base+i,n,f'AUX{i}',d)
        port(500+i,5,'', 'in',f'ardour:MPC {i//2*2+1:02d}-{i//2*2+2:02d}/audio_in {i%2+1}')
        link(1000+i,3,2,300+i,200+i);link(1100+i,1,4,100+i,400+i);link(1200+i,1,5,100+i,500+i)
    for i,ch in enumerate(('FL','FR')):
        port(600+i,5,ch,'out',f'ardour:Master/audio_out {i+1}');port(700+i,6,ch,'in');link(1300+i,5,6,600+i,700+i)
    return objects


REMOTE={'boot':'first-boot','mpc_pid':'304','gadget':'ff580000.usb','usb_state':'configured','visibility':'XAC2_Gadget',
        'playback':'closed\nclosed','capture':'closed\nclosed',
        'midi':"client 16: 'MPC One MIDI'\n    2 'MPC Studio Live MIDI Port'\n\tConnecting To: 129:0, 28:1\nclient 28: 'f_midi'\n"}


class GraphTests(unittest.TestCase):
    def test_all_real_pairs(self):
        s=graph_health(graph_fixture())
        self.assertTrue(s['usb']);self.assertEqual(s['tracks'],16);self.assertEqual(s['master'],2)
        self.assertEqual(s['keepalive']['playback']['channels'],16)
    def test_process_alive_but_wrong_target(self):
        g=graph_fixture()
        l=next(o for o in g if o['id']==1000);l['info']['input-node-id']=6
        s=graph_health(g)['keepalive']['playback']
        self.assertTrue(s['present']);self.assertEqual(s['channels'],15);self.assertEqual(s['wrong'],1)
    def test_paused_is_not_live_keepalive(self):
        g=graph_fixture();next(o for o in g if o['id']==1100)['info']['state']='paused'
        self.assertEqual(graph_health(g)['keepalive']['capture']['channels'],15)
    def test_missing_device_and_swapped_channels(self):
        g=[o for o in graph_fixture() if o['id']!=1]
        self.assertFalse(graph_health(g)['usb'])
        g=graph_fixture();next(o for o in g if o['id']==1300)['info']['input-port-id']=701
        s=graph_health(g);self.assertEqual(s['master'],1);self.assertEqual(s['master_other'],1)


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=self.root/'data';self.data.mkdir()
        p=self.root/'integrations/mpc_usb/studio.py';p.parent.mkdir(parents=True);p.write_text('')
        write_json(self.root/'studio.json',dict(data_root=str(self.data),host='192.0.2.1',session='/music/studio',automatic=False))
        self.c=StudioController(self.root)
    def fresh_session(self,name='/music/studio'):
        write_json(self.root/'run/status.json',dict(running=True,ardour='responding',stereo={'session':name}))
    def snapshot(self,remote=REMOTE):
        with patch.object(self.c.backend,'remote',return_value=remote),patch('studio_control.subprocess.check_output',return_value=json.dumps(graph_fixture())):
            return self.c.backend.snapshot()
    def test_pcm_closed_is_not_ready_and_does_not_trigger_reprepare(self):
        s=self.snapshot();self.assertFalse(s['pcm_running']);self.assertFalse(s['repair_needed'])
        self.assertEqual(next(x for x in s['components'] if x['key']=='pcm')['state'],'warning')
    def test_only_mpc_owned_pcm_proves_application_selected(self):
        pcm='state: RUNNING\nowner_pid   : 999\nperiod_size: 128\nbuffer_size: 768'
        self.assertFalse(self.snapshot({**REMOTE,'playback':pcm,'capture':pcm})['pcm_running'])
        pcm=pcm.replace('999','304')
        self.assertTrue(self.snapshot({**REMOTE,'playback':pcm,'capture':pcm})['pcm_running'])
    def test_bound_gadget_without_cable_is_not_connected(self):
        s=self.snapshot({**REMOTE,'usb_state':'not attached'})
        self.assertEqual(next(c for c in s['components'] if c['key']=='gadget')['state'],'warning')
    def test_unreachable_mpc_does_not_repair_or_reuse_old_pcm(self):
        with patch.object(self.c.backend,'remote',side_effect=subprocess.TimeoutExpired('ssh',12)),patch('studio_control.subprocess.check_output',return_value=json.dumps(graph_fixture())):
            s=self.c.backend.snapshot()
        self.assertFalse(s['repair_needed']);self.assertEqual(s['remote'],{});self.assertNotIn('pcm_running',s)
    def test_route_rejects_wrong_session_and_stale_file(self):
        self.fresh_session('/music/other')
        with self.assertRaises(ValueError):self.c.request({'action':'route'})
        self.fresh_session();self.assertTrue(self.c.backend.route_allowed())
        p=self.root/'run/status.json';os.utime(p,(time.time()-10,)*2)
        self.assertFalse(self.c.backend.route_allowed())
    def test_no_arbitrary_command_or_path(self):
        for payload in ({'action':'stop'},{'action':'recover','command':'echo x'},{'action':'automatic','enabled':1}):
            with self.assertRaises(ValueError):self.c.request(payload)
    def test_duplicate_requests_and_followup_verification(self):
        self.fresh_session();self.c.request({'action':'recover'})
        with self.assertRaises(ValueError):self.c.request({'action':'recover'})
        calls=[]
        with patch.object(self.c,'run_command',side_effect=lambda a:calls.append(a)),patch.object(self.c.backend,'snapshot',return_value=self.snapshot()):self.c.tick()
        self.assertEqual(calls,['prepare','route']);self.assertEqual(self.c.job['state'],'succeeded');self.assertFalse(self.c.state()['stale'])
    def test_session_change_during_prepare_does_not_route(self):
        self.fresh_session();self.c.request({'action':'recover'})
        calls=[]
        def run(a):calls.append(a);self.fresh_session('/music/another')
        with patch.object(self.c,'run_command',side_effect=run),patch.object(self.c.backend,'snapshot',return_value=self.snapshot()):self.c.tick()
        self.assertEqual(calls,['prepare'])
    def test_failure_cooldown_and_auto_after_reboot(self):
        self.c.config['automatic']=True
        s=self.snapshot({**REMOTE,'gadget':'','visibility':''})
        with patch.object(self.c.backend,'snapshot',return_value=s),patch.object(self.c,'run_command',side_effect=RuntimeError('offline')) as run:
            self.c.tick();self.assertEqual(self.c.job['state'],'queued')
            self.c.tick();self.assertEqual(self.c.job['state'],'failed');self.assertGreater(self.c.next_retry,time.time())
            for _ in range(3):self.c.tick()
            self.assertEqual(run.call_count,1)
    def test_restarts_observed_without_repair(self):
        def snap(trigger,boot='first-boot'):
            pcm=f'state: RUNNING\nowner_pid   : 304\ntrigger_time: {trigger}\nperiod_size: 128\nbuffer_size: 768'
            return self.snapshot({**REMOTE,'boot':boot,'playback':pcm,'capture':pcm})
        for trigger,boot,expected in [('1','first-boot',0),('2','first-boot',1),('3','reboot',0)]:
            with patch.object(self.c.backend,'snapshot',return_value=snap(trigger,boot)):self.c.tick()
            self.assertEqual(self.c.state()['pcm_restarts'],expected);self.assertIsNone(self.c.pending)
    def test_shutdown_terminates_job_process_group(self):
        p=self.c.backend.path
        pidfile=self.data/'child.pid'
        p.write_text("import subprocess,time,os\nfrom pathlib import Path\np=subprocess.Popen(['sleep','100'])\nPath('child.pid').write_text(str(p.pid))\ntime.sleep(100)\n")
        errors=[]
        def run():
            try:self.c.run_command('prepare')
            except RuntimeError as e:errors.append(str(e))
        (self.root/'run').mkdir(exist_ok=True)
        t=threading.Thread(target=run);t.start()
        try:
            deadline=time.monotonic()+3
            while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(pidfile.exists());child=int(pidfile.read_text())
            self.c.stopping.set();t.join(4);self.assertFalse(t.is_alive());self.assertTrue(errors)
            stat=Path(f'/proc/{child}/stat')
            self.assertTrue(not stat.exists() or stat.read_text().split()[2]=='Z')
        finally:
            self.c.stopping.set();t.join(4)
    def test_busy_rejected_during_worker_claim(self):
        self.c.request({'action':'recover'})
        def operation(a):
            with self.assertRaises(ValueError):self.c.request({'action':'route'})
        with patch.object(self.c,'operate',side_effect=operation),patch.object(self.c.backend,'snapshot',return_value=self.snapshot()):self.c.tick()
    def test_logs_are_bounded_and_stale_means_unknown(self):
        self.c.log_path.parent.mkdir(exist_ok=True);self.c.log_path.write_text('a'*50000)
        self.assertEqual(len(self.c.logs()['supervision']),16000)
        self.c.current['checked_at']=time.time()-31
        self.assertTrue(self.c.state()['stale'])


class ApiTests(unittest.TestCase):
    def test_local_api_security_and_diagnostics(self):
        import urllib.request
        import urllib.error
        from settings_web import serve
        with tempfile.TemporaryDirectory() as temp:
            server=serve(Path(temp),0)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            base='http://127.0.0.1:'+str(server.server_port)
            try:
                state=json.load(urllib.request.urlopen(base+'/api/studio'))
                self.assertFalse(state['configured']);self.assertTrue(state['stale'])
                self.assertIn('supervision',json.load(urllib.request.urlopen(base+'/api/studio/logs')))
                def post(body,origin):
                    return urllib.request.urlopen(urllib.request.Request(base+'/api/studio/action',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':origin}))
                with self.assertRaises(urllib.error.HTTPError) as e:post({'action':'recover'},'https://outside.example')
                self.assertEqual(e.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError) as e:post({'action':'exec','cmd':'true'},base)
                self.assertEqual(e.exception.code,400)
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+'/api/studio/logs/../../settings.json')
                self.assertEqual(e.exception.code,404)
            finally:
                server.shutdown();server.server_close();worker.join()


if __name__=='__main__':unittest.main()
