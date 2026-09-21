#!/usr/bin/env python3
"""Deux lectures des quatre trous du programme comm et de son mot de contrôle.

1 768 octets de trous et deux octets de contrôle par passe ; lots de 16.
Aperçu par défaut. --send arrête la passerelle, prend son verrou, puis la relance.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
from functools import partial
import comm_preservation

FIELDS = ('comm-app-gap-20008', 'comm-app-gap-20080', 'comm-app-gap-20110',
          'comm-app-gap-2fce4', 'comm-application-checksum')
acquire = partial(comm_preservation.acquire, fields=FIELDS, schema='comm-application-gaps-v1')


def main(argv=None):
    return comm_preservation.main(argv, fields=FIELDS, collector=acquire, description=__doc__)


if __name__ == '__main__':
    raise SystemExit(main())
