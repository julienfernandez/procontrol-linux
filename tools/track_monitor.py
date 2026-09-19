"""Confirmed per-track IN/DISK monitoring, independent of record enable."""
# SPDX-License-Identifier: GPL-3.0-or-later
import re
import time
from surface_map import osc
from surface_feedback import button_led, scribble

INPUT = '/strip/monitor_input'
DISK = '/strip/monitor_disk'
FIELDS = (INPUT, DISK)
MODES = {(0, 0): 'AUTO', (1, 0): 'IN', (0, 1): 'DISK', (1, 1): 'IN+DISK'}
TARGETS = {'input': (1, 0), 'disk': (0, 1), 'auto': (0, 0)}


class TrackMonitor:
    TIMEOUT = 2.0

    def __init__(self, routing, feedback, clock=time.monotonic):
        self.routing = routing; self.feedback = feedback; self.mapper = routing.mapper
        self.clock = clock; self.active = False; self.held = set()
        self.pending = {}; self.errors = {}; self.queried = {}; self.error = None
        self.selection_pending = None
        routing.monitor = self; self.mapper.monitor = self; feedback.monitor = self
        self.render()

    @staticmethod
    def normalize(path, values):
        match = re.fullmatch(r'(/strip/monitor_(?:input|disk))/(\d+)', path)
        if match and len(values) == 1:
            return match[1], [int(match[2]), values[0]]
        return path, values

    def state(self, sid):
        bits = []
        for path in FIELDS:
            row = self.routing.cache.get((path, sid))
            if not row or len(row) != 2 or type(row[1]) not in (int, float) or row[1] not in (0, 1):
                return None
            bits.append(int(row[1]))
        return tuple(bits)

    def track(self, sid):
        return self.routing.ready and self.routing.rows.get(sid, {}).get('kind') in ('AT', 'MT')

    def selected(self):
        selected = [sid for sid in self.routing.rows if self.track(sid) and
                    self.routing.cache.get(('/strip/select', sid), [sid, 0])[1] == 1]
        return selected[0] if len(selected) == 1 else None

    def select_requested(self, sid=None):
        # A SELECT followed immediately by INPUT must use the user's new
        # absolute target, even before Ardour publishes its selection feedback.
        self.selection_pending = None if sid is not None and sid == self.selected() else (sid, self.clock())

    def target_selected(self):
        if self.selection_pending is None: return self.selected()
        sid, at = self.selection_pending
        return sid if self.clock() - at < self.TIMEOUT and self.track(sid) else None

    def enter(self):
        eq = getattr(self.routing, 'eq', None)
        if eq is not None and eq.active: eq.exit()
        self.active = True; self.error = None; self.render()

    def exit(self):
        self.active = False; self.error = None
        # Only the display mode ends. A valid command already in flight may
        # finish on its original absolute track ID after a bank/mode change.
        for ch in range(1, 9):
            self.feedback.put(('led', ch-1, 4), button_led(ch-1, 4, False))
        for key in (9, 10, 11, 7):
            self.feedback.put(('led', 8, key), button_led(8, key, False))
        self.feedback.end_eq_display()

    def disconnect(self):
        self.pending.clear(); self.errors.clear(); self.queried.clear(); self.held.clear()
        self.selection_pending = None
        self.exit()

    def catalog_changed(self):
        self.pending.clear(); self.errors.clear(); self.queried.clear()
        self.selection_pending = None
        # Absolute OSC IDs can be reused after track removal/reordering.
        self.routing.cache = {k: v for k, v in self.routing.cache.items() if k[0] not in FIELDS}

    def command(self, c):
        if len(c) == 3 and c[0] == 0xb0 and self.active and (0x40 <= c[1] <= 0x47 or 0x4d <= c[1] <= 0x54):
            return []  # no hidden pan/plugin edit while displaying monitoring
        if len(c) != 3 or c[0] != 0x90 or c[2] >= 128: return None
        zone, key, down = c[2] & 63, c[1], bool(c[2] & 64)
        physical = (zone, key)
        if not down and physical in self.held:
            self.held.discard(physical); return []
        if down and physical in self.held: return []
        if physical == (8, 9) and not self.mapper.modifiers:
            if not down: return []
            self.held.add(physical)
            if self.active: self.exit()
            else: self.enter()
            return []
        if physical in ((8, 10), (8, 11)) or (self.active and physical == (8, 7)):
            if not down: return []
            self.held.add(physical); self.enter()
            return [('monitor', 'selected', [{10: 'input', 11: 'disk', 7: 'auto'}[key]])]
        if self.active and zone < 8 and key == 4:
            if not down: return []
            self.held.add(physical)
            return [('monitor', 'toggle', [zone+1])]
        if self.active and down and (
                (zone == 8 and key in (8, 12, 14, 15, 16, 17, 18)) or
                (zone < 8 and key in (1, 2, 3, 10)) or
                (zone == 0x15 and key in (1, 2, 3)) or
                physical in ((0x19, 4), (0x17, 0x30))):
            self.exit()
            if physical == (0x17, 0x30): return []
        return None

    def handle(self, action, values):
        if action == 'selected':
            sid = self.target_selected(); target = TARGETS.get(values[0]) if values else None
            if target is None: return []
            if sid is None:
                self.error = 'SELECT?'; self.render(); return []
        elif action == 'toggle' and values:
            slots = self.routing.slots(); slot = values[0]
            if type(slot) is not int or not 1 <= slot <= len(slots): return []
            sid = slots[slot-1]
            current = self.pending.get(sid, {}).get('target') or self.state(sid)
            # Unknown state is queried before interpreting a toggle.
            target = (0, 1) if current == (1, 0) else (1, 0) if current is not None else None
        else: return []
        if not self.track(sid): return []
        self.error = None; self.errors.pop(sid, None)
        previous = self.pending.get(sid, {})
        self.pending[sid] = dict(target=target, at=self.clock(), inflight=previous.get('inflight'))
        return self.advance(sid)

    def query(self, sid):
        now = self.clock()
        if now - self.queried.get(sid, -100) < .5: return []
        self.queried[sid] = now
        # Embed SSID: Ardour's one-argument read reply otherwise omits its ID.
        return [osc(path + '/' + str(sid)) for path in FIELDS]

    def feed(self, path, values):
        if path in FIELDS and len(values) == 2:
            sid, value = values
            pending = self.pending.get(sid)
            if pending and pending['inflight'] == (path, value): pending['inflight'] = None
        if path == '/strip/select' and len(values) == 2 and values[1] == 1:
            if self.selection_pending is not None and self.selection_pending[0] in (None, values[0]):
                self.selection_pending = None
            self.error = None
        if path in FIELDS or path == '/strip/select': self.render()

    def advance(self, sid):
        pending = self.pending.get(sid)
        if not pending or not self.track(sid): return []
        if self.clock() - pending['at'] >= self.TIMEOUT:
            self.pending.pop(sid); self.errors[sid] = self.clock(); return self.query(sid)
        current = self.state(sid)
        if current is None: return self.query(sid)
        if pending['inflight'] is not None: return []
        if pending['target'] is None: pending['target'] = (0, 1) if current == (1, 0) else (1, 0)
        target = pending['target']
        if current == target:
            self.pending.pop(sid); return []
        # MonitorControl is RealTime: two immediate read-modify-write OSC
        # packets can both read the old value and accidentally enable both.
        # Disable unwanted sources first, then enable the requested source,
        # waiting for confirmed feedback after EACH write.
        changes = sorted((target[i], i) for i in range(2) if current[i] != target[i])
        value, index = changes[0]; path = FIELDS[index]
        pending['inflight'] = (path, value)
        return [osc(path, sid, value)]

    def tick(self, now=None):
        self.errors = {sid: at for sid, at in self.errors.items() if self.clock()-at < 3}
        result = []
        for sid in list(self.pending): result.extend(self.advance(sid))
        if self.active and self.routing.ready:
            for sid in self.routing.slots():
                if self.track(sid) and self.state(sid) is None: result.extend(self.query(sid))
        self.render()
        return result

    def render(self):
        if not self.active: return
        now = self.clock(); slots = self.routing.display_slots()
        for ch in range(1, 9):
            sid = slots[ch-1] if ch <= len(slots) else None
            state = self.state(sid) if self.track(sid) else None
            waiting = sid in self.pending or (self.track(sid) and state is None)
            if self.error: text = self.error
            elif sid in self.errors and now-self.errors[sid] < 3: text = 'ERREUR'
            elif waiting: text = 'Attente'
            elif not self.track(sid): text = '--'
            else: text = MODES[state]
            on = (int(now*8) % 2 == 0) if waiting else (int(now) % 2 == 0) if state == (0, 0) else bool(state and state[0])
            self.feedback.put(('value', ch), scribble(ch, text, False))
            self.feedback.put(('led', ch-1, 4), button_led(ch-1, 4, on))
        selected = self.state(self.selected())
        for key, on in ((9, True), (10, bool(selected and selected[0])),
                        (11, bool(selected and selected[1])), (7, selected == (0, 0))):
            self.feedback.put(('led', 8, key), button_led(8, key, on))

    def status(self):
        return dict(active=self.active, error=self.error, pending=len(self.pending),
                    tracks=[dict(slot=i, sid=sid, mode=MODES.get(self.state(sid)),
                                 pending=sid in self.pending, error=sid in self.errors)
                            for i, sid in enumerate(self.routing.slots(), 1) if self.track(sid)])
