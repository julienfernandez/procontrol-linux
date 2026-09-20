#!/bin/sh
# Temporary USB Audio Class 2 gadget for MPC One / Linux 6.18.
# Install in /tmp only. No firmware, startup or project files are changed.
set -eu
ROOT=/sys/kernel/config/usb_gadget
G=$ROOT/codex_mpc_audio
UDC=ff580000.usb

status() {
    if [ ! -d "$G" ]; then
        echo 'USB audio test: stopped'
        return
    fi
    printf 'Controller: '; cat "$G/UDC"
    printf 'USB state: '; cat "/sys/class/udc/$UDC/state"
    printf 'USB speed: '; cat "/sys/class/udc/$UDC/current_speed"
    for attr in p_chmask c_chmask p_srate c_srate p_ssize c_ssize; do
        printf '%s: ' "$attr"; cat "$G/functions/uac2.audio/$attr"
    done
    if [ -d "$G/functions/midi.usb" ]; then
        printf 'USB MIDI ports: '; cat "$G/functions/midi.usb/in_ports"
    fi
    cat /proc/asound/cards
}

stop() {
    [ -d "$G" ] || return 0
    printf '\n' > "$G/UDC"
    [ ! -L "$G/configs/c.1/uac2.audio" ] || rm "$G/configs/c.1/uac2.audio"
    [ ! -L "$G/configs/c.1/midi.usb" ] || rm "$G/configs/c.1/midi.usb"
    [ ! -d "$G/functions/midi.usb" ] || rmdir "$G/functions/midi.usb"
    [ ! -d "$G/functions/uac2.audio" ] || rmdir "$G/functions/uac2.audio"
    [ ! -d "$G/configs/c.1/strings/0x409" ] || rmdir "$G/configs/c.1/strings/0x409"
    [ ! -d "$G/configs/c.1" ] || rmdir "$G/configs/c.1"
    [ ! -d "$G/strings/0x409" ] || rmdir "$G/strings/0x409"
    rmdir "$G"
    echo 'USB audio test removed; no persistent settings changed by this script.'
}

start() {
    channels=${1:-2}
    midi_ports=${2:-0}
    sample_bytes=${3:-4}
    case "$sample_bytes" in 2|4) ;; *) echo 'Sample width must be 2 or 4 bytes' >&2; exit 2;; esac
    case "$midi_ports" in 0|1|2) ;; *) echo 'MIDI port count must be 0, 1 or 2' >&2; exit 2;; esac
    case "$channels" in
        2|4|8|16) mask=$(( (1 << channels) - 1 )); interval=2 ;;
        32) mask=4294967295; interval=1 ;;
        *) echo 'Supported channel counts: 2 4 8 16 32' >&2; exit 2 ;;
    esac
    [ -d "/sys/class/udc/$UDC" ] || { echo 'MPC One controller missing' >&2; exit 1; }
    [ "$(cat /sys/devices/platform/usb-otg-mux/state)" = peripheral ] || {
        echo 'USB is not in peripheral mode; refusing to change the hardware role.' >&2; exit 1;
    }
    if [ -d "$G" ]; then
        existing_midi=0
        if [ -d "$G/functions/midi.usb" ]; then existing_midi=$(cat "$G/functions/midi.usb/in_ports"); fi
        if [ "$(cat "$G/functions/uac2.audio/p_chmask")" = "$mask" ] &&
           [ "$(cat "$G/functions/uac2.audio/c_chmask")" = "$mask" ] &&
           [ "$(cat "$G/functions/uac2.audio/p_ssize")" = "$sample_bytes" ] &&
           [ "$(cat "$G/functions/uac2.audio/c_ssize")" = "$sample_bytes" ] &&
           [ "$(cat "$G/functions/uac2.audio/p_srate")" = 44100 ] &&
           [ "$(cat "$G/functions/uac2.audio/c_srate")" = 44100 ] &&
           [ "$existing_midi" = "$midi_ports" ]; then
            bound=$(cat "$G/UDC")
            if [ -z "$bound" ]; then echo "$UDC" > "$G/UDC";
            elif [ "$bound" != "$UDC" ]; then echo 'Unexpected USB controller; refusing to replace it.' >&2; exit 1; fi
            status; return
        fi
        echo 'Stop the existing test before changing channels or sample width.' >&2; exit 1
    fi
    for other in "$ROOT"/*; do
        [ ! -d "$other" ] || { echo "Another gadget exists: $other; refusing to replace it." >&2; exit 1; }
    done
    mkdir "$G"
    trap 'stop' EXIT
    echo 0x0200 > "$G/bcdUSB"
    echo 0x0101 > "$G/bcdDevice"
    echo 0xef > "$G/bDeviceClass"
    echo 0x02 > "$G/bDeviceSubClass"
    echo 0x01 > "$G/bDeviceProtocol"
    echo 0x09e8 > "$G/idVendor"
    echo 0x1046 > "$G/idProduct"
    echo high-speed > "$G/max_speed"
    mkdir "$G/strings/0x409"
    echo MPCONE-USB-AUDIO-TEST > "$G/strings/0x409/serialnumber"
    echo 'Akai Professional' > "$G/strings/0x409/manufacturer"
    echo "MPC One USB Audio ${channels}ch" > "$G/strings/0x409/product"
    mkdir "$G/configs/c.1"
    mkdir "$G/configs/c.1/strings/0x409"
    echo 'Temporary audio interface' > "$G/configs/c.1/strings/0x409/configuration"
    echo 2 > "$G/configs/c.1/MaxPower"
    echo 0xc0 > "$G/configs/c.1/bmAttributes"
    mkdir "$G/functions/uac2.audio"
    f=$G/functions/uac2.audio
    echo "$mask" > "$f/p_chmask"
    echo "$mask" > "$f/c_chmask"
    echo 44100 > "$f/p_srate"
    echo 44100 > "$f/c_srate"
    echo "$sample_bytes" > "$f/p_ssize"
    echo "$sample_bytes" > "$f/c_ssize"
    echo "$interval" > "$f/p_hs_bint"
    echo "$interval" > "$f/c_hs_bint"
    echo async > "$f/c_sync"
    echo 8 > "$f/req_number"
    echo 0 > "$f/p_mute_present"
    echo 0 > "$f/c_mute_present"
    echo 0 > "$f/p_volume_present"
    echo 0 > "$f/c_volume_present"
    echo 'MPC USB Audio' > "$f/function_name"
    echo 'MPC USB Audio' > "$f/if_ctrl_name"
    ln -s "$f" "$G/configs/c.1/uac2.audio"
    if [ "$midi_ports" -gt 0 ]; then
        m=$G/functions/midi.usb
        mkdir "$m"
        echo MPCUSBMIDI > "$m/id"
        echo "$midi_ports" > "$m/in_ports"
        echo "$midi_ports" > "$m/out_ports"
        echo 512 > "$m/buflen"
        echo 32 > "$m/qlen"
        if [ -f "$m/interface_string" ]; then echo 'MPC USB MIDI' > "$m/interface_string"; fi
        ln -s "$m" "$G/configs/c.1/midi.usb"
    fi
    echo "$UDC" > "$G/UDC"
    trap - EXIT
    status
}

case ${1:-status} in
    start) start "${2:-2}" "${3:-0}" "${4:-4}" ;;
    stop) stop ;;
    status) status ;;
    *) echo 'Usage: mpc-usb-audio.sh start [2|4|8|16|32 channels] [0|1|2 MIDI ports] [2|4 sample bytes] | status | stop' >&2; exit 2 ;;
esac
