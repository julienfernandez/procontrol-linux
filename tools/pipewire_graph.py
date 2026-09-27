"""Validated, bounded reads of the live PipeWire graph; never a stale fallback."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
import time


def read_graph(attempts=3):
    last = None
    for attempt in range(attempts):
        try:
            raw = subprocess.check_output(['pw-dump', '--no-colors'], text=True,
                                          stderr=subprocess.PIPE, timeout=4)
            objects = json.loads(raw)
            if not isinstance(objects, list) or any(
                not isinstance(o, dict) or type(o.get('id')) is not int or
                not isinstance(o.get('type'), str) or
                (o.get('info') is not None and not isinstance(o['info'], dict))
                for o in objects
            ):
                raise ValueError('Structure du graphe PipeWire invalide')
            for obj in objects:
                info = obj.get('info')
                kind = obj['type'].rsplit(':', 1)[-1]
                if kind in ('Node', 'Port', 'Link') and not isinstance(info, dict):
                    raise ValueError('Objet PipeWire incomplet : ' + kind)
                if info is None:
                    obj['info'] = {}  # Metadata/Profiler have no info payload.
                elif 'props' in info and not isinstance(info['props'], dict):
                    raise ValueError('Propriétés PipeWire invalides')
                if kind == 'Link' and not all(type(info.get(k)) is int for k in
                        ('input-node-id', 'output-node-id', 'input-port-id', 'output-port-id')):
                    raise ValueError('Extrémités de lien PipeWire incomplètes')
            return objects
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(.1)
    raise ValueError(f'Graphe PipeWire indisponible après {attempts} lectures : {last}') from last


def unused_meter_links(objects):
    """Only the laptop-input -> Ardour dummy meter links, never track inputs."""
    props = {o['id']: (o.get('info') or {}).get('props', {}) for o in objects}
    meters = {o['id'] for o in objects if o.get('type') == 'PipeWire:Interface:Port'
              and props[o['id']].get('port.name') == 'physical_audio_input_monitor_enable'
              and props.get(int(props[o['id']].get('node.id', -1)), {}).get('node.name') == 'ardour'}
    pairs = set()
    for obj in objects:
        if obj.get('type') != 'PipeWire:Interface:Link' or not obj.get('info'):
            continue
        link = obj['info']
        source = props.get(link.get('output-node-id'), {}).get('node.name', '')
        if link.get('input-port-id') in meters and source.startswith('alsa_input.pci-'):
            pairs.add((link['output-port-id'], link['input-port-id']))
    return meters, pairs
