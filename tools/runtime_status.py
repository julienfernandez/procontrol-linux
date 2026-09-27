"""Read service snapshots without mistaking a recent file for a live worker."""
# SPDX-License-Identifier: GPL-3.0-or-later
import fcntl
import json
import os
import time


def lock_held(path):
    try:
        with path.open('r') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
    except OSError:
        pass
    return False


def service_status(runtime, filename='status.json', lockname='daemon.lock'):
    data, fresh = {}, False
    try:
        # Read metadata from the same inode as the atomic snapshot.
        with (runtime / filename).open() as stream:
            age = time.time() - os.fstat(stream.fileno()).st_mtime
            data = json.load(stream)
        if not isinstance(data, dict):
            data = {}
        fresh = 0 <= age < 5
    except (OSError, ValueError):
        pass
    running = lock_held(runtime / lockname)
    live = bool(running and fresh and data.get('running'))
    data.update(running=running, fresh=fresh, live=live)
    if not live:
        # Keep PID/counters for diagnosis, but never replay old connection or meter states.
        data.update(console='stopped' if data.get('console') == 'stopped' else 'unknown', ardour='waiting')
        data['stereo'] = {'active': False, 'routes_ready': False, 'sources': [], 'large': []}
        data['track_monitor'] = {'tracks': []}
    return data
