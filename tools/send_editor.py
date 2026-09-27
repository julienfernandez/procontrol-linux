"""Eight existing auxiliary sends of the selected route on the DSP section."""
# SPDX-License-Identifier: GPL-3.0-or-later
import math
import time
from surface_map import osc
from surface_feedback import scribble, button_led
from dsp_controls import dsp_text

class SendEditor:
    def __init__(self, routing, feedback, clock=time.monotonic):
        self.routing=routing; self.feedback=feedback; self.clock=clock
        self.active=False; self.ready=False; self.rows=[]; self.page=0; self.cursor=0
        self.last_valid=0; self.next_poll=0; self.request_at=None; self.pending={}
        self.flip=False; self.error=None; self.previous_mode='pan'
        routing.sends=self; routing.mapper.sends=self

    def valid(self):
        r=self.routing
        return (self.active and r.ready and self.sid in r.slots() and
                (r.session,r.revision,r.identities.get(self.sid),r.rows[self.sid]['name'])==self.target)

    def usable(self):
        return self.valid() and self.ready and self.clock()-self.last_valid<1.5

    def command(self,c):
        if len(c)!=3:return None
        if c[0]==0x90 and c[2]<128:
            z,k,down=c[2]&63,c[1],bool(c[2]&64)
            if (z,k)==(0x15,3):return [('sends','toggle',[])] if down else []
            if not self.active:return None
            if 0x0d<=z<=0x14 and k in (0,1,2):
                return [('sends',('focus','enable','mute')[k],[z-0x0d])] if down else []
            actions={(0x17,0x2a):('page',[-1 if self.routing.mapper.modifiers else 1]),
                     (0x17,0x30):('exit',[]),(0x15,7):('focus',[self.cursor]),
                     (0x15,5):('enable',[self.cursor]),(0x15,8):('mute',[self.cursor]),
                     (0x15,6):('toggle_send',[self.cursor]),(0x15,10):('toggle_send',[self.cursor]),
                     (8,0x13):('flip',[]),(8,0x1e):('focus',[self.cursor]),
                     (8,0x20):('toggle_send',[self.cursor])}
            if (z,k) in actions:
                name,args=actions[z,k];return [('sends',name,args)] if down else []
            # A target or another mode change cannot reuse this route's sends.
            if down and (z<8 and k in (1,2,3,4,6,10) or z==0x1b and k in (10,12)
                         or z==0x15 and k in (1,2,4,9) or z==8 and k in (8,12,14,15,16,17,18,22,34)
                         or z==0x17 and k in range(1,40)):
                self.exit()
        if self.active and c[0]==0xb0 and c[2]<128:
            if 0x4d<=c[1]<=0x54:return [('sends','turn',[c[1]-0x4d,c[2]-64])]
            if 0x40<=c[1]<=0x47:return [('sends','turn',[c[1]-0x40,c[2]-64])]
        return None

    def enter(self):
        r=self.routing
        selected=[sid for sid in r.slots() if r.cache.get(('/strip/select',sid),[sid,0])[1]]
        if not r.ready or len(selected)!=1:return
        for name in ('eq','monitor'):
            editor=getattr(r,name,None)
            if editor and editor.active:editor.exit()
        self.sid=selected[0];self.route_name=r.rows[self.sid]['name']
        self.target=(r.session,r.revision,r.identities.get(self.sid),self.route_name)
        self.active=True;self.ready=False;self.rows=[];self.page=0;self.cursor=0
        self.next_poll=0;self.request_at=None;self.pending={};self.error=None
        self.previous_mode=r.mapper.encoder_mode;r.mapper.encoder_mode='sends'
        self.render()

    def exit(self):
        if not self.active:return
        self.active=False;self.ready=False;self.pending={};self.rows=[];self.request_at=None
        self.routing.mapper.encoder_mode=self.previous_mode
        for i in range(8):
            self.feedback.put(('dsp',i+1),dsp_text(i+1,''))
            for key in (0,1,2):self.feedback.put(('led',13+i,key),button_led(13+i,key,False))
        self.feedback.put(('led',21,3),button_led(21,3,False))
        self.feedback.end_eq_display();self.routing.render()

    def handle(self,path,values):
        if path=='toggle':
            self.exit() if self.active else self.enter()
            return []
        if not self.active:return []
        if path=='exit':self.exit();return []
        if path=='flip':self.flip=not self.flip
        if path=='page':self.page=max(0,min(max(0,(len(self.rows)-1)//8),self.page+values[0]))
        result=[]
        if self.usable() and path in ('focus','enable','mute','toggle_send','turn'):
            index=self.page*8+values[0]
            if 0<=index<len(self.rows):
                self.cursor=values[0];row=self.rows[index];send=row['id']
                if path=='turn':
                    gain=max(0.,min(1.,row['gain']+values[1]*(.002 if self.routing.mapper.modifiers else .01)))
                    if gain!=row['gain']:
                        row['gain']=gain;result=[osc('/strip/send/fader',self.sid,send,gain)]
                elif path!='focus':
                    enabled=not row['enabled'] if path=='toggle_send' else path=='enable'
                    if enabled!=row['enabled']:
                        row['enabled']=enabled;result=[osc('/strip/send/enable',self.sid,send,float(enabled))]
                if result:self.pending[send]=(dict(row),self.clock())
        self.render();return result

    def tick(self,now=None):
        now=self.clock() if now is None else now
        if not self.active:return []
        if not self.routing.ready:return []
        if not self.valid():self.exit();return []
        if self.request_at is not None and now-self.request_at>1.5:
            self.request_at=None;self.ready=False;self.error='ATTENTE';self.next_poll=now+1
        result=[]
        if self.request_at is None and now>=self.next_poll:
            self.request_at=now;result=[osc('/strip/sends',self.sid)]
        self.render();return result

    def feed(self,path,values):
        if not self.active:return
        if path=='/strip/select' and len(values)==2 and values[1] and values[0]!=self.sid:
            self.exit();return
        if path!='/strip/sends' or self.request_at is None or not self.valid():return
        if not values or values[0]!=self.sid or (len(values)-1)%5:return
        rows=[];seen=set()
        for i in range(1,len(values),5):
            target,name,index,gain,enabled=values[i:i+5]
            if (type(index) is not int or index<1 or index in seen or not isinstance(name,str)
                or type(gain) not in (int,float) or not math.isfinite(gain) or not 0<=gain<=1
                or enabled not in (0,1)):return
            seen.add(index);row=dict(id=index,name=name,gain=gain,enabled=bool(enabled))
            pending=self.pending.get(index)
            if pending and self.request_at<=pending[1]:row=pending[0]
            elif pending:self.pending.pop(index,None)
            rows.append(row)
        self.rows=rows;self.page=min(self.page,max(0,(len(rows)-1)//8))
        self.last_valid=self.clock();self.ready=True;self.error=None
        self.request_at=None;self.next_poll=self.clock()+.2;self.render()

    def render(self):
        if not self.active:return
        usable=self.usable()
        for i in range(8):
            index=self.page*8+i;row=self.rows[index] if index<len(self.rows) else None
            name=row['name'] if usable and row else 'AUCUN' if usable and i==0 else ''
            value=('ON ' if row['enabled'] else 'OFF ')+f"{row['gain']*100:.0f}%" if usable and row else 'DEPART' if usable and i==0 else ''
            if not usable:name='LECTURE' if i==0 else '';value='DEPARTS' if i==0 else ''
            if self.flip:name,value=value,name
            self.feedback.put(('dsp',i+1),dsp_text(i+1,name))
            self.feedback.put(('value',i+1),scribble(i+1,value,False))
            for key,on in ((0,row is not None and i==self.cursor),(1,usable and row is not None and row['enabled']),(2,usable and row is not None and not row['enabled'])):
                self.feedback.put(('led',13+i,key),button_led(13+i,key,on))
        self.feedback.put(('led',21,3),button_led(21,3,True))

    def status(self):
        return dict(active=self.active,ready=self.usable(),page=self.page+1,count=len(self.rows),error=self.error)
