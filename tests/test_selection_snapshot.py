import socket,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_routing import SurfaceRouting
from surface_feedback import SurfaceFeedback
from surface_map import SurfaceMap
from surface_osc import ArdourSurface
from ardour_transport import decode

class SnapshotTests(unittest.TestCase):
 def setUp(self):
  self.m=SurfaceMap();self.f=SurfaceFeedback(self.m);self.r=SurfaceRouting(self.m,self.f)
 def snapshot(self):
  self.r.feed('/strip',[1,'AT','One',2,2,0,0,0])
  self.r.feed('/strip',[2,'AT','Two',2,2,0,0,0])
  self.r.feed('/set_surface',[0,63,8307,2,8,8,0,1,0])
 def test_discovery_uses_read_only_snapshot_not_legacy_list(self):
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as server:
   server.bind(('127.0.0.1',0));server.settimeout(.1)
   c=ArdourSurface(server.getsockname()[1],self.m)
   try:
    rows=[decode(server.recv(65535))[0] for _ in range(4)]
    self.assertEqual(rows[1:],[('/strip',[]),('/set_surface',[]),('/procontrol/plugin_ui/version',[])])
    c.request_catalog()
    self.assertEqual([decode(server.recv(65535))[0] for _ in range(2)],[('/strip',[]),('/set_surface',[])])
   finally:c.close()
 def test_selection_notifications_refresh_immediately_and_keep_selection(self):
  self.r.begin_catalog();self.snapshot();self.r.feed('/strip/select',[2,1])
  for i in range(10):
   self.r.feed('/strip/list',[])
   self.assertTrue(self.r.catalog_due(100+i*.01,102))
   self.r.begin_catalog();self.snapshot()
   self.assertTrue(self.r.ready)
   self.assertEqual(self.r.actions([('matrix','select',[1])]),[('osc','/strip/select',[1,0])])
   self.assertEqual(self.r.cache[('/strip/select',2)],[2,1])
   self.assertFalse(self.r.catalog_due(100+i*.01,102))
 def test_snapshot_is_not_published_before_reply_boundary(self):
  self.r.begin_catalog();self.r.feed('/strip',[1,'AT','One',2,2,0,0,0])
  self.assertFalse(self.r.ready)
  self.assertEqual(self.r.actions([('matrix','select',[1])]),[])
 def test_hole_or_missing_tail_rejected(self):
  self.r.begin_catalog();self.r.feed('/strip',[2,'AT','Two',2,2,0,0,0])
  self.r.feed('/set_surface',[0]*9);self.assertFalse(self.r.ready)
  self.r.lua_rows=[{'hidden':False,'kind':'AT'}]*3
  self.r.begin_catalog();self.snapshot();self.assertFalse(self.r.ready)
  self.assertTrue(self.r.catalog_due(103,102))

if __name__=='__main__':unittest.main()
