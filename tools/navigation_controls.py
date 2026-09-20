"""Navigation keys from the user's ordered 3-press capture, 2026-09-20.

Evidence: docs/navigation-buttons-confirmed.json. These are command zone 0x18,
not track 25 as the incomplete third-party reference fallback suggested.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
NAVIGATION_KEYS = {0: 'Up', 1: 'Previous', 2: 'Zoom/SEL', 3: 'Next', 4: 'Down'}


def navigation_button(command):
    if len(command)!=3 or command[0]!=0x90 or command[2]>=128:
        return None
    zone=command[2]&63; number=command[1]
    if zone!=0x18 or number not in NAVIGATION_KEYS:
        return None
    return dict(zone=zone,key=number,pressed=bool(command[2]&64),
                label=NAVIGATION_KEYS[number],group='Navigation')
