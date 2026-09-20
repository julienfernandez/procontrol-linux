"""Retours Ardour → ProControl : afficheurs, compteur, LEDs, faders et vumètres."""
# SPDX-License-Identifier: GPL-3.0-or-later
from collections import OrderedDict
import math
import re
import time
import unicodedata
from procontrol_display import clock_command, bbt_clock_command
from automation_modes import PATH as AUTO_PATH, mode_value, lamp_command


def ascii8(text):
    return unicodedata.normalize('NFKD',str(text)).encode('ascii','ignore')[:8].ljust(8,b' ')


def scribble(channel,text,lower=True):
    if not 1<=channel<=8:raise ValueError('Tranche 1..8')
    return bytes([0xf0,0x13,0,0x40,channel-1+(0x20 if lower else 0),0])+ascii8(text)+b'\xf7'


def button_led(zone,key,on):
    return bytes([0x90,key,zone|(0x40 if on else 0)])


def motor(channel,position):
    if not 1<=channel<=8 or not math.isfinite(position):raise ValueError('Fader invalide')
    raw=round(max(0.,min(1.,position))*1023)
    return bytes([0xb0,channel-1,raw>>3,0x20+channel-1,(raw&7)<<4])


def meter(channel,db):
    # 14 segments documentés dans ReaVumeter ; seuils de présentation locaux.
    thresholds=(-60,-50,-40,-32,-26,-21,-17,-13,-10,-7,-5,-3,-1,0)
    level=sum(db>=threshold for threshold in thresholds)
    bits=(1<<level)-1
    return bytes([0xf0,0x13,0,0x10,channel,(bits>>7)&0x7f,bits&0x7f,0xf7])


class SurfaceFeedback:
    SEND_INTERVAL = 0.002
    ACK_TIMEOUT = 0.100
    MOTOR_INTERVAL = 0.020
    PULSE_SECONDS = 0.350
    PULSE_MAX_WAIT = 1.0
    # Momentary commands only. Transport, REC, mute/solo, monitor and DSP LEDs
    # remain authoritative state indicators and are never flashed here.
    PULSE_BUTTONS = ({(0x18, n) for n in (0, 1, 3, 4)} |
                     {(8, n) for n in (0, 2, 4, 6)} |
                     {(0x19, n) for n in (0, 1, 2, 3, 5, 6, 7)} |
                     {(0x1b, n) for n in range(17) if n != 11} |
                     {(0x1c, n) for n in (0, 1, 2, 3, 4, 6, 7, 10)} |
                     {(0x17, n) for n in (0x28, 0x29, 0x30)})
    def __init__(self,mapper):
        self.mapper=mapper;self.queue=OrderedDict();self.sent={};self.active={}
        self.pending=None;self.last_send=0.;self.error=None;self.counts={'sent':0,'acked':0,'timeouts':0,'recoveries':0}
        self.desired={};self.retry_after=0.;self.failures=0;self.needs_refresh=False
        self.urgent_burst=0; self.pulses={}
        self.local_motor={};self.motor_echo=set()
        self.clock_mode='smpte';self.last_clock={};self.initialized=False
        self.eq=None;self.monitor=None;self.mix_values={}
        self.pending_items={};self.confirmed={};self.last_motor_send=-1.
        self.last_ack_ms=None;self.max_ack_ms=0.;self.motor_batches=0;self.motor_targets=0

    def put(self,key,body):
        self.desired[key]=body
        if key in self.pulses and body==button_led(key[1],key[2],True):
            self.pulses.pop(key)  # a real state update takes ownership
        self.queue_body(key,self.effective(key))

    def effective(self,key):
        return button_led(key[1],key[2],True) if key in self.pulses else self.desired[key]

    def queue_body(self,key,body):
        if self.sent.get(key)==body:
            self.queue.pop(key,None)
            return
        self.queue[key]=body

    def pulse_buttons(self,buttons,now=None):
        """Receipt of forwarded commands; not an Ardour execution acknowledgement."""
        now=time.monotonic() if now is None else now
        for zone,number in buttons:
            if (zone,number) not in self.PULSE_BUTTONS:continue
            key=('led',zone,number);on=button_led(zone,number,True)
            if self.desired.get(key)==on:continue
            self.desired.setdefault(key,button_led(zone,number,False))
            # Extend an existing pulse after another accepted press; do not
            # stack timers or queue old on/off edges during a burst.
            sent=self.sent.get(key)==on
            self.pulses[key]={'expires':now+self.PULSE_SECONDS if sent else None,
                              'latest_start':now+self.PULSE_MAX_WAIT}
            self.queue_body(key,on)

    def expire_pulses(self,now):
        for key,pulse in list(self.pulses.items()):
            deadline=pulse['expires'] if pulse['expires'] is not None else pulse['latest_start']
            if now>=deadline:
                self.pulses.pop(key)
                self.queue_body(key,self.desired[key])

    def initialize(self):
        self.pulses.clear()
        self.pending=None;self.error=None;self.sent.clear();self.queue.clear();self.active.clear()
        self.desired.clear();self.retry_after=0.;self.failures=0;self.needs_refresh=False
        self.pending_items.clear();self.confirmed.clear();self.last_motor_send=-1.
        for channel in range(1,9):
            self.put(('name',channel),scribble(channel,f'CH {channel:02d}'))
            self.put(('value',channel),scribble(channel,'Ardour',False))
            self.put(('automation',channel),lamp_command(channel,None))
        self.put(('clock_mode',),bytes.fromhex('f0 13 00 20 09 20 f7'))
        self.put(('clock',),clock_command('00000000'))
        self.put(('led',0x17,0x21),button_led(0x17,0x21,False))
        self.put(('led',0x18,2),button_led(0x18,2,False))
        self.put(('led',0x17,0x24),button_led(0x17,0x24,True))
        self.initialized=True

    def resync(self):
        """Replay current output after console reconnect, retaining motor guards."""
        self.pulses.clear()
        self.pending=None;self.error=None;self.sent.clear()
        self.pending_items.clear();self.confirmed.clear();self.last_motor_send=-1.
        self.desired[('led',0x18,2)]=button_led(0x18,2,self.mapper.editing.zoom_navigation)
        self.queue=OrderedDict(self.desired)
        self.local_motor.clear();self.motor_echo.clear()
        self.retry_after=0.;self.failures=0;self.needs_refresh=False

    def local(self,action):
        kind,path,values=action
        if kind=='osc' and path=='/strip/fader':
            channel,value=values;body=motor(channel,float(value));key=('motor',channel)
            self.local_motor[channel]=body
            self.motor_echo.add(channel)
            self.put(key,body)
        elif kind=='osc' and path=='/strip/gain/touch':
            channel,on=values;key=('motor',channel)
            if on:
                # Discard an old DAW target before taking local ownership.
                self.queue.pop(key,None);self.motor_echo.discard(channel)
            elif channel in self.local_motor:
                # ProControl's reference driver echoes the final target at
                # touch release. Do not delay it behind the DAW holdoff.
                body=self.local_motor[channel];self.motor_echo.add(channel)
                self.desired[key]=body;self.queue[key]=body
        if kind=='led':
            zone,key=map(int,path.split(':'));self.put(('led',zone,key),button_led(zone,key,values[0]))
        if kind=='mode' and path=='clock':
            self.clock_mode=values[0]
            self.put(('clock_mode',),bytes([0xf0,0x13,0,0x20,9,8 if self.clock_mode=='bbt' else 32,0xf7]))
            if self.clock_mode in self.last_clock:self.clock(self.clock_mode,self.last_clock[self.clock_mode])

    def clock(self,mode,text):
        self.last_clock[mode]=str(text)
        if mode!=self.clock_mode:return
        if mode=='bbt':
            self.put(('clock',),bbt_clock_command(text));return
        digits=re.sub('[^0-9]','',str(text))[-8:].rjust(8,'0')
        body=bytearray(clock_command(digits));body[5]=0x2a
        self.put(('clock',),bytes(body))

    def feed(self,path,values):
        if path==AUTO_PATH and len(values)==2 and type(values[0]) is int and 1<=values[0]<=8:
            channel=values[0];mode=mode_value(values[1])
            if mode is None:self.mapper.state.pop((path,channel),None)
            else:self.mapper.feedback(path,[channel,mode])
            self.put(('automation',channel),lamp_command(channel,mode))
            return
        self.mapper.feedback(path,values)
        if not values:return
        if path in ('/position/smpte','/position/bbt'):
            self.clock(path.rsplit('/',1)[1],values[0]);return
        transport={'/transport_play':(0x1c,0x10),'/transport_stop':(0x1c,0x0f),
                   '/rewind':(0x1c,0x0d),'/ffwd':(0x1c,0x0e),'/rec_enable_toggle':(0x1c,0x11),
                   '/loop_toggle':(0x1c,9),'/cancel_all_solos':(8,0x14)}
        if path in transport:
            z,k=transport[path];self.put(('led',z,k),button_led(z,k,bool(values[0])));return
        if not path.startswith('/strip/') or len(values)<2:return
        channel=int(values[0]);value=values[1]
        if not 1<=channel<=8:return
        if path=='/strip/name':
            self.active[channel]=bool(str(value).strip())
            self.put(('name',channel),scribble(channel,value))
        elif path=='/strip/fader':
            # Incoming DAW echoes must not overwrite the target sampled from
            # the physical fader while touched or while its release settles.
            if channel in self.mapper.touched or time.monotonic()-self.mapper.fader_moved.get(channel,-100)<0.3:
                return
            self.motor_echo.discard(channel)
            self.put(('motor',channel),motor(channel,float(value)))
            # gainmode=2 supplies dB separately: fader feedback drives only
            # the motor, so the display does not alternate percent and dB.
        elif path=='/strip/gain':
            body=scribble(channel,f'{float(value):+.1f} dB',False)
            self.mix_values[channel]=body
            if (self.eq is None or not self.eq.active) and (self.monitor is None or not self.monitor.active):self.put(('value',channel),body)
        elif path in ('/strip/mute','/strip/solo','/strip/select','/strip/recenable'):
            k={'/strip/mute':8,'/strip/solo':7,'/strip/select':6,'/strip/recenable':0}[path]
            self.put(('led',channel-1,k),button_led(channel-1,k,bool(value)))
        elif path=='/strip/pan_stereo_position':
            position=max(0.,min(1.,float(value)));index=round(position*14)
            pattern=[(0x40,0,0),(0,64,0),(0,32,0),(0,16,0),(0,8,0),(0,4,0),(0,2,0),
                     (0,1,0),(0,0,64),(0,0,32),(0,0,16),(0,0,8),(0,0,4),(0,0,2),(0,0,1)][index]
            self.put(('pan',channel),bytes([0xf0,0x13,0,0,(channel-1)|pattern[0],pattern[1],pattern[2],0xf7]))

    def end_eq_display(self):
        for channel in range(1,9):
            self.put(('value',channel),self.mix_values.get(channel,scribble(channel,'',False)))

    def meter_address(self,address,db):
        self.put(('meter',address),meter(address,db))

    def strip_meter(self,channel,left,right):
        self.meter_address(channel-1,left)
        self.meter_address(channel-1+32,right)

    def clear_strip_meter(self,channel):
        self.strip_meter(channel,-193.,-193.)

    def acknowledge(self,h,now=None):
        if self.pending and h.get('command_field')==0xa0 and h.get('ack_candidate')==self.pending[0]:
            now=time.monotonic() if now is None else now
            self.last_ack_ms=max(0.,(now-self.pending[1])*1000)
            self.max_ack_ms=max(self.max_ack_ms,self.last_ack_ms)
            self.confirmed.update(self.pending_items);self.pending_items.clear()
            self.pending=None;self.counts['acked']+=1
            if self.failures:self.counts['recoveries']+=1
            self.failures=0;self.error=None;self.retry_after=0.

    def is_local_echo(self,key):
        return (key[0]=='motor' and key[1] in self.motor_echo
                and self.queue.get(key)==self.local_motor.get(key[1]))

    def motor_blocked(self, key, now):
        if key[0] != 'motor':return False
        channel=key[1]
        if self.is_local_echo(key):return False
        return (not self.active.get(channel,False) or channel in self.mapper.touched
                or now-self.mapper.fader_moved.get(channel,-100)<0.3)

    def wait_timeout(self, now, maximum=0.05):
        if self.pulses:
            due=min(p['expires'] if p['expires'] is not None else p['latest_start'] for p in self.pulses.values())
            maximum=min(maximum,max(0.,due-now))
        if self.pending:
            return min(maximum,max(0.,self.pending[1]+self.ACK_TIMEOUT-now))
        deadlines=[]
        for key in self.queue:
            if self.motor_blocked(key,now):continue
            due=max(self.retry_after,self.last_send+self.SEND_INTERVAL)
            if key[0]=='motor' and not self.is_local_echo(key):
                due=max(due,self.last_motor_send+self.MOTOR_INTERVAL)
            deadlines.append(due)
        return min(maximum,max(0.,min(deadlines)-now)) if deadlines else maximum

    def status(self,now=None):
        now=time.monotonic() if now is None else now
        return dict(pending_sequence=self.pending[0] if self.pending else None,
                    pending_ms=round((now-self.pending[1])*1000,3) if self.pending else 0,
                    last_ack_ms=self.last_ack_ms,max_ack_ms=self.max_ack_ms,
                    motor_batches=self.motor_batches,motor_targets=self.motor_targets,
                    queued_motors=sum(k[0]=='motor' for k in self.queue),
                    motor_hz=1/self.MOTOR_INTERVAL,ack_timeout_ms=self.ACK_TIMEOUT*1000,button_pulses=len(self.pulses))

    def next_frame(self,session,now=None):
        now=time.monotonic() if now is None else now
        self.expire_pulses(now)
        if not session.online_acked:return None
        if self.pending:
            if now-self.pending[1]>=self.ACK_TIMEOUT:
                self.counts['timeouts']+=1;self.failures+=1
                self.error='ACK manquant ; reprise automatique des retours'
                self.pending=None
                # Only invalidate the unconfirmed packet. Rebuild these keys
                # from CURRENT desired state; never replay a previous trajectory
                # or all the LCDs/LEDs because a single ACK was lost.
                for key in self.pending_items:
                    self.sent.pop(key,None);self.confirmed.pop(key,None)
                    if key in self.desired:self.queue[key]=self.effective(key)
                self.pending_items.clear()
                delay=0. if self.failures<=2 else min(2.,.1*2**min(self.failures-3,5))
                self.retry_after=now+delay
                if self.failures==3:self.needs_refresh=True
            return None
        if now<self.retry_after:return None
        if now-self.last_send<self.SEND_INTERVAL:return None
        keys=list(self.queue)
        # Four urgent outputs maximum before servicing the oldest output.
        # Coalescing retains only the newest clock/meter value.
        if self.urgent_burst<4:
            keys.sort(key=lambda k: -1 if self.is_local_echo(k) else 0 if k[0]=='clock' else 1 if k[0]=='motor' else 2 if k[0] in ('led','automation') else 3)
        for key in keys:
            if key[0]=='motor':
                channel=key[1]
                if not self.is_local_echo(key):
                    if not self.active.get(channel,False):self.queue.pop(key);continue
                    if self.motor_blocked(key,now):continue
                    if now<self.last_motor_send+self.MOTOR_INTERVAL:continue
            self.urgent_burst=self.urgent_burst+1 if self.is_local_echo(key) or key[0] in ('clock','led','automation','motor') else 0
            if self.urgent_burst>4:self.urgent_burst=0
            selected=[key]
            if key[0]=='motor' and not self.is_local_echo(key):
                selected += [k for k in self.queue if k!=key and k[0]=='motor'
                             and not self.is_local_echo(k) and not self.motor_blocked(k,now)]
                selected=selected[:8]
                self.last_motor_send=now
                self.motor_batches+=1;self.motor_targets+=len(selected)
            self.pending_items={k:self.queue.pop(k) for k in selected}
            for k in selected:
                if k in self.pulses and self.pulses[k]['expires'] is None:
                    self.pulses[k]['expires']=now+self.PULSE_SECONDS
            body=b''.join(self.pending_items.values())
            session.sequence+=1
            frame=session.frame(0,count=len(selected),sequence=session.sequence,body=body)
            self.sent.update(self.pending_items);self.pending=(session.sequence,now);self.last_send=now;self.counts['sent']+=1
            return frame
        return None
