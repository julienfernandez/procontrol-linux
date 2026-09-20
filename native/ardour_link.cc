// SPDX-License-Identifier: GPL-3.0-or-later
// Ardour/JACK timebase -> Ableton Link. No audio ports or timebase ownership.
#include <ableton/Link.hpp>
#include <jack/jack.h>
#include <jack/transport.h>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <fstream>
#include <iostream>
#include <thread>
#include <unistd.h>
#include <sys/file.h>
#include <fcntl.h>
#include "link_transport.h"

namespace {
volatile std::sig_atomic_t running = 1;
void stop(int) { running = 0; }
struct Bridge {
    ableton::Link link{120.0};
    jack_client_t* client = nullptr;
    std::atomic<bool> valid{false}, playing{false}, shutdown{false};
    std::atomic<double> bpm{0}, quantum{4}, phase_error_ms{0};
    std::atomic<unsigned long> cycles{0}, realignments{0};
    std::atomic<unsigned long> transport_starts{0}, transport_stops{0};
    bool previous_playing = false, previous_rolling = false, previous_valid = false;
    jack_nframes_t previous_frame = 0, previous_size = 0;
    std::size_t previous_peers = 0;
    double previous_quantum = 4;
    std::chrono::microseconds last_alignment{0}, play_started{0};

    static int process(jack_nframes_t frames, void* opaque) {
        auto& b = *static_cast<Bridge*>(opaque);
        jack_position_t p{};
        const auto transport = jack_transport_query(b.client, &p);
        const auto now = b.link.clock().micros();
        const bool ok = (p.valid & JackPositionBBT) && p.frame_rate > 0 &&
            std::isfinite(p.beats_per_minute) && p.beats_per_minute > 0 &&
            std::isfinite(p.beat_type) && p.beat_type > 0 &&
            std::isfinite(p.beats_per_bar) && p.beats_per_bar > 0 &&
            std::isfinite(p.ticks_per_beat) && p.ticks_per_beat > 0;
        b.valid.store(ok);
        ++b.cycles;
        const bool rolling = ok && (transport == JackTransportRolling || transport == JackTransportLooping);
        const bool playing = link_transport_playing(transport, ok, b.previous_playing);
        auto state = b.link.captureAudioSessionState();
        // Link beats are quarter notes, even for a JACK meter such as 6/8.
        const double scale = ok ? 4.0 / p.beat_type : 1.0;
        const double tempo = ok ? p.beats_per_minute * scale : 120.0;
        const double q = ok ? p.beats_per_bar * scale : 4.0;
        const double beat = ok ? (p.beat - 1.0 + p.tick / p.ticks_per_beat) * scale : 0;
        const auto peers = b.link.numPeers();
        bool changed = false;
        if (ok && std::abs(state.tempo() - tempo) > 0.001) {
            state.setTempo(tempo, now);
            changed = true;
        }
        // Only JACK transitions publish transport commands. A peer joining does
        // not itself start playback; no incoming command is sent into Ardour.
        if (playing != b.previous_playing || !ok) {
            if (state.isPlaying() != playing) {
                state.setIsPlaying(playing, now);
                if (playing) ++b.transport_starts; else ++b.transport_stops;
                changed = true;
            }
        }
        if (playing && !b.previous_playing) b.play_started = now;
        const auto expected = b.previous_frame + b.previous_size;
        const auto delta = std::abs(static_cast<double>(p.frame) - expected);
        const bool jump = rolling && b.previous_rolling && delta > frames * 2.0;
        const double error = ok ? std::remainder(state.phaseAtTime(now, q) - beat, q) : 0;
        const double error_ms = error * 60000.0 / tempo;
        b.phase_error_ms.store(rolling ? error_ms : 0);
        // Anchor at PLAY, a seek/loop, a peer arrival, or a meter change. Correct
        // sustained clock drift only beyond 10 ms, at most once a second.
        const auto correction_interval = now - b.play_started < std::chrono::milliseconds(250)
            ? std::chrono::milliseconds(20) : std::chrono::milliseconds(1000);
        const bool drift = rolling && std::abs(error_ms) > 10 && now - b.last_alignment > correction_interval;
        if (rolling && (!b.previous_rolling || !b.previous_valid || jump ||
                peers != b.previous_peers || q != b.previous_quantum || drift)) {
            state.forceBeatAtTime(beat, now, q);
            b.last_alignment = now;
            ++b.realignments;
            changed = true;
        }
        if (changed) b.link.commitAudioSessionState(state);
        b.previous_playing = playing;
        b.previous_rolling = rolling;
        b.previous_valid = ok;
        b.previous_frame = p.frame;
        b.previous_size = frames;
        b.previous_peers = peers;
        b.previous_quantum = q;
        b.playing.store(playing);
        b.bpm.store(ok ? tempo : 0);
        b.quantum.store(q);
        return 0;
    }
    static void lost(void* opaque) { static_cast<Bridge*>(opaque)->shutdown.store(true); }
};
}
int main(int argc, char** argv) {
    if (argc != 2) { std::cerr << "Usage: procontrol-link STATUS_JSON\n"; return 2; }
    const std::string path = argv[1];
    const int lock = open((path + ".lock").c_str(), O_CREAT | O_RDWR, 0600);
    if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB) != 0) {
        std::cerr << "Link bridge already running or status directory unavailable\n"; return 2;
    }
    std::signal(SIGINT, stop); std::signal(SIGTERM, stop);
    Bridge b;
    jack_status_t status{};
    b.client = jack_client_open("procontrol-link", JackNoStartServer, &status);
    if (!b.client) { std::cerr << "Cannot connect to JACK: " << status << '\n'; return 1; }
    b.link.enableStartStopSync(true);
    jack_set_process_callback(b.client, Bridge::process, &b);
    jack_on_shutdown(b.client, Bridge::lost, &b);
    if (jack_activate(b.client) != 0) { jack_client_close(b.client); return 1; }
    unsigned long last_cycles = 0;
    while (running && !b.shutdown.load()) {
        const bool fresh = b.cycles.load() != last_cycles;
        last_cycles = b.cycles.load();
        const bool enabled = fresh && b.valid.load();
        if (b.link.isEnabled() != enabled) b.link.enable(enabled);
        const auto state = b.link.captureAppSessionState();
        const auto epoch = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
        std::ofstream out(path + ".tmp");
        out.precision(12);
        out << "{\"pid\":" << getpid() << ",\"updated_at\":" << epoch
            << ",\"running\":true,\"enabled\":" << (enabled ? "true" : "false")
            << ",\"source\":\"JACK timebase (Ardour)\",\"direction\":\"Ardour to Link\""
            << ",\"peers\":" << b.link.numPeers() << ",\"tempo\":" << b.bpm.load()
            << ",\"link_tempo\":" << state.tempo() << ",\"quantum\":" << b.quantum.load()
            << ",\"playing\":" << (b.playing.load() ? "true" : "false")
            << ",\"transport_starts\":" << b.transport_starts.load()
            << ",\"transport_stops\":" << b.transport_stops.load()
            << ",\"phase_error_ms\":" << b.phase_error_ms.load()
            << ",\"realignments\":" << b.realignments.load() << ",\"audio_cycles\":" << last_cycles << "}\n";
        out.close();
        if (!out || rename((path + ".tmp").c_str(), path.c_str()) != 0) { running = 0; break; }
        for (int i=0; i<10 && running && !b.shutdown.load(); ++i)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    // Graceful service shutdown publishes STOP, then leaves the Link session.
    if (!b.shutdown.load()) jack_deactivate(b.client);
    auto state = b.link.captureAppSessionState();
    if (state.isPlaying()) {
        state.setIsPlaying(false, b.link.clock().micros());
        b.link.commitAppSessionState(state);
        if (b.link.numPeers()) std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
    b.link.enable(false);
    jack_client_close(b.client);
    unlink(path.c_str());
    close(lock);
    return b.shutdown.load() ? 1 : 0;
}
