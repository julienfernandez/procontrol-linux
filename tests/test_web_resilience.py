"""Offline snapshots and simultaneous browser reads must remain bounded."""
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from console_web import ConsoleController
from runtime_status import service_status
from settings_web import App


class ResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.runtime=self.root/'run';self.runtime.mkdir()
        self.path=self.runtime/'status.json'
        self.path.write_text(json.dumps(dict(running=True,console='online',ardour='responding',
            stereo=dict(active=True,routes_ready=True,sources=[{'name':'Master'}],large=[{'db':-3}]))))

    def test_recent_snapshot_does_not_keep_meters_alive_after_worker_exit(self):
        s=App(self.root).state()
        self.assertFalse(s['daemon']['running']);self.assertFalse(s['daemon']['live'])
        self.assertEqual(s['daemon']['console'],'unknown');self.assertEqual(s['sources'],[])
        self.assertEqual(s['daemon']['stereo']['large'],[])

    def test_locked_service_with_stale_or_invalid_snapshot_is_not_live(self):
        with (self.runtime/'daemon.lock').open('a') as guard:
            fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertTrue(service_status(self.runtime)['live'])
            os.utime(self.path,(time.time()-6,)*2)
            s=service_status(self.runtime)
            self.assertTrue(s['running']);self.assertFalse(s['fresh']);self.assertFalse(s['live'])
            for content in ('null','[]','{'):
                self.path.write_text(content)
                self.assertFalse(service_status(self.runtime)['live'])

    def test_waiting_web_clients_share_one_slow_timeout(self):
        controller=ConsoleController(self.root)
        barrier=threading.Barrier(9)
        replies=[]
        def slow(*args,**kwargs):
            time.sleep(.31)
            raise TimeoutError('Gateway timeout')
        def client():
            barrier.wait();replies.append(controller.state())
        with patch('console_web.rpc',side_effect=slow) as rpc:
            threads=[threading.Thread(target=client) for _ in range(8)]
            for t in threads:t.start()
            barrier.wait()
            for t in threads:t.join(5)
            self.assertEqual(len(replies),8)
            self.assertEqual(rpc.call_count,1)
            self.assertTrue(all(not r['ok'] for r in replies))


if __name__=='__main__':unittest.main()
