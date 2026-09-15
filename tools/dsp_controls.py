"""Pure decoder for locally captured ProControl DSP controls.

Evidence: docs/dsp-buttons-confirmed.json and dsp-encoders-2026-09-14.md.
This module describes physical controls; it does not assign DAW actions.
"""
# SPDX-License-Identifier: GPL-3.0-or-later


def decode_dsp(command):
    if len(command) != 3:
        return None
    status, number, value = command
    if value >= 128:
        return None
    if status == 0xb0 and 0x4d <= number <= 0x54:
        return {'kind': 'encoder', 'row': number - 0x4d + 1,
                'delta': value - 64}
    zone = value & 0x3f
    if status == 0x90 and 0x0d <= zone <= 0x14 and number in (0, 1, 2):
        return {'kind': 'button', 'row': zone - 0x0d + 1,
                'position': ('left_outer', 'left_inner', 'right_of_encoder')[number],
                'pressed': bool(value & 0x40)}
    return None


def dsp_text(row, text):
    """Write a DSP display confirmed by the user's DSP1-B..DSP8-B photo."""
    from surface_feedback import ascii8
    if type(row) is not int or not 1 <= row <= 8:
        raise ValueError('Rangée DSP 1..8')
    return bytes([0xf0,0x13,0,0x40,0x2c+row,0])+ascii8(text)+b'\xf7'
