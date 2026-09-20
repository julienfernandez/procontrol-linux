"""Versioned physical console inventory. Geometry is independent of DAW actions.

Drawn from the locally consulted main-unit reference; no photo is redistributed.
A reference code is evidence, never a claim of physical confirmation.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from functools import lru_cache
from pathlib import Path
from procontrol_mapping import mapping_tree, SOURCE_COMMIT

ROOT = Path(__file__).resolve().parents[1]
MODES = ['normal', 'modifier', 'alpha', 'monitor', 'eq', 'browse', 'library', 'params', 'nudge', 'zoom']


def button_id(zone, key):
    return f'button.{zone:02x}.{key:02x}'


@lru_cache(maxsize=1)
def layout():
    elements = []
    sections = [dict(id=k, label=n, box=b) for k, n, b in [
        ('meters', 'Vumètres & compteur', [24, 20, 1392, 130]),
        ('strips', '8 tranches', [24, 170, 716, 830]),
        ('dsp', 'DSP Edit / Assign', [756, 170, 368, 355]),
        ('monitor', 'Control Room', [1138, 170, 278, 355]),
        ('matrix', 'Channel Matrix', [756, 537, 368, 212]),
        ('keys', 'Windows & pavé', [1138, 537, 278, 212]),
        ('transport', 'Édition & transport', [756, 761, 660, 239]),
        ('automation', 'Automation', [24, 719, 104, 281]),
    ]]
    def add(id, label, kind, section, box, input=None, output=None, **extra):
        row = dict(id=id, label=label, kind=kind, section=section, box=box,
                   input=input, output=output,
                   validation=dict(position='documented', input='documented' if input else 'unknown',
                                   output='documented' if output else 'unknown', function='unknown'),
                   evidence=['Implantation : photo locale main-unit (schéma, proportions adaptées)'])
        if input or output: row['evidence'].append('ReaControl24 '+SOURCE_COMMIT)
        row.update(extra); elements.append(row); return row
    def btn(z, k, label, section, x, y, w=42, h=23):
        tree=mapping_tree()[0x90]['Children']
        node=tree[0]['Children'].get(k,{}) if z<8 else tree[8]['Children'].get(13 if 13<=z<=20 else z,{}).get('Children',{}).get(k,{})
        output=dict(family='led',zone=z,key=k) if node.get('LED') or z==24 else None
        return add(button_id(z, k), label, 'button', section, [x, y, w, h],
                   dict(family='button', zone=z, key=k), output)
    # Strips preserve the visible order, not the numeric order of the protocol.
    for ch in range(8):
        x = 137 + ch*74
        for y, k, label in [(195,0,'REC'),(230,1,'INS / SEND'),(265,2,'EQ'),(300,3,'DYN'),
                            (435,4,'ASSIGN'),(488,5,'AUTO'),(534,6,'SELECT'),(575,7,'SOLO'),(616,8,'MUTE')]:
            btn(ch,k,label,'strips',x+9,y,48,23)
        for suffix, y, addr in [('upper',341,ch),('lower',661,ch+32)]:
            add(f'strip.{ch+1}.display.{suffix}',f'Afficheur {suffix} {ch+1}','display','strips',[x, y, 69, 24], output=dict(family='display',address=addr))
        add(f'strip.{ch+1}.encoder',f'Encodeur {ch+1}','encoder','strips',[x+17,380,38,38], input=dict(family='encoder',address=0x40+ch))
        add(f'strip.{ch+1}.ring',f'Couronne {ch+1}','ring','strips',[x+4,374,64,50],output=dict(family='ring',address=ch))
        add(f'strip.{ch+1}.automation',f'LED automation {ch+1}','indicator','strips',[x+4,473,8,39],output=dict(family='automation',address=ch))
        add(f'strip.{ch+1}.fader',f'Fader {ch+1}','fader','strips',[x+17,721,34,245],input=dict(family='fader',channel=ch+1),output=dict(family='motor',channel=ch+1))
        btn(ch,9,'TOUCH','strips',x+7,976,56,12)['output']=None
        # Additional codes are not asserted to be separate physical switches.
        add(button_id(ch,10),f'Inserts alternatif {ch+1}','reference','strips',[x,690,31,12],input=dict(family='button',zone=ch,key=10),note='Code de référence alternatif ; emplacement physique à établir.')
        for key,label in [(12,'Source Toggle'),(13,'Roll Off')]:
            ref=add(button_id(ch,key),label+' '+str(ch+1),'reference','strips',[x+(key-11)*23,690,21,12],input=dict(family='button',zone=ch,key=key),note='Entrée de table tierce ; ne correspond pas nécessairement à un bouton distinct sur la tranche. Position physique à identifier.')
            ref['validation']['position']='unknown'
        add(button_id(ch,11),f'Peak {ch+1}','indicator','meters',[x+9,42,40,9],output=dict(family='led',zone=ch,key=11))
        for side, offset in [('L',0),('R',32)]:
            add(f'strip.{ch+1}.meter.{side}',f'VU {ch+1} {side}','meter','meters',[x+17+(side=='R')*18,58,11,72],output=dict(family='meter',address=ch+offset))
    globals = mapping_tree()[0x90]['Children'][8]['Children']
    for idx,k in enumerate(range(8)):
        btn(8,k,globals[8]['Children'][k]['Address'].replace('_',' '),'strips',38+(idx%2)*45,195+(idx//2)*35,40,25)
    for idx,k in enumerate(range(8,20)):
        btn(8,k,globals[8]['Children'][k]['Address'].replace('_',' '),'strips',38+(idx%2)*45,360+(idx//2)*32,40,25)
    for idx,k in enumerate(range(20,23)):
        btn(8,k,globals[8]['Children'][k]['Address'].replace('_',' '),'strips',44,568+idx*42,66,25)
    for idx,k in enumerate(range(0x17,0x23)):
        btn(8,k,globals[8]['Children'][k]['Address'].replace('_',' '),'automation',35+(idx%2)*45,748+(idx//2)*29,39,23)
    for idx,k in enumerate(range(0x23,0x27)):
        btn(8,k,['SHIFT','OPTION','CTRL','CMD'][idx],'automation',35+(idx%2)*45,932+(idx//2)*29,39,23)
    add('clock','Compteur huit chiffres','clock','meters',[790,56,218,55],output=dict(family='clock',address=9))
    add('clock.mode','LED unité compteur','indicator','meters',[790,36,218,13],output=dict(family='clock_mode',address=9))
    for i in range(6):
        add(f'master.meter.{i+1}',f'Grande colonne {i+1}','meter','meters',[1060+i*48,52,16,77],note='Six colonnes visibles. Paires confirmées : 10/42, 11/43, 12/44, 13/45. La correspondance avec chaque colonne reste à établir ; ne pas la déduire de cette liste.')
    for i in range(8):
        y=199+i*34
        for k,x in [(0,824),(1,857),(2,1085)]:btn(13+i,k,['SELECT / AUTO','ASSIGN / ENABLE','BYPASS'][k],'dsp',x,y,29,21)
        add(f'dsp.{i+1}.display',f'Afficheur DSP {i+1} · B','display','dsp',[896,y,124,23],output=dict(family='display',address=45+i))
        add(f'dsp.{i+1}.encoder',f'Encodeur DSP {i+1}','encoder','dsp',[1040,y-2,26,26],input=dict(family='encoder',address=77+i))
    for idx,k in enumerate(range(9)):
        btn(21,k,globals[21]['Children'][k]['Address'].replace('_',' '),'dsp',769,195+idx*31,43,22)
    for k,x in [(9,1043),(10,1085)]:btn(21,k,globals[21]['Children'][k]['Address'],'dsp',x,494,34,20)
    add('dsp.channel','Channel / Group','display','dsp',[894,493,130,23],note='Adresse de sortie à identifier.')
    for idx,(label,x,y) in enumerate([('AUX',1165,206),('TALKBACK',1165,272),('ALT',1165,339),('MAIN',1165,410),('HEADPHONE',1359,410)]):
        add('analog.'+str(idx),label,'knob','monitor',[x,y,35,35],note='Commande analogique ; aucun encodage Ethernet établi.')
    for k,(x,y) in enumerate([(1240,212),(1357,212),(1357,259),(1357,297),(1357,335),(1271,335),(1271,379),(1271,422)]):
        btn(22,k,globals[22]['Children'][k]['Address'],'monitor',x,y,45,24)
    add('analog.alt','ALT monitor','button','monitor',[1220,379,43,24],note='Commande analogique, encodage non établi.')
    for k,label,x,y in [(0,'UP',1269,459),(1,'PREV',1224,487),(2,'ZOOM / SEL',1269,487),(3,'NEXT',1314,487),(4,'DOWN',1269,515)]:
        btn(24,k,label,'monitor',x,y,39,21)
    for k in range(1,33):
        idx=k-1;btn(23,k,globals[23]['Children'][k]['Address'].replace('_',' · '),'matrix',807+(idx%8)*38,571+(idx//8)*32,33,23)
    for k,y in [(0,565),(33,618),(35,706)]:btn(23,k,globals[23]['Children'][k]['Address'],'matrix',768,y,31,23)
    for idx,k in enumerate([36,37,38,39,40,41,42]):btn(23,k,globals[23]['Children'][k]['Address'],'matrix',807+idx*43,707,38,24)
    for idx,k in enumerate([43,44,45,46,47,48]):btn(23,k,globals[23]['Children'][k]['Address'],'matrix',1110,562+idx*30,27,22)
    for idx,k in enumerate(range(8)):btn(25,k,globals[25]['Children'][k]['Address'],'keys',1150+(idx%2)*47,571+(idx//2)*43,40,25)
    keypad=[[10,11,12,13],[7,8,9,14],[4,5,6,15],[1,2,3,17],[0,16]]
    for r,keys in enumerate(keypad):
        for c,k in enumerate(keys):btn(26,k,globals[26]['Children'][k]['Address'],'keys',1257+c*36,570+r*33,30,27)
    for idx,k in enumerate([0,1,2,3,13,14,15,16]):btn(27,k,globals[27]['Children'][k]['Address'],'transport',769+(idx%4)*40,789+(idx//4)*35,34,24)
    for idx,k in enumerate([4,5,6,7,8,9]):btn(27,k,globals[27]['Children'][k]['Address'],'transport',940+idx*33,789,29,24)
    for idx,k in enumerate([10,11,12]):btn(27,k,globals[27]['Children'][k]['Address'],'transport',1280+idx*42,789,35,24)
    for idx,k in enumerate([0,1,2,3,4]):btn(28,k,globals[28]['Children'][k]['Address'],'transport',940+idx*41,828,35,24)
    for idx,k in enumerate([5,6,7,8,9,10,11]):btn(28,k,globals[28]['Children'][k]['Address'],'transport',802+idx*48,878,41,24)
    for idx,k in enumerate([12,13,14,15,16,17]):btn(28,k,globals[28]['Children'][k]['Address'],'transport',773+idx*60,935,51,38)
    for idx,k in enumerate([18,19]):btn(28,k,globals[28]['Children'][k]['Address'],'transport',1158+idx*51,789,44,24)
    add('jog','Jog / Shuttle','jog','transport',[1150,844,116,115],input=dict(family='encoder',address=92))
    add('pointer','Trackpad','pad','transport',[1294,842,108,96],input=dict(family='pointer'))
    for side,x,number,label in [('left',1298,1,'gauche'),('right',1354,3,'droit')]:add('pointer.'+side,'Clic '+label,'button','transport',[x,958,45,18],input=dict(family='pointer_button',button=number),note='Bit 0x20 (gauche) / 0x10 (droit) du paquet trackpad ; docs/input-live-validation.json.')
    by_id={r['id']:r for r in elements}
    for file,level in [('dsp-buttons-confirmed.json','observed'),('navigation-buttons-confirmed.json','confirmed')]:
        for b in json.loads((ROOT/'docs'/file).read_text())['buttons']:
            item=by_id[button_id(b['zone'],b['key'])]
            item['validation']['input']=level;item['evidence'].append('docs/'+file)
    for i in range(8):
        item=by_id[f'dsp.{i+1}.display'];item['validation']['output']='confirmed';item['evidence'].append('docs/dsp-displays-confirmed.json · série B seulement')
    coverage=json.loads((ROOT/'docs/mapping-coverage.json').read_text())
    for row in coverage:
        id=button_id(row['zone'],row['button'])
        if id in by_id:by_id[id]['functions']=row['actions']
    return dict(version=1,width=1440,height=1024,sections=sections,elements=elements,modes=MODES,
                evidence_note='Le dessin situe les éléments. Les couleurs indiquent les états logiciels ; un ACK ne confirme pas un effet physique.',
                confirmed_meter_pairs=[[10,42],[11,43],[12,44],[13,45]])


def elements():
    return {r['id']:r for r in layout()['elements']}
