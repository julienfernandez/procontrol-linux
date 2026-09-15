import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from plugin_window import PluginWindowFollower, PREFIX


class PluginWindowTests(unittest.TestCase):
    def setUp(self):
        self.ui = PluginWindowFollower()
        self.e = SimpleNamespace(active=True, ready=True, mode='eq', error=None,
                                 sid=1, plugin=1, plugin_name='EQ')
        self.e.usable = lambda: self.e.ready
        self.e.valid_target = lambda: True
        self.r = SimpleNamespace(ready=True, session='/music/session', identities={1:'174',2:'265'})
        self.ui.feed(PREFIX+'version',[1])

    def update(self,now=100):
        return self.ui.update(self.e,self.r,now)

    def confirm(self):
        self.ui.feed(PREFIX+'result',list(self.ui.target)+[1])

    def test_opens_once_no_polling_reopen_or_audio_writes(self):
        self.assertEqual(self.update(), [('osc',PREFIX+'show',['/music/session','174',1,'EQ'])])
        self.confirm()
        for now in (100.5,101,102,110): self.assertEqual(self.update(now),[])

    def test_track_and_plugin_change_replace_target(self):
        self.update();self.confirm();self.e.sid=2
        self.assertEqual(self.update()[0][2][1],'265')
        self.confirm(); self.e.plugin=2;self.e.plugin_name='Compressor'
        self.assertEqual(self.update()[0][2][2:],[2,'Compressor'])

    def test_snapshot_keeps_window_until_ready(self):
        self.update();self.confirm();self.r.ready=False;self.e.ready=False
        self.assertEqual(self.update(110),[])
        self.r.ready=True;self.e.ready=True
        self.assertEqual(self.update(111),[])

    def test_next_track_waits_for_valid_descriptors(self):
        self.update();self.confirm();self.e.sid=2;self.e.ready=False
        self.assertEqual(self.update(),[])
        self.e.ready=True
        self.assertEqual(self.update()[0][2][1],'265')

    def test_browser_and_escape_clear_only_once(self):
        self.update();self.confirm();self.e.mode='browse'
        self.assertEqual(self.update(),[('osc',PREFIX+'clear',[])])
        self.assertEqual(self.update(),[])
        self.e.mode='params';self.update();self.confirm();self.e.active=False
        self.assertEqual(self.update(),[('osc',PREFIX+'clear',[])])

    def test_old_ardour_without_extension_remains_usable(self):
        self.ui.reset();self.ui.feed(PREFIX+'version',[2])
        self.assertEqual(self.update(),[])

    def test_missing_identity_never_opens_wrong_track(self):
        self.r.identities={}
        self.assertEqual(self.update(),[])

    def test_retry_bounded_and_stale_ack_ignored(self):
        self.update();old=list(self.ui.target);self.e.sid=2;self.update()
        self.ui.feed(PREFIX+'result',old+[1]);self.assertTrue(self.ui.waiting)
        self.assertEqual(self.update(100.5),[])
        self.assertEqual(self.update(101)[0][1],PREFIX+'show')
        self.assertEqual(self.update(102),[('osc',PREFIX+'clear',[])])
        self.assertEqual(self.update(110),[])
        self.assertIsNotNone(self.ui.error)

    def test_rejection_clears_old_window_and_does_not_retry(self):
        self.update();self.confirm();self.e.sid=2;self.update()
        self.ui.feed(PREFIX+'result',list(self.ui.target)+[-1])
        self.assertEqual(self.update(),[('osc',PREFIX+'clear',[])])
        self.assertIsNone(self.ui.confirmed)
        self.assertEqual(self.update(110),[])

    def test_reconnect_resets_capability_and_last_target(self):
        self.update();self.confirm();self.ui.reset()
        self.assertEqual(self.update(),[])
        self.ui.feed(PREFIX+'version',[1])
        self.assertEqual(self.update()[0][1],PREFIX+'show')

if __name__=='__main__':unittest.main()
