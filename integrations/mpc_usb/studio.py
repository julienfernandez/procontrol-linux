#!/usr/bin/env python3
"""MPC USB / PipeWire studio: reversible prepare, start, status and stop."""
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess as S
import sys
import time

TOOLS = Path(__file__).resolve().parent
ROOT = Path(os.environ['MPC_STUDIO_ROOT']).resolve()
RUN = ROOT / 'run'
RUN.mkdir(mode=0o700, exist_ok=True)
sys.path.insert(0, str(TOOLS))
from jack_ports import Jack
HOST = os.environ['MPC_HOST']
SSH = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
       '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=3', '-o', 'ServerAliveCountMax=1',
       '-o', 'UserKnownHostsFile=' + str(RUN / 'known_hosts'), 'root@' + HOST]
MPC_NODE = 'alsa_output.usb-Akai_Professional_MPC_One_USB_Audio_16ch_MPCONE-USB-AUDIO-TEST-00.pro-output-0'
MPC_SOURCE = 'alsa_input.usb-Akai_Professional_MPC_One_USB_Audio_16ch_MPCONE-USB-AUDIO-TEST-00.pro-input-0'
SESSION = Path(os.environ['MPC_STUDIO_SESSION'])

def command(args, **kwargs):
    kwargs.setdefault('timeout', 30)
    return S.run(args, check=True, text=True, **kwargs)

def remote(cmd):
    return command(SSH + [cmd], stdout=S.PIPE).stdout

def graph():
    return json.loads(S.check_output(['pw-dump'], timeout=4))

def mpc_pcm_status():
    return remote('for c in /proc/asound/card[0-9]*; do '
                  'if [ "$(cat "$c/id" 2>/dev/null)" = UAC2Gadget ]; then '
                  'cat "$c/pcm0p/sub0/status"; exit; fi; done; exit 1').strip()

def ardour_pids():
    result = []
    for p in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = p.read_bytes().split(b'\0')
            if args and args[0].endswith(b'/ardour-9.8.0'):
                result.append(int(p.parent.name))
        except (FileNotFoundError, PermissionError):
            pass
    return result

def process_alive(state, name='codex-mpc-usb-silence'):
    try:
        p = Path('/proc') / str(state['pid'])
        return (p.joinpath('stat').read_text().split()[21] == state['start_ticks']
                and b'pw-cat\0' in p.joinpath('cmdline').read_bytes()
                and name.encode() in p.joinpath('cmdline').read_bytes())
    except (FileNotFoundError, KeyError, PermissionError):
        return False

def keepalive_link_plan(objects, name, target, playback):
    """Check real channel links, not just the lifetime of the pw-cat process."""
    props = {o['id']: o.get('info', {}).get('props', {}) for o in objects}
    def node(label):
        matches = [o['id'] for o in objects if o['type'] == 'PipeWire:Interface:Node'
                   and props[o['id']].get('node.name') == label]
        if len(matches) != 1:
            raise RuntimeError('Nœud USB absent ou ambigu : ' + label)
        return matches[0]
    stream, device = node(name), node(target)
    def ports(owner, direction):
        return {props[o['id']].get('audio.channel'): o['id'] for o in objects
                if o['type'] == 'PipeWire:Interface:Port'
                and str(props[o['id']].get('node.id')) == str(owner)
                and props[o['id']].get('port.direction') == direction
                and not props[o['id']].get('port.monitor')}
    source = ports(stream if playback else device, 'out')
    dest = ports(device if playback else stream, 'in')
    channels = ['AUX%d' % i for i in range(16)]
    if not all(ch in source and ch in dest for ch in channels):
        raise RuntimeError('Maintien USB : les 16 canaux ne sont pas disponibles')
    expected = {(source[ch], dest[ch]) for ch in channels}
    existing = set()
    active = set()
    for obj in objects:
        if obj['type'] != 'PipeWire:Interface:Link':
            continue
        info = obj['info']
        if info['output-node-id' if playback else 'input-node-id'] == stream:
            pair = (info['output-port-id'], info['input-port-id'])
            existing.add(pair)
            if info.get('state') == 'active':
                active.add(pair)
    return expected - active, existing - expected

def ensure_keepalive_links(name, target, playback):
    for attempt in range(20):
        try:
            missing, wrong = keepalive_link_plan(graph(), name, target, playback)
            break
        except RuntimeError:
            if attempt == 19:
                raise
            time.sleep(.1)
    # Establish the intended path before removing a stale fallback path.
    # WirePlumber may create the same link concurrently. Verify the graph
    # afterwards instead of treating its EEXIST race as a broken stream.
    for output, inp in sorted(missing):
        S.run(['pw-link', str(output), str(inp)], stdout=S.PIPE, stderr=S.PIPE)
    for output, inp in sorted(wrong):
        S.run(['pw-link', '-d', str(output), str(inp)], stdout=S.PIPE, stderr=S.PIPE)
    for _ in range(10):
        missing, wrong = keepalive_link_plan(graph(), name, target, playback)
        if not missing and not wrong:
            return
        time.sleep(.1)
    raise RuntimeError('Maintien USB : raccordement incomplet')

def keepalive(playback):
    base = 'codex-mpc-usb-silence' if playback else 'codex-mpc-usb-capture-keepalive'
    name = base + '-v3'
    target = MPC_NODE if playback else MPC_SOURCE
    stem = 'duplex' if playback else 'capture-keepalive'
    statefile = RUN / (stem + '.json')
    previous = json.loads(statefile.read_text()) if statefile.exists() else {}
    alive = process_alive(previous, base)
    if alive and previous.get('version') == 3:
        ensure_keepalive_links(name, target, playback)
        return
    args = ['pw-cat', '--playback' if playback else '--record', '--target', target,
            '--rate', '44100', '--channels', '16', '--channel-map',
            ','.join('AUX%d' % i for i in range(16)), '--format', 's32', '--latency', '512',
            '--properties', '{ node.name = '+name+' node.dont-fallback = true '
            'node.dont-reconnect = true state.restore-target = false '
            'node.dont-move = true stream.dont-remix = true }', '-']
    with open('/dev/zero', 'rb') as inp, open(RUN / (stem + '.log'), 'a') as log:
        p = S.Popen(args, stdin=inp if playback else S.DEVNULL,
                    stdout=log if playback else S.DEVNULL, stderr=log, start_new_session=True)
    try:
        ensure_keepalive_links(name, target, playback)
        if p.poll() is not None:
            raise RuntimeError('Maintien USB arrêté ; voir run/' + stem + '.log')
    except Exception:
        p.terminate()
        raise
    # Migrate old clients only after their replacement is actually connected.
    statefile.write_text(json.dumps({'pid': p.pid, 'version': 3,
        'start_ticks': Path('/proc/%d/stat' % p.pid).read_text().split()[21]}))
    if alive:
        os.kill(previous['pid'], signal.SIGTERM)

def silence():
    keepalive(True)

def capture_keepalive():
    # MPC's duplex ALSA device can fail when the PC stops reading USB capture.
    # Keep capture active across Ardour closes; audio is discarded, never stored.
    keepalive(False)

def tune_output():
    """Keep the PCM2902 follower's pointer granularity below the resync limit."""
    nodes = [o for o in graph() if o['type'] == 'PipeWire:Interface:Node'
             and o.get('info', {}).get('props', {}).get('node.name', '').startswith(
                 'alsa_output.usb-Burr-Brown_from_TI_USB_Audio_CODEC-00.analog-stereo-output')]
    if not nodes:
        return
    if len(nodes) != 1:
        raise RuntimeError('Plusieurs sorties Behringer identiques : réglage de tampon non appliqué')
    node = nodes[0]
    current = {}
    for props in node['info'].get('params', {}).get('Props', []):
        values = props.get('params', [])
        current.update(zip(values[::2], values[1::2]))
    desired = {'api.alsa.period-size': 128, 'api.alsa.headroom': 512}
    if all(current.get(key) == value for key, value in desired.items()):
        return
    # PipeWire 1.0.5 halves this period for batch USB devices, yielding 64
    # frames rather than the old 256. The old pointer steps crossed its
    # 256-frame follower resync limit. Headroom alone did not fix that.
    ident = str(node['id'])
    command(['pw-cli', 'set-param', ident, 'Props',
             '{ params = [ "api.alsa.period-size" 128 "api.alsa.headroom" 512 ] }'],
            stdout=S.DEVNULL)
    # These ALSA parameters take effect on open; keep the node and links.
    command(['pw-cli', 'send-command', ident, 'Suspend', '{}'], stdout=S.DEVNULL)
    if node['info'].get('state') == 'running':
        command(['pw-cli', 'send-command', ident, 'Start', '{}'], stdout=S.DEVNULL)
    print('Sortie Behringer : période USB affinée, marge de tampon 512.')

def route():
    j = Jack()
    try:
        ports = j.ports()
        for i in range(8):
            for c in range(2):
                name = 'MPC %02d-%02d' % (i*2+1, i*2+2)
                dest = 'ardour:%s/audio_in %d' % (name, c+1)
                if dest not in ports:
                    raise RuntimeError('Ouvrir la session studio-mpc-usb avant le raccordement : ' + dest)
                j.connect('MPC One USB Audio 16ch Pro:capture_AUX%d' % (2*i+c), dest)
        for c, ch in enumerate(['FL', 'FR']):
            j.connect('PCM2902 Audio Codec Stéréo analogique:capture_' + ch,
                      'ardour:Behringer stereo/audio_in %d' % (c+1))
            master = 'ardour:Master/audio_out %d' % (c+1)
            # Remove the first-device auto-connection added by Ardour on initial setup.
            # Playback monitoring goes to the mixer; the MPC only receives our silent support stream.
            for destination in j.connections(master):
                if destination.startswith('MPC One USB Audio 16ch Pro:playback_'):
                    j.disconnect(master, destination)
            j.connect(master, 'PCM2902 Audio Codec Stéréo analogique:playback_' + ch)
        src = next(p for p in ports if 'MPC One USB' in p and '(capture_1)' in p)
        dest = 'ardour:Roland RS-9 MIDI/midi_in 1'
        j.connect(src, dest)
        print('Routage : 16 canaux MPC + Behringer stéréo + Roland MIDI USB 2.')
    finally:
        j.close()

def tune():
    """Stop unused laptop input metering, keeping every real track connection."""
    # Ardour meters all physical inputs by default, including the unused PCH
    # microphone. That device repeatedly resynced against the MPC USB clock.
    # Only disconnect its dummy meter port, never an audio track or USB input.
    first_seen = None
    count = 0
    for _ in range(45):
        objects = graph()
        props = {o['id']: o.get('info', {}).get('props', {}) for o in objects}
        meters = {o['id'] for o in objects if o.get('type') == 'PipeWire:Interface:Port'
                  and props[o['id']].get('port.name') == 'physical_audio_input_monitor_enable'
                  and props.get(int(props[o['id']].get('node.id', -1)), {}).get('node.name') == 'ardour'}
        if meters:
            if first_seen is None:
                first_seen = time.monotonic()
            for obj in objects:
                if obj.get('type') != 'PipeWire:Interface:Link':
                    continue
                link = obj['info']
                source = props.get(link['output-node-id'], {}).get('node.name', '')
                if link['input-port-id'] in meters and source.startswith('alsa_input.pci-'):
                    command(['pw-link', '-d', str(link['output-port-id']), str(link['input-port-id'])])
                    count += 1
            # The port appears before Ardour finishes restoring its links.
            # Cover that startup window instead of returning on an empty graph.
            if time.monotonic() - first_seen >= 15:
                print('Vu-mètre micro interne : %d connexions inutilisées retirées.' % count)
                return
        time.sleep(1)
    print('Réglage vu-mètre terminé : %d connexions inutilisées retirées.' % count)

def prepare():
    """Prepare hardware without opening Ardour or changing a session's routing."""
    for path in [RUN/'known_hosts', ROOT/'tools/vendor/alsa-utils-armhf/usr/bin/aconnect',
                 ROOT/'tools/vendor/coreutils-armhf/bin/dd']:
        if not path.is_file():
            raise RuntimeError('Dépendance locale absente : '+str(path))
    # This installed HAKAI preload reads its legacy pathname each time ALSA
    # opens a device. Without the file, this build selected 64-sample USB
    # periods and repeatedly recovered its capture/playback streams under load.
    # The 192 setting requests a 768-sample ring buffer. The gadget still
    # caps 16 x S16 periods at 128, leaving six periods of scheduling margin.
    # Verify hw_params after device selection; writing the file is not live.
    # Never restart the MPC application here.
    # /media is volatile here, so normal launch must re-establish the setting.
    buffer_hook_hash = '5609484183b9c1859c8c7db2a0613fd13e9ec7d72d4a459503bf27d8663d73ac'
    actual = remote('sha256sum /usr/lib/customBufferSizeMPC.so 2>/dev/null || true').split()
    if actual and actual[0] == buffer_hook_hash:
        remote('mkdir -p /media/az01-internal-sd; '
               'printf "192\\n" > /media/az01-internal-sd/custtomBuffer.txt')
        print('HAKAI : tampon audio 768 demandé pour la prochaine ouverture du périphérique ; vérifier hw_params après sélection.')
    else:
        print('HAKAI : version du réglage de tampon différente ; aucun réglage imposé.')
    # Files are sent only to volatile /tmp on the MPC.
    for src, dest in [(TOOLS/'mpc-usb-audio.sh', '/tmp/codex-mpc-usb-audio.sh'),
                      (ROOT/'tools/vendor/alsa-utils-armhf/usr/bin/aconnect', '/tmp/aconnect'),
                      (ROOT/'tools/vendor/coreutils-armhf/bin/dd', '/tmp/codex-dd')]:
        command(['scp', '-q', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=3',
                 '-o', 'ServerAliveInterval=3', '-o', 'ServerAliveCountMax=1',
                 '-o', 'UserKnownHostsFile='+str(RUN/'known_hosts'),
                 str(src), 'root@'+HOST+':'+dest])
    # 16 x S32 forced 64-sample periods on the MPC gadget's 4096-byte limit.
    # S16 keeps all 16 channels and permits the requested 128-sample period.
    print(remote('chmod 700 /tmp/aconnect /tmp/codex-dd /tmp/codex-mpc-usb-audio.sh; /tmp/codex-mpc-usb-audio.sh start 16 2 2'))
    listing = remote('/tmp/aconnect -l')
    din = re.search(r"client (\d+): 'MPC One MIDI'", listing)
    usb = re.search(r"client (\d+): 'f_midi'", listing)
    if not (din and usb): raise RuntimeError('Ports MIDI MPC indisponibles')
    # A connection already in place returns nonzero; its existence is checked below.
    remote('/tmp/aconnect %s:2 %s:1 2>/dev/null || true' % (din[1], usb[1]))
    listing = remote('/tmp/aconnect -l')
    section = listing.split("'MPC One MIDI'", 1)[1].split('client ', 1)[0]
    if usb[1]+':1' not in section: raise RuntimeError('Pont DIN vers USB 2 non établi')
    for _ in range(20):
        devices = [o for o in graph() if o.get('type') == 'PipeWire:Interface:Device'
                   and 'MPCONE-USB-AUDIO-TEST' in o.get('info', {}).get('props', {}).get('device.name', '')]
        if devices: break
        time.sleep(.5)
    if not devices: raise RuntimeError('MPC USB absente du PC; vérifier le câble USB vers le PC')
    profiles = devices[0].get('info', {}).get('params', {}).get('Profile', [])
    if not any(p.get('index') == 3 for p in profiles):
        command(['pw-cli', 'set-param', str(devices[0]['id']), 'Profile', '{ index: 3 }'], stdout=S.DEVNULL)
    metadata = S.check_output(['pw-metadata', '-n', 'settings'], text=True)
    for key, value in [('clock.force-rate', '44100'), ('clock.force-quantum', '512')]:
        if not re.search(r"key:'" + re.escape(key) + r"' value:'" + value + "'", metadata):
            command(['pw-metadata', '-n', 'settings', '0', key, value], stdout=S.DEVNULL)
    silence()
    capture_keepalive()
    tune_output()
    command([sys.executable, str(TOOLS/'mpc_audio_visibility.py'), 'apply'])
    print('MPC USB prête : 16 canaux audio et pont MIDI DIN vers USB 2.')
    selection = RUN/'mpc-selection-required'
    state = mpc_pcm_status()
    if state == 'closed':
        selection.write_text('Sélectionner UAC2_Gadget 0 dans Preferences > Audio Device sur la MPC.\n')
        print(selection.read_text().strip())
    else:
        selection.unlink(missing_ok=True)

def start():
    prepare()
    if not ardour_pids():
        env = os.environ.copy()
        lib = str(ROOT/'tools/vendor/pipewire-jack/usr/lib/x86_64-linux-gnu/pipewire-0.3/jack')
        env['LD_LIBRARY_PATH'] = lib + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
        env['PIPEWIRE_LATENCY'] = '512/44100'
        env['MPC_STUDIO_PREPARED'] = '1'
        with open(RUN/'ardour.log', 'a') as log:
            S.Popen([os.environ.get('MPC_ARDOUR_BIN', str(Path.home()/'.local/opt/ardour-9.8/bin/ardour9')), str(SESSION)], env=env,
                    stdout=log, stderr=log, start_new_session=True)
    for _ in range(40):
        j = Jack()
        ready = 'ardour:MPC 01-02/audio_in 1' in j.ports()
        j.close()
        if ready: break
        time.sleep(.5)
    route()
    state = mpc_pcm_status()
    if state == 'closed':
        print('Interface et pistes raccordées. Application MPC encore sur Internal : '
              'fermer puis rouvrir Preferences > Audio Device et sélectionner UAC2_Gadget 0.')
    else:
        print('Interface et pistes raccordées. Sortie USB ouverte côté MPC; vérifier le signal musical.')

def status():
    print(remote('/tmp/codex-mpc-usb-audio.sh status; /tmp/aconnect -l'))
    print('Application MPC : sortie USB\n'+mpc_pcm_status())
    print('Ardour PID :', ardour_pids())
    p = RUN/'duplex.json'
    print('Support USB bidirectionnel :', bool(p.exists() and process_alive(json.loads(p.read_text()))))
    p = RUN/'capture-keepalive.json'
    print('Maintien capture USB :', bool(p.exists() and process_alive(json.loads(p.read_text()), 'codex-mpc-usb-capture-keepalive')))
    for playback, base, target in [(True, 'codex-mpc-usb-silence', MPC_NODE),
                                    (False, 'codex-mpc-usb-capture-keepalive', MPC_SOURCE)]:
        try:
            missing, wrong = keepalive_link_plan(graph(), base + '-v3', target, playback)
            print(base, ': %d/16 canaux raccordés, %d liens erronés' % (16-len(missing), len(wrong)))
        except RuntimeError as exc:
            print(base, ':', exc)
    j = Jack()
    try:
        for port in j.ports():
            if port.startswith('ardour:') and ('/audio_in' in port or '/midi_in' in port or 'Master/audio_out' in port):
                connected = j.connections(port)
                if connected: print(port, '<->', ', '.join(connected))
    finally:
        j.close()

def stop():
    if ardour_pids():
        raise RuntimeError('Enregistrer et fermer Ardour avant studio stop; aucun arrêt forcé.')
    if mpc_pcm_status() != 'closed':
        raise RuntimeError('Sélectionner Internal sur la MPC avant de retirer son interface USB.')
    for filename, name in [('duplex.json', 'codex-mpc-usb-silence'),
                           ('capture-keepalive.json', 'codex-mpc-usb-capture-keepalive')]:
        p = RUN/filename
        if p.exists():
            state = json.loads(p.read_text())
            if process_alive(state, name): os.kill(state['pid'], signal.SIGTERM)
            p.unlink()
    command([sys.executable, str(TOOLS/'mpc_audio_visibility.py'), 'restore'])
    print(remote('/tmp/codex-mpc-usb-audio.sh stop'))
    for key in ['clock.force-rate', 'clock.force-quantum']:
        command(['pw-metadata', '-n', 'settings', '0', key, '0'], stdout=S.DEVNULL)
    print('Test USB arrêté; horloge PipeWire remise en mode automatique.')

if __name__ == '__main__':
    actions = {'prepare': prepare, 'start': start, 'status': status, 'route': route, 'stop': stop, 'tune': tune}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        raise SystemExit('Usage : studio prepare | start | status | route | stop | tune')
    lock = open(RUN/('tune.lock' if sys.argv[1] == 'tune' else 'studio.lock'), 'w')
    try:
        # Normal launch uses an outer timeout; wait for a concurrent prepare there.
        flags = fcntl.LOCK_EX if sys.argv[1] == 'prepare' else fcntl.LOCK_EX | fcntl.LOCK_NB
        fcntl.flock(lock, flags)
        actions[sys.argv[1]]()
    except (RuntimeError, S.SubprocessError, OSError) as exc:
        raise SystemExit(str(exc))
