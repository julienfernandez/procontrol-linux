"""Mapping fonctionnel ProControl → Ardour/X11, dérivé de la table GPL ReaControl24."""
# SPDX-License-Identifier: GPL-3.0-or-later
from collections import deque
import time
from procontrol_mapping import mapping_tree, split_commands, decode_command
from procontrol_pointer import decode_pointer

# Coordonnées physiques (zone, numéro), conservées même quand le libellé tiers est incomplet.
# OSC directs : sources Ardour 8.4 osc.cc ; actions : /etc/ardour8/ardour.keys.
OSC_BUTTONS = {
    (0x1c,0x06):'/goto_start', (0x1c,0x07):'/goto_end',
    (0x1c,0x0d):'/rewind', (0x1c,0x0e):'/ffwd',
    (0x1c,0x0f):'/transport_stop', (0x1c,0x10):'/transport_play',
    (0x1c,0x11):'/rec_enable_toggle', (0x1c,0x09):'/loop_toggle',
    (0x1c,0x02):'/toggle_punch_in', (0x1c,0x03):'/toggle_punch_out',
    (0x19,0x06):'/undo', (0x19,0x07):'/save_state',
    (0x08,0x00):'/refresh', (0x08,0x02):'/add_marker',
    (0x08,0x04):'/prev_marker', (0x08,0x06):'/next_marker',
    (0x08,0x01):'/rec_enable_toggle', (0x08,0x14):'/cancel_all_solos',
    (0x16,0x05):'/toggle_monitor_mono', (0x16,0x06):'/toggle_monitor_dim',
    (0x16,0x07):'/toggle_monitor_mute',
}
ACTION_BUTTONS = {
    (0x19,0x00):'Common/show-mixer', (0x19,0x01):'Common/show-editor',
    (0x19,0x02):'Common/toggle-meterbridge', (0x19,0x05):'Window/toggle-locations',
    (0x1b,0x04):'Editor/editor-cut', (0x1b,0x05):'Editor/editor-copy',
    (0x1b,0x06):'Editor/editor-paste', (0x1b,0x07):'Editor/editor-delete',
    (0x1b,0x08):'Editor/split-region',
    (0x1b,0x0d):'MouseMode/set-mouse-mode-timefx',
    (0x1b,0x0e):'MouseMode/set-mouse-mode-range',
    (0x1b,0x0f):'MouseMode/set-mouse-mode-object',
    (0x1b,0x10):'MouseMode/set-mouse-mode-draw',
    (0x17,0x30):'Main/Escape',
    (0x08,0x05):'Common/show-editor',
    (0x15,0x09):'Mixer/ab-plugins',
    (0x1b,0x09):'Editor/set-loop-from-edit-range',
    (0x1c,0x00):'Region/play-selected-regions',
    (0x1c,0x01):'Transport/PlayPreroll',
    (0x1c,0x05):'Transport/ToggleExternalSync',
    (0x1c,0x08):'Transport/ToggleExternalSync',
    (0x1c,0x0b):'Transport/TogglePunch',
}
NUMPAD = {**{i:str(i) for i in range(10)}, 10:'BackSpace', 11:'equal',
          12:'slash',13:'asterisk',14:'minus',15:'plus',16:'period',17:'Return'}
MODIFIERS = {0x23:'Shift_L',0x24:'Alt_L',0x25:'Control_L',0x26:'Control_R'}
ALPHA_EXTRA = {0x1b:'Shift_R',0x1f:'BackSpace',0x20:'space'}


def button_info(command):
    if len(command) != 3 or command[0] != 0x90 or command[2] & 0x80:
        return None
    key, zone = command[1], command[2] & 0x3f
    tree = mapping_tree()[0x90]['Children']
    if zone in tree[8]['Children']:
        group = tree[8]['Children'][zone]
        node = group.get('Children',{}).get(key)
        if node is None: return None
        return {'zone':zone,'key':key,'pressed':bool(command[2]&0x40),
                'label':node.get('Address',f'DSP {key+1}'),'group':group.get('Address','Numeric keypad')}
    if 0 <= zone < 8:
        node = tree[0]['Children'].get(key)
        if node is not None:
            return {'zone':zone,'key':key,'pressed':bool(command[2]&0x40),
                    'label':node.get('Address',''),'group':f'Channel {zone+1}'}
    return None


def osc(path,*values): return ('osc',path,list(values))
def select_strip(ssid):
    # Ardour 8.4 _strip_parse ignores 1 and selects on 0.
    return osc('/strip/select',ssid,0)

def key(name,pressed): return ('key',name,[int(pressed)])
def led(zone,number,on): return ('led',f'{zone}:{number}',[int(on)])


class SurfaceMap:
    def __init__(self):
        self.seen=deque(maxlen=512); self.state={}; self.alpha=False; self.caps=False
        self.modifiers=set(); self.held_keys={}; self.buttons=0
        self.matrix_mode='select'; self.matrix_bank=0; self.bank_start=1; self.nudge=False
        self.encoder_mode='pan'; self.send_index=1; self.plugin_index=1
        self.master_mode=False; self.jog_gain=1.; self.automation_target='gain'
        self.touched=set(); self.fader_moved={}; self.clock_mode='smpte'; self.jog_mode=0
        self.last_unknown=[]
        self.auto_held=set()

    def reset_inputs(self):
        if getattr(self,'eq',None) is not None:self.eq.exit('Console reconnectée')
        self.seen.clear(); self.alpha=False; self.caps=False; self.modifiers.clear()
        self.held_keys.clear(); self.buttons=0; self.touched.clear()
        self.auto_held.clear()
        return [('release_all','',[]),led(0x17,0x21,False)]

    def invalidate_selected(self, plugin_only=False):
        prefixes=('/select/plugin/',) if plugin_only else ('/select/',)
        self.state={k:v for k,v in self.state.items() if not k[0].startswith(prefixes)}

    def feedback(self,path,values):
        if path=='/select/name':self.invalidate_selected()
        elif path=='/select/plugin/name':self.invalidate_selected(plugin_only=True)
        if values:
            if (path.startswith('/strip/') or path.startswith('/select/plugin/parameter') or path.startswith('/select/send_')) and len(values)>=2:
                self.state[(path,int(values[0]))]=values[1]
            else: self.state[(path,None)]=values[0]

    def toggle(self,path,ssid=None):
        value=0 if self.state.get((path,ssid),0) else 1
        self.state[(path,ssid)]=value
        return osc(path,*([ssid] if ssid is not None else []),value)

    def route(self,sequence,body,now=None):
        token=(sequence,body)
        if token in self.seen:return []
        self.seen.append(token); now=time.monotonic() if now is None else now
        actions=[]; self.last_unknown=[]
        for command in split_commands(body):
            result=self.command(command,now)
            if result is None:self.last_unknown.append(command.hex(' '))
            else:actions.extend(result)
        return actions

    def command(self,c,now):
        if getattr(self,'eq',None) is not None:
            result=self.eq.command(c)
            if result is not None:return result
        pointer=decode_pointer(c)
        if pointer is not None:
            bits=pointer['button_bits']; result=[]
            for bit,number in ((0x20,1),(0x10,3)):
                if (bits^self.buttons)&bit:result.append(('button',str(number),[int(bool(bits&bit))]))
            self.buttons=bits
            return result
        if len(c)==5 and c[0]==0xb0 and c[1]<8:
            decoded=decode_command(c)
            if decoded.get('status')!='mapped_reference':return None
            channel=c[1]+1; self.fader_moved[channel]=now
            return [osc('/strip/fader',channel,decoded['fader_raw_10bit']/1023.)]
        if len(c) in (3,4) and c[0]==0xb0 and c[1]>=0x40 and c[2]<128:
            delta=c[2]-64
            if not delta:return []
            if c[1]==0x5c:
                return [osc('/jog',float(delta)*self.jog_gain)]
            # Local capture dsp-encoders-take2-20260914: top to bottom 4d..54.
            # Dedicated DSP controls always address the selected plugin page.
            if len(c)==3 and 0x4d<=c[1]<=0x54:
                channel=c[1]-0x4d+1
                path='/select/plugin/parameter';token=(path,channel)
                if token not in self.state:return []
                step=delta*(0.002 if self.modifiers else 0.01)
                value=max(0.,min(1.,self.state[token]+step))
                self.state[token]=value
                return [osc(path,channel,value)]
            if 0x40<=c[1]<0x48:
                channel=c[1]-0x40+1
                step=delta*(0.002 if self.modifiers else 0.01)
                if self.encoder_mode=='pan':
                    path='/strip/pan_stereo_position'; old=self.state.get((path,channel),0.5)
                    # ProControl pan rotation is reversed relative to Ardour's 0=L, 1=R.
                    value=max(0.,min(1.,old-step));self.state[(path,channel)]=value
                    return [osc(path,channel,value)]
                if self.encoder_mode=='send':
                    return [('send_delta','',[channel,self.send_index,step])]
                if self.encoder_mode=='plugin':
                    path='/select/plugin/parameter';token=(path,channel)
                    if token not in self.state:return [osc('/refresh',1.0)]
                    value=max(0.,min(1.,self.state[token]+step));self.state[token]=value
                    return [osc(path,channel,value)]
            return None
        info=button_info(c)
        if info is None:return None
        z,n,on=info['zone'],info['key'],info['pressed']; physical=(z,n)
        # Releases use the key chosen at press time, even if ALPHA has since changed.
        if not on and physical in self.held_keys:
            name=self.held_keys.pop(physical)
            self.modifiers.discard(name)
            return [key(name,False)]
        if z==0x17 and n==0x21:
            if not on:return []
            self.alpha=not self.alpha; self.held_keys.clear();self.modifiers.clear()
            return [('release_all','',[]),led(z,n,self.alpha),('mode','alpha',[self.alpha])]
        if z==8 and n in MODIFIERS:
            name=MODIFIERS[n]
            if on:self.modifiers.add(name);self.held_keys[physical]=name
            else:self.modifiers.discard(name)
            return [key(name,on)]
        if self.alpha and z==0x17 and 1<=n<=32:
            if not on:return []
            if n==0x1c:
                self.caps=not self.caps
                return [led(z,n,self.caps)]
            if n in (0x1d,0x1e):return [('text','numbersign' if n==0x1d else 'ampersand',[])]
            name=chr(96+n) if n<=26 else ALPHA_EXTRA.get(n)
            if not name:return []
            if n<=26 and self.caps:name=name.upper()
            self.held_keys[physical]=name
            return [key(name,True)]
        if z==0x1a:
            name=NUMPAD.get(n)
            if name and on:self.held_keys[physical]=name;return [key(name,True)]
            return []
        if z<8:
            channel=z+1
            if n==5:
                if not on:
                    self.auto_held.discard(channel);return []
                if channel in self.auto_held:return []
                self.auto_held.add(channel)
                backwards=bool(self.modifiers & {'Shift_L','Shift_R'})
                return [('automation','cycle',[channel,-1 if backwards else 1])]
            if n==9:
                if on:self.touched.add(channel)
                else:self.touched.discard(channel)
                return [osc('/strip/gain/touch',channel,int(on))]
            if not on:return []
            if n in (0,7,8):
                return [self.toggle({0:'/strip/recenable',7:'/strip/solo',8:'/strip/mute'}[n],channel)]
            if n==6:return [select_strip(channel)]
            if n in (1,2,3,10):
                self.encoder_mode='pan' if n==1 else 'plugin'
                return [select_strip(channel),osc('/select/expand',1)]
            return None
        if not on:return []
        if z==8 and n in (0,2,4,6) and self.modifiers:
            return [osc('/access_action',{0:'Editor/zoom-to-session',
                2:'Editor/zoom-to-selection',4:'Editor/temporal-zoom-out',
                6:'Editor/temporal-zoom-in'}[n])]
        if z==8 and n in (0x18,0x1a,0x1c,0x1d):
            self.automation_target={0x18:'gain',0x1a:'pan',0x1c:'mute',0x1d:'trimdB'}[n]
            return [led(z,k,k==n) for k in (0x18,0x1a,0x1c,0x1d)]
        if physical in ((0x19,4),(0x15,1)):
            self.encoder_mode='plugin'
            return [osc('/select/expand',1),('mode','encoders',['plugin'])]
        if physical in OSC_BUTTONS:
            path=OSC_BUTTONS[physical]
            if physical==(0x19,6) and self.modifiers:path='/redo'
            return [osc(path,1.0)]
        if physical in ACTION_BUTTONS:return [osc('/access_action',ACTION_BUTTONS[physical])]
        if z==0x1b and n in (0x0a,0x0c):
            if self.nudge:return [osc('/select/previous' if n==0x0a else '/select/next',1.0)]
            direction=-1 if n==0x0a else 1
            return [('bank','delta',[direction])]
        if z==0x1b and n==0x0b:
            self.nudge=not self.nudge;return [led(z,n,self.nudge)]
        if z==0x1b and n in (0,1,2,3):
            # Correspondances Ardour explicites : ripple, slide, verrouillage, grille.
            return [osc('/access_action',{0:'Editor/set-edit-ripple',1:'Editor/set-edit-slide',
                                         2:'Editor/set-edit-lock',3:'Editor/cycle-snap-mode'}[n])]
        if z==0x1c and n in (0x12,0x13):
            mode=2 if n==0x12 else 3;self.jog_mode=0 if self.jog_mode==mode else mode
            return [osc('/jog/mode',float(self.jog_mode)),led(0x1c,0x12,self.jog_mode==2),led(0x1c,0x13,self.jog_mode==3)]
        if z==0x17:
            if n in (0x24,0x25,0x26,0x27):
                self.matrix_mode={0x24:'select',0x25:'mute',0x26:'solo',0x27:'recenable'}[n]
                return [led(z,k,k==n) for k in (0x24,0x25,0x26,0x27)]
            if 0x2c<=n<=0x2f:
                self.matrix_bank=(n-0x2c)*32
                return [led(z,k,k==n) for k in range(0x2c,0x30)]
            if 1<=n<=32:
                return [('matrix',self.matrix_mode,[self.matrix_bank+n])]
            if n==0:return [osc('/select/expand',1)]
            if n==0x23:
                self.master_mode=not self.master_mode;self.bank_start=1
                return [('bank','master',[self.master_mode]),led(z,n,self.master_mode)]
            if n==0x28:return [osc('/quick_snapshot_stay',1.0)]
            if n==0x29:return [osc('/cancel_all_solos',1.0)]
            if n==0x2a:return [osc('/select/plug_page',-1.0 if self.modifiers else 1.0)]
            if n==0x2b:return [osc('/access_action','Common/show-mixer')]
        if physical==(8,0x09):
            path='/select/polarity'
            if (path,None) not in self.state:return [osc(path)]
            return [self.toggle(path)]
        if physical==(8,0x0d):
            path='/select/send_enable'; token=(path,self.send_index)
            if token not in self.state:return [osc('/refresh',1.0)]
            return [self.toggle(path,self.send_index)]
        if z==8 and n in (0x17,0x19,0x1b,0x1f,0x21):
            return [osc('/select/'+self.automation_target+'/automation',{0x17:2,0x19:3,0x1b:4,0x1f:1,0x21:0}[n])]
        if z==8 and n in (0x08,0x0e,0x10,0x12,0x0f,0x11):
            self.encoder_mode='pan' if n==8 else 'send'
            self.send_index={0x0e:1,0x10:2,0x12:3,0x0f:4,0x11:5}.get(n,1)
            return [('mode','encoders',[self.encoder_mode,self.send_index]),led(z,n,True)]
        if z==0x15 and n==0:
            self.clock_mode='bbt' if self.clock_mode=='smpte' else 'smpte'
            return [('mode','clock',[self.clock_mode])]
        if z==0x15 and n in (2,3):
            self.encoder_mode='plugin' if n==2 else 'send'
            return [osc('/select/expand',1),('mode','encoders',[self.encoder_mode])]
        if z==0x15 and n in (5,8):return [osc('/use_group',float(n==5))]
        if z==0x15 and n in (6,10) or physical==(8,3):
            return [self.toggle('/select/plugin/activate')]
        return None
