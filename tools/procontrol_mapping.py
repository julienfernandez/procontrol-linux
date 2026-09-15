"""Décodage ProControl dérivé de ReaControl24, sans accès réseau."""
# SPDX-License-Identifier: GPL-3.0-or-later
# Adapté de ReaCommon.py, Copyright (C) 2018 PhaseWalker.
# Provenance et modifications : vendor/reacontrol24/README.md.
import ast
from functools import lru_cache
from pathlib import Path

SOURCE_COMMIT = 'b6268cbb75ee6dc1ad773ca0e8a11fa87cf4a069'
TABLE_PATH = Path(__file__).resolve().parents[1] / 'vendor/reacontrol24/procontrolmap.py'


@lru_cache(maxsize=1)
def mapping_tree():
    for node in ast.parse(TABLE_PATH.read_text()).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'MAPPING_TREE_PROC' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Table ProControl de référence absente')


def split_commands(body):
    """Heuristique de itsplit : octet de statut ou terminateur f7/ff.

    Le corps doit déjà être limité à sa longueur logique, hors padding Ethernet.
    Ce découpage tiers ne constitue pas une grammaire complète du protocole.
    """
    current = bytearray()
    for value in body:
        if value in (0xf7, 0xff):
            current.append(value)
            yield bytes(current)
            current.clear()
        elif value & 0x80 and current:
            yield bytes(current)
            current = bytearray([value])
        else:
            current.append(value)
    if current:
        yield bytes(current)


def decode_command(command):
    result = {'hex': command.hex(' '), 'status': 'unmapped'}
    if not command:
        return {**result, 'status': 'malformed', 'reason': 'empty command'}
    if command[0] == 0x90 and len(command) != 3:
        return {**result, 'status': 'malformed', 'reason': 'button length must be 3'}
    if command[0] == 0xb0 and len(command) < 3:
        return {**result, 'status': 'malformed', 'reason': 'truncated controller'}
    if command[0] == 0xf0 and (len(command) < 5 or command[-1] != 0xf7):
        return {**result, 'status': 'malformed', 'reason': 'unterminated sysex'}
    lookup = mapping_tree()
    key = command[0]
    addresses, attributes = [], {}
    try:
        while True:
            node = lookup.get(key)
            if not node:
                return {**result, 'partial_address': '/' + '/'.join(addresses)}
            if 'Address' in node:
                addresses.append(node['Address'])
            attributes.update({k: v for k, v in node.items() if k not in ('Children', 'Address')})
            if 'ChildByte' not in node:
                break
            key = command[node['ChildByte']]
            if 'ChildByteMask' in node:
                key &= node['ChildByteMask']
            elif 'ChildByteMatch' in node:
                match = node['ChildByteMatch']
                if command[0] == 0x90 and node is mapping_tree()[0x90]:
                    # La table contient aussi les zones 15/16/17 (DSP, monitor,
                    # matrice) sans le bit 08 ; le test historique les masquait.
                    command_zones = node['Children'][8]['Children']
                    key = 8 if command[2] & 0x3f in command_zones else 0
                else:
                    key = match if key & match == match else 0
            lookup = node['Children']
        if 'TrackByte' in attributes:
            track = command[attributes['TrackByte']] & attributes.get('TrackByteMask', 0xff)
            result['track'] = track + 1
            index = addresses.index('track')
            addresses.insert(index + 1, str(track + 1))
        if 'ValueByte' in attributes:
            value = command[attributes['ValueByte']]
            mask = attributes.get('ValueByteMask')
            result['value'] = int((value & mask) == mask) if mask is not None else value
        if 'DirectionByte' in attributes:
            result['direction'] = command[attributes['DirectionByte']] - 64
    except (IndexError, ValueError):
        return {**result, 'status': 'malformed', 'reason': 'required byte or track token absent'}
    result.update(status='mapped_reference', address='/' + '/'.join(addresses))
    if 'CmdClass' in attributes:
        result['control_class'] = attributes['CmdClass']
    if command[0] == 0xb0 and attributes.get('CmdClass') == 'reafader':
        track_index = result['track'] - 1
        if (len(command) != 5 or command[1] != track_index
                or command[3] != 0x20 + track_index or command[2] > 0x7f
                or command[4] & 0x8f):
            return {**result, 'status': 'malformed', 'reason': 'invalid reference fader encoding'}
        # Inverse de ReaBase.tenbits ; position brute, pas un gain Ardour.
        result['fader_raw_10bit'] = (command[2] << 3) | (command[4] >> 4)
    return result


def decode_body(body):
    return [decode_command(command) for command in split_commands(body)]
