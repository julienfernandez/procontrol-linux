#!/usr/bin/env python3
"""Offline inventory of reference button handlers, not physical validation."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import json
from pathlib import Path

from eq_editor import EQEditor
from procontrol_mapping import mapping_tree, SOURCE_COMMIT
from surface_feedback import SurfaceFeedback
from surface_map import SurfaceMap
from surface_routing import SurfaceRouting
from track_monitor import TrackMonitor
from navigation_controls import NAVIGATION_KEYS

ROOT = Path(__file__).resolve().parents[1]
MODES = ('normal', 'modifier', 'alpha', 'monitor', 'eq', 'browse', 'library', 'params', 'nudge', 'zoom')


def mapper_for(mode):
    """Install the same mode handlers as the daemon, with no network client."""
    mapper = SurfaceMap()
    feedback = SurfaceFeedback(mapper)
    routing = SurfaceRouting(mapper, feedback)
    eq = EQEditor(routing, feedback, lambda: 0.)
    monitor = TrackMonitor(routing, feedback, lambda: 0.)
    mapper.alpha = mode == 'alpha'
    mapper.nudge = mode == 'nudge'
    mapper.editing.zoom_navigation = mode == 'zoom'
    if mode == 'modifier':
        mapper.modifiers.add('Shift_L')
    if mode == 'monitor':
        monitor.enter()
    if mode in ('eq', 'browse', 'library', 'params'):
        eq.active = True
        eq.mode = mode
    return mapper


def inventory():
    tree = mapping_tree()[0x90]['Children']
    groups = [(z, f'Channel {z+1}', tree[0]['Children']) for z in range(8)]
    groups += [(z, g.get('Address', 'Numeric keypad'), g.get('Children', {}))
               for z, g in tree[8]['Children'].items()]
    groups.append((0x18, 'Navigation', {key: {'Address': label} for key, label in NAVIGATION_KEYS.items()}))
    rows = []
    for zone, group, children in groups:
        for key, node in children.items():
            # A fresh context per press avoids a preceding button changing the
            # mode, held state or selection of the next inventory entry.
            states = {mode: mapper_for(mode).command(bytes([0x90, key, zone | 64]), 0.)
                      for mode in MODES}
            rows.append(dict(zone=zone, button=key, group=group,
                             label=node.get('Address', 'Unknown'),
                             mapped=any(value is not None for value in states.values()),
                             actions=states, provenance=('docs/navigation-buttons-confirmed.json' if zone==0x18 else 'ReaControl24 ' + SOURCE_COMMIT),
                             physical_validation='not asserted by inventory'))
    return rows


def documents():
    rows = inventory()
    missing = [row for row in rows if not row['mapped']]
    normal = sum(row['actions']['normal'] is not None for row in rows)
    lines = ['# Inventaire logiciel des boutons', '',
             'Généré par `python3 tools/mapping_inventory.py` ; vérifier sans modifier avec `--check`.', '',
             'La table de référence est complétée par les cinq touches de navigation capturées ; ce total ne mesure pas la validation physique de toutes les fonctions.',
             f'{len(rows)} entrées ; {normal} prises en charge en mode normal ; '
             f'{len(rows)-len(missing)} dans au moins un mode ; {len(missing)} sans gestionnaire.', '',
             'Modes inspectés : normal, Shift, ALPHA, monitoring, EQ, chaîne de plugins,',
             'bibliothèque, paramètres, NUDGE et zoom. Les éditeurs de mode du daemon sont installés',
             'dans un contexte neuf pour chaque touche. Aucun message réseau n’est envoyé.', '',
             'Dans [le JSON](mapping-coverage.json), `null` signifie sans gestionnaire ; `[]`',
             'signifie touche consommée, éventuellement pour changer un état local ou bloquer',
             'une action inadaptée au mode. Une liste non vide décrit les actions demandées.',
             '`mapped` signifie uniquement qu’un gestionnaire reconnaît la touche dans au',
             'moins un mode : cela ne prouve ni un effet dans Ardour ni une validation physique.', '',
             '## Adresses sans gestionnaire', '',
             '| Zone | Code | Libellé tiers | Groupe |',
             '|---|---|---|---|']
    lines += [f"| {r['zone']:02x} | {r['button']:02x} | {r['label']} | {r['group']} |" for r in missing]
    lines += ['', 'Les contrôles analogiques peuvent ne pas émettre en Ethernet. Les encodeurs,',
              'faders et commandes absentes de la table nécessitent un inventaire séparé.',
              'La table tierce ne décrit notamment que la première rangée DSP ; les huit',
              'rangées et les rotatifs ont leurs [captures dédiées](dsp-buttons-2026-09-14.md).',
              'Les cinq touches de navigation autour de ZOOM/SEL sont identifiées par la',
              '[capture contrôlée](navigation-buttons-confirmed.json) du 20 septembre.',
              'Le [guide fonctionnel](control-map.md) décrit les usages actuels.']
    # One button per line keeps nine contexts from producing tens of thousands
    # of repeated array-layout lines in the versioned machine-readable report.
    coverage = '[\n' + ',\n'.join('  ' + json.dumps(row, ensure_ascii=False) for row in rows) + '\n]\n'
    return {'docs/mapping-coverage.json': coverage,
            'docs/mapping-backlog.md': '\n'.join(lines) + '\n'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail when generated documentation is stale')
    args = parser.parse_args(argv)
    stale = []
    for relative, content in documents().items():
        path = ROOT / relative
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != content:
                stale.append(relative)
        else:
            path.write_text(content, encoding='utf-8')
    if stale:
        print('Stale inventory: ' + ', '.join(stale))
        print('Run: python3 tools/mapping_inventory.py')
        return 1
    print('Mapping inventory is current.' if args.check else 'Mapping inventory generated.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
