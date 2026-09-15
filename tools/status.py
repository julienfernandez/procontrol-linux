#!/usr/bin/env python3
"""État local, sans sudo, sans ouvrir d'interface de capture."""
# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import os
import grp
import json
from procontrold import status as daemon_status, RUNTIME

root = Path(__file__).resolve().parents[1]
print('ProControl —', datetime.now().astimezone().isoformat(timespec='seconds'))
print('Projet :', root)
print('Démon continu :', json.dumps(daemon_status(RUNTIME), ensure_ascii=False))
for name in ('tcpdump', 'dumpcap', 'python3'):
    executable = shutil.which(name)
    installed = next((Path(part) / name for part in os.get_exec_path() if (Path(part) / name).is_file()), None)
    print(f'{name} : {executable or (str(installed) + " (présent, exécution refusée pour cette session)" if installed else "absent")}')
print('Groupes actifs :', ', '.join(grp.getgrgid(gid).gr_name for gid in os.getgroups()))
try:
    capture_group = grp.getgrnam('wireshark')
    print('Membres configurés du groupe wireshark :', ', '.join(capture_group.gr_mem) or 'aucun')
except KeyError:
    pass
for field in ('carrier', 'speed', 'duplex'):
    try:
        value = (Path('/sys/class/net/enp0s25') / field).read_text().strip()
    except OSError:
        value = 'indisponible'
    print(f'enp0s25 {field} : {value}')
try:
    print('AppArmor de cette commande :', Path('/proc/self/attr/current').read_text().strip())
except OSError:
    pass
print('\nDernières expériences :')
folders = sorted(p for p in (root / 'captures').iterdir() if p.is_dir())[-8:]
for folder in folders:
    metadata = (folder / 'metadata.txt').read_text() if (folder / 'metadata.txt').exists() else ''
    result = (folder / 'summary.txt').read_text() if (folder / 'summary.txt').exists() else ''
    pcap = folder / 'traffic.pcap'
    size = pcap.stat().st_size if pcap.exists() else 0
    probe_metadata = folder / 'metadata.json'
    if probe_metadata.exists():
        probe = json.loads(probe_metadata.read_text())
        state = f"Essai actif clôturé (code {probe['capture_exit_code']}) ; {probe['counts']}"
    elif 'postprocess_status=verified' in metadata:
        state = 'PCAP clôturé et bilan récupéré après interruption du script'
    elif 'capture_exit_code=' in metadata:
        code = metadata.split('capture_exit_code=')[-1].splitlines()[0]
        state = f'Processus terminé (code {code})'
        if code in ('0', '124', '130') and 'Trames :' in result:
            state = 'Capture clôturée et PCAP relu'
    else:
        state = 'Pas de bilan final : en cours, en attente ou interrompue — vérifier les processus'
    print(f'\n{folder.name}\n  {state}\n  PCAP : {size} octets')
    if (folder / 'traffic-us.provenance.json').exists():
        print('  Mesures temporelles : utiliser traffic-us.pcap (original conservé ; unité corrigée)')
    for line in result.splitlines():
        if line.startswith(('Trames :', 'Intervalle global :')):
            print(' ', line)
    for log in sorted(folder.glob('*.log')):
        lines = log.read_text(errors='replace').splitlines()
        print(f'  Dernier message {log.name} : {lines[-1] if lines else "aucun"}')
print('\nProcessus de capture présents (tous projets ; vérifier avant toute action) :')
result = subprocess.run(['ps', '-eo', 'pid,user,comm,args'], capture_output=True, text=True, check=True)
found = False
for line in result.stdout.splitlines()[1:]:
    parts = line.split(None, 3)
    if len(parts) == 4 and (parts[2] in ('tcpdump', 'dumpcap', 'timeout', 'pkexec') or
                           (parts[2].startswith('python') and 'tools/session_probe.py' in parts[3])):
        print(line)
        found = True
if not found:
    print('  Aucun.')
