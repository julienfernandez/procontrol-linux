#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Capture passive : dumpcap avec arrêt natif, ou tcpdump depuis un terminal adapté.
set -euo pipefail

main() {
# Charger le corps entier avant toute commande longue. Une ancienne version
# pouvait relire le fichier modifié pendant une capture et manquer le bilan.
usage() {
    cat <<'EOF'
Usage: bash tools/capture.sh INTERFACE EXPERIENCE [SECONDES]
Exemple: bash tools/capture.sh enp0s25 startup 90
Durée par défaut : 60 s (1 à 3600). Ctrl+C permet une fin anticipée.
Sans filtre : conserve toutes les trames de cette interface Ethernet.
Attendre le message d'ouverture de capture avant de commencer l'expérience.
Backend : dumpcap si installé, sinon tcpdump. PROCONTROL_CAPTURE_BACKEND force le choix.
Pour l'authentification graphique Linux : PROCONTROL_AUTH=pkexec bash tools/capture.sh ...
EOF
}
if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
if (( $# < 2 || $# > 3 )); then usage >&2; exit 2; fi
iface=$1
label=$2
seconds=${3:-60}
[[ $iface =~ ^[a-zA-Z0-9_.:-]+$ && -d /sys/class/net/$iface ]] || {
    echo 'Interface réseau inconnue.' >&2; exit 2;
}
[[ $label =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$ ]] || {
    echo 'Nom attendu : lettres, chiffres, tirets ou underscores (64 caractères max).' >&2; exit 2;
}
[[ $seconds =~ ^[1-9][0-9]{0,3}$ ]] && (( seconds <= 3600 )) || {
    echo 'Durée attendue : entier de 1 à 3600 secondes.' >&2; exit 2;
}
[[ $(cat "/sys/class/net/$iface/type") == 1 && ! -d /sys/class/net/$iface/wireless ]] || {
    echo 'Choisir une interface Ethernet filaire ; ni any, ni loopback, ni Wi-Fi.' >&2; exit 2;
}
backend=${PROCONTROL_CAPTURE_BACKEND:-auto}
if [[ $backend == auto ]]; then
    if command -v dumpcap >/dev/null; then backend=dumpcap; else backend=tcpdump; fi
fi
case $backend in
    dumpcap) default_auth=none ;;
    tcpdump) default_auth=sudo ;;
    *) echo 'Backend attendu : auto, dumpcap ou tcpdump.' >&2; exit 2 ;;
esac
# Sur ce laptop, le profil tcpdump refuse les signaux issus du profil chatgpt.
# Ne pas démarrer une capture dont timeout ne pourrait pas assurer l'arrêt.
profile=$(cat /proc/self/attr/current 2>/dev/null || true)
if [[ $backend == tcpdump && $profile == chatgpt* && -f /etc/apparmor.d/usr.bin.tcpdump ]]; then
    echo 'Capture tcpdump depuis le profil AppArmor chatgpt désactivée : arrêt non fiable.' >&2
    echo 'Utiliser dumpcap (durée native) ou lancer ce script dans un terminal Linux extérieur à l’app.' >&2
    exit 2
fi
for dep in "$backend" ip python3 sha256sum tee flock; do
    command -v "$dep" >/dev/null || { echo "Commande absente : $dep" >&2; exit 2; }
done
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
umask 077
mkdir -p "$root/captures"
exec 9> "$root/captures/.capture-$iface.lock"
flock -n 9 || { echo "Une capture du kit est déjà lancée sur $iface." >&2; exit 2; }
priv=()
if (( EUID != 0 )); then
    case ${PROCONTROL_AUTH:-$default_auth} in
        none) ;;
        sudo)
            sudo -v
            priv=(sudo -n)
            ;;
        pkexec)
            command -v pkexec >/dev/null || { echo 'pkexec absent.' >&2; exit 2; }
            priv=(pkexec)
            ;;
        *) echo 'PROCONTROL_AUTH doit être none, sudo ou pkexec.' >&2; exit 2 ;;
    esac
fi
out=$(mktemp -d "$root/captures/$(date -u +%Y%m%dT%H%M%SZ)-$label-XXXXXX")
cp "$root/docs/experiment-template.md" "$out/notes.md"
if [[ $backend == dumpcap ]]; then
    command_line=(dumpcap -q -P -i "$iface" -s 0 -B 4 -a "duration:$seconds" -w -)
else
    command -v timeout >/dev/null || { echo 'timeout absent.' >&2; exit 2; }
    command_line=(timeout --foreground --signal=INT --kill-after=5s "${seconds}s"
        tcpdump -i "$iface" -nn -s 0 -B 4096 -U -w -)
fi
logfile="$out/$backend.log"
{
    echo "experience=$label"
    echo "interface=$iface"
    echo "backend=$backend"
    echo "capture_shell_pid=$$"
    echo "requested_duration_seconds=$seconds"
    echo "requested_start_utc=$(date -u --iso-8601=ns)"
    echo 'filter=NONE; actual first/last packet timestamps are in the PCAP'
    printf 'command='; printf '%q ' "${priv[@]}" "${command_line[@]}"; printf '\n'
    uname -srmo
    "$backend" --version 2>&1
    ip -details -statistics link show dev "$iface"
    ip address show dev "$iface"
    for field in address carrier speed duplex; do
        printf '%s=' "$field"
        cat "/sys/class/net/$iface/$field" 2>/dev/null || true
    done
} > "$out/metadata.txt"
echo "Dossier : $out"
echo 'Attendre « listening on » (tcpdump) ou « File: - » (dumpcap), puis réaliser une seule expérience.'
echo 'Pour startup : allumer seulement après cette confirmation.'
# Le shell utilisateur ouvre le fichier. tcpdump peut ainsi abandonner ses
# privilèges normalement, sans problème d'accès au dossier de l'utilisateur.
# Une interruption du groupe laisse le shell écrire le bilan après tcpdump.
trap ':' INT
set +e
"${priv[@]}" "${command_line[@]}" > "$out/traffic.pcap" \
    2> >(trap '' INT; tee "$logfile" >&2)
status=$?
wait
set -e
trap - INT
{
    echo "end_utc=$(date -u --iso-8601=ns)"
    echo "capture_exit_code=$status"
    echo '124 = durée timeout atteinte ; 130 = interruption utilisateur possible.'
    ip -statistics link show dev "$iface"
} >> "$out/metadata.txt"
(cd "$out" && sha256sum traffic.pcap > SHA256SUMS)
if [[ $status != 0 && $status != 124 && $status != 130 ]]; then
    echo "Échec capture ($status) ; consulter $logfile" >&2
    exit "$status"
fi
if ! python3 "$root/tools/inspect_pcap.py" "$out/traffic.pcap" --show 0 > "$out/summary.txt"; then
    echo "PCAP invalide/incomplet ; fichiers conservés dans $out" >&2
    exit 1
fi
cat "$out/summary.txt"
echo "Compléter : $out/notes.md"
echo "À vérifier : pertes dans $logfile ; zéro trame n'est pas une preuve de panne."
}

main "$@"
