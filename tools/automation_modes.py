"""Ardour OSC mode values and ProControl's five automation lamps.

OSC mode numbers are not Ardour's internal AutoState bit flags.
Lamp bits come from ProCautomode/_ReaAutomode in the vendored ProControl driver.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import math

PATH = '/strip/gain/automation'
NAMES = ('Manual', 'Play', 'Write', 'Touch', 'Latch')
# Manual: all off. ProControl TM is a trim mode absent from this Ardour cycle.
LAMPS = (0, 0x04, 0x40, 0x20, 0x10)


def mode_value(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    if value != int(value) or not 0 <= value < len(NAMES):
        return None
    return int(value)


def lamp_command(channel, mode):
    if not 1 <= channel <= 8:
        raise ValueError('Tranche 1..8')
    mode = mode_value(mode)
    return bytes([0xf0, 0x13, 0, 0x20, channel-1, LAMPS[mode] if mode is not None else 0, 0xf7])
