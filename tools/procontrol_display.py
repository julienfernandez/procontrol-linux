"""Commandes d'affichage dérivées de ReaClock / ProCclock, sans émission."""
# SPDX-License-Identifier: GPL-3.0-or-later
# Adapté de ReaCommon.py / procontrolosc.py, Copyright (C) 2018 PhaseWalker.
import ast
import re
from functools import lru_cache
from pathlib import Path

REFERENCE_PATH = Path(__file__).resolve().parents[1] / 'vendor/reacontrol24-lazlooose/procontrolosc.py'
CLOCK_SOURCE_COMMIT = 'b23402542cdfdb09fbb44cc3000ecede1103125b'


@lru_cache(maxsize=1)
def clock_reference():
    tree = ast.parse(REFERENCE_PATH.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'C24clock')
    return {t.id: ast.literal_eval(n.value)
            for n in cls.body if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name) and t.id in ('sevenseg', 'clockbytes')}


def clock_command(text):
    """Huit chiffres/espaces/tirets, sans points ni LED de mode pour ce test.

    Le fork lazlooose fournit déjà famille 00 et adresse compteur 09, ainsi
    que l'ordre inversé et l'encodage sept segments de C24clock._xform_txt.
    """
    if len(text) != 8 or any(c not in '0123456789 -' for c in text):
        raise ValueError('Le compteur attend exactement huit chiffres, espaces ou tirets')
    ref = clock_reference()
    command = list(ref['clockbytes'])
    command[5] = 0x00
    command[6:14] = [ref['sevenseg'][c] for c in reversed(text)]
    return bytes(command)


CLOCK_TEST_STEPS = ((3, '12345678'), (33, '87654321'), (63, '        '))


# Ardour Temporal::ticks_per_beat is 1920. The three-digit console field uses
# 960 ticks per beat. Convert before formatting so 1000..1919 never shifts
# the bar/beat fields; dots 0x14 delimit the fixed 3 / 2 / 3 digit layout.
def bbt_clock_command(text):
    match = re.fullmatch(r"\s*(-?\d+)\|(\d+)\|(\d+)\s*", str(text))
    if not match:
        return clock_command('        ')
    bar, beat, tick = map(int, match.groups())
    bars = f'{bar:03d}' if -99 <= bar <= 999 and bar != 0 else '---'
    beats = f'{beat:02d}' if 1 <= beat <= 99 else '--'
    ticks = f'{tick // 2:03d}' if 0 <= tick < 1920 else '---'
    command = bytearray(clock_command(bars + beats + ticks))
    command[5] = 0x14
    return bytes(command)
