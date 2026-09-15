"""Bound normal jog traffic without building a history of transport seeks."""
# SPDX-License-Identifier: GPL-3.0-or-later
import time


class JogScheduler:
    INTERVAL = .020

    def __init__(self):
        self.mode = 0
        self.pending = 0.
        self.last_send = -float('inf')
        self.inputs = 0
        self.outputs = 0
        self.input_delta = 0.
        self.output_delta = 0.
        self.cancelled_delta = 0.

    def cancel(self):
        self.cancelled_delta += self.pending
        self.pending = 0.

    def flush(self, now=None, force=False):
        now = time.monotonic() if now is None else now
        if not self.pending or (not force and now < self.last_send + self.INTERVAL):
            return []
        delta = self.pending
        self.pending = 0.
        self.last_send = now
        self.outputs += 1
        self.output_delta += delta
        return [('osc', '/jog', [delta])]

    def actions(self, actions, now=None):
        now = time.monotonic() if now is None else now
        result = []
        for kind, path, values in actions:
            if kind == 'osc' and path == '/jog' and self.mode == 0:
                # Relative displacement must be summed, never latest-only.
                # The first gesture is immediate; at most one sum waits 20ms.
                delta = float(values[0])
                self.pending += delta
                self.inputs += 1
                self.input_delta += delta
                result.extend(self.flush(now))
            else:
                # Keep transport/mode changes ordered. Scrub and shuttle have
                # different semantics and bypass normal jog accumulation.
                result.extend(self.flush(now, force=True))
                result.append((kind, path, values))
                if kind == 'osc' and path == '/jog/mode':
                    self.mode = int(values[0])
        return result

    def wait_timeout(self, now, maximum=.05):
        if not self.pending:
            return maximum
        return min(maximum, max(0., self.last_send + self.INTERVAL - now))

    def status(self):
        return dict(hz=1/self.INTERVAL, inputs=self.inputs, outputs=self.outputs,
                    pending_delta=self.pending, input_delta=self.input_delta,
                    output_delta=self.output_delta, cancelled_delta=self.cancelled_delta)
