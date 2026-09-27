"""Context on the ninth DSP display, through the normal feedback/ACK queue.

Firmware 1.37: text handler 0x2a574 calls 0x25d8c, which accepts DSP
indices 0x0d..0x15 inclusive and ignores the row bit for those indices.
See docs/channel-group-2026-09-27.md for static and physical evidence.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import re
from surface_feedback import ascii8

ADDRESS = 0x35
KEY = ('channel_group',)


def channel_group_text(text):
    return bytes([0xf0, 0x13, 0, 0x40, ADDRESS, 0]) + ascii8(text) + b'\xf7'


def track_label(name):
    # Preserve both channel numbers within eight characters.
    name = str(name or '')
    return re.sub(r'^MPC (\d{2}-\d{2})$', r'MPC\1', name)


def context_frames(surface, eq, connected, learning=False):
    """Read existing state only: never select, create, validate or send OSC."""
    if not connected:
        return ('ARD WAIT',)
    if learning:
        return ('CAPTURE',)
    selected = surface.state.get(('/select/name', None), '')
    sends = getattr(surface, 'sends', None)
    if sends is not None and sends.active:
        if not sends.usable():return ('ATTENTE',)
        if not sends.rows:return ('0 DEPART', track_label(sends.route_name))
        return (f'AUX {sends.page+1}/{max(1,(len(sends.rows)+7)//8)}', track_label(sends.route_name))
    if eq.active:
        name = track_label(getattr(eq, 'route_name', ''))
        if eq.create_pending:
            title = 'AJOUT...'
        elif eq.create_error or eq.error:
            title = 'ERREUR'
        elif not eq.usable():
            title = 'ATTENTE'
        elif eq.mode == 'eq':
            title = f'EQ B{eq.filter + 1}/8'
        elif eq.mode in ('browse', 'library'):
            pages = max(1, (len(eq.browser_rows()) + 7) // 8)
            label = 'INS' if eq.mode == 'browse' else 'LIB'
            title = f'{label} {eq.plugin_page + 1}/{pages}'
        else:
            pages = max(1, (len(eq.parameter_list()) + 7) // 8)
            label = 'DYN' if eq.family == 'comp' else 'FX'
            title = f'{label} {eq.page + 1}/{pages}'
        # An operation or error must not disappear behind the name carousel.
        if eq.create_pending or eq.create_error or eq.error or not eq.usable():
            return (title,)
        if getattr(eq,'notice_until',0)>eq.clock():return (eq.notice,)
        if getattr(eq,'info',False):
            detail = ('BIBLIO' if eq.mode=='library' else 'INSERTS') if eq.mode in ('browse','library') else getattr(eq,'plugin_name','DSP')
            return (detail,name) if name else (detail,)
        return (title, name) if name else (title,)
    name = track_label(selected)
    if surface.encoder_mode == 'send':
        title = f'SEND {chr(64 + surface.send_index)}'
        return (title, name) if name else (title,)
    monitor = getattr(surface, 'monitor', None)
    if monitor is not None and monitor.active:
        return ('ECOUTE', name) if name else ('ECOUTE',)
    return (name or 'ARDOUR',)


class ChannelGroupDisplay:
    DWELL = 3.0

    def __init__(self, feedback, surface, eq):
        self.feedback = feedback
        self.surface = surface
        self.eq = eq
        self.frames = ()
        self.started = 0.0
        self.next_render = 0.0
        self.text = ''

    def tick(self, now, connected, learning=False):
        if now < self.next_render:
            return
        self.next_render = now + 0.1
        frames = context_frames(self.surface, self.eq, connected, learning)
        if frames != self.frames:
            self.frames = frames
            self.started = now
        self.text = frames[int((now - self.started) / self.DWELL) % len(frames)]
        self.feedback.put(KEY, channel_group_text(self.text))

    def status(self):
        return {'address': ADDRESS, 'text': ascii8(self.text).decode('ascii'),
                'frames': list(self.frames)}
