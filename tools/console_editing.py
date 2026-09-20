"""Console editing actions for Ardour 9.8's explicit main-editor context.

Button addresses come from the vendored ProControl reference. Unknown navigation
addresses are deliberately not inferred from the appearance of the console.
"""
# SPDX-License-Identifier: GPL-3.0-or-later


def actions(*names):
    return [('osc', '/access_action', [name]) for name in names]


class ConsoleEditing:
    BUTTONS = ({(0x18, n) for n in range(5)} |
               {(0x19, n) for n in (0, 1, 3, 6, 7)} |
               {(0x1b, n) for n in range(17)} |
               {(0x1c, n) for n in (0, 1, 2, 3, 4, 5, 8, 9, 10, 11)})

    def __init__(self, mapper):
        self.mapper = mapper
        self.held = set()
        self.zoom_navigation = False

    def reset(self):
        self.held.clear()
        self.zoom_navigation = False
        indicators = getattr(self.mapper, 'indicators', None)
        if indicators is not None: indicators.reset_range()

    def editor(self, *names):
        # Edits must never follow a stale mouse pointer over another waveform.
        return actions('Common/show-editor', 'Editor/edit-at-playhead', *names)

    def command(self, c):
        if len(c) != 3 or c[0] != 0x90 or c[2] >= 128:
            return None
        z, n, down = c[2] & 63, c[1], bool(c[2] & 64)
        physical = z, n
        if physical not in self.BUTTONS:
            return None
        if not down and physical in self.held:
            self.held.discard(physical)
            return []
        # Plugin browsing owns bank arrows until the user enters the editor.
        if z == 0x1b and n in (10, 11, 12):
            eq = getattr(self.mapper, 'eq', None)
            if eq is not None and eq.active:
                return None
            if n in (10, 12) and not self.mapper.nudge:
                return None  # ordinary bank changes retain their normal path
        if not down:
            self.held.discard(physical)
            return []
        if physical in self.held:
            return []
        self.held.add(physical)
        shift = bool(self.mapper.modifiers & {'Shift_L', 'Shift_R'})
        ctrl = bool(self.mapper.modifiers & {'Control_L', 'Control_R'})
        alt = bool(self.mapper.modifiers & {'Alt_L', 'Alt_R'})

        if z == 0x18:
            for name in ('eq', 'monitor'):
                mode = getattr(self.mapper, name, None)
                if mode is not None and mode.active:
                    mode.exit()
            if n == 2:
                if shift:
                    return self.editor('Editor/zoom-to-selection')
                if alt:
                    return self.editor('Editor/zoom-to-session')
                self.zoom_navigation = not self.zoom_navigation
                return [('led', '24:2', [int(self.zoom_navigation)])]
            if self.zoom_navigation:
                return self.editor({0: 'Editor/expand-tracks', 4: 'Editor/shrink-tracks',
                                    1: 'EditorEditing/temporal-zoom-out',
                                    3: 'EditorEditing/temporal-zoom-in'}[n])
            if n in (0, 4):
                # The routing layer tracks pending OSC selection so an immediate
                # INPUT/OUTPUT press cannot act on the previous strip.
                return self.editor() + [('osc', '/select/previous' if n == 0 else '/select/next', [1.0])]
            return self.editor('Editor/playhead-to-previous-region-boundary' if n == 1
                               else 'Editor/playhead-to-next-region-boundary')

        if z == 0x19:
            if n == 0:
                return actions('Common/show-mixer')
            if n == 6:
                return actions('EditorEditing/redo' if shift else 'EditorEditing/undo')
            if n == 7:
                return actions('Common/Save')
            if n == 3:
                return self.editor('Editor/center-playhead')
            for name in ('eq', 'monitor'):
                mode = getattr(self.mapper, name, None)
                if mode is not None and mode.active:
                    mode.exit()
            return self.editor()

        if z == 0x1b:
            if n in (10, 12):
                return self.editor('Editor/nudge-backward' if n == 10 else 'Editor/nudge-forward')
            if n == 11:
                self.mapper.nudge = not self.mapper.nudge
                return [('led', '27:11', [int(self.mapper.nudge)])]
            if n in (0, 1):
                return self.editor('Editor/set-edit-ripple' if n == 0 else 'Editor/set-edit-slide')
            if n == 2:
                return self.editor('Region/align-regions-end-relative' if shift else 'Region/align-regions-start-relative')
            if n == 3:
                if alt:
                    return self.editor('EditorEditing/snap-off')
                return self.editor('EditorSnap/grid-type-beat' if shift else 'EditorSnap/grid-type-bar',
                                   'EditorEditing/snap-normal')
            if n in (4, 5, 6, 7):
                if shift and n in (5, 6):
                    return self.editor('Editor/duplicate')
                return self.editor('EditorEditing/' + {4: 'editor-cut', 5: 'editor-copy',
                                                       6: 'editor-paste', 7: 'editor-delete'}[n])
            if n == 8:
                if shift:
                    return self.editor('EditorEditing/set-mouse-mode-object', 'Editor/select-all-objects',
                                       'Editor/split-region')
                return self.editor('Editor/split-region')
            if n == 9:
                return self.editor('Editor/select-loop-range' if shift else 'Editor/set-loop-from-edit-range')
            if n == 13:
                return self.editor('EditorEditing/set-mouse-mode-timefx' if shift else 'Editor/editor-crop')
            if n == 14:
                return self.editor(*(['Common/select-all-tracks'] if shift else []),
                                   'EditorEditing/set-mouse-mode-range')
            if n == 15:
                # Restore range mode before reading IN/OUT, even after a prior GRAB.
                return self.editor('EditorEditing/set-mouse-mode-range',
                                   'Editor/select-all-within-cursors' if shift else 'Editor/select-all-between-cursors',
                                   'EditorEditing/set-mouse-mode-object')
            if n == 16:
                return self.editor('EditorEditing/set-mouse-mode-draw')

        if z == 0x1c:
            if n in (5, 8, 11):
                return actions('Transport/TogglePunch' if n == 11 else 'Transport/ToggleExternalSync')
            if n in (1, 4):
                if ctrl:
                    return self.editor('Editor/playhead-to-range-start' if n == 1 else 'Editor/playhead-to-range-end')
                return [('osc', '/jump_bars', [float((-1 if n == 1 else 1) * (4 if shift else 1))])]
            if n in (2, 3):
                if ctrl:
                    return [('osc', '/toggle_punch_in' if n == 2 else '/toggle_punch_out', [1.0])]
                if shift:
                    return self.editor('Common/start-loop-range' if n == 2 else 'Common/finish-loop-range',
                                       'Editor/select-loop-range')
                # Reset to a zero-length range on IN: Ardour's bare mark_in
                # otherwise selects to infinity when there is no previous OUT.
                names = ['EditorEditing/set-mouse-mode-range']
                names += (['Common/finish-range-from-playhead', 'Common/start-range-from-playhead']
                          if n == 2 else ['Common/finish-range-from-playhead'])
                return self.editor(*names)
            if n == 0:
                return self.editor('Region/play-selected-regions' if shift else 'Transport/PlaySelection')
            if n == 10:
                return self.editor('Editor/set-punch-from-edit-range')
            if n == 9:
                if shift or self.mapper.state.get(('/loop_toggle', None), 0):
                    return actions('Transport/Loop')
                # Both execute in GUI order. Transport/Roll must not be sent
                # alongside Loop: their asynchronous transport events conflict.
                return self.editor('Editor/set-loop-from-edit-range', 'Transport/Loop')
        return None
