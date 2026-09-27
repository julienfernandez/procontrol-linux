"""Read-only evidence for bank/matrix commands and actual mix feedback."""
# SPDX-License-Identifier: GPL-3.0-or-later

MIX_PATHS = {'/strip/solo', '/strip/mute', '/strip/recenable'}


def context(mapper, routing):
    editor = getattr(routing, 'eq', None)
    return dict(matrix_mode=mapper.matrix_mode, matrix_bank=mapper.matrix_bank,
                bank_start=routing.start + 1, master=routing.master,
                ready=routing.ready,
                editor=dict(active=editor.active, mode=editor.mode, sid=editor.sid,
                            plugin=editor.plugin, ready=editor.ready) if editor else None,
                slots=[dict(slot=i, sid=sid, name=routing.rows[sid]['name'],
                            route_id=routing.identities.get(sid))
                       for i, sid in enumerate(routing.slots(), 1)])


def relevant(actions, before, after):
    return before != after or any(kind in ('bank', 'matrix', 'eq') or path in MIX_PATHS
                                  for kind, path, values in actions)


def mix_change(routing, path, values):
    if path not in MIX_PATHS or len(values) != 2 or type(values[0]) is not int:
        return None
    sid, value = values
    if sid <= 0 or type(value) not in (int, float) or value not in (0, 1):
        return None
    previous = routing.cache.get((path, sid))
    old = previous[1] if previous is not None else None
    if old == value:
        return None
    return dict(address=path, sid=sid, value=value, previous=old,
                name=routing.rows.get(sid, {}).get('name'),
                route_id=routing.identities.get(sid))
