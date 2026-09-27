"""Shared bounded meter sampling for all local web clients."""
# SPDX-License-Identifier: GPL-3.0-or-later
import threading
import time
from surface_settings import rpc

class WebMeters:
    INTERVAL = .04
    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = threading.Lock()
        self.sampled = float('-inf')
        self.frame = {'ok': False, 'active': False, 'strips': [], 'large': []}
    def state(self):
        with self.lock:
            if time.monotonic()-self.sampled < self.INTERVAL: return dict(self.frame)
            try:
                frame = rpc(self.runtime, 'control.sock', {'command': 'meters'}, timeout=.12)
                if not frame.get('ok'): raise ValueError('Meter source unavailable')
                self.frame = frame
            except (OSError, ValueError):
                self.frame = {'ok': False, 'active': False, 'strips': [], 'large': []}
            # Completion time: a slow failed RPC cannot multiply across clients.
            self.sampled = time.monotonic()
            return dict(self.frame)
