// SPDX-License-Identifier: GPL-3.0-or-later
#include <cassert>
#include "../link_transport.h"
int main ()
{
    bool playing = false;
    playing = link_transport_playing(JackTransportStarting, true, playing);
    assert(!playing); // Initial preroll must not start the peer early.
    playing = link_transport_playing(JackTransportRolling, true, playing);
    assert(playing);
    for (int i = 0; i < 4096; ++i) {
        playing = link_transport_playing(JackTransportStarting, true, playing);
        assert(playing); // A rolling seek is not a STOP/PLAY command.
        playing = link_transport_playing(JackTransportRolling, true, playing);
        assert(playing);
    }
    assert(link_transport_playing(JackTransportLooping, true, playing));
    assert(!link_transport_playing(JackTransportRolling, false, playing));
    playing = link_transport_playing(JackTransportStopped, true, playing);
    assert(!playing);
    assert(!link_transport_playing(JackTransportStarting, true, playing));
}
