import copy,json,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from surface_map import SurfaceMap
from surface_feedback import SurfaceFeedback
from surface_routing import SurfaceRouting
from stereo_bridge import StereoBridge,source_key
from surface_settings import DEFAULTS,validate,save,load
from ardour_transport import decode,message

class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.m=SurfaceMap();self.f=SurfaceFeedback(self.m);self.r=SurfaceRouting(self.m,self.f)
        self.r.begin_catalog()
        for n in range(1,19):self.r.feed('#reply',['AT','Track '+str(n),2,2,0,0,n,0])
        self.r.feed('#reply',['MA','Master',2,2,0,0,19]);self.r.feed('#reply',['end_route_list',48000,1000,0])
    def test_matrix_and_last_bank_targets(self):
        self.assertEqual(self.r.actions([('matrix','select',[17])]),[('osc','/strip/select',[17,0])])
        self.assertEqual(self.r.slots(),[17,18]);self.assertEqual(self.m.bank_start,17)
        self.assertEqual(self.r.actions([('osc','/strip/select',[2,0])]),[('osc','/strip/select',[18,0])])
        self.assertEqual(self.r.actions([('osc','/strip/select',[3,0])]),[])
        self.r.actions([('bank','delta',[1])]);self.assertEqual(self.r.slots(),[17,18])
        self.r.actions([('bank','master',[True])]);self.assertEqual(self.r.slots(),[19])
    def test_cache_and_leds_follow_real_feedback(self):
        self.r.feed('/strip/solo',[17,1]);self.r.actions([('matrix','solo',[17])])
        self.assertEqual(self.r.actions([('matrix','solo',[17])]),[('osc','/strip/solo',[17,0])])
        self.r.feed('/strip/select',[18,1]);self.assertEqual(self.m.state[('/strip/select',2)],1)
        self.assertEqual(self.f.queue[('led',1,6)],bytes.fromhex('90 06 41'))
    def test_metadata_mismatch_suspends_identity(self):
        rows=[dict(id=str(n),kind='AT',name='Track '+str(n),order=n,hidden=False,channels=2) for n in range(1,19)]
        rows.append(dict(id='master',kind='MA',name='Master',order=99,hidden=False,channels=2))
        self.r.set_lua_catalog('/session',rows);self.assertTrue(self.r.identity_ready)
        rows[0]['name']='Renamed';self.r.set_lua_catalog('/session',rows)
        self.assertFalse(self.r.identity_ready);self.assertEqual(self.r.identities,{})
        self.r.feed('/strip/name',[1,'Renamed']);self.assertFalse(self.r.ready)
        self.assertEqual(self.r.actions([('osc','/strip/select',[1,0])]),[])
    def test_bank_cannot_reassign_touched_fader(self):
        self.m.touched.add(1);self.r.actions([('bank','delta',[1])]);self.assertEqual(self.r.start,0)

class StereoTests(unittest.TestCase):
    def setUp(self):
        self.m=SurfaceMap();self.f=SurfaceFeedback(self.m);self.r=SurfaceRouting(self.m,self.f)
        self.r.begin_catalog();self.r.feed('#reply',['AT','Stereo',2,2,0,0,1,0]);self.r.feed('#reply',['MA','Master',2,2,0,0,2]);self.r.feed('#reply',['end_route_list',48000,0,0])
        self.settings=copy.deepcopy(DEFAULTS);self.settings['meter_addresses']=[8,40,None,None,None,None]
        self.b=StereoBridge(self.r,self.f,self.settings,bind=False)
        self.b.receive('/procontrol/catalog/begin',['session',1,2],0)
        for rid,kind,name,order in [('a','AT','Stereo',1),('m','MA','Master',2)]:
            self.b.receive('/procontrol/catalog/route',['session',1,rid,order,kind,name,2,0],0)
        self.b.receive('/procontrol/catalog/end',['session',1],0)
    def test_independent_lr_and_master(self):
        self.b.receive('/procontrol/meter',['session',1,1,'a',-10.,-40.],1)
        self.b.receive('/procontrol/meter',['session',1,1,'m',-3.,-20.],1)
        self.b.render(1)
        self.assertNotEqual(self.f.queue[('meter',0)][5:7],self.f.queue[('meter',32)][5:7])
        self.assertNotEqual(self.f.queue[('meter',8)][5:7],self.f.queue[('meter',40)][5:7])
        self.b.render(2.01)
        for a in (0,32,8,40):self.assertEqual(self.f.queue[('meter',a)][5:7],b'\0\0')
    def test_stale_reordered_and_invalid_udp(self):
        self.b.receive('/procontrol/meter',['session',1,3,'a',-10.,-30.],1)
        self.b.receive('/procontrol/meter',['session',1,2,'a',0.,0.],1.1)
        self.assertEqual(self.b.value('a',0,1.1),-10)
        self.b.receive('/procontrol/meter',['session',1,4,'a',float('nan'),0.],1.1)
        self.assertEqual(self.b.invalid,1)
        self.b.receive('/procontrol/meter',['other',1,9,'a',0.,0.],1.1)
        self.assertEqual(self.b.value('a',1,1.1),-30)
    def test_incomplete_catalogue_does_not_replace(self):
        self.b.receive('/procontrol/catalog/begin',['other',2,5],2)
        self.b.receive('/procontrol/catalog/end',['other',2],2)
        self.assertEqual(self.b.session,'session')
    def test_probe_is_bounded(self):
        self.b.test_address(10,2);self.b.render(4.1)
        self.assertIsNone(self.b.probe);self.assertEqual(self.f.queue[('meter',10)][5:7],b'\0\0')
    def test_packet_codec_accepts_real_stereo(self):
        v=['session',1,42,'a',-4.,-21.]
        self.assertEqual(decode(message('/procontrol/meter',*v)),[('/procontrol/meter',v)])

class SettingsTests(unittest.TestCase):
    def test_persist_and_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'settings.json';s=load(p);s['pointer_gain']=.35;s['revision']=4;save(p,s)
            self.assertEqual(load(p),s)
            for key,val in [('jog_gain',float('nan')),('pointer_gain',True),('meter_addresses',[8]*6)]:
                invalid=copy.deepcopy(s);invalid[key]=val
                with self.assertRaises(ValueError):save(p,invalid)
                self.assertEqual(load(p),s)

if __name__=='__main__':unittest.main()

class WebTests(unittest.TestCase):
    def test_http_origin_validation_and_no_lost_updates(self):
        import threading,urllib.request,urllib.error
        from settings_web import serve
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'run').mkdir();server=serve(root,0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url='http://127.0.0.1:'+str(server.server_port)
            try:
                state=json.load(urllib.request.urlopen(url+'/api/state'))
                self.assertEqual(state['saved']['pointer_gain'],.24)
                data={'revision':0,'pointer_gain':.3}
                def post(data,origin=None):
                    headers={'Content-Type':'application/json'}
                    if origin:headers['Origin']=origin
                    return urllib.request.urlopen(urllib.request.Request(url+'/api/settings',data=json.dumps(data).encode(),headers=headers))
                with self.assertRaises(urllib.error.HTTPError) as c:post(data,'https://outside.example')
                self.assertEqual(c.exception.code,403)
                result=json.load(post(data));self.assertEqual(result['saved']['revision'],1)
                self.assertFalse(result['applied']['daemon']['ok'])
                with self.assertRaises(urllib.error.HTTPError):post(data)
                self.assertEqual(load(root/'settings.json')['pointer_gain'],.3)
            finally:server.shutdown();server.server_close();thread.join()
