"""USB channel counts must come from device ports, independently of track names."""
# SPDX-License-Identifier: GPL-3.0-or-later
import re


def channel_count(value):
    if isinstance(value, bool) or str(value) not in ('16', '32'):
        raise ValueError('Le studio USB accepte 16 ou 32 canaux')
    return int(value)


def usb_nodes(objects):
    result = {}
    for direction, kind in (('capture', 'input'), ('playback', 'output')):
        matches = [o for o in objects if o.get('type') == 'PipeWire:Interface:Node'
                   and re.fullmatch(r'alsa_' + kind + r'\.usb-(?:Akai_Professional_MPC_One_USB_Audio_(?:16|32)ch_.+|Juju_Juju_Driver_32ch_JUJU-MPCONE-32-00\.pro-(?:input|output)-0)',
                                    o.get('info', {}).get('props', {}).get('node.name', ''))]
        result[direction] = matches[0] if len(matches) == 1 else None
    return result


def usb_channel_names(objects, node, direction):
    if node is None:
        return set()
    names = [o.get('info', {}).get('props', {}).get('audio.channel')
             for o in objects if o.get('type') == 'PipeWire:Interface:Port'
             and str(o.get('info', {}).get('props', {}).get('node.id')) == str(node['id'])
             and o.get('info', {}).get('props', {}).get('port.direction') == direction
             and not o.get('info', {}).get('props', {}).get('port.monitor')]
    channels = {n for n in names if isinstance(n, str) and re.fullmatch(r'AUX(?:[0-9]|[12][0-9]|3[01])', n)}
    # Duplicated, missing, or non-contiguous port maps are not complete devices.
    return channels if len(channels) == len(names) and channels == {f'AUX{i}' for i in range(len(channels))} else set()
