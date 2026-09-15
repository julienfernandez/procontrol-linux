"""LSP x8 EQ editing on the strip encoders, using Ardour's absolute plugin API.

Descriptor IDs are 1-based nth *control* parameters, not raw LV2 port numbers.
Snapshots are bounded read-only requests; no /refresh or observer rebuild.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import math
import time
from surface_map import osc, select_strip
from surface_feedback import scribble, button_led
from dsp_controls import dsp_text

NAMES = {'LSP Parametric Equalizer x8 Mono', 'LSP Parametric Equalizer x8 Stereo'}
COMPRESSORS = {'LSP Compressor Mono', 'LSP Compressor Stereo'}
FIELDS = {'type': 'Filter type', 'mode': 'Filter mode', 'slope': 'Filter slope',
          'mute': 'Filter mute', 'frequency': 'Frequency', 'width': 'Filter Width',
          'gain': 'Gain', 'q': 'Quality factor'}
TYPES = ('Off', 'Bell', 'HiPass', 'HiShelf', 'LoPass', 'LoShelf', 'Notch',
         'Reson', 'Allpass', 'Band', 'LadPass', 'LadRej')
MODES = ('RLC-BT', 'RLC-MT', 'BWC-BT', 'BWC-MT', 'LRX-BT', 'LRX-MT', 'APO-DR')
KNOBS = ('frequency', 'gain', 'q', 'type', 'slope', 'mode', 'width', 'output')


class EQEditor:
    POLL_INTERVAL = 0.5
    SNAPSHOT_TIMEOUT = 1.5

    def __init__(self, routing, feedback, clock=time.monotonic):
        self.routing = routing; self.feedback = feedback; self.clock = clock
        self.active = False; self.ready = False; self.sid = None; self.plugin = None
        self.filter = 0; self.params = {}; self.outgoing = []; self.pending = {}
        self.stage = None; self.error = None; self.next_poll = 0; self.last_valid = 0
        self.edits = 0; self.snapshots = 0
        self.mode = 'eq'; self.plugins = []; self.page = 0; self.plugin_page = 0
        self.explicit_plugin = False
        self.family = 'eq'
        self.processor_enabled = False
        self.catalog_wait = False
        routing.eq = self; routing.mapper.eq = self; feedback.eq = self
        self.exit(force=True)

    def command(self, c):
        """Called inside SurfaceMap.route, after its Ethernet retry deduplication."""
        if len(c) == 3 and c[0] == 0x90 and c[2] < 128:
            zone, key, down = c[2] & 63, c[1], bool(c[2] & 64)
            if zone < 8 and key == 2:
                return [('eq', 'enter', [zone + 1])] if down else []
            if zone < 8 and key == 3:
                return [('eq', 'compressor', [zone + 1])] if down else []
            if (zone, key) in ((0x15, 2), (0x19, 4)):
                return [('eq', 'browse', [])] if down else []
            if self.active:
                if zone < 8 and key == 6:
                    return [('eq', 'track', [zone + 1])] if down else []
                if zone == 0x17 and 1 <= key <= 32 and not self.routing.mapper.alpha and self.routing.mapper.matrix_mode == 'select':
                    return [('eq', 'matrix_track', [self.routing.mapper.matrix_bank+key-1])] if down else []
                if zone == 0x1b and key in (10,12):
                    return [('eq', 'bank', [-1 if key==10 else 1])] if down else []
                if (zone, key) == (0x17, 0x2a):
                    return [('eq', 'page', [-1 if self.routing.mapper.modifiers else 1])] if down else []
                if (zone, key) == (0x17, 0x30):
                    return [('eq', 'exit', [])] if down else []
                if 0x0d <= zone <= 0x14 and key in (0, 1, 2):
                    if self.mode == 'browse':
                        return [('eq', 'open' if key == 0 else 'plugin_enable', [zone - 0x0d])] if down else []
                    if self.mode == 'params':
                        return [('eq', 'focus', [zone - 0x0d])] if down and key == 0 else []
                    return [('eq', 'filter' if key == 0 else 'enable', [zone - 0x0d])] if down else []
                if (zone, key) == (0x15, 10):
                    return [('eq', 'bypass', [])] if down else []
                # Leave editing before a normal selection/bank/mode change.
                if down and ((zone < 8 and key in (1, 3, 6, 10)) or
                             (zone == 0x17 and key in (0x21, 0x23)) or
                             (zone == 0x15 and key in (1, 3))):
                    self.exit()
        if self.active and len(c) == 3 and c[0] == 0xb0 and c[2] < 128:
            delta = c[2] - 64
            if 0x40 <= c[1] <= 0x47:
                return [('eq', 'turn', [c[1] - 0x40, delta])]
            if 0x4d <= c[1] <= 0x54:
                return [('eq', 'type', [c[1] - 0x4d, delta])] if self.mode == 'eq' else []
        return None

    def handle(self, path, values):
        if path in ('matrix_track','bank'):
            ids = self.routing.view_ids()
            if not self.routing.ready or not ids or self.routing.mapper.touched: return []
            if path == 'matrix_track': index = values[0]
            elif self.routing.mapper.nudge: index = ids.index(self.sid)+values[0]
            else: index = max(0,min(((len(ids)-1)//8)*8,self.routing.start+values[0]*8))
            if not 0 <= index < len(ids): return []
            if not self.routing.change_bank((index//8)*8): return []
            return self.handle('track',[index%8+1])
        if path == 'browse':
            if self.active:
                self.mode = 'browse'; self.plugin_page = 0; self.stage = None; self.next_poll = 0
                self.pending.clear(); self.outgoing.clear(); self.ready = False; self.render()
                return []
            slots = self.routing.slots()
            selected = [s for s in slots if self.routing.cache.get(('/strip/select',s),[s,0])[1]]
            if not slots: return []
            slot = slots.index(selected[0])+1 if selected else 1
            result = self.handle('enter',[slot]); self.mode = 'browse'; self.render()
            return result
        if path == 'track':
            if self.active and self.sid in self.routing.slots() and self.routing.slots().index(self.sid)+1 == values[0]:
                return []
            # Continue the same EQ/compressor family on the next track. A
            # generic plugin or the browser returns to the new track's list.
            family = self.family if self.mode != 'browse' else None
            result = self.handle('compressor' if family == 'comp' else 'enter',values)
            if family not in ('eq', 'comp'): self.mode = 'browse'
            self.render()
            return result
        if path in ('enter','compressor'):
            slot = values[0]; ids = self.routing.slots()
            if not 1 <= slot <= len(ids): return []
            sid = ids[slot - 1]
            family = 'comp' if path == 'compressor' else 'eq'
            if self.active and self.sid == sid and self.mode != 'browse' and self.family == family:
                self.exit(); return []
            self.exit()
            self.active = True; self.ready = False; self.sid = sid; self.plugin = None
            self.route_name = self.routing.rows[sid]['name']
            self.identity = self.routing.identities.get(sid)
            self.revision = self.routing.revision; self.session = self.routing.session
            self.filter = 0; self.params = {}; self.error = None; self.pending = {}
            self.mode = 'eq'; self.plugins = []; self.page = 0; self.plugin_page = 0
            self.explicit_plugin = False
            self.catalog_wait = False
            self.family = family
            if family == 'comp': self.mode = 'params'
            self.previous_mode = self.routing.mapper.encoder_mode
            self.routing.mapper.encoder_mode = 'eq'
            self.outgoing = [select_strip(sid)]; self.stage = None
            self.next_poll = 0; self.last_valid = 0
            self.render()
        elif path == 'exit': self.exit()
        elif self.active:
            if path == 'page':
                if self.mode == 'browse': self.plugin_page = max(0,min((len(self.plugins)-1)//8,self.plugin_page+values[0]))
                elif self.mode == 'params': self.page = max(0,min((len(self.parameter_list())-1)//8,self.page+values[0]))
                elif self.mode == 'eq': self.filter = (self.filter+values[0])%8
            elif path == 'open' and self.mode == 'browse' and self.usable():
                row = self.plugin_page*8+values[0]
                if row < len(self.plugins):
                    self.plugin,self.plugin_name,self.processor_enabled = self.plugins[row]
                    self.explicit_plugin = True
                    self.mode = 'eq' if self.plugin_name in NAMES else 'params'
                    self.family = 'eq' if self.plugin_name in NAMES else 'comp' if self.plugin_name in COMPRESSORS else None
                    self.ready = False; self.params = {}; self.pending = {}; self.page = 0
                    self.stage = None; self.next_poll = 0
            elif path == 'plugin_enable' and self.mode == 'browse' and self.usable():
                row = self.plugin_page*8+values[0]
                if row < len(self.plugins):
                    pid,name,on = self.plugins[row]
                    self.outgoing.append(osc('/strip/plugin/deactivate' if on else '/strip/plugin/activate',self.sid,pid))
                    self.plugins[row] = (pid,name,not on)
            elif path == 'focus' and self.mode == 'params': self.filter = values[0]
            elif path == 'filter': self.filter = values[0]
            elif self.usable():
                if path == 'enable':
                    band = values[0]; self.filter = band
                    if self.value('type', band) == 0:
                        self.write('type', 1, band); self.write('mute', 0, band)
                    else: self.write('mute', 0 if self.value('mute', band) else 1, band)
                elif path == 'bypass':
                    if self.mode == 'eq':
                        if not self.processor_enabled:
                            self.outgoing.append(osc('/strip/plugin/activate',self.sid,self.plugin))
                            self.processor_enabled = True
                        else: self.write('enabled', 0 if self.value('enabled') else 1)
                    elif self.mode == 'params':
                        self.outgoing.append(osc('/strip/plugin/deactivate' if self.processor_enabled else '/strip/plugin/activate',self.sid,self.plugin))
                        self.processor_enabled = not self.processor_enabled
                elif path == 'type':
                    self.filter = values[0]; self.turn(3, values[1])
                elif path == 'turn':
                    if self.mode == 'eq': self.turn(*values)
                    elif self.mode == 'params': self.turn_parameter(*values)
            self.render()
        result = self.outgoing; self.outgoing = []
        return result

    def exit(self, reason=None, force=False):
        if not self.active and not force: return
        self.active = False; self.ready = False; self.stage = None; self.params = {}
        self.outgoing = []; self.pending = {}; self.error = reason
        self.routing.mapper.encoder_mode = getattr(self, 'previous_mode', 'pan')
        for ch in range(1, 9):
            self.feedback.put(('led', ch-1, 2), button_led(ch-1, 2, False))
            self.feedback.put(('led', ch-1, 3), button_led(ch-1, 3, False))
            self.feedback.put(('dsp', ch), dsp_text(ch, ''))
            for key in (0, 1, 2):
                self.feedback.put(('led', 0x0c+ch, key), button_led(0x0c+ch, key, False))
        self.feedback.put(('led', 0x15, 10), button_led(0x15, 10, False))
        self.feedback.put(('led', 0x15, 2), button_led(0x15, 2, False))
        self.feedback.end_eq_display()
        self.routing.render()

    def usable(self):
        return self.active and self.ready and self.clock() - self.last_valid < self.SNAPSHOT_TIMEOUT

    def valid_target(self):
        r = self.routing
        return (r.ready and self.sid in r.slots() and r.revision == self.revision and
                r.session == self.session and r.rows[self.sid]['name'] == self.route_name and
                r.identities.get(self.sid) == self.identity)

    def tick(self, now=None):
        now = self.clock() if now is None else now
        if not self.active: return []
        if not self.routing.ready:
            # Selection can emit /strip/list even though route identities are
            # unchanged. Keep the current display while the snapshot resolves.
            return []
        if not self.valid_target(): self.exit('Piste ou banque modifiée'); return []
        if self.catalog_wait:
            self.catalog_wait = False; self.next_poll = 0
        if self.stage and now - self.request_at > self.SNAPSHOT_TIMEOUT:
            self.stage = None; self.ready = False; self.error = 'Réponse EQ absente'
            self.next_poll = now + 1
        if self.stage is None and now >= self.next_poll:
            self.stage = 'list'; self.request_at = now
            self.outgoing.append(osc('/strip/plugin/list', self.sid))
        self.render(now)
        result = self.outgoing; self.outgoing = []
        return result

    def feed(self, path, values):
        if not self.active: return
        if path == '/strip/list':
            self.catalog_wait = True; self.ready = False; self.stage = None
            self.outgoing.clear(); self.pending.clear(); return
        if path == '/strip/select' and len(values) == 2 and values[1] and values[0] != self.sid:
            self.exit('Autre piste sélectionnée'); return
        if path == '/strip/plugin/list' and self.stage == 'list' and values and values[0] == self.sid:
            if (len(values)-1) % 3: return
            if not all(type(values[i]) is int and values[i]>0 and isinstance(values[i+1],str)
                       and values[i+2] in (0,1) for i in range(1,len(values),3)): return
            self.plugins = [(values[i], values[i+1], bool(values[i+2])) for i in range(1,len(values),3)]
            if self.mode == 'browse':
                self.ready = True; self.error = None; self.last_valid = self.clock()
                self.stage = None; self.next_poll = self.clock()+self.POLL_INTERVAL
                self.plugin_page = min(self.plugin_page,max(0,(len(self.plugins)-1)//8))
                self.render(); return
            matches = ([p for p in self.plugins if p[1] in (NAMES if self.family=='eq' else COMPRESSORS)] if self.family and not self.explicit_plugin
                       else [p for p in self.plugins if p[:2] == (self.plugin,self.plugin_name)])
            if len(matches) != 1:
                self.ready = False; self.error = 'Absent' if not matches else 'Plusieurs EQ'
                self.stage = None; self.next_poll = self.clock()+1; return
            plugin, name, enabled = matches[0]
            if self.plugin is not None and (plugin != self.plugin or name != self.plugin_name):
                self.ready = False; self.params = {}; self.pending = {}
            self.plugin = plugin; self.plugin_name = name; self.processor_enabled = bool(enabled)
            self.snapshot = {}; self.snapshot_invalid = False; self.stage = 'descriptor'
            self.snapshot_at = self.clock()
            self.outgoing.append(osc('/strip/plugin/descriptor', self.sid, plugin))
        elif path == '/strip/plugin/descriptor' and self.stage == 'descriptor':
            if len(values) < 11 or values[:2] != [self.sid, self.plugin]: return
            pid, label, flags = values[2:5]; low, high = values[6:8]; count = values[9]
            if type(count) is not int or count < 0 or len(values) != 11 + count*2: return
            value = values[-1]
            if (type(pid) is not int or pid < 1 or type(flags) is not int or not flags & 128 or
                not isinstance(label,str) or not all(type(x) in (int,float) and math.isfinite(x) for x in (low,high,value)) or
                low > high or not low <= value <= high): return
            if label in self.snapshot:
                if self.mode == 'eq': self.snapshot_invalid = True; return
                label = f'{label} [{pid}]'
            self.snapshot[label] = dict(id=pid, low=low, high=high, value=value, flags=flags,
                                       fmt=values[8], choices=dict(zip(values[10:-1:2],values[11:-1:2])))
        elif path == '/strip/plugin/descriptor_end' and self.stage == 'descriptor' and values == [self.sid,self.plugin]:
            required = ([f'{prefix} {i}' for prefix in FIELDS.values() for i in range(8)] + ['Output gain','Enabled']) if self.mode == 'eq' else []
            if self.snapshot_invalid or not all(label in self.snapshot for label in required):
                self.ready = False; self.error = 'Profil LSP incomplet'
            else:
                # A descriptor snapshot in flight must not rewind a newer turn.
                for label, (value, edited_at) in list(self.pending.items()):
                    if label not in self.snapshot: continue
                    actual = self.snapshot[label]['value']
                    if self.snapshot_at <= edited_at:
                        self.snapshot[label]['value'] = value
                    elif math.isclose(value, actual, rel_tol=1e-5, abs_tol=1e-6):
                        del self.pending[label]
                    else:
                        # The DAW/automation is authoritative after a fresh read.
                        del self.pending[label]
                self.params = self.snapshot; self.ready = True; self.error = None
                self.last_valid = self.clock(); self.snapshots += 1
            self.stage = None; self.next_poll = self.clock() + self.POLL_INTERVAL
            self.render()

    def label(self, field, band=None):
        if field in ('output','enabled'): return {'output':'Output gain','enabled':'Enabled'}[field]
        return f'{FIELDS[field]} {self.filter if band is None else band}'

    def value(self, field, band=None): return self.params[self.label(field,band)]['value']

    def write(self, field, value, band=None):
        self.write_label(self.label(field,band),value)

    def write_label(self, label, value):
        if not self.usable() or not self.valid_target(): return
        param = self.params[label]
        value = float(max(param['low'],min(param['high'],value)))
        if not math.isfinite(value) or math.isclose(param['value'],value,rel_tol=1e-8,abs_tol=1e-9): return
        param['value'] = value; self.pending[label] = (value,self.clock()); self.edits += 1
        self.outgoing.append(osc('/strip/plugin/parameter',self.sid,self.plugin,param['id'],value))

    def turn(self, knob, delta):
        if not delta or not 0 <= knob < 8: return
        field = KNOBS[knob]; old = self.value(field)
        fine = bool(self.routing.mapper.modifiers)
        if field == 'frequency': value = old * 2**(delta/(240 if fine else 24))
        elif field in ('gain','output'): value = max(old,1e-6) * 10**(delta*(.05 if fine else .25)/20)
        elif field == 'q': value = old + delta*(.01 if fine else .05)
        elif field == 'width': value = old + delta*(.01 if fine else .1)
        else: value = round(old) + (1 if delta > 0 else -1)
        self.write(field,value)

    def parameter_list(self):
        rows = sorted(((label,p) for label,p in self.params.items() if not p['flags'] & 0x100), key=lambda x:x[1]['id'])
        if getattr(self,'plugin_name','') in COMPRESSORS:
            first = ('Attack threshold','Ratio','Attack time','Release time','Knee','Makeup gain','Wet gain','Output gain')
            rows.sort(key=lambda x:first.index(x[0]) if x[0] in first else 8+x[1]['id'])
        return rows

    def turn_parameter(self, knob, delta):
        rows = self.parameter_list(); index = self.page*8+knob
        if not delta or not 0 <= index < len(rows): return
        label,p = rows[index]; fine = bool(self.routing.mapper.modifiers)
        if getattr(self,'plugin_name','').startswith('LSP Compressor') and label in ('Attack threshold','Knee','Makeup gain','Wet gain','Output gain'):
            value = max(p['value'],1e-3)*10**(delta*(.05 if fine else .25)/20)
        elif getattr(self,'plugin_name','').startswith('LSP Compressor') and label in ('Attack time','Release time'):
            value = p['value']+delta*(.1 if fine else 1)
        elif getattr(self,'plugin_name','').startswith('LSP Compressor') and label == 'Ratio':
            value = p['value']+delta*(.02 if fine else .1)
        elif p['flags'] & 64: value = 1 if delta>0 else 0
        elif p['flags'] & 1 and p.get('choices'):
            choices = sorted(p['choices']); index = min(range(len(choices)),key=lambda i:abs(choices[i]-p['value']))
            value = choices[max(0,min(len(choices)-1,index+(1 if delta>0 else -1)))]
        elif p['flags'] & 3: value = round(p['value']) + (1 if delta>0 else -1)
        elif p['flags'] & 4 and p['low'] > 0:
            value = max(p['value'],p['low']) * (p['high']/p['low'])**(delta*(.001 if fine else .005))
        else: value = p['value'] + delta*(p['high']-p['low'])*(.001 if fine else .005)
        self.write_label(label,value)

    def render(self, now=None):
        if not self.active: return
        now = self.clock() if now is None else now
        blink = int(now*4)%2 == 0; slots = self.routing.display_slots()
        usable = self.usable()
        if self.mode != 'eq': self.render_browser(now); return
        for ch in range(1,9):
            on = self.sid in slots and ch == slots.index(self.sid)+1 and blink
            self.feedback.put(('led',ch-1,2),button_led(ch-1,2,on))
            self.feedback.put(('led',ch-1,3),button_led(ch-1,3,False))
            text = self.knob_text(ch-1) if usable else ('EQ WAIT' if not self.error else 'EQ ERROR')
            self.feedback.put(('value',ch),scribble(ch,text,False))
            band = ch-1; enabled = usable and self.value('type',band) != 0 and not self.value('mute',band)
            kind = TYPES[min(11,max(0,round(self.value('type',band))))] if usable else '...'
            if usable and self.value('mute',band): kind = 'MUTE'
            if self.error: kind = self.error
            text = ('>' if band == self.filter else ' ') + str(ch) + ' ' + kind
            self.feedback.put(('dsp',ch),dsp_text(ch,text))
            for key, state in ((0, band == self.filter and blink), (1,enabled), (2,usable and not enabled)):
                z = 0x0d+band; self.feedback.put(('led',z,key),button_led(z,key,state))
        self.feedback.put(('led',0x15,2),button_led(0x15,2,True))
        self.feedback.put(('led',0x15,10),button_led(0x15,10,usable and (not self.value('enabled') or not self.processor_enabled)))

    def knob_text(self, knob):
        n = self.filter+1; field = KNOBS[knob]; v = self.value(field)
        if field == 'frequency':
            if v >= 10000: return f'F{n} {v/1000:.1f}k'
            return f'F{n} {v/1000:.2f}k' if v >= 1000 else f'F{n} {v:.0f}Hz'
        if field == 'gain': return f'G{n} {20*math.log10(max(v,1e-9)):+.1f}'
        if field == 'q': return f'Q{n} {v:.2f}'
        if field == 'type': return f'T{n} '+TYPES[min(11,max(0,round(v)))]
        if field == 'slope': return f'S{n} x{round(v)+1}'
        if field == 'mode': return f'M{n} '+MODES[min(6,max(0,round(v)))]
        if field == 'width': return f'W{n} {v:.2f}o'
        return f'Out{20*math.log10(max(v,1e-9)):+.1f}'

    @staticmethod
    def short_plugin(name):
        if name in NAMES: return 'LSP EQ8'
        if name.startswith('LSP Compressor'): return 'LSP Comp'
        return name.replace('LSP ','').replace(' Stereo','').replace(' Mono','')[:8]

    def render_browser(self, now):
        usable = self.usable(); blink = int(now*4)%2 == 0; slots = self.routing.display_slots()
        parameters = self.parameter_list()
        for ch in range(1,9):
            target = self.sid in slots and ch == slots.index(self.sid)+1
            self.feedback.put(('led',ch-1,2),button_led(ch-1,2,False))
            self.feedback.put(('led',ch-1,3),button_led(ch-1,3,target and self.family=='comp' and self.mode=='params' and blink))
            index = (self.plugin_page if self.mode == 'browse' else self.page)*8+ch-1
            text = ''; value = ''; enabled = False; present = False
            if self.mode == 'browse' and index < len(self.plugins):
                pid,name,enabled = self.plugins[index]; present = True
                text = self.short_plugin(name); value = f'P{pid} '+('ON' if enabled else 'BYPASS')
            elif self.mode == 'params' and usable and index < len(parameters):
                label,p = parameters[index]; present = True; text = label[:8]
                value = self.parameter_text(label,p); enabled = True
            if not usable: text = (self.error or 'Charg...')[:8]
            elif not self.plugins: text = 'Vide' if ch==1 else ''
            self.feedback.put(('dsp',ch),dsp_text(ch,text))
            self.feedback.put(('value',ch),scribble(ch,value,False))
            for key,on in ((0,present and (self.mode=='browse' or ch-1==self.filter and blink)),
                           (1,present and enabled),(2,present and not enabled)):
                z=0x0c+ch;self.feedback.put(('led',z,key),button_led(z,key,on))
        self.feedback.put(('led',0x15,2),button_led(0x15,2,True))
        self.feedback.put(('led',0x15,10),button_led(0x15,10,usable and self.mode=='params' and not self.processor_enabled))

    def parameter_text(self, label, p):
        v = p['value']
        if p.get('choices'): return str(p['choices'].get(v,f'{v:.4g}'))[:8]
        if p['flags'] & 64: return 'ON' if v else 'OFF'
        if getattr(self,'plugin_name','').startswith('LSP Compressor'):
            if label in ('Attack threshold','Knee','Makeup gain','Wet gain','Output gain'):
                return '-inf dB' if v <= 0 else f'{20*math.log10(v):+.1f}dB'
            if label in ('Attack time','Release time'): return f'{v:.1f}ms'
            if label == 'Ratio': return f'{v:.2f}:1'
        return f'{v:.4g}'

    def status(self):
        return {'active':self.active,'ready':self.usable(),'mode':self.mode,'page':self.page+1,'plugin_page':self.plugin_page+1,'track':getattr(self,'route_name',None),
                'sid':self.sid,'plugin':self.plugin,'filter':self.filter+1,
                'error':self.error,'edits':self.edits,'snapshots':self.snapshots}
