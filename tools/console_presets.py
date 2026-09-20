"""Atomic versioned console calibration and DAW presets; no network side effects."""
# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import fcntl
import json
import math
import os
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from console_layout import elements, MODES

BUILTIN = 'ardour-current'
LEVELS = {'unknown', 'documented', 'observed', 'confirmed'}
# Only existing behaviors, routed through the normal bank/mode machinery.
GUIDED = {
    'play': ('Lecture', 'button.1c.10'), 'stop': ('Stop', 'button.1c.0f'),
    'record': ('Enregistrement', 'button.1c.11'), 'save': ('Enregistrer la session', 'button.19.07'),
    'undo': ('Annuler', 'button.19.06'), 'eq': ('Ouvrir EQ de la tranche', 'button.00.02'),
    'dyn': ('Ouvrir dynamique de la tranche', 'button.00.03'),
    'mute': ('Mute de la tranche', 'button.00.08'), 'solo': ('Solo de la tranche', 'button.00.07'),
    'select': ('Sélectionner la tranche', 'button.00.06'),
    'bank_next': ('Banque suivante', 'button.1b.0c'), 'bank_previous': ('Banque précédente', 'button.1b.0a'),
}

def builtin():
    return dict(id=BUILTIN,name='Ardour — configuration actuelle',adapter='ardour',revision=1,protected=True,bindings={})


def default_state():
    return dict(version=1,revision=0,protocol={},positions={},validations={},presets={},
                active=dict(preset=BUILTIN,name=builtin()['name'],revision=1,bindings={},protocol={}),previous=None)


def encoding(value, direction):
    if value is None:return None
    if not isinstance(value,dict):raise ValueError('Encodage structuré requis')
    family=value.get('family')
    shapes={'button':{'family','zone','key'},'led':{'family','zone','key'},
            'encoder':{'family','address'},'fader':{'family','channel'},'pointer':{'family'},'pointer_button':{'family','button'},
            'meter':{'family','address'},'display':{'family','address'},'motor':{'family','channel'},
            'clock':{'family','address'},'clock_mode':{'family','address'},'ring':{'family','address'},'automation':{'family','address'}}
    allowed={'button','encoder','fader','pointer','pointer_button'} if direction=='input' else {'led','meter','display','motor','clock','clock_mode','ring','automation'}
    if family not in allowed or set(value)!=shapes[family]:raise ValueError('Famille ou champs d’encodage invalides')
    for k,v in value.items():
        if k!='family' and type(v) is not int:raise ValueError('Adresse entière requise')
    if family=='pointer_button' and value['button'] not in (1,3):raise ValueError('Clic gauche ou droit requis')
    if family in ('button','led') and not (0<=value['zone']<=28 and 0<=value['key']<64):raise ValueError('Zone/code hors limites')
    if family in ('fader','motor') and not 1<=value['channel']<=8:raise ValueError('Tranche hors limites')
    if family in ('encoder','meter','display','ring','automation','clock','clock_mode'):
        n=value['address']
        valid=(64<=n<=92) if family=='encoder' else (n==9) if family in ('clock','clock_mode') else (0<=n<8) if family in ('ring','automation') else (0<=n<64)
        if not valid:raise ValueError('Adresse hors limites')
    return copy.deepcopy(value)


def signature(spec):
    return tuple(sorted(spec.items())) if spec else None


def validate_protocol(protocol):
    if not isinstance(protocol,dict) or len(protocol)>450:raise ValueError('Calibration invalide')
    catalog=elements()
    for id, spec in protocol.items():
        if id not in catalog or not isinstance(spec,dict) or set(spec)-{'input','output'}:raise ValueError('Élément/encodage inconnu')
        for direction, value in spec.items():
            encoding(value,direction)
            # Do not silently change the type of an already established device.
            original=catalog[id][direction]
            if value and original and value['family']!=original['family']:raise ValueError('Famille différente du contrôle existant')
            if original and original['family'] in ('motor','fader','pointer','pointer_button') and value!=original:raise ValueError('Conserver les protections de tranche et le paquet pointeur établis')
            if not original and direction=='input' and value and value['family'] not in ('button','encoder'):raise ValueError('Apprentissage réservé aux boutons et encodeurs inconnus')
    for direction in ('input','output'):
        seen={}
        for id,item in catalog.items():
            value=protocol.get(id,{}).get(direction,item[direction]);key=signature(value)
            if key and key in seen:raise ValueError('Conflit '+direction+' : '+seen[key]+' / '+id)
            if key:seen[key]=id
    return copy.deepcopy(protocol)


def binding(value, item):
    if not isinstance(value,dict):raise ValueError('Affectation invalide')
    kind=value.get('kind')
    if kind in ('inherit','disabled'):
        if set(value)!={'kind'}:raise ValueError('Champs d’affectation inconnus')
    elif kind=='guided':
        if set(value)!={'kind','action'} or value['action'] not in GUIDED:raise ValueError('Fonction inconnue')
        if (item.get('input') or {}).get('family') not in ('button','pointer_button',None):raise ValueError('Fonction guidée réservée aux boutons')
    elif kind=='osc':
        if set(value)!={'kind','path','args','trigger'}:raise ValueError('OSC : chemin, arguments et déclenchement requis')
        path=value['path']
        if not isinstance(path,str) or len(path)>160 or not re.fullmatch(r'/[A-Za-z0-9_./-]+',path):raise ValueError('Chemin OSC invalide')
        if path.startswith(('/set_surface','/refresh','/strip/list')):raise ValueError('La gestion de surface est réservée à la Gateway')
        if value['trigger'] not in ('press','release','both','change'):raise ValueError('Déclenchement invalide')
        if not isinstance(value['args'],list) or len(value['args'])>12:raise ValueError('12 arguments maximum')
        for arg in value['args']:
            if not isinstance(arg,dict) or set(arg) not in ({'type','value'},{'type','source'}):raise ValueError('Argument OSC typé requis')
            t=arg['type']
            if t not in ('i','f','s'):raise ValueError('Types OSC : i, f, s')
            if 'source' in arg:
                if arg['source'] not in ('value','delta','pressed','channel','selected'):raise ValueError('Source d’argument inconnue')
            else:
                v=arg['value']
                if t=='s' and (not isinstance(v,str) or len(v)>256 or '\0' in v):raise ValueError('Texte OSC invalide')
                if t in ('i','f') and (type(v) not in (int,float) or not math.isfinite(v) or abs(v)>2147483647):raise ValueError('Nombre OSC invalide')
                if t=='i' and type(v) is not int:raise ValueError('Argument entier requis')
    else:raise ValueError('Type d’affectation inconnu')
    return copy.deepcopy(value)


def validate_preset(p):
    if not isinstance(p,dict) or set(p)-{'id','name','adapter','revision','protected','bindings'}:raise ValueError('Preset invalide')
    if not isinstance(p.get('name'),str) or not p['name'].strip() or len(p['name'])>80:raise ValueError('Nom de preset requis (80 caractères maximum)')
    if p.get('adapter') not in ('ardour','logic'):raise ValueError('Adaptateur inconnu')
    bindings=p.get('bindings',{})
    if not isinstance(bindings,dict) or len(bindings)>450:raise ValueError('Affectations invalides')
    catalog=elements()
    for id, modes in bindings.items():
        if id not in catalog or not isinstance(modes,dict) or set(modes)-set(MODES):raise ValueError('Élément/contexte inconnu')
        for b in modes.values():binding(b,catalog[id])
    return dict(name=p['name'].strip(),adapter=p['adapter'],bindings=copy.deepcopy(bindings))


class PresetStore:
    def __init__(self, root):
        self.path=Path(root)/'console-mapping.json'
        self.lock_path=Path(root)/'run/console-mapping.lock'

    @contextmanager
    def locked(self):
        self.lock_path.parent.mkdir(parents=True,exist_ok=True)
        with self.lock_path.open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX);yield

    def read(self):
        if not self.path.exists():return default_state()
        raw=self.path.read_bytes()
        if len(raw)>512*1024:raise ValueError('Fichier mapping trop grand')
        state=json.loads(raw)
        if state.get('version')!=1:raise ValueError('Version de mapping non prise en charge')
        validate_protocol(state['protocol'])
        for preset in state['presets'].values():validate_preset(preset)
        validate_preset(dict(name=state['active']['name'],adapter='ardour',bindings=state['active']['bindings']))
        validate_protocol(state['active']['protocol'])
        return state

    def write(self, state):
        data=json.dumps(state,ensure_ascii=False,allow_nan=False,indent=2)+'\n'
        if len(data.encode())>512*1024:raise ValueError('Limite locale de mapping atteinte ; exporter les presets anciens')
        fd,name=tempfile.mkstemp(prefix='.console-mapping-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w') as f:f.write(data);f.flush();os.fsync(f.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)

    def view(self):
        s=self.read()
        return {**s,'builtin':builtin(),'guided':{k:v[0] for k,v in GUIDED.items()}}

    def mutate(self, request, before_commit=None):
        with self.locked():
            state=self.read()
            if request.get('revision')!=state['revision']:raise ValueError('Mapping modifié ailleurs ; actualise avant d’enregistrer')
            action=request.get('action')
            if action in ('duplicate','import','logic'):
                if len(state['presets'])>=24:raise ValueError('24 presets maximum ; exporter puis supprimer un brouillon')
                source=(builtin() if request.get('preset',BUILTIN)==BUILTIN else state['presets'].get(request['preset']))
                if action=='logic':source=dict(name='Logic — brouillon',adapter='logic',bindings={})
                if action=='import':
                    data=request['data']
                    if not isinstance(data,dict) or data.get('version')!=1 or set(data)!={'version','preset'}:raise ValueError('Export de preset version 1 requis')
                    source=data['preset']
                if source is None:raise ValueError('Preset introuvable')
                preset=validate_preset(source);id='preset-'+uuid4().hex[:12]
                preset.update(id=id,revision=1,protected=False)
                if action=='duplicate':preset['name']=request.get('name',preset['name']+' · copie')[:80]
                state['presets'][id]=preset
            elif action=='save':
                id=request['preset']
                if id==BUILTIN:raise ValueError('Duplique le preset protégé avant de le modifier')
                if id not in state['presets']:raise ValueError('Preset introuvable')
                preset=validate_preset(request['data'])
                preset.update(id=id,revision=state['presets'][id]['revision']+1,protected=False)
                state['presets'][id]=preset
            elif action=='delete':
                id=request['preset']
                if id==state['active']['preset'] or id==BUILTIN:raise ValueError('Impossible de supprimer le preset actif ou protégé')
                state['presets'].pop(id,None)
            elif action=='position':
                id=request['element'];box=request['box']
                if id not in elements() or not isinstance(box,list) or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box):raise ValueError('Position invalide')
                x,y,w,h=box
                if not (0<=x<=1440 and 0<=y<=1024 and 4<=w<=400 and 4<=h<=400 and x+w<=1440 and y+h<=1024):raise ValueError('Position hors de la console')
                state.setdefault('positions',{})[id]=box
                state['validations'].setdefault(id,{})['position']=dict(level='documented',note='Position corrigée ; confirmation physique à renouveler',at=time.time())
            elif action=='validation':
                id=request['element']; dimension=request['dimension']; level=request['level']
                if id not in elements() or dimension not in ('position','input','output','function') or level not in LEVELS:raise ValueError('Validation inconnue')
                note=request.get('note','')
                if not isinstance(note,str) or len(note)>500:raise ValueError('Note trop longue')
                if level=='confirmed' and request.get('confirmed') is not True:raise ValueError('Confirmation physique explicite requise')
                record=dict(level=level,note=note,at=time.time())
                if dimension=='function':
                    preset_id=request.get('preset');mode=request.get('mode')
                    p=builtin() if preset_id==BUILTIN else state['presets'].get(preset_id)
                    if p is None or mode not in MODES:raise ValueError('Preset et contexte de fonction requis')
                    record['preset_revision']=p['revision']
                    state['validations'].setdefault(id,{}).setdefault('functions',{}).setdefault(preset_id,{})[mode]=record
                else:state['validations'].setdefault(id,{})[dimension]=record
            elif action=='protocol':
                id=request['element'];direction=request['direction']
                if id not in elements() or direction not in ('input','output'):raise ValueError('Élément inconnu')
                if request.get('confirmed') is not True:raise ValueError('Association explicite requise')
                state['protocol'].setdefault(id,{})[direction]=encoding(request['encoding'],direction)
                validate_protocol(state['protocol'])
                state['validations'].setdefault(id,{})[direction]=dict(level='observed' if direction=='input' else 'documented',note=request.get('note','Association manuelle')[:500],at=time.time())
            elif action in ('activate','rollback'):
                if action=='rollback':
                    if not state['previous']:raise ValueError('Aucune version précédente')
                    active=state['previous']
                else:
                    id=request['preset'];p=builtin() if id==BUILTIN else state['presets'].get(id)
                    if not p:raise ValueError('Preset introuvable')
                    if p['adapter']!='ardour':raise ValueError('Logic est un brouillon : adaptateur non installé')
                    active=dict(preset=id,name=p['name'],revision=p['revision'],bindings=p['bindings'],protocol=state['protocol'])
                state['previous']=copy.deepcopy(state['active']);state['active']=copy.deepcopy(active)
            else:raise ValueError('Opération de mapping inconnue')
            if before_commit is not None:before_commit()
            state['revision']+=1;self.write(state)
            return self.view()
