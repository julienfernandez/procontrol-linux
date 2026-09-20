// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the actual libardour event manager with a deliberately small pool.
#include <iostream>
#include "ardour/session_event.h"
namespace ARDOUR { void setup_enum_writer (); }

class EventManager : public ARDOUR::SessionEventManager {
public:
    EventManager () { next_event = events.end (); }
    void queue_event (ARDOUR::SessionEvent* ev) override { merge_event (ev); }
    void process_event (ARDOUR::SessionEvent* ev) override { delete ev; }
    void set_next_event () override { next_event = events.begin (); }
    size_t scheduled () const { return events.size (); }
};

int main () {
    using namespace ARDOUR;
    setup_enum_writer ();
    SessionEvent::init_event_pool ();
    SessionEvent::create_per_thread_pool ("event-pool-regression", 16);
    const auto initial = SessionEvent::pool_available ();
    EventManager manager;
    manager.queue_event (new SessionEvent (SessionEvent::TransportStateChange,
                                          SessionEvent::Add, 100, 100, 1));
    for (unsigned i = 0; i < 4096; ++i) {
        manager.queue_event (new SessionEvent (SessionEvent::TransportStateChange,
                                              SessionEvent::Add, 100, 100, 1));
        if (SessionEvent::pool_available () != initial - 1 || manager.scheduled () != 1) {
            std::cerr << "FAIL: rejected duplicate leaked a pool slot at iteration " << i << '\n';
            return 1;
        }
    }
    manager.clear_events (SessionEvent::TransportStateChange);
    if (SessionEvent::pool_available () != initial || manager.scheduled () != 0) return 2;
    std::cout << "PASS: 4096 duplicates returned to pool; all slots recovered\n";
}
