#include <future>
#include <iostream>
#include <stdexcept>
#include <thread>
#include "pbd/pbd.h"
#include "pbd/abstract_ui.h"
#include "pbd/abstract_ui.inc.cc"
#include "osc_observer_connections.h"

struct Request : PBD::EventLoop::BaseRequestObject {};
class Loop : public AbstractUI<Request> {
public:
    Loop () : AbstractUI<Request> ("OSC-observer-regression") { _ok = true; run (); }
    ~Loop () { quit (); }
    void sync (const std::function<void ()>& fn = [] {}) {
        std::promise<void> done;
        call_slot (nullptr, [&] { fn (); done.set_value (); });
        done.get_future ().get ();
    }
protected:
    void do_request (Request* req) override {
        if (req->type == CallSlot) req->the_slot ();
        else if (req->type == Quit) _main_loop->quit ();
    }
};

// Keep the real PBD event loop busy while another thread emits a signal.
// Disconnect/reset on the event loop before it can dispatch the queued slot.
static void pending_reset (Loop& loop, PBD::Signal<void ()>& signal,
                           const std::function<void ()>& reset) {
    std::promise<void> entered, release;
    auto ready = entered.get_future ();
    auto proceed = release.get_future ();
    loop.call_slot (nullptr, [&] { entered.set_value (); proceed.get (); reset (); });
    ready.get ();
    signal ();
    release.set_value ();
    loop.sync ();
}

static void require (bool condition, const char* message) {
    if (!condition) throw std::runtime_error (message);
}

static void check (Loop& loop, const char* mode) {
    PBD::Signal<void ()> signal;
    int old_calls = 0;
    PBD::ScopedConnectionList old;
    loop.sync ([&] { signal.connect (old, MISSING_INVALIDATOR, [&] { ++old_calls; }, &loop); });
    pending_reset (loop, signal, [&] { old.drop_connections (); });
    require (old_calls == 1, "negative control did not reproduce the stale callback");

    int valid_calls = 0, stale_calls = 0;
    OSCObserverConnections connections;
    for (int cycle = 0; cycle < 4096; ++cycle) {
        loop.sync ([&] {
            signal.connect (connections, PBD::EventLoop::__invalidator (connections, __FILE__, __LINE__), [&] { ++valid_calls; }, &loop);
        });
        signal ();
        loop.sync ();
        loop.sync ([&] {
            connections.drop_connections ();
            signal.connect (connections, PBD::EventLoop::__invalidator (connections, __FILE__, __LINE__), [&] { ++stale_calls; }, &loop);
        });
        pending_reset (loop, signal, [&] { connections.drop_connections (); });
        auto owner = std::make_unique<OSCObserverConnections> ();
        loop.sync ([&] {
            signal.connect (*owner, PBD::EventLoop::__invalidator (*owner, __FILE__, __LINE__), [&] { ++stale_calls; }, &loop);
        });
        pending_reset (loop, signal, [&] { owner.reset (); });
    }
    require (valid_calls == 4096, "live notifications were lost");
    require (stale_calls == 0, "stale callback escaped invalidation");
    loop.sync ();
    // Let the current dispatch batch end; PBD reclaims trash at the next entry.
    std::this_thread::sleep_for (std::chrono::milliseconds (20));
    size_t remaining = 0;
    loop.sync ([&] { remaining = loop.trash.size (); });
    require (remaining == 0, "invalidation records were not reclaimed");
    std::cout << mode << ": old stale callbacks=" << old_calls
              << ", live=" << valid_calls << ", stale=" << stale_calls
              << ", pending records=" << remaining << std::endl;
}

int main () {
    PBD::init ();
    {
        Loop loop;
        check (loop, "heap queue");
        loop.register_thread (pthread_self (), "test-emitter", 64);
        check (loop, "realtime ring buffer");
    }
    PBD::cleanup ();
}
