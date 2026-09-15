#!/usr/bin/env python3
"""Start the ProControl user services from the desktop, then open settings."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import fcntl
from pathlib import Path
import shutil
import subprocess
import sys
import json
import time
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8765'

def notify(text, error=False):
    if shutil.which('notify-send'):
        try:
            subprocess.run(['notify-send','--app-name=ProControl','--icon=audio-card',
                            '--urgency='+('critical' if error else 'normal'),
                            'ProControl',text],timeout=5,check=False)
        except (OSError,subprocess.TimeoutExpired):pass

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--restart',action='store_true',help='Arrêter proprement puis relancer les services')
    args=parser.parse_args()
    runtime=ROOT/'run';runtime.mkdir(mode=0o700,exist_ok=True)
    with (runtime/'desktop-launch.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            notify('Un démarrage ou redémarrage est déjà en cours.');return 0
        with (runtime/'desktop-launch.log').open('w') as log:
            log.write(datetime.now().astimezone().isoformat()+'\n');log.flush()
            def state(script):
                result=subprocess.run([str(ROOT/script),'status'],cwd=ROOT,capture_output=True,text=True,timeout=5,check=True)
                return json.loads(result.stdout).get('running',False)
            def run(script,action):
                result=subprocess.run([str(ROOT/script),action],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=30)
                if result.returncode:raise RuntimeError(f'{script} : {action} impossible')
            try:
                already=all(state(script) for script in ('procontrol','pointer','settings'))
                if args.restart:
                    for script in ('pointer','procontrol','settings'):
                        run(script,'stop')
                        deadline=time.monotonic()+5
                        while state(script):
                            if time.monotonic()>deadline:raise RuntimeError(f'{script} ne s’arrête pas')
                            time.sleep(.1)
                for script in ('procontrol','pointer','settings'):
                    run(script,'start')
                    if not state(script):raise RuntimeError(f'{script} n’est pas actif après démarrage')
            except (OSError,subprocess.SubprocessError,RuntimeError,ValueError) as exc:
                log.write(str(exc)+'\n');log.flush()
                notify(f'{exc}. Détails : {runtime / "desktop-launch.log"}',True)
                return 1
        if not args.no_browser:
            try:
                subprocess.Popen(['xdg-open',URL],stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            except OSError as exc:notify(f'Services démarrés. Ouvre {URL} ({exc}).',True)
        message='Passerelle redémarrée.' if args.restart else ('Passerelle déjà active.' if already else 'Passerelle démarrée.')
        notify(message+' Les réglages affichent l’état de la console et d’Ardour.')
    return 0

if __name__=='__main__':sys.exit(main())
