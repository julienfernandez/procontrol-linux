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
sys.path.insert(0, str(TOOLS.parents[1] / "tools"))
from pipewire_graph import read_graph, unused_meter_links
from mpc_channels import channel_count, usb_nodes, usb_channel_names
HOST = os.environ['MPC_HOST']
SSH = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
       '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=3', '-o', 'ServerAliveCountMax=1',
       '-o', 'UserKnownHostsFile=' + str(RUN / 'known_hosts'), 'root@' + HOST]
CONFIG = TOOLS.parents[1] / 'studio.json'
CONFIG_VALUES = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
CHANNELS = channel_count(os.environ.get('MPC_USB_CHANNELS', CONFIG_VALUES.get('usb_channels', 16)))
SESSION = Path(os.environ['MPC_STUDIO_SESSION'])

def command(args, **kwargs):
    kwargs.setdefault('timeout', 30)
    return S.run(args, check=True, text=True, **kwargs)

def remote(cmd):
    return command(SSH + [cmd], stdout=S.PIPE).stdout

def graph():
    return read_graph()

def usb_target(playback):
    node = usb_nodes(graph())['playback' if playback else 'capture']
    if node is None:
        raise RuntimeError('Interface USB MPC absente ou ambiguë')
    return node['info']['props']['node.name']

def driver_command(action):
    if CHANNELS == 32:
        return '/usr/local/sbin/juju-usb ' + action
    return '/tmp/codex-mpc-usb-audio.sh ' + action

def mpc_pcm_status():
    return remote('for c in /proc/asound/card[0-9]*; do '
                  'case "$(cat "$c/id" 2>/dev/null)" in UAC2Gadget|JujuDriver) '
                  'cat "$c/pcm0p/sub0/status"; exit;; esac; done; exit 1').strip()

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
    channels = ['AUX%d' % i for i in range(CHANNELS)]
    if not all(ch in source and ch in dest for ch in channels):
        raise RuntimeError('Maintien USB : les %d canaux ne sont pas disponibles' % CHANNELS)
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
    name = base + ('-v3-32ch' if CHANNELS == 32 else '-v3')
    target = usb_target(playback)
    stem = 'duplex' if playback else 'capture-keepalive'
    statefile = RUN / (stem + '.json')
    previous = json.loads(statefile.read_text()) if statefile.exists() else {}
    alive = process_alive(previous, base)
    if alive and previous.get('version') == 3 and previous.get('channels', 16) == CHANNELS:
        ensure_keepalive_links(name, target, playback)
        return
    args = ['pw-cat', '--playback' if playback else '--record', '--target', target,
            '--rate', '44100', '--channels', str(CHANNELS), '--channel-map',
            ','.join('AUX%d' % i for i in range(CHANNELS)), '--format', 's32', '--latency', '512',
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
    statefile.write_text(json.dumps({'pid': p.pid, 'version': 3, 'channels': CHANNELS,
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
        prefixes = {p.split(':capture_AUX', 1)[0] for p in ports
                    if re.fullmatch(r'(?:MPC One USB Audio (?:16|32)ch|Juju Driver 32ch) Pro:capture_AUX[0-9]+', p)}
        if len(prefixes) != 1:
            raise RuntimeError('Interface USB absente ou ambiguë ; aucune liaison modifiée')
        prefix = prefixes.pop()
        required = [(f'{prefix}:capture_AUX{i}',
                     'ardour:MPC %02d-%02d/audio_in %d' % (i//2*2+1, i//2*2+2, i%2+1))
                    for i in range(CHANNELS)]
        missing = [p for pair in required for p in pair if p not in ports]
        if missing:
            raise RuntimeError('Routage USB incomplet ; aucune liaison modifiée : ' + ', '.join(missing))
        for i in range(CHANNELS // 2):
            for c in range(2):
                name = 'MPC %02d-%02d' % (i*2+1, i*2+2)
                dest = 'ardour:%s/audio_in %d' % (name, c+1)
                if dest not in ports:
                    raise RuntimeError('Ouvrir la session studio-mpc-usb avant le raccordement : ' + dest)
                j.connect(f'{prefix}:capture_AUX{2*i+c}', dest)
        for c, ch in enumerate(['FL', 'FR']):
            j.connect('PCM2902 Audio Codec Stéréo analogique:capture_' + ch,
                      'ardour:Behringer stereo/audio_in %d' % (c+1))
            master = 'ardour:Master/audio_out %d' % (c+1)
            # Remove the first-device auto-connection added by Ardour on initial setup.
            # Playback monitoring goes to the mixer; the MPC only receives our silent support stream.
            for destination in j.connections(master):
                if re.match(r'(?:MPC One USB Audio (16|32)ch|Juju Driver 32ch) Pro:playback_', destination):
                    j.disconnect(master, destination)
            j.connect(master, 'PCM2902 Audio Codec Stéréo analogique:playback_' + ch)
        src = next(p for p in ports if ('MPC One USB' in p or 'Juju Driver' in p) and '(capture_1)' in p)
        dest = 'ardour:Roland RS-9 MIDI/midi_in 1'
        j.connect(src, dest)
        print('Routage : %d canaux MPC + Behringer stéréo + Roland MIDI USB 2.' % CHANNELS)
    finally:
        j.close()

def tune(timeout=45, settle=15):
    """Verify the unused internal input meter is disconnected after startup."""
    deadline = time.monotonic() + timeout
    first_seen = None
    count = failures = 0
    print('Vumètre interne : attente du port Ardour, PID(s) %s.' % ardour_pids(), flush=True)
    while time.monotonic() < deadline:
        try:
            meters, pairs = unused_meter_links(graph())
        except (OSError, ValueError, S.SubprocessError) as exc:
            failures += 1
            print('Vumètre interne : lecture à reprendre : %s' % exc, flush=True)
            time.sleep(1)
            continue
        if meters:
            if first_seen is None:
                first_seen = time.monotonic()
            for source, dest in sorted(pairs):
                try:
                    command(['pw-link', '-d', str(source), str(dest)])
                    count += 1
                except (OSError, S.SubprocessError) as exc:
                    # A port may disappear between the snapshot and disconnect.
                    # Re-read the graph; never assume the failed command succeeded.
                    print('Vumètre interne : lien à revérifier : %s' % exc, flush=True)
            if not pairs and time.monotonic() - first_seen >= settle:
                result = dict(checked_at=time.time(), ardour_pids=ardour_pids(),
                              removed=count, read_failures=failures, verified=True)
                (RUN/'input-meter-tune.json').write_text(json.dumps(result)+'\n')
                print('Vumètre interne vérifié : %d connexions retirées, aucune restante.' % count, flush=True)
                return result
        else:
            first_seen = None
        time.sleep(1)
    raise RuntimeError('Vumètre interne non vérifié dans le délai ; consulter input-meter-tune.log')

def preflight():
    """Reject unavailable 32-channel kernels before any remote or local write."""
    if CHANNELS != 32:
        return
    result = remote('f=/sys/kernel/config/usb_gadget/juju_driver/functions/juju.audio; '
                    'if [ -f "$f/p_channels" ] && [ -f "$f/c_channels" ]; then '
                    'echo explicit-channel-count; elif [ -x /usr/local/sbin/juju-usb ] && '
                    '[ -s /usr/lib/modules/$(uname -r)/extra/juju_driver.ko ]; then '
                    'echo explicit-channel-count; fi').strip()
    if result != 'explicit-channel-count':
        raise RuntimeError('32 canaux indisponibles : le pilote UAC2 de la MPC ne fournit pas '
                           'p_channels/c_channels. Liaison existante conservée. '
                           'Installer et valider un pilote MPC compatible avant la bascule.')


def verify_usb_width(objects):
    nodes = usb_nodes(objects)
    for direction, port_direction in (('capture', 'out'), ('playback', 'in')):
        actual = len(usb_channel_names(objects, nodes[direction], port_direction))
        if actual != CHANNELS:
            raise RuntimeError('USB %s : %d canaux réels, %d demandés ; maintien non lancé' %
                               (direction, actual, CHANNELS))


def prepare():
    """Prepare hardware without opening Ardour or changing a session's routing."""
    for path in [RUN/'known_hosts', ROOT/'tools/vendor/alsa-utils-armhf/usr/bin/aconnect',
                 ROOT/'tools/vendor/coreutils-armhf/bin/dd']:
        if not path.is_file():
            raise RuntimeError('Dépendance locale absente : '+str(path))
    preflight()
    # The installed HAKAI hook accepts 64/96/128/192 only. MPC 3.9.1 crashed
    # in its audio thread when the hardware accepted the non-power-of-two 192
    # period (Internal and Juju). 128 works with 32 channels and a 512-frame ring.
    # This volatile setting must be re-established without restarting the app.
    buffer_hook_hash = '5609484183b9c1859c8c7db2a0613fd13e9ec7d72d4a459503bf27d8663d73ac'
    actual = remote('sha256sum /usr/lib/customBufferSizeMPC.so 2>/dev/null || true').split()
    if actual and actual[0] == buffer_hook_hash:
        remote('mkdir -p /media/az01-internal-sd; '
               'printf "128\\n" > /media/az01-internal-sd/custtomBuffer.txt')
        print('HAKAI : tampon audio 512 / période 128 demandés pour la prochaine ouverture du périphérique ; vérifier hw_params après sélection.')
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
    print(remote('chmod 700 /tmp/aconnect /tmp/codex-dd /tmp/codex-mpc-usb-audio.sh; ' + driver_command('start') + ('' if CHANNELS == 32 else ' %d 2 2' % CHANNELS)))
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
                   and any(serial in o.get('info', {}).get('props', {}).get('device.name', '')
                           for serial in ('MPCONE-USB-AUDIO-TEST', 'JUJU-MPCONE-32'))]
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
    # The profile change can expose its ports asynchronously.
    for attempt in range(20):
        try:
            verify_usb_width(graph())
            break
        except RuntimeError:
            if attempt == 19:
                raise
            time.sleep(.1)
    silence()
    capture_keepalive()
    tune_output()
    if CHANNELS != 32:
        command([sys.executable, str(TOOLS/'mpc_audio_visibility.py'), 'apply'])
    print('MPC USB prête : %d canaux audio et pont MIDI DIN vers USB 2.' % CHANNELS)
    selection = RUN/'mpc-selection-required'
    state = mpc_pcm_status()
    if state == 'closed':
        selection.write_text('Sélectionner le périphérique USB MPC (Juju Driver en 32 canaux) dans Preferences > Audio Device sur la MPC.\n')
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
              'fermer puis rouvrir Preferences > Audio Device et sélectionner le périphérique USB MPC (Juju Driver en 32 canaux).')
    else:
        print('Interface et pistes raccordées. Sortie USB ouverte côté MPC; vérifier le signal musical.')

def status():
    print(remote(driver_command('status') + '; /tmp/aconnect -l'))
    print('Application MPC : sortie USB\n'+mpc_pcm_status())
    print('Ardour PID :', ardour_pids())
    p = RUN/'duplex.json'
    print('Support USB bidirectionnel :', bool(p.exists() and process_alive(json.loads(p.read_text()))))
    p = RUN/'capture-keepalive.json'
    print('Maintien capture USB :', bool(p.exists() and process_alive(json.loads(p.read_text()), 'codex-mpc-usb-capture-keepalive')))
    for playback, base, target in [(True, 'codex-mpc-usb-silence', usb_target(True)),
                                    (False, 'codex-mpc-usb-capture-keepalive', usb_target(False))]:
        try:
            missing, wrong = keepalive_link_plan(graph(), base + ('-v3-32ch' if CHANNELS == 32 else '-v3'), target, playback)
            print(base, ': %d/%d canaux raccordés, %d liens erronés' % (CHANNELS-len(missing), CHANNELS, len(wrong)))
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
    if CHANNELS != 32:
        command([sys.executable, str(TOOLS/'mpc_audio_visibility.py'), 'restore'])
    print(remote(driver_command('stop')))
    for key in ['clock.force-rate', 'clock.force-quantum']:
        command(['pw-metadata', '-n', 'settings', '0', key, '0'], stdout=S.DEVNULL)
    print('Test USB arrêté; horloge PipeWire remise en mode automatique.')

if __name__ == '__main__':
    actions = {'check': preflight, 'prepare': prepare, 'start': start, 'status': status, 'route': route, 'stop': stop, 'tune': tune}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        raise SystemExit('Usage : studio check | prepare | start | status | route | stop | tune')
    lock = open(RUN/('tune.lock' if sys.argv[1] == 'tune' else 'studio.lock'), 'w')
    try:
        # Normal launch uses an outer timeout; wait for a concurrent prepare there.
        flags = fcntl.LOCK_EX if sys.argv[1] == 'prepare' else fcntl.LOCK_EX | fcntl.LOCK_NB
        fcntl.flock(lock, flags)
        actions[sys.argv[1]]()
    except (RuntimeError, S.SubprocessError, OSError) as exc:
        raise SystemExit(str(exc))
