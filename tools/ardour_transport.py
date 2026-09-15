"""Pont de transport OSC local ; aucune commande audio ou enregistrement."""
# SPDX-License-Identifier: GPL-3.0-or-later
from collections import deque
import socket
import struct
from procontrol_mapping import decode_command


def string(value):
    raw = value.encode('utf8') + b'\0'
    return raw + bytes((-len(raw)) % 4)


def message(address, *values):
    tags, data = ',', b''
    for value in values:
        if isinstance(value, int):
            tags += 'i'; data += struct.pack('>i', value)
        elif isinstance(value, float):
            tags += 'f'; data += struct.pack('>f', value)
        elif isinstance(value, str):
            tags += 's'; data += string(value)
        else:
            raise ValueError('Type OSC non pris en charge')
    return string(address) + string(tags) + data


def decode(data, depth=0):
    if depth > 4 or len(data) > 65535:
        raise ValueError('Message OSC excessif')
    if data.startswith(b'#bundle\0'):
        if len(data) < 16:
            raise ValueError('Bundle tronqué')
        result, offset = [], 16
        while offset < len(data):
            if offset + 4 > len(data): raise ValueError('Bundle tronqué')
            size = struct.unpack_from('>I', data, offset)[0]; offset += 4
            if not size or offset + size > len(data): raise ValueError('Taille bundle invalide')
            result.extend(decode(data[offset:offset+size], depth+1)); offset += size
            if len(result) > 256: raise ValueError('Trop de messages')
        return result
    def read_string(offset):
        end = data.find(b'\0', offset)
        if end < 0: raise ValueError('Chaîne OSC non terminée')
        after = (end + 4) & ~3
        if after > len(data): raise ValueError('Padding OSC tronqué')
        return data[offset:end].decode('utf8'), after
    address, offset = read_string(0)
    tags, offset = read_string(offset)
    if not tags.startswith(',') or len(tags) > 129:
        raise ValueError('Types OSC invalides')
    values = []
    for tag in tags[1:]:
        if tag == 's':
            value, offset = read_string(offset)
        elif tag in 'ifhd':
            format_code = 'q' if tag == 'h' else tag
            size = struct.calcsize('>' + format_code)
            if offset + size > len(data): raise ValueError('Argument OSC tronqué')
            value = struct.unpack_from('>' + format_code, data, offset)[0]; offset += size
        elif tag in 'TF': value = tag == 'T'
        else: raise ValueError('Type OSC non pris en charge : ' + tag)
        values.append(value)
    if offset != len(data): raise ValueError('Octets OSC supplémentaires')
    return [(address, values)]


class TransportMap:
    # Noms issus de la table ProControl d'origine ; PLAY/STOP validés localement.
    buttons = {'/button/command/Transport/Play': '/transport_play',
               '/button/command/Transport/Stop': '/transport_stop',
               '/button/command/Transport/Go To Start': '/goto_start',
               '/button/command/Transport/Go To End': '/goto_end',
               '/button/command/Transport/Rewind': '/rewind',
               '/button/command/Transport/Forward': '/ffwd'}

    def __init__(self):
        self.seen = deque(maxlen=128)

    def route(self, sequence, body):
        key = (sequence, body)
        if key in self.seen:
            return None
        self.seen.append(key)
        # Un seul bouton complet : le découpage des corps multiplexés reste hors ligne.
        if len(body) != 3 or body[0] != 0x90:
            return None
        decoded = decode_command(body)
        if decoded['status'] == 'mapped_reference' and decoded.get('value') == 1:
            return self.buttons.get(decoded.get('address'))
        return None


class ArdourTransport:
    def __init__(self, port=3819):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('127.0.0.1', 0))
        self.socket.connect(('127.0.0.1', port))
        self.socket.setblocking(False)
        self.mapper = TransportMap()
        # Mode Auto demandé : réponse au socket émetteur ; section principale seulement.
        self.socket.send(message('/set_surface', 8, 31, 16, 0, 0, 0, 0))
        self.socket.send(message('/set_surface'))

    def forward(self, sequence, body):
        address = self.mapper.route(sequence, body)
        if address:
            # Les PATH_CALLBACK d'Ardour 8.4 acceptent un float 1.0 à l'appui.
            self.socket.send(message(address, 1.0))
        return address

    def poll(self):
        result = []
        for _ in range(256):
            try:
                data = self.socket.recv(65535)
            except BlockingIOError:
                break
            try:
                result.extend(decode(data))
            except ValueError as exc:
                result.append(('decode_error', [str(exc)]))
        return result

    def close(self):
        self.socket.close()
