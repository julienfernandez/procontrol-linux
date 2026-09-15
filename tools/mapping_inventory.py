#!/usr/bin/env python3
"""Inventory reference button addresses, not a claim of physical validation."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
from procontrol_mapping import mapping_tree,SOURCE_COMMIT
from surface_map import SurfaceMap

def inventory():
    tree=mapping_tree()[0x90]['Children']; rows=[]
    groups=[(z,f'Channel {z+1}',tree[0]['Children']) for z in range(8)]
    groups += [(z,g.get('Address','Numeric keypad'),g.get('Children',{})) for z,g in tree[8]['Children'].items()]
    for z,group,children in groups:
        for n,node in children.items():
            states={}
            for mode in ('normal','modifier','alpha'):
                m=SurfaceMap();m.alpha=mode=='alpha'
                if mode=='modifier':m.modifiers.add('Shift_L')
                states[mode]=m.command(bytes([0x90,n,z|64]),0)
            rows.append({'zone':z,'button':n,'group':group,'label':node.get('Address','Unknown'),
                         'mapped':states['normal'] is not None,'actions':states,
                         'provenance':'ReaControl24 '+SOURCE_COMMIT,'physical_validation':'not asserted by inventory'})
    return rows

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];rows=inventory()
    (root/'docs/mapping-coverage.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
    missing=[r for r in rows if not r['mapped']]
    lines=['# Adresses de boutons restant sans action','','Inventaire de la table de référence, pas un comptage de boutons physiques validés.',
           f"{len(rows)} entrées ; {len(rows)-len(missing)} ont une action en mode normal ; {len(missing)} restent sans action.",'',
           '| Zone | Code | Libellé tiers | Groupe |','|---|---|---|---|']
    lines += [f"| {r['zone']:02x} | {r['button']:02x} | {r['label']} | {r['group']} |" for r in missing]
    lines += ['', 'Les contrôles analogiques peuvent ne pas émettre en Ethernet. Les encodeurs,',
              'faders et commandes absentes de la table nécessitent un inventaire séparé.',
              'Une adaptation expérimentale existante compte comme action, pas comme validation.',
              'Ne pas attribuer arbitrairement des codes aux huit encodeurs DSP ou aux flèches.']
    (root/'docs/mapping-backlog.md').write_text('\n'.join(lines)+'\n')
    print(lines[3])
