"""One unbanked OSC catalogue; eight physical strips; stable Lua route identities."""
# SPDX-License-Identifier: GPL-3.0-or-later
import time
import math
from surface_map import osc, select_strip
from automation_modes import PATH as AUTO_PATH, NAMES as AUTO_NAMES, mode_value

FIELDS = ('name', 'gain', 'fader', 'mute', 'solo', 'select', 'recenable', 'pan_stereo_position')


class SurfaceRouting:
    def __init__(self, mapper, feedback):
        self.mapper = mapper; self.feedback = feedback
        self.rows = {}; self.cache = {}; self.pending = None; self.ready = False
        self.start = 0; self.master = False; self.revision = 0; self.need_catalog = False
        self.lua_rows = []; self.identities = {}; self.session = ''; self.identity_ready = False
        self.last_error = None
        self.send_pending = {}; self.deferred = []
        self.automation_pending = {}
        self.render_matrix()

    def render_matrix(self):
        """32 absolute track positions; LEDs use Ardour feedback, never guesses."""
        ids = self.view_ids()
        mode = self.mapper.matrix_mode
        for key in range(1, 33):
            index = self.mapper.matrix_bank + key - 1
            sid = ids[index] if index < len(ids) else None
            on = bool(self.cache.get(('/strip/' + mode, sid), [sid, 0])[1]) if sid is not None else False
            if self.mapper.alpha:
                on = key == 0x1c and self.mapper.caps
            self.feedback.local(('led', f'23:{key}', [int(on)]))
        for key, name in ((0x24, 'select'), (0x25, 'mute'), (0x26, 'solo'), (0x27, 'recenable')):
            self.feedback.local(('led', f'23:{key}', [int(not self.mapper.alpha and mode == name)]))
        for bank in range(4):
            self.feedback.local(('led', f'23:{0x2c + bank}', [int(not self.mapper.alpha and self.mapper.matrix_bank == bank * 32)]))
        self.feedback.local(('led', '23:33', [int(self.mapper.alpha)]))

    def catalog_due(self, now, retry_at):
        # /strip/list rebuilds Ardour observers: only discovery, invalidation,
        # or a missing reply warrants another request, never an idle poll.
        return self.need_catalog or (now >= retry_at and not self.ready)

    def begin_catalog(self):
        self.need_catalog = False
        self.pending = {}; self.list_started = time.monotonic()

    def disconnect(self):
        if getattr(self,'eq',None) is not None:
            self.eq.exit('Ardour déconnecté'); self.eq.creation_supported = False; self.eq.creation_version = 0
        self.ready = False; self.identity_ready = False; self.cache.clear(); self.rows.clear()
        self.send_pending.clear(); self.deferred.clear()
        self.automation_pending.clear()
        self.identities.clear(); self.pending = None; self.mapper.invalidate_selected(); self.render()

    def view_ids(self):
        return [sid for sid, row in sorted(self.rows.items()) if (row['kind'] == 'MA') == self.master]

    def display_slots(self):
        # Keep the last committed view during an asynchronous catalogue read.
        # Command routing still uses slots()/ready and cannot target stale IDs.
        return self.view_ids()[self.start:self.start + 8]

    def slots(self):
        return self.view_ids()[self.start:self.start + 8] if self.ready else []

    def feed(self, path, values):
        # gainmode=2 sends gain automation under /fader, not /gain. Keep one
        # canonical cache for initial feedback, bank switches and GUI changes.
        if path in (AUTO_PATH, '/strip/fader/automation'):
            if len(values)!=2 or type(values[0]) is not int or mode_value(values[1]) is None:return
            path=AUTO_PATH;values=[values[0],mode_value(values[1])]
            pending=self.automation_pending.get(values[0])
            if pending:
                modes=[v for v,t in pending]
                if values[1] in modes:pending=pending[modes.index(values[1])+1:]
                else:pending=[]  # external GUI/direct-mode choice is authoritative
                if pending:self.automation_pending[values[0]]=pending
                else:self.automation_pending.pop(values[0],None)
        if getattr(self,'eq',None) is not None:
            self.eq.feed(path,values)
        if path.startswith('/strip/plugin/'):
            # Plugin replies have absolute route/plugin/parameter IDs. Never
            # reinterpret them as the normal physical-strip feedback cache.
            return
        if path == '/strip' and self.pending is not None:
            # Ardour 8.4 strip_state: SSID, type, name, inputs, outputs,
            # mute, solo, record enable. Reuse the catalogue row decoder.
            if len(values) == 8 and type(values[0]) is int and values[0] > 0:
                self.feed('#reply', list(values[1:5]) + [max(0,values[5]),max(0,values[6]),values[0],max(0,values[7])])
            return
        if path == '/set_surface' and self.pending is not None and len(values) == 9:
            ids=sorted(self.pending)
            expected=[r for r in self.lua_rows if not r['hidden'] and r['kind'] in ('AT','MT','B','MB','V','MA')]
            # Never publish an incomplete snapshot with holes, or a count that
            # disagrees with the independently received Lua catalogue.
            if ids != list(range(1,len(ids)+1)) or (self.lua_rows and len(ids)!=len(expected)):
                self.pending=None;self.ready=False
                return
            self.feed('#reply',['end_route_list'])
            return
        if path == '/strip/sends':
            self.receive_sends(values); return
        if path in ('#reply', '/reply') and values:
            if values[0] == 'end_route_list' and self.pending is not None:
                new = self.pending; self.pending = None
                changed = new != self.rows
                self.rows = new; self.ready = True
                self.start = min(self.start, max(0, ((len(self.view_ids()) - 1) // 8) * 8))
                if changed:
                    self.send_pending.clear(); self.deferred.clear()
                    self.automation_pending.clear()
                    self.revision += 1
                    self.cache = {k:v for k,v in self.cache.items() if k[1] in new}
                self.match_identities(); self.render()
                return
            if self.pending is not None and len(values) >= 7 and values[0] in ('AT','MT','V','MA','MO','SM','FB','B','MB'):
                sid = int(values[6])
                self.pending[sid] = {'sid':sid, 'kind':values[0], 'name':str(values[1]), 'channels':int(values[3])}
                for field, val in [('name', values[1]), ('mute',values[4]), ('solo',values[5])]:
                    self.cache[('/strip/'+field,sid)] = [sid,val]
                if len(values)>7:self.cache[('/strip/recenable',sid)]=[sid,values[7]]
            return
        if path == '/strip/list':
            self.need_catalog = True; self.ready = False; return
        if path.startswith('/strip/') and len(values)>=2:
            sid = int(values[0]); self.cache[(path,sid)] = list(values)
            if path == '/strip/name' and sid in self.rows and self.rows[sid]['name'] != str(values[1]):
                self.ready = False; self.identity_ready = False; self.need_catalog = True
            slots = self.slots()
            if sid in slots:self.feedback.feed(path, [slots.index(sid)+1]+list(values[1:]))
            if path == '/strip/' + self.mapper.matrix_mode:self.render_matrix()
            return
        self.feedback.feed(path, values)

    def render(self):
        self.mapper.state = {k:v for k,v in self.mapper.state.items() if not k[0].startswith('/strip/')}
        slots = self.display_slots(); self.mapper.bank_start = self.start + 1
        for channel in range(1,9):
            sid = slots[channel-1] if channel <= len(slots) else None
            auto=self.cache.get((AUTO_PATH,sid)) if sid is not None else None
            self.feedback.feed(AUTO_PATH,[channel,auto[1] if auto else None])
            if sid is None:
                self.feedback.feed('/strip/name',[channel,''])
                for field in ('mute','solo','select','recenable'):
                    self.feedback.feed('/strip/'+field,[channel,0])
                self.feedback.clear_strip_meter(channel)
                continue
            for field in FIELDS:
                path = '/strip/'+field; value = self.cache.get((path,sid))
                if value is not None:self.feedback.feed(path,[channel]+value[1:])
            self.feedback.feed('/strip/name',[channel,self.rows[sid]['name']])
        self.feedback.local(('led','27:10',[int(self.start>0)]))
        self.feedback.local(('led','27:12',[int(self.start+8<len(self.view_ids()))]))
        self.render_matrix()

    def change_bank(self, start):
        if self.mapper.touched:return False
        ids = self.view_ids()
        maximum = max(0, ((len(ids)-1)//8)*8)
        self.send_pending.clear(); self.deferred.clear()
        self.automation_pending.clear()
        self.start = max(0,min(maximum,start)); self.render(); return True

    def actions(self, actions):
        result=[]
        for kind,path,values in actions:
            if kind=='automation':
                slot,direction=values;slots=self.slots()
                if path!='cycle' or direction not in (-1,1) or not 1<=slot<=len(slots):continue
                sid=slots[slot-1];now=time.monotonic()
                pending=self.automation_pending.get(sid,[])
                if pending and now-pending[-1][1]>=1:pending=[]
                current=pending[-1][0] if pending else mode_value(self.cache.get((AUTO_PATH,sid),[sid,None])[1])
                if current is None:continue  # wait for Ardour, never invent Manual
                mode=(current+direction)%len(AUTO_NAMES)
                self.automation_pending[sid]=(pending+[(mode,now)])[-32:]
                result.append(osc(AUTO_PATH,sid,mode))
                continue
            if kind=='eq':
                if getattr(self,'eq',None) is not None:result.extend(self.eq.handle(path,values))
                continue
            if kind=='send_delta':
                slot,send_id,delta=values; slots=self.slots()
                if not 1<=slot<=len(slots) or not math.isfinite(delta):continue
                sid=slots[slot-1];now=time.monotonic();pending=self.send_pending.get(sid)
                if pending is None or now-pending['at']>1:
                    pending={'at':now,'deltas':{}};self.send_pending[sid]=pending
                    result.append(osc('/strip/sends',sid))
                pending['deltas'][send_id]=max(-1.,min(1.,pending['deltas'].get(send_id,0.)+delta))
                continue
            if kind=='bank':
                if path=='master':
                    if not self.mapper.touched:
                        self.send_pending.clear();self.deferred.clear()
                        self.automation_pending.clear()
                        self.master=bool(values[0]);self.start=0;self.render()
                    self.mapper.master_mode=self.master
                elif path=='delta':self.change_bank(self.start+int(values[0])*8)
                continue
            if kind=='matrix':
                ids=self.view_ids(); index=int(values[0])-1
                if not self.ready or not 0<=index<len(ids):continue
                if not self.change_bank((index//8)*8):continue
                sid=ids[index]
                if path=='select':
                    self.mapper.invalidate_selected();result.append(select_strip(sid))
                else:
                    addr='/strip/'+path; old=self.cache.get((addr,sid),[sid,0])[1]
                    result.append(osc(addr,sid,0 if old else 1))
                continue
            if kind!='osc':continue
            if path=='/refresh':
                self.feedback.resync();self.render()
            if path in ('/strip/select','/select/next','/select/previous'):
                self.mapper.invalidate_selected()
            elif path in ('/select/plug_page','/select/plugin'):
                self.mapper.invalidate_selected(plugin_only=True)
            if path.startswith('/strip/') and values:
                slot=int(values[0]); slots=self.slots()
                if not 1<=slot<=len(slots):continue
                result.append(osc(path,slots[slot-1],*values[1:]))
            else:result.append((kind,path,values))
        self.render_matrix()
        return result

    def receive_sends(self, values):
        # Ardour 8.4 /strip/sends: SSID followed by groups of
        # target SSID, name, send index (1-based), normalized gain, enabled.
        if not values or type(values[0]) is not int:return
        sid=values[0];pending=self.send_pending.pop(sid,None)
        if not pending or not self.ready or sid not in self.slots() or time.monotonic()-pending['at']>1:return
        if (len(values)-1)%5:return
        parsed={}
        for i in range(1,len(values),5):
            target,name,index,gain,enabled=values[i:i+5]
            if type(index) is not int or index<1 or index in parsed:return
            if type(gain) not in (int,float) or not math.isfinite(gain) or not 0<=gain<=1:return
            parsed[index]=gain
        for index,delta in pending['deltas'].items():
            if index in parsed:
                self.deferred.append(osc('/strip/send/fader',sid,index,max(0.,min(1.,parsed[index]+delta))))

    def drain(self):
        result=self.deferred;self.deferred=[]
        return result if self.ready else []

    def set_lua_catalog(self, session, rows):
        self.session=session;self.lua_rows=rows;self.match_identities()

    def match_identities(self):
        if not self.ready and self.rows and self.identities:return
        # Exactly match OSC's type mask 63 and presentation ordering. Names are
        # only a cross-check; persisted choices use session path + route ID.
        normal=[r for r in self.lua_rows if not r['hidden'] and r['kind'] in ('AT','MT','B','MB','V')]
        normal.sort(key=lambda r:r['order'])
        expected=normal+[r for r in self.lua_rows if r['kind']=='MA']
        actual=[r for _,r in sorted(self.rows.items())]
        self.identity_ready=self.ready and len(expected)==len(actual) and all(
            x['name']==y['name'] and x['kind']==y['kind'] for x,y in zip(expected,actual))
        self.identities={r['sid']:l['id'] for r,l in zip(actual,expected)} if self.identity_ready else {}
        self.last_error=None if self.identity_ready else 'Correspondance des pistes en attente'

    def status(self):
        automation=[]
        for slot,sid in enumerate(self.slots(),1):
            mode=mode_value(self.cache.get((AUTO_PATH,sid),[sid,None])[1])
            automation.append(dict(slot=slot,sid=sid,mode=mode,name=AUTO_NAMES[mode] if mode is not None else None))
        return {'ready':self.ready,'stereo_routes_ready':self.identity_ready,'bank_start':self.start+1,
                'automation':automation,
                'master_mode':self.master,'revision':self.revision,'error':self.last_error,
                'slots':[dict(self.rows[s],route_id=self.identities.get(s)) for s in self.slots()]}
