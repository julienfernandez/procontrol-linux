#!/usr/bin/env python3
"""One desktop entry for Ardour, the Gateway and the configured USB studio."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8765'


def notify(text, error=False):
    try:
        subprocess.run(['notify-send', '--app-name=Ardour Studio', '--icon=ardour',
                        '--urgency='+('critical' if error else 'normal'),
                        'Ardour — Studio', text], timeout=4, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def api(action=None):
    request = urllib.request.Request(URL+'/api/studio'+('/action' if action else ''),
              data=json.dumps({'action':action}).encode() if action else None,
              headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=4) as response:
        return json.load(response)


def running_ardour(binary):
    executable = binary.parent.parent/'lib/ardour9/ardour-9.8.0'
    result = []
    for entry in Path('/proc').glob('[0-9]*/exe'):
        try:
            if entry.resolve() == executable.resolve():
                result.append(int(entry.parent.name))
        except OSError:
            pass
    return result


def focus(pids):
    try:
        windows = subprocess.check_output(['wmctrl', '-lp'], text=True, timeout=4)
        for line in windows.splitlines():
            fields = line.split(None, 4)
            if len(fields) >= 4 and int(fields[2]) in pids:
                subprocess.run(['wmctrl', '-ia', fields[0]], timeout=4, check=True)
                return True
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return False


def usb_ready(state):
    graph = state.get('graph', {})
    return bool(not state.get('stale', True) and graph.get('usb') and
                not state.get('repair_needed', True))


def prepare_usb(timeout=65):
    """Reuse a running Gateway job; never run a second hardware controller."""
    deadline, requested = time.monotonic()+timeout, False
    while time.monotonic() < deadline:
        state = api()
        busy = state.get('job', {}).get('state') in ('queued', 'running')
        if usb_ready(state) and not busy:
            return True
        if not busy and not requested:
            try:
                api('recover')
                requested = True
            except urllib.error.HTTPError as exc:
                if exc.code != 400:
                    raise
                # The supervisor can enqueue automatic recovery concurrently.
                if api().get('job', {}).get('state') not in ('queued', 'running'):
                    raise
                requested = True
        elif requested and not busy and state.get('job', {}).get('state') in ('failed', 'interrupted'):
            return False
        time.sleep(.5)
    return False


def finish_routing(timeout=40):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        state = api()
        if not state.get('stale') and state.get('route_allowed'):
            graph = state.get('graph', {})
            if graph.get('tracks') == 16 and graph.get('master') == 2 and not graph.get('master_other'):
                return
            if usb_ready(state) and graph.get('behringer') and state.get('job', {}).get('state') not in ('queued', 'running'):
                api('route')
                return
        time.sleep(.5)


def launch(config, project=None, control=False, output=None):
    binary = Path(config.get('ardour_launcher', str(Path.home()/'.local/opt/ardour-9.8/bin/ardour9')))
    if not control and not binary.is_file():
        raise RuntimeError('Ardour 9.8 introuvable : '+str(binary))
    session = Path(config['session'])
    target = Path(project).expanduser().resolve() if project else session/(session.name+'.ardour')
    if not control and not target.exists():
        raise RuntimeError('Projet Ardour introuvable : '+str(target))
    subprocess.run([sys.executable, str(ROOT/'tools/desktop_launcher.py'), '--no-browser'],
                   stdout=output, stderr=subprocess.STDOUT, timeout=100, check=True)
    if control:
        subprocess.Popen(['xdg-open', URL], stdout=output, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        return 'control'
    if config.get('launch_link') is True:
        try:
            subprocess.run([str(ROOT/'link'), 'start'], stdout=output, stderr=subprocess.STDOUT,
                           timeout=12, check=True)
        except (OSError, subprocess.SubprocessError):
            notify('La synchronisation Link est indisponible. Consulter la Gateway.', True)
    pids = running_ardour(binary)
    if pids:
        focus(pids)
        if project:
            notify('Ardour est déjà ouvert. Utilise Session → Ouvrir pour changer de projet.')
        return 'focused'
    notify('Préparation du studio et ouverture d’Ardour…')
    try:
        ready = prepare_usb()
    except (OSError, ValueError, urllib.error.URLError):
        ready = False
    if not ready:
        notify('La MPC USB est en attente. Ardour ouvre le projet ; l’état et la remise en service restent dans la Gateway.')
    # The installed Ardour wrapper still supplies the PipeWire JACK library and
    # latency. The Gateway already owns preparation, so its hook must not repeat it.
    env = dict(os.environ, MPC_STUDIO_PREPARED='1')
    if running_ardour(binary):
        focus(running_ardour(binary))
        return 'focused'
    child = subprocess.Popen([str(binary), str(target)], env=env, stdout=output,
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    if ready and target == session/(session.name+'.ardour'):
        try:
            finish_routing()
        except (OSError, ValueError, urllib.error.URLError):
            notify('Ardour est lancé. Vérifie les connexions dans la Gateway.')
    if child.poll() not in (None, 0):
        raise RuntimeError('Ardour n’a pas démarré ; consulter run/ardour-studio-launch.log')
    return 'started'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', nargs='?')
    parser.add_argument('--control', action='store_true')
    args=parser.parse_args()
    runtime=ROOT/'run';runtime.mkdir(exist_ok=True)
    with (runtime/'ardour-studio-launch.lock').open('a') as guard:
        try:
            fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            notify('Le studio est déjà en cours d’ouverture.')
            return 0
        path=runtime/'ardour-studio-launch.log'
        if path.exists() and path.stat().st_size>1024*1024:
            path.replace(runtime/'ardour-studio-launch.log.1')
        with path.open('a', buffering=1) as output:
            output.write('\n'+time.strftime('%Y-%m-%d %H:%M:%S %z')+' — lancement\n')
            try:
                config=json.loads((ROOT/'studio.json').read_text())
                result=launch(config,args.project,args.control,output)
                output.write('Résultat : '+result+'\n')
                return 0
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
                output.write('Erreur : '+str(exc)+'\n')
                notify(str(exc),True)
                return 1


if __name__ == '__main__':
    sys.exit(main())
