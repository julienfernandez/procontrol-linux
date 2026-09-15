import sys,tempfile,unittest,subprocess,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from settings_web import App
from surface_settings import load
from procontrold import NET_HELPER,packet_sockets
class LocalSetupTests(unittest.TestCase):
 def test_calibration_requires_observation_and_unique_columns(self):
  with tempfile.TemporaryDirectory() as d,patch('settings_web.rpc',return_value={'ok':True}):
   a=App(d)
   with self.assertRaises(ValueError):a.calibrate(dict(revision=0,column=0,address=8,confirmed=False))
   self.assertEqual(a.calibrate(dict(revision=0,column=0,address=8,confirmed=True))['saved']['meter_addresses'][0],8)
   with self.assertRaises(ValueError):a.calibrate(dict(revision=1,column=1,address=8,confirmed=True))
   self.assertEqual(load(a.path)['revision'],1)
 def test_light_test_does_not_persist_and_rejects_strip_addresses(self):
  with tempfile.TemporaryDirectory() as d,patch('settings_web.rpc',return_value={'ok':True}) as rpc:
   a=App(d);self.assertEqual(a.meter_test({'address':40}),{'ok':True})
   self.assertFalse(a.path.exists())
   for address in (0,32,-1,64,True):
    with self.assertRaises(ValueError):a.meter_test({'address':address})
   self.assertEqual(rpc.call_count,1)
 @unittest.skipUnless(NET_HELPER.exists(),'local capability helper not installed')
 def test_helper_rejects_other_interfaces_and_invalid_fds(self):
  for args in (['lo','3'],['enp0s25','0'],['enp0s25','abc'],['enp0s25','3','extra']):
   p=subprocess.run([str(NET_HELPER),*args],capture_output=True)
   self.assertEqual(p.returncode,2)
