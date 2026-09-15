"""Écriture PCAP Ethernet, horodatages en microsecondes explicitement déclarés."""
# SPDX-License-Identifier: GPL-3.0-or-later
import struct


def write_header(stream):
    stream.write(struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))


def write_packet(stream, timestamp_ns, frame):
    stream.write(struct.pack('<IIII', timestamp_ns // 10**9,
                             (timestamp_ns % 10**9) // 1000, len(frame), len(frame)) + frame)
    stream.flush()
