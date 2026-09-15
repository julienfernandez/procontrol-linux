"""Receive versioned complete Lua catalogues and independent audio channel levels."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
import socket
import time
from ardour_transport import decode


def source_key(session, rid):
    return json.dumps([session,rid],separators=(',',':'),ensure_ascii=False)


class StereoBridge:
    def __init__(self, routing, feedback, settings, port=3820, bind=True):
        self.routing=routing;self.feedback=feedback;self.settings=settings
        self.socket=None; self.pending=None;self.rows={};self.levels={};self.session='';self.generation=-1
        self.last_seen=None;self.invalid=0;self.last_sequence={};self.last_render={};self.probe=None
        if bind:
            self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.socket.bind(('127.0.0.1',port));self.socket.setblocking(False)

    def receive(self, path, v, now=None):
        now=time.monotonic() if now is None else now
        try:
            if path=='/procontrol/catalog/begin':
                session,gen,count=v
                if not isinstance(session,str) or not isinstance(gen,int) or not isinstance(count,int) or not 0<=count<=4096:raise ValueError()
                self.pending={'session':session,'gen':gen,'count':count,'rows':{},'started':now}
            elif path=='/procontrol/catalog/route':
                session,gen,rid,order,kind,name,channels,hidden=v;p=self.pending
                if not p or (session,gen)!=(p['session'],p['gen']):return
                if not isinstance(rid,str) or not isinstance(name,str) or not isinstance(channels,int) or not 0<=channels<=64:raise ValueError()
                if kind not in ('AT','MT','B','MB','V','MA','MO','FB','OTHER') or not isinstance(order,int):raise ValueError()
                p['rows'][rid]={'id':rid,'order':order,'kind':kind,'name':name,'channels':channels,'hidden':bool(hidden)}
            elif path=='/procontrol/catalog/end':
                session,gen=v;p=self.pending
                if not p or (session,gen)!=(p['session'],p['gen']) or len(p['rows'])!=p['count']:return
                changed=self.session!=session or self.generation!=gen or self.rows!=p['rows']
                if changed:self.levels.clear();self.last_sequence.clear()
                self.session=session;self.generation=gen;self.rows=p['rows'];self.pending=None
                self.routing.set_lua_catalog(session,list(self.rows.values()))
            elif path=='/procontrol/meter':
                session,gen,seq,rid,*levels=v
                if session!=self.session or gen!=self.generation or rid not in self.rows:return
                if not isinstance(seq,int) or seq<=self.last_sequence.get(rid,-1):return
                if len(levels)!=self.rows[rid]['channels']:raise ValueError()
                if any(type(x) not in (int,float) or not math.isfinite(x) for x in levels):raise ValueError()
                self.levels[rid]=(now,[max(-193.,min(40.,float(x))) for x in levels])
                self.last_sequence[rid]=seq;self.last_seen=now
            else:return
        except (ValueError,TypeError):self.invalid+=1

    def poll(self):
        if not self.socket:return
        for _ in range(512):
            try:data,_=self.socket.recvfrom(65535)
            except BlockingIOError:break
            try:
                for path,values in decode(data):self.receive(path,values)
            except ValueError:self.invalid+=1

    def value(self,rid,channel,now):
        stamp,levels=self.levels.get(rid,(-100,[]))
        return levels[channel] if now-stamp<=1 and 0<=channel<len(levels) else -193.

    def render(self,now=None):
        now=time.monotonic() if now is None else now
        slots=self.routing.display_slots()
        for channel in range(1,9):
            rid=self.routing.identities.get(slots[channel-1]) if channel<=len(slots) else None
            self.feedback.strip_meter(channel,self.value(rid,0,now),self.value(rid,1,now))
        large=[]
        for i,(assignment,address) in enumerate(zip(self.settings['meter_assignments'],self.settings['meter_addresses'])):
            source=assignment['source'];rid=None
            if source=='master':rid=next((r['id'] for r in self.rows.values() if r['kind']=='MA'),None)
            elif source:
                try:
                    session,rid=json.loads(source)
                    if session!=self.session:rid=None
                except (ValueError,TypeError):rid=None
            value=self.value(rid,assignment['channel'],now)
            available=rid in self.rows and assignment['channel']<self.rows[rid]['channels']
            large.append({'db':value,'available':available,'calibrated':address is not None})
            if address is not None and not self.probe:self.feedback.meter_address(address,value)
        if self.probe and now>=self.probe['until']:
            self.feedback.meter_address(self.probe['address'],-193.);self.probe=None
        self.last_render={'large':large}

    def test_address(self,address,now=None):
        if type(address) is not int or not 0<=address<64:raise ValueError('Adresse de test invalide')
        now=time.monotonic() if now is None else now
        if self.probe:self.feedback.meter_address(self.probe['address'],-193.)
        self.probe={'address':address,'until':now+2.}
        self.feedback.meter_address(address,-12.)

    def configure(self,settings):
        for a in self.settings['meter_addresses']:
            if a is not None:self.feedback.meter_address(a,-193.)
        self.settings=settings

    def status(self):
        now=time.monotonic()
        return {'active':self.last_seen is not None and now-self.last_seen<=1,
                'routes_ready':self.routing.identity_ready,'session':self.session,'invalid':self.invalid,
                'sources':[{'source':'master' if r['kind']=='MA' else source_key(self.session,r['id']),
                            'name':r['name'],'channels':r['channels'],'kind':r['kind']}
                           for r in self.rows.values() if r['kind'] in ('MA','B','MB','FB')],
                **self.last_render}

    def close(self):
        if self.socket:self.socket.close()
