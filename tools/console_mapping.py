"""Single-daemon mapping runtime: observe, isolate, route, and bounded output probes."""
# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import math
import json
import time
from collections import deque
from uuid import uuid4
from console_layout import elements, button_id
from console_presets import PresetStore, GUIDED, encoding, signature
from procontrol_mapping import split_commands, decode_command
from procontrol_pointer import decode_pointer
from procontrol_display import clock_command, clock_reference
from surface_feedback import ascii8, button_led, motor, meter


def suspend_plugin_window(follower):
    """Close editing UI while retaining the negotiated native capability."""
    supported=follower.supported;had_target=follower.target is not None
    follower.reset();follower.supported=supported
    return [('osc','/procontrol/plugin_ui/clear',[])] if had_target and supported else []


def input_value(c):
    d=decode_command(c)
    if len(c)==3 and c[0]==0x90 and c[1]<64 and c[2]<128:
        return dict(family='button',zone=c[2]&63,key=c[1]),dict(pressed=int(bool(c[2]&64)),value=int(bool(c[2]&64)))
    if d.get('fader_raw_10bit') is not None:
        return dict(family='fader',channel=d['track']),dict(value=d['fader_raw_10bit']/1023,raw=d['fader_raw_10bit'])
    if len(c) in (3,4) and c[0]==0xb0 and 64<=c[1]<=92 and c[2]<128:
        return dict(family='encoder',address=c[1]),dict(delta=c[2]-64,value=c[2]-64)
    p=decode_pointer(c)
    if p is not None:return dict(family='pointer'),dict(**p,value=p['dx'],delta=p['dx'])
    return None,{}


def rewrite_input(c, spec):
    if not spec:return c
    f=spec['family']
    if f=='button':return bytes([0x90,spec['key'],spec['zone']|(c[2]&64)])
    if f=='encoder':return bytes([c[0],spec['address'],*c[2:]])
    if f=='fader':return bytes([0xb0,spec['channel']-1,c[2],0x1f+spec['channel'],c[4]])
    return c


def output_spec(body):
    if len(body)==3 and body[0]==0x90:return dict(family='led',zone=body[2]&63,key=body[1])
    if len(body)==5 and body[0]==0xb0:return dict(family='motor',channel=body[1]+1)
    if len(body)>=7 and body[:3]==b'\xf0\x13\x00':
        family={0x10:'meter',0x40:'display',0x20:'automation',0:'ring'}.get(body[3])
        if body[3]==0x20 and body[4]==9:family='clock_mode'
        if body[3]==0 and body[4]==9:family='clock'
        if family:return dict(family=family,address=(body[4]&7) if family=='ring' else body[4])
    return None


def rewrite_output(body, spec):
    if spec['family']=='led':return button_led(spec['zone'],spec['key'],bool(body[2]&64))
    if spec['family']=='motor':return motor(spec['channel'],((body[2]<<3)|(body[4]>>4))/1023)
    result=bytearray(body)
    result[4]=(result[4]&0x40)|spec['address'] if spec['family']=='ring' else spec['address']
    return bytes(result)


def output_value(body):
    spec=output_spec(body)
    if not spec:return {}
    f=spec['family']
    if f=='led':return dict(value=int(bool(body[2]&64)))
    if f in ('automation','clock_mode'):return dict(value=int(bool(body[5])),mask=body[5])
    if f=='ring':return dict(value=int(bool((body[4]&64)|body[5]|body[6])))
    if f=='motor':return dict(value=((body[2]<<3)|(body[4]>>4))/1023)
    if f=='clock':
        table={v:k for k,v in clock_reference()['sevenseg'].items()}
        return dict(text=''.join(table.get(v,'?') for v in reversed(body[6:14])))
    if f=='display':return dict(text=body[6:-1].decode('ascii','replace').strip())
    if f=='meter':return dict(value=(((body[5]<<7)|body[6]).bit_count())/14)
    return {}


class MappingRuntime:
    MAX_LEARN=600
    LEASE=7
    def __init__(self,root,surface,feedback,routing,indicators,reset=lambda:None,pointer_guard=lambda active:None,clock=time.monotonic):
        self.store=PresetStore(root);self.surface=surface;self.feedback=feedback;self.routing=routing;self.indicators=indicators
        self.reset=reset;self.pointer_guard=pointer_guard;self.clock=clock
        self.catalog=elements();self.config=self.store.read()['active'];self.build_indexes()
        self.events=deque(maxlen=128);self.serial=0;self.epoch=uuid4().hex;self.seen=deque(maxlen=512)
        self.latest={};self.outputs={};self.normal={};self.output_revision=0
        self.learning=None;self.last_learning='Aucune capture active';self.candidates={};self.held=set();self.ignore=set();self.touch=set()
        self.press_bindings={};self.probe=None;self.speed=None;self.speed_at=-100;self.online=False;self.error=None
        self.pointer_bits=0;self.next_pointer_lease=0;self.counters=dict(duplicates=0,events=0,coalesced=0)
        feedback.mapping_hook=self.output;feedback.mapping_motor_guard=self.motor_guard
        for key,body in list(feedback.desired.items()):feedback.queue_body(key,feedback.effective(key))

    def suppress_pointer(self):
        choice=self.config['bindings'].get('pointer',{}).get(self.context(),{'kind':'inherit'})
        return bool(self.learning or choice['kind']!='inherit')

    def build_indexes(self):
        self.inputs={};self.original_inputs=set();self.out_defaults={};self.out_live={}
        for id,item in self.catalog.items():
            spec=self.config['protocol'].get(id,{}).get('input',item['input'])
            if item['input']:self.original_inputs.add(signature(item['input']))
            if spec:self.inputs[signature(spec)]=id
            target=self.config['protocol'].get(id,{}).get('output',item['output'])
            if target:self.out_live[signature(target)]=id
            if item['output']:self.out_defaults[signature(item['output'])]=id

    def emit(self, kind, **details):
        self.serial+=1;self.events.append(dict(id=self.serial,kind=kind,at=time.time(),**details))

    def feed(self,path,values,now):
        if path=='/transport_speed' and len(values)==1 and type(values[0]) in (int,float) and math.isfinite(values[0]):
            self.speed=values[0];self.speed_at=now

    def stopped(self):
        now=self.clock();ind=self.indicators
        return (self.online and self.speed==0 and now-self.speed_at<2 and ind.transport is not None
                and ind.received is not None and now-ind.received<2 and ind.transport[4]==0)

    def clear_actions(self):
        self.reset();self.surface.reset_inputs()
        self.routing.send_pending.clear();self.routing.deferred.clear();self.routing.automation_pending.clear()
        self.indicators.reset_range();self.press_bindings.clear()
        # Do not clear deduplication on mode transitions: a retransmission is not a new gesture.
        for key in list(self.feedback.queue):
            if key[0]=='motor':self.feedback.queue.pop(key,None)

    def start_learning(self,request):
        if self.learning:raise ValueError('Un apprentissage est déjà actif')
        if not self.stopped():raise ValueError('Ardour doit être arrêté, hors enregistrement, avec un état reçu depuis moins de 2 secondes')
        duration=request.get('seconds',600)
        if type(duration) is not int or not 10<=duration<=self.MAX_LEARN:raise ValueError('Durée de 10 à 600 secondes requise')
        if self.surface.touched:raise ValueError('Relâche les faders avant de démarrer la capture')
        self.pointer_guard(True)  # synchronous acknowledgement before accepting a gesture
        self.clear_actions();self.cancel_probe();self.candidates={}
        now=self.clock();token=uuid4().hex
        self.learning=dict(token=token,deadline=now+duration,lease=now+self.LEASE,element=request.get('element'))
        self.emit('learning',active=True);return dict(ok=True,token=token)

    def stop_learning(self,reason='Arrêt demandé'):
        if not self.learning:return
        self.learning=None;self.last_learning=reason;self.ignore.update(self.held)
        self.clear_actions();self.surface.touched.update(self.touch);self.surface.buttons=self.pointer_bits
        try:self.pointer_guard(False)
        except OSError:pass  # pointer lease expires independently, no held input is replayed
        self.emit('learning',active=False,reason=reason)

    def tick(self,now,online):
        if self.online and not online:self.cancel_probe();self.stop_learning('Console déconnectée')
        self.online=online
        if self.learning:
            if now>=self.learning['deadline']:self.stop_learning('Durée maximale atteinte')
            elif now>=self.learning['lease']:self.stop_learning('Page déconnectée : capture terminée')
            elif now-self.speed_at>=2 or self.speed!=0 or self.indicators.transport is None or self.indicators.transport[4]!=0:
                self.stop_learning('Transport modifié ou état périmé')
            elif now>=self.next_pointer_lease:
                # A log lease supplements per-frame suppression; it never replays input.
                self.next_pointer_lease=now+1
                return True
        if self.probe and (now>=self.probe['expires'] or (self.probe['spec']['family']=='motor' and self.probe['spec']['channel'] in self.surface.touched)):
            self.cancel_probe()
        return False

    def reconnect(self):
        self.cancel_probe();self.stop_learning('Console reconnectée');self.ignore.update(self.held)
        self.seen.clear();self.press_bindings.clear();self.touch.clear()

    def context(self):
        s=self.surface;eq=getattr(s,'eq',None)
        if s.modifiers:return 'modifier'
        if s.alpha:return 'alpha'
        if getattr(s,'monitor',None) and s.monitor.active:return 'monitor'
        if eq and eq.active:return eq.mode if eq.mode in ('browse','library','params') else 'eq'
        if s.nudge:return 'nudge'
        if s.editing.zoom_navigation:return 'zoom'
        return 'normal'

    def route(self,sequence,body,now=None):
        now=self.clock() if now is None else now;token=(sequence,body)
        if token in self.seen:self.counters['duplicates']+=1;return []
        self.seen.append(token);parts=list(split_commands(body));records=[]
        expanded=[]
        for c in parts:
            spec,values=input_value(c);expanded.append((c,spec,values))
            if spec and spec['family']=='pointer':
                for bit,number in ((0x20,1),(0x10,3)):
                    if (values['button_bits']^self.pointer_bits)&bit:
                        pressed=int(bool(values['button_bits']&bit))
                        expanded.append((c,dict(family='pointer_button',button=number),dict(value=pressed,pressed=pressed)))
                self.pointer_bits=values['button_bits']
        for c,spec,values in expanded:
            sig=signature(spec);id=self.inputs.get(sig)
            info=dict(hex=c[:96].hex(' '),encoding=spec,element=id,**values)
            if len(c)>96:info['truncated']=True
            if spec and spec['family'] in ('button','pointer_button'):
                if values['pressed']:self.held.add(sig)
                else:self.held.discard(sig)
                if spec.get('zone',99)<8 and spec['key']==9:
                    ch=spec['zone']+1
                    if values['pressed']:
                        self.touch.add(ch)
                        if self.probe and self.probe['spec'].get('family')=='motor' and self.probe['spec']['channel']==ch:self.cancel_probe()
                    else:self.touch.discard(ch);self.surface.touched.discard(ch)
                    if self.learning:self.surface.touched.update(self.touch)
            if id:self.latest[id]=dict(hex=info['hex'],**values,at=round(time.time(),3))
            self.counters['events']+=1
            if self.learning:
                key=c[:96].hex(' ') if not sig else repr(sig)
                candidate=self.candidates.get(key,dict(**info,count=0,min=values.get('raw',values.get('value')),max=values.get('raw',values.get('value'))))
                candidate.update(info);candidate['candidate_id']=key;candidate['count']+=1
                value=values.get('raw',values.get('value'))
                if value is not None:
                    candidate['min']=min(candidate['min'],value);candidate['max']=max(candidate['max'],value)
                if 'pressed' in values:candidate['press' if values['pressed'] else 'release']=c.hex(' ')
                if len(self.candidates)<64 or key in self.candidates:self.candidates[key]=candidate
            # Continuous values are coalesced in latest; edge events retain a bounded history.
            if spec is None or spec['family'] in ('button','pointer_button'):self.emit('input',**info)
            else:self.counters['coalesced']+=1
            blocked=sig in self.ignore or (sig in self.original_inputs and id is None)
            if blocked and not values.get('pressed',1):self.ignore.discard(sig)
            if spec and spec['family']=='fader' and signature(dict(family='button',zone=spec['channel']-1,key=9)) in self.ignore:blocked=True
            records.append((c,spec,id,values,blocked))
        if self.learning:return []
        # Preserve exact existing route semantics for the default preset.
        if not self.config['bindings'] and not self.config['protocol'] and not any(r[4] for r in records):
            return self.surface.route(sequence,body,now)
        result=[];self.surface.last_unknown=[];self.surface.last_button_presses=[]
        for c,spec,id,values,blocked in records:
            if blocked:continue
            modes=self.config['bindings'].get(id,{})
            choice=modes.get(self.context(),{'kind':'inherit'})
            # Pair each release with its press even if the modifier/mode changed meanwhile.
            sig=signature(spec)
            if spec and spec['family'] in ('button','pointer_button'):
                if values['pressed']:self.press_bindings[sig]=choice
                else:choice=self.press_bindings.pop(sig,choice)
            if choice['kind']=='disabled':continue
            if choice['kind']=='osc':
                trigger=choice['trigger']
                if trigger=='press' and not values.get('pressed'):continue
                if trigger=='release' and values.get('pressed',1):continue
                selected=[sid for sid in self.routing.rows if self.routing.cache.get(('/strip/select',sid),[sid,0])[1]]
                if any(a.get('source')=='selected' for a in choice['args']) and len(selected)!=1:
                    self.emit('mapping_error',element=id,reason='Aucune piste sélectionnée unique et connue');continue
                control=self.catalog[id]['input'] or spec or {}
                channel=control.get('channel',control.get('zone',99)+1 if control.get('zone',99)<8 else control.get('address',99)-63 if 64<=control.get('address',99)<=71 else 0)
                if any(a.get('source')=='channel' for a in choice['args']) and not channel:
                    self.emit('mapping_error',element=id,reason='Ce contrôle ne correspond pas à une tranche');continue
                source=dict(value=values.get('value',0),delta=values.get('delta',0),pressed=values.get('pressed',0),
                            channel=channel,
                            selected=selected[0] if len(selected)==1 else 0)
                args=[]
                for arg in choice['args']:
                    val=source[arg['source']] if 'source' in arg else arg['value']
                    args.append({'i':int,'f':float,'s':str}[arg['type']](val))
                # Expert paths use actual OSC SSIDs, bypassing slot translation.
                result.append(('direct_osc',choice['path'],args));continue
            if spec and spec['family']=='pointer':continue  # motion is handled by the guarded pointer worker
            if spec and spec['family']=='pointer_button' and choice['kind']=='inherit':
                result.append(('button',str(spec['button']),[values['pressed']]));continue
            canonical=self.catalog[id]['input'] if id else spec
            if choice['kind']=='guided':
                canonical=copy.deepcopy(self.catalog[GUIDED[choice['action']][1]]['input'])
                if canonical['zone']==0 and spec and spec.get('zone',99)<8:canonical['zone']=spec['zone']
            if spec and spec['family']=='pointer_button':c=bytes([0x90,0,64 if values['pressed'] else 0])
            command=rewrite_input(c,canonical)
            actions=self.surface.command(command,now)
            if actions is None:self.surface.last_unknown.append(c.hex(' '))
            else:
                result.extend(actions)
                if actions and len(command)==3 and command[0]==0x90 and command[2]&64:self.surface.last_button_presses.append((command[2]&63,command[1]))
        return result

    def output(self,key,body):
        spec=output_spec(body);id=self.out_defaults.get(signature(spec),self.out_live.get(signature(spec)))
        if not spec:return body
        target=self.config['protocol'].get(id,{}).get('output',spec)
        if target is None:return None
        body=rewrite_output(body,target);sig=signature(target)
        self.normal[sig]=dict(key=key,body=body,at=self.clock(),element=id)
        effective=self.probe['body'] if self.probe and sig==signature(self.probe['spec']) else body
        if id:
            row=dict(hex=effective.hex(' '),**output_value(effective))
            if self.outputs.get(id)!=row:self.outputs[id]=row;self.output_revision+=1
        return effective

    def motor_guard(self,key):
        return key[0]=='motor' and bool(self.learning)

    def start_probe(self,request):
        if not self.online:raise ValueError('Console hors ligne')
        if self.learning:raise ValueError('Termine l’apprentissage avant un test de sortie')
        if self.probe:raise ValueError('Un test est déjà actif')
        id=request['element']
        if id not in self.catalog:raise ValueError('Élément inconnu')
        spec=encoding(request.get('encoding') or self.config['protocol'].get(id,{}).get('output',self.catalog[id]['output']),'output')
        if not spec:raise ValueError('Adresse de sortie à identifier')
        if spec['family']=='motor' and spec!=self.catalog[id]['output']:raise ValueError('Le moteur doit conserver sa tranche et sa protection tactile')
        f=spec['family'];now=self.clock();sig=signature(spec);normal=self.normal.get(sig)
        if f=='motor':
            ch=spec['channel']
            if request.get('motor_confirmed') is not True:raise ValueError('Essai moteur explicite requis')
            if not self.stopped() or ch in self.surface.touched or ch in self.touch:raise ValueError('Moteur : transport arrêté et fader non touché requis')
            if not normal or now-normal['at']>5:raise ValueError('Position moteur récente inconnue')
            position=output_value(normal['body'])['value'];delta=request.get('delta',.025)
            if type(delta) not in (int,float) or not math.isfinite(delta) or not 0<abs(delta)<=.04:raise ValueError('Course moteur limitée à 4 %')
            body=motor(ch,max(0,min(1,position+delta)));key=('motor',ch)
        elif f=='led':body=button_led(spec['zone'],spec['key'],True);key=('led',spec['zone'],spec['key'])
        elif f=='meter':body=meter(spec['address'],-13);key=('meter',spec['address'])
        elif f=='display':body=bytes([240,19,0,64,spec['address'],0])+ascii8('TEST '+id.split('.')[-1])+bytes([247]);key=('mapping_display',spec['address'])
        elif f=='clock':body=clock_command('12345678');key=('clock',)
        elif f=='clock_mode':body=bytes.fromhex('f0 13 00 20 09 20 f7');key=('clock_mode',)
        elif f=='ring':body=bytes([240,19,0,0,spec['address'],1,0,247]);key=('pan',spec['address']+1)
        elif f=='automation':body=bytes([240,19,0,32,spec['address'],4,247]);key=('automation',spec['address']+1)
        else:raise ValueError('Famille non testable')
        if normal:key=normal['key']
        # Use the existing sender/ACK queue; never create an Ethernet socket here.
        self.probe=dict(element=id,spec=spec,key=key,body=body,expires=now+(1 if f=='motor' else 2))
        self.outputs[id]=dict(hex=body.hex(' '),**output_value(body));self.output_revision+=1
        self.feedback.sent.pop(key,None);self.feedback.queue[key]=body
        self.emit('probe',element=id,encoding=spec,seconds=1 if f=='motor' else 2)
        return dict(ok=True)

    def cancel_probe(self):
        if not self.probe:return
        p,self.probe=self.probe,None;key=p['key'];normal=self.normal.get(signature(p['spec']))
        self.feedback.queue.pop(key,None);self.feedback.sent.pop(key,None)
        if p['spec']['family']=='motor' and p['spec']['channel'] in (self.surface.touched|self.touch):return
        # Current normal value, updated throughout the probe; no saved stale state.
        if normal:restore=normal['body']
        else:
            restore=bytearray(p['body']);f=p['spec']['family']
            if f=='led':restore[2]&=63
            elif f=='display':restore[6:-1]=b' '*len(restore[6:-1])
            elif f=='clock':restore=clock_command('        ')
            else:restore[5:-1]=bytes(len(restore[5:-1]))
            restore=bytes(restore)
        self.feedback.queue[key]=restore
        self.outputs[p['element']]=dict(hex=restore.hex(' '),**output_value(restore));self.output_revision+=1
        self.emit('probe_end',element=p['element'])

    def snapshot(self,cursor=0):
        now=self.clock();learning=None
        if self.learning:learning=dict(active=True,remaining=max(0,round(self.learning['deadline']-now)),element=self.learning['element'])
        rows=[e for e in self.events if e['id']>cursor][-24:]
        gap=bool(self.events and cursor and cursor<self.events[0]['id']-1) or (rows and rows[0]['id']>cursor+1)
        result=dict(ok=True,epoch=self.epoch,cursor=self.serial,gap=bool(gap),events=rows,
                    inputs=dict(sorted(self.latest.items(),key=lambda row:row[1]['at'])[-96:]),outputs=self.outputs,output_revision=self.output_revision,
                    learning=learning,learning_note=self.last_learning,candidates=list(self.candidates.values()),
                    active={k:v for k,v in self.config.items() if k not in ('bindings','protocol')},
                    probe={k:v for k,v in self.probe.items() if k in ('element','expires')} if self.probe else None,
                    can_learn=self.stopped(),online=self.online,counters=self.counters,error=self.error)

        while len(json.dumps(result).encode())>60000:
            result['gap']=True;result['truncated']=True
            if result['inputs']:result['inputs'].pop(next(iter(result['inputs'])))
            elif result['candidates']:result['candidates'].pop(0)
            else:break
        return result

    def request(self,request):
        action=request.get('action')
        if action=='state':return self.snapshot(int(request.get('cursor',0)))
        if action=='learn_start':return self.start_learning(request)
        if action in ('learn_heartbeat','learn_stop','associate'):
            if not self.learning or request.get('token')!=self.learning['token']:raise ValueError('Capture expirée ou détenue par une autre page')
            if action=='learn_heartbeat':self.learning['lease']=self.clock()+self.LEASE;return dict(ok=True)
            if action=='learn_stop':self.stop_learning();return dict(ok=True)
            candidate=next((c for c in self.candidates.values() if c['candidate_id']==request.get('candidate_id')),None)
            if not candidate or not candidate['encoding']:raise ValueError('Sélectionne un geste capturé')
            self.store.mutate(dict(action='protocol',revision=request['revision'],element=request['element'],direction='input',encoding=candidate['encoding'],confirmed=request.get('confirmed'),note='Geste capturé '+candidate['hex']))
            return dict(ok=True)
        if action=='probe':return self.start_probe(request)
        if action=='probe_stop':self.cancel_probe();return dict(ok=True)
        if action in ('activate','rollback'):
            if self.learning:raise ValueError('Termine la capture avant d’appliquer')
            if not self.stopped():raise ValueError('Application : arrêter le transport et attendre son état courant')
            # Store validates and atomically commits before swapping the complete in-memory snapshot.
            def prepare():
                self.cancel_probe();self.clear_actions();self.ignore.update(self.held)
            state=self.store.mutate(request,before_commit=prepare)
            self.config=state['active'];self.build_indexes();self.outputs.clear();self.normal.clear()
            self.feedback.resync();self.routing.render();self.emit('activated',preset=self.config['preset'])
            return dict(ok=True,revision=state['revision'])
        raise ValueError('Commande Mapping inconnue')
