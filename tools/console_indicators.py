"""Console range-building guide and read-only Ardour transport indicators."""
# SPDX-License-Identifier: GPL-3.0-or-later
import time
from surface_feedback import button_led

PATH = '/procontrol/transport/state'


class ConsoleIndicators:
    INTERVAL = .25
    TIMEOUT = 2.

    def __init__(self, mapper, feedback, clock=time.monotonic):
        self.mapper = mapper; self.feedback = feedback; self.clock = clock
        self.next_query = 0.; self.received = None; self.transport = None
        self.range_phase = 'idle'; self.range_start = None
        self.position = None; self.position_at = None
        mapper.indicators = self

    def reset_range(self):
        self.range_phase = 'idle'; self.range_start = None

    def disconnect(self):
        self.transport = None; self.received = None; self.next_query = 0.
        self.position = None; self.position_at = None; self.reset_range()
        for key in (5, 8, 11, 17): self.led(key, False)
        self.render(self.clock())

    def feed(self, path, values, now=None):
        now = self.clock() if now is None else now
        if path == '/position/samples' and len(values) == 1:
            try:
                position = int(values[0])
                if position < 0: return
            except (ValueError, TypeError, OverflowError): return
            self.position = position; self.position_at = now
        if path != PATH: return
        if (len(values) != 7 or any(type(v) is not int for v in values)
                or values[0] != 1 or any(v not in (0, 1) for v in values[1:5] + values[6:])
                or values[5] not in (0, 1, 2)): return
        self.transport = tuple(values[1:]); self.received = now
        self.next_query = min(self.next_query, now + self.INTERVAL)
        self.render(now)

    def accepted(self, actions, now=None):
        """Guide only the IN/OUT sequence sent from this console, not GUI selection."""
        now = self.clock() if now is None else now
        names = [v[0] for kind, path, v in actions if kind == 'osc' and path == '/access_action' and v]
        fresh = self.position is not None
        if 'Common/start-range-from-playhead' in names:
            self.range_start = self.position if fresh else None
            self.range_phase = 'in'
        elif 'Common/finish-range-from-playhead' in names:
            self.range_phase = ('ready' if fresh and self.range_start is not None
                                and self.position != self.range_start else 'in')
        if any(n in names for n in ('EditorEditing/editor-cut', 'EditorEditing/editor-delete',
                                    'EditorEditing/undo', 'EditorEditing/redo',
                                    'EditorEditing/set-mouse-mode-object')):
            self.reset_range()
        # Ask promptly after state-changing buttons, never invent a toggle state.
        if any(n in names for n in ('Transport/TogglePunch', 'Transport/ToggleExternalSync',
                                    'Transport/Loop', 'Editor/set-punch-from-edit-range')):
            self.next_query = min(self.next_query, now + .05)
        self.render(now)

    def led(self, number, on):
        self.feedback.put(('led', 0x1c, number), button_led(0x1c, number, on))

    def render(self, now):
        blink = bool(int(now * 2) % 2)  # slow: half a second on/off
        ready = self.range_phase == 'ready'
        self.led(2, ready or (self.range_phase == 'in' and blink))
        self.led(3, ready)
        if self.transport is None: return
        external, punch_in, punch_out, loop, record, armed_track = self.transport
        self.led(5, external); self.led(8, external)
        self.led(11, bool(punch_in and punch_out) or (bool(punch_in or punch_out) and blink))
        # A rolling transport is not evidence of recording; use Ardour's record state.
        self.led(17, bool(record == 2 and armed_track) or (bool(record) and blink))

    def tick(self, now=None):
        now = self.clock() if now is None else now
        if self.received is not None and now - self.received > self.TIMEOUT:
            self.transport = None; self.received = None
            for key in (5, 8, 11, 17): self.led(key, False)
        self.render(now)
        if now < self.next_query: return []
        self.next_query = now + (self.INTERVAL if self.transport is not None else 5.)
        return [('osc', PATH, [])]

    def status(self):
        return {'transport_feedback': self.transport is not None, 'range_guide': self.range_phase}
