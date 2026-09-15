"""Follow console editing with one native Ardour plugin window.

The optional local Ardour OSC extension validates session, persistent route ID,
plugin index and name. No audio parameters or mixer selection are written here.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

PREFIX = '/procontrol/plugin_ui/'


class PluginWindowFollower:
    def __init__(self):
        self.reset()

    def reset(self):
        self.supported = False
        self.target = None
        self.confirmed = None
        self.waiting = False
        self.attempts = 0
        self.deadline = 0
        self.error = None
        self.clear_pending = False

    def feed(self, path, values):
        if path == PREFIX+'version' and values == [1]:
            self.supported = True
        elif path == PREFIX+'result' and len(values) == 5 and tuple(values[:4]) == self.target:
            self.waiting = False
            if values[4] == 1:
                self.confirmed = self.target
                self.error = None
            else:
                self.error = 'Cible refusée par Ardour'
                self.clear_pending = True

    def update(self, editor, routing, now):
        if not self.supported:
            return []
        if self.clear_pending:
            self.clear_pending = False
            self.confirmed = None
            return [('osc', PREFIX+'clear', [])]
        if not editor.active or editor.mode == 'browse' or editor.error:
            if self.target is None:
                return []
            self.target = self.confirmed = None
            self.waiting = False
            self.error = None
            return [('osc', PREFIX+'clear', [])]
        # A selection triggers a brief catalogue refresh. Keep the old window
        # while identities/descriptors settle; never reopen for every snapshot.
        if not routing.ready or not editor.usable() or not editor.valid_target():
            return []
        route_id = routing.identities.get(editor.sid)
        if not routing.session or not route_id or not editor.plugin:
            return []
        target = (routing.session, str(route_id), editor.plugin, editor.plugin_name)
        if target != self.target:
            self.target = target
            self.attempts = 0
            self.waiting = True
            self.error = None
        elif not self.waiting or now < self.deadline:
            return []
        if self.attempts >= 2:
            self.waiting = False
            self.error = 'Ouverture non confirmée'
            self.confirmed = None
            return [('osc', PREFIX+'clear', [])]
        self.attempts += 1
        self.deadline = now+1
        return [('osc', PREFIX+'show', list(target))]

    def status(self):
        return dict(supported=self.supported, target=self.target,
                    confirmed=self.confirmed, waiting=self.waiting, error=self.error)
