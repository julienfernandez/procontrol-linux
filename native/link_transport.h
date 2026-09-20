// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <jack/transport.h>

inline bool link_transport_playing (jack_transport_state_t state, bool valid, bool was_playing)
{
    // JACK also enters Starting during a rolling locate. Keep the peer's
    // transport running while JACK waits for disk readers to become ready.
    return valid && (state == JackTransportRolling || state == JackTransportLooping ||
                     (state == JackTransportStarting && was_playing));
}
