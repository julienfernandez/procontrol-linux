import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import studio_launcher as sl


class LauncherTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.binary=self.root/'bin/ardour9';self.binary.parent.mkdir();self.binary.touch()
        self.session=self.root/'studio';self.session.mkdir();self.project=self.session/'studio.ardour';self.project.touch()
        self.config=dict(session=str(self.session),ardour_launcher=str(self.binary),launch_link=True)
    def test_existing_ardour_is_focused_without_preparation_or_second_process(self):
        with patch.object(sl.subprocess,'run') as run,patch.object(sl,'running_ardour',return_value=[123]),patch.object(sl,'focus') as focus,patch.object(sl,'prepare_usb') as prepare,patch.object(sl.subprocess,'Popen') as spawn:
            self.assertEqual(sl.launch(self.config),'focused')
        focus.assert_called_once_with([123]);prepare.assert_not_called();spawn.assert_not_called()
        self.assertIn('desktop_launcher.py',run.call_args_list[0].args[0][1])
        self.assertEqual(run.call_args_list[1].args[0][-1],'start')
    def test_new_launch_prepares_via_gateway_and_preserves_argument(self):
        custom=self.root/'autre projet.ardour';custom.touch()
        sequence=[]
        with patch.object(sl.subprocess,'run',side_effect=lambda *a,**kw:sequence.append('gateway')),patch.object(sl,'running_ardour',return_value=[]),patch.object(sl,'notify'),patch.object(sl,'prepare_usb',side_effect=lambda:sequence.append('prepare') or True),patch.object(sl,'finish_routing') as route,patch.object(sl.subprocess,'Popen',return_value=Mock(poll=lambda:None)) as spawn:
            self.assertEqual(sl.launch({**self.config,'launch_link':False},str(custom)),'started')
        self.assertEqual(sequence,['gateway','prepare']);self.assertEqual(spawn.call_args.args[0],[str(self.binary),str(custom)])
        self.assertEqual(spawn.call_args.kwargs['env']['MPC_STUDIO_PREPARED'],'1');route.assert_not_called()
    def test_default_project_finishes_its_routing(self):
        with patch.object(sl.subprocess,'run'),patch.object(sl,'running_ardour',return_value=[]),patch.object(sl,'notify'),patch.object(sl,'prepare_usb',return_value=True),patch.object(sl,'finish_routing') as route,patch.object(sl.subprocess,'Popen',return_value=Mock(poll=lambda:None)) as spawn:
            self.assertEqual(sl.launch(self.config),'started')
        route.assert_called_once();self.assertEqual(spawn.call_args.args[0][1],str(self.project))
    def test_offline_mpc_still_opens_ardour_without_second_prepare(self):
        with patch.object(sl.subprocess,'run'),patch.object(sl,'running_ardour',return_value=[]),patch.object(sl,'notify'),patch.object(sl,'prepare_usb',return_value=False),patch.object(sl,'finish_routing') as route,patch.object(sl.subprocess,'Popen',return_value=Mock(poll=lambda:None)) as spawn:
            self.assertEqual(sl.launch(self.config),'started')
        route.assert_not_called();self.assertEqual(spawn.call_args.kwargs['env']['MPC_STUDIO_PREPARED'],'1')
    def test_busy_recovery_is_reused(self):
        busy={'job':{'state':'running'}}
        ready={'stale':False,'repair_needed':False,'graph':{'usb':True},'job':{'state':'succeeded'}}
        with patch.object(sl,'api',side_effect=[busy,ready]) as api,patch.object(sl.time,'sleep'):
            self.assertTrue(sl.prepare_usb())
        self.assertEqual([c.args for c in api.call_args_list],[(),()])
    def test_failed_recovery_does_not_repeat_forever(self):
        with patch.object(sl,'api',side_effect=[{'job':{}},{'job':{'state':'queued'}},{'job':{'state':'failed'}}]) as api,patch.object(sl.time,'sleep'):
            self.assertFalse(sl.prepare_usb())
        self.assertEqual(sum(c.args==('recover',) for c in api.call_args_list),1)
    def test_no_routing_for_another_session(self):
        state={'stale':False,'route_allowed':False,'graph':{'usb':True,'behringer':True},'repair_needed':False}
        with patch.object(sl,'api',return_value=state) as api,patch.object(sl.time,'monotonic',side_effect=[0,0,50]),patch.object(sl.time,'sleep'):
            sl.finish_routing(timeout=40)
        self.assertEqual([c.args for c in api.call_args_list],[()])
    def test_gateway_failure_does_not_open_unconfigured_ardour(self):
        with patch.object(sl.subprocess,'run',side_effect=sl.subprocess.CalledProcessError(1,'gateway')),patch.object(sl.subprocess,'Popen') as spawn:
            with self.assertRaises(sl.subprocess.CalledProcessError):sl.launch(self.config)
        spawn.assert_not_called()

if __name__=='__main__':unittest.main()
