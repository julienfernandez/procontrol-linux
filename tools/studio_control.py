#!/usr/bin/env python3
"""USB studio supervision, outside the console/OSC timing loop.

The backend owns hardware changes and its flock. The Gateway owns observation,
serialized jobs, bounded retries and their journal. HTTP cannot supply commands.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def sections(text):
    result, key = {}, None
    for line in text.splitlines():
        if line.startswith('@@'):
            key = line[2:]
            result[key] = ''
        elif key:
            result[key] += line + '\n'
    return {k: v.strip() for k, v in result.items()}


def pcm_info(text):
    return dict(re.findall(r'^([a-z_]+)\s*:\s*(.*?)\s*$', text, re.M))


def graph_health(objects):
    """Count actual channel pairs, not process names or old status files."""
    nodes = {o['id']: o.get('info', {}).get('props', {}) for o in objects
             if o['type'] == 'PipeWire:Interface:Node'}
    ports = {o['id']: o.get('info', {}).get('props', {}) for o in objects
             if o['type'] == 'PipeWire:Interface:Port'}
    links = [o['info'] for o in objects if o['type'] == 'PipeWire:Interface:Link'
             and o.get('info', {}).get('state') != 'error']
    def node(prefix):
        found = [i for i, p in nodes.items() if p.get('node.name', '').startswith(prefix)]
        return found[0] if len(found) == 1 else None
    source = node('alsa_input.usb-Akai_Professional_MPC_One_USB_Audio_16ch_')
    sink = node('alsa_output.usb-Akai_Professional_MPC_One_USB_Audio_16ch_')
    behringer = node('alsa_output.usb-Burr-Brown_from_TI_USB_Audio_CODEC-')
    def owner(p):
        try:
            return int(p.get('node.id', -1))
        except (ValueError, TypeError):
            return -1
    keepalive = {}
    for key, name, playback in [('playback', 'codex-mpc-usb-silence-v3', True),
                                ('capture', 'codex-mpc-usb-capture-keepalive-v3', False)]:
        stream = node(name)
        src, dst = (stream, sink) if playback else (source, stream)
        expected = {(f'AUX{i}', f'AUX{i}') for i in range(16)}
        found, wrong = set(), 0
        for l in links:
            if stream is None or l.get('output-node-id' if playback else 'input-node-id') != stream:
                continue
            if l.get('output-node-id') != src or l.get('input-node-id') != dst:
                wrong += 1
                continue
            a, b = ports.get(l.get('output-port-id'), {}), ports.get(l.get('input-port-id'), {})
            pair = (a.get('audio.channel'), b.get('audio.channel'))
            if pair in expected and l.get('state') == 'active':
                found.add(pair)
            elif pair not in expected:
                wrong += 1
        keepalive[key] = {'channels': len(found), 'wrong': wrong, 'present': stream is not None}
    track_pairs, master_pairs, master_wrong = set(), set(), 0
    for l in links:
        a, b = ports.get(l.get('output-port-id'), {}), ports.get(l.get('input-port-id'), {})
        alias = b.get('port.alias', '')
        for i in range(16):
            track = f'ardour:MPC {(i//2)*2+1:02d}-{(i//2)*2+2:02d}/audio_in {i%2+1}'
            if owner(a) == source and a.get('audio.channel') == f'AUX{i}' and alias == track:
                track_pairs.add(i)
        for i, ch in [(1, 'FL'), (2, 'FR')]:
            if a.get('port.alias') == f'ardour:Master/audio_out {i}':
                if owner(b) == behringer and b.get('audio.channel') == ch:
                    master_pairs.add(i)
                else:
                    master_wrong += 1
    return {'usb': source is not None and sink is not None,
            'behringer': behringer is not None, 'keepalive': keepalive,
            'tracks': len(track_pairs), 'master': len(master_pairs), 'master_other': master_wrong}


class StudioBackend:
    def __init__(self, root, config):
        self.root, self.config = Path(root), config
        self.path = self.root/'integrations/mpc_usb/studio.py'
        self.home = Path(config.get('data_root', '/nonexistent/studio'))
        self.host = config.get('host', '')
        self.available = (self.path.is_file() and self.home.is_dir() and bool(config.get('session')) and
                          bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', self.host)))

    def remote(self):
        visibility = read_json(self.home / 'run/audio-visibility.json')
        address = visibility.get('address', '')
        address = int(address, 16) if re.fullmatch(r'0x[0-9a-fA-F]{1,16}', str(address)) else 0
        script = '''
echo @@boot; cat /proc/sys/kernel/random/boot_id
echo @@gadget; cat /sys/kernel/config/usb_gadget/codex_mpc_audio/UDC 2>/dev/null
echo @@usb_state; cat /sys/class/udc/ff580000.usb/state 2>/dev/null
echo @@cards; cat /proc/asound/cards
echo @@mpc_pid; systemctl show -p MainPID --value acvs
for c in /proc/asound/card[0-9]*; do
  if [ "$(cat "$c/id" 2>/dev/null)" = UAC2Gadget ]; then
    echo @@playback; cat "$c/pcm0p/sub0/status" "$c/pcm0p/sub0/hw_params"
    echo @@capture; cat "$c/pcm0c/sub0/status" "$c/pcm0c/sub0/hw_params"
  fi
done
echo @@midi; if [ -x /tmp/aconnect ]; then /tmp/aconnect -l; fi
'''
        if address:
            script += ('echo @@visibility; p=$(systemctl show -p MainPID --value acvs); '
                       f'dd if=/proc/$p/mem bs=1 skip={address} count=11 2>/dev/null; echo\n')
        args = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=4',
                '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=3',
                '-o', 'ServerAliveCountMax=1', '-o', 'UserKnownHostsFile=' + str(self.home/'run/known_hosts'),
                'root@' + self.host, script]
        return sections(subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=12))

    def route_allowed(self):
        status_path = self.root/'run/status.json'
        d = read_json(status_path)
        try:
            fresh = time.time() - status_path.stat().st_mtime < 5
        except OSError:
            fresh = False
        return bool(fresh and d.get('running') and d.get('ardour') == 'responding' and
                    self.config.get('session') and
                    d.get('stereo', {}).get('session') == self.config['session'])

    def snapshot(self):
        result = {'configured': self.available, 'components': [], 'repair_needed': False,
                  'route_allowed': self.route_allowed(), 'remote': {}, 'graph': {}}
        def add(key, label, state, detail):
            result['components'].append(dict(key=key, label=label, state=state, detail=detail))
        if not self.available:
            add('config', 'Studio USB', 'unknown', 'Backend non configuré ; voir la configuration locale studio.json.')
            return result
        try:
            remote = self.remote()
            result['remote'] = remote
            add('network', 'MPC sur le réseau', 'ok', 'Connexion vérifiée')
        except (OSError, subprocess.SubprocessError) as exc:
            remote = {}
            result['error'] = str(exc)[:600]
            add('network', 'MPC sur le réseau', 'error', 'MPC injoignable ou authentification SSH indisponible')
        if remote:
            gadget = bool(remote.get('gadget'))
            connected = gadget and remote.get('usb_state') == 'configured'
            add('gadget', 'Interface USB de la MPC', 'ok' if connected else 'warning' if gadget else 'error',
                ('Connexion USB établie' if connected else 'Créée ; connexion USB au PC en attente') if gadget else 'À recréer après le redémarrage')
            visible = remote.get('visibility') == 'XAC2_Gadget'
            add('visibility', 'Périphérique proposé sur la MPC', 'ok' if visible else 'warning',
                'UAC2_Gadget autorisé dans la liste Audio Device' if visible else 'Préparation de la liste audio nécessaire')
            pcms = [pcm_info(remote.get(k, '')) for k in ('playback', 'capture')]
            active = all(p.get('state') == 'RUNNING' and p.get('owner_pid') == remote.get('mpc_pid') for p in pcms)
            result['pcm_running'] = active
            details = []
            for label, p in zip(('Sortie', 'Entrée'), pcms):
                details.append(f"{label} : {('active' if p.get('state') == 'RUNNING' else 'fermée')}, période {p.get('period_size', '—')}, tampon {p.get('buffer_size', '—')}")
            add('pcm', 'Audio sélectionné sur la MPC', 'ok' if active else 'warning',
                ' · '.join(details) if active else 'Sélectionner UAC2_Gadget 0 dans Preferences → Audio Device')
            midi = remote.get('midi', '')
            target = re.search(r"client (\d+): 'f_midi'", midi)
            source = re.search(r"client \d+: 'MPC One MIDI'.*?(?=\nclient |\Z)", midi, re.S)
            port = re.search(r"^\s+2 '.*?(?=\n\s+\d+ '|\Z)", source[0], re.M | re.S) if source else None
            midi_ok = bool(target and port and re.search(r'Connecting To:.*\b'+target[1]+r':1\b', port[0]))
            add('midi', 'Pont MIDI DIN → USB 2', 'ok' if midi_ok else 'warning',
                'Connexion ALSA vérifiée' if midi_ok else 'Connexion absente')
            result['repair_needed'] = not gadget or not visible or not midi_ok
        try:
            objects = json.loads(subprocess.check_output(['pw-dump'], text=True, stderr=subprocess.PIPE, timeout=4))
            graph = graph_health(objects)
            result['graph'] = graph
            add('usb', 'Interface USB sur le PC', 'ok' if graph['usb'] else 'error',
                'Entrée et sortie 16 canaux présentes' if graph['usb'] else 'Interface absente ; vérifier aussi le câble USB-B')
            for key, label in [('playback', 'Maintien PC → MPC'), ('capture', 'Maintien MPC → PC')]:
                k = graph['keepalive'][key]
                ok = k['channels'] == 16 and k['wrong'] == 0
                add(key, label, 'ok' if ok else 'error', f"{k['channels']}/16 canaux actifs · {k['wrong']} liaison(s) erronée(s)")
                if remote and graph['usb'] and not ok:
                    result['repair_needed'] = True
            add('tracks', 'Entrées des pistes Ardour', 'ok' if graph['tracks'] == 16 else 'warning',
                f"{graph['tracks']}/16 canaux raccordés à la session studio")
            add('master', 'Master → Behringer', 'ok' if graph['master'] == 2 and not graph['master_other'] else 'warning',
                f"{graph['master']}/2 canaux raccordés · {graph['master_other']} autre(s) destination(s)")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            add('pipewire', 'Audio du PC', 'error', 'Graphe PipeWire indisponible')
            result['error'] = str(exc)[:600]
        result['repair_needed'] = bool(remote and result['repair_needed'])
        return result


class StudioController:
    def __init__(self, root):
        self.root = Path(root)
        self.runtime = self.root/'run'
        self.config = read_json(self.root/'studio.json')
        self.backend = StudioBackend(self.root, self.config)
        self.lock = threading.RLock()
        self.wake, self.stopping = threading.Event(), threading.Event()
        self.thread = None
        self.current = {'checked_at': None, 'components': [], 'configured': self.backend.available}
        self.job = read_json(self.runtime/'studio-job.json')
        if self.job.get('state') in ('queued', 'running'):
            self.job.update(state='interrupted', error='Supervision redémarrée ; vérifier l’état avant de relancer.')
        self.pending = None
        self.next_retry, self.failures = 0, 0
        self.pcm_identity = None
        self.pcm_times = {}
        self.pcm_restarts = 0
        self.log_path = self.runtime/'studio.log'

    def start(self):
        self.runtime.mkdir(exist_ok=True)
        self.guard = (self.runtime/'studio-supervisor.lock').open('a')
        fcntl.flock(self.guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.thread = threading.Thread(target=self.loop, name='studio-supervisor')
        self.thread.start()

    def close(self):
        self.stopping.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=20)
        if hasattr(self, 'guard') and not (self.thread and self.thread.is_alive()):
            self.guard.close()

    def state(self):
        with self.lock:
            data = copy.deepcopy(self.current)
            data.update(job=copy.deepcopy(self.job), automatic=bool(self.config.get('automatic', False)),
                        next_retry=self.next_retry, supervising=bool(self.thread and self.thread.is_alive()))
        data['stale'] = data['checked_at'] is None or time.time()-data['checked_at'] > 30
        # Do not expose last-good remote details as a current diagnostic.
        return data

    def log(self, message):
        self.runtime.mkdir(exist_ok=True)
        if self.log_path.exists() and self.log_path.stat().st_size > 1024*1024:
            self.log_path.replace(self.runtime/'studio.log.1')
        with self.log_path.open('a') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S %z')+' '+message+'\n')

    def logs(self):
        result = {}
        for label, path in [('supervision', self.log_path), ('derniere_operation', self.runtime/'studio-operation.log'),
                            ('maintien_sortie', self.backend.home/'run/duplex.log'),
                            ('maintien_entree', self.backend.home/'run/capture-keepalive.log')]:
            try:
                with path.open('rb') as f:
                    f.seek(0, 2); f.seek(max(0, f.tell()-16000))
                    result[label] = f.read(16000).decode(errors='replace')
            except OSError:
                result[label] = 'Aucun journal disponible.'
        return result

    def request(self, values):
        if not isinstance(values, dict) or set(values)-{'action', 'enabled'}:
            raise ValueError('Requête studio invalide')
        action = values.get('action')
        if action not in ('check', 'recover', 'route', 'automatic'):
            raise ValueError('Action studio inconnue')
        if set(values) != ({'action', 'enabled'} if action == 'automatic' else {'action'}):
            raise ValueError('Champs studio invalides')
        with self.lock:
            if action == 'automatic':
                if type(values.get('enabled')) is not bool:
                    raise ValueError('État de surveillance invalide')
                if values['enabled'] and not self.backend.available:
                    raise ValueError('Configurer le backend studio avant la reprise automatique')
                self.config['automatic'] = values['enabled']
                write_json(self.root/'studio.json', self.config)
                self.log('Reprise automatique '+('activée' if values['enabled'] else 'désactivée'))
            elif action != 'check':
                if not self.backend.available:
                    raise ValueError('Backend studio indisponible')
                if self.pending or self.job.get('state') in ('queued', 'running'):
                    raise ValueError('Une opération studio est déjà en cours')
                if action == 'route' and not self.backend.route_allowed():
                    raise ValueError('La session studio configurée doit être ouverte dans Ardour')
                self.pending = action
                self.job = dict(action=action, state='queued', requested_at=time.time(), automatic=False)
                write_json(self.runtime/'studio-job.json', self.job)
        self.wake.set()
        return self.state()

    def run_command(self, action):
        if self.stopping.is_set():
            raise RuntimeError('Supervision en cours d’arrêt ; aucune nouvelle commande lancée')
        session = Path(self.config['session'])
        env = dict(os.environ, MPC_HOST=self.backend.host, PYTHONUNBUFFERED='1',
                   MPC_STUDIO_ROOT=str(self.backend.home),
                   MPC_STUDIO_SESSION=str(session/(session.name+'.ardour')))
        with (self.runtime/'studio-operation.log').open('a') as output:
            p = subprocess.Popen([sys.executable, str(self.backend.path), action], cwd=self.backend.home,
                                 env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                 start_new_session=True)
            deadline = time.monotonic()+150
            while p.poll() is None and not self.stopping.wait(.2) and time.monotonic() < deadline:
                pass
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait()
                # The leader may exit while a descendant ignores SIGTERM.
                # Its original process group still needs to be reclaimed.
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                raise RuntimeError('Opération interrompue à l’arrêt de la supervision' if self.stopping.is_set()
                                   else 'Délai de préparation dépassé ; consulter le journal')
            rc = p.returncode
        if rc:
            raise RuntimeError(f'Opération {action} interrompue (code {rc}) ; consulter le journal')

    def operate(self, action):
        with self.lock:
            self.job.update(state='running', started_at=time.time())
            write_json(self.runtime/'studio-job.json', self.job)
        self.log('Début '+action)
        (self.runtime/'studio-operation.log').write_text('')
        try:
            if action == 'recover':
                self.run_command('prepare')
                if self.backend.route_allowed():
                    self.run_command('route')
                else:
                    self.log('Routage conservé : la session studio configurée n’est pas active.')
            else:
                if not self.backend.route_allowed():
                    raise RuntimeError('La session active a changé ; routage annulé')
                self.run_command('route')
            with self.lock:
                self.job.update(state='succeeded', error=None)
            self.failures = 0
        except (OSError, RuntimeError) as exc:
            with self.lock:
                self.job.update(state='failed', error=str(exc))
            self.failures += 1
        with self.lock:
            self.job['finished_at'] = time.time()
            self.next_retry = time.time()+min(300, 60*2**min(self.failures, 3))
            write_json(self.runtime/'studio-job.json', self.job)
            self.log('Fin '+action+' : '+self.job['state']+(' — '+self.job['error'] if self.job.get('error') else ''))

    def tick(self):
        with self.lock:
            action, self.pending = self.pending, None
            if action:
                self.job['state'] = 'running'
        if action:
            self.operate(action)
        if self.stopping.is_set():
            return
        snapshot = self.backend.snapshot()
        snapshot['checked_at'] = time.time()
        remote = snapshot.get('remote', {})
        identity = (remote.get('boot'), remote.get('mpc_pid'))
        times = {k: pcm_info(remote.get(k, '')).get('trigger_time') for k in ('playback', 'capture')}
        if remote:
            if identity != self.pcm_identity:
                self.pcm_restarts = 0
            else:
                # One observation may include a restart in both PCM directions.
                if any(times[k] and self.pcm_times.get(k) and times[k] != self.pcm_times[k] for k in times):
                    self.pcm_restarts += 1
                    self.log('Changement du démarrage PCM observé ; sélection manuelle ou reprise audio possible.')
            self.pcm_identity, self.pcm_times = identity, times
        snapshot['pcm_restarts'] = self.pcm_restarts
        path = self.runtime/'status.json'
        d = read_json(path)
        try:
            fresh = time.time()-path.stat().st_mtime < 5 and d.get('running') and d.get('ardour') == 'responding'
        except OSError:
            fresh = False
        snapshot['monitoring'] = d.get('track_monitor', {}).get('tracks', []) if fresh else []
        with self.lock:
            old = [(c['key'], c['state']) for c in self.current.get('components', [])]
            new = [(c['key'], c['state']) for c in snapshot['components']]
            if old != new:
                self.log('État : '+', '.join(k+'='+v for k, v in new))
            self.current = snapshot
            if (self.config.get('automatic') and snapshot.get('repair_needed') and
                    time.time() >= self.next_retry and not self.pending):
                self.pending = 'recover'
                self.job = dict(action='recover', state='queued', requested_at=time.time(), automatic=True)
                write_json(self.runtime/'studio-job.json', self.job)

    def loop(self):
        while not self.stopping.is_set():
            self.wake.clear()
            try:
                self.tick()
            except Exception as exc:
                self.log('Erreur de supervision : '+str(exc))
                with self.lock:
                    self.current['error'] = str(exc)
                    self.current['checked_at'] = None
            self.wake.wait(10)
