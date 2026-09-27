#!/usr/bin/env python3
"""Compile the real callback body against JACK removal scenarios (no live audio)."""
import argparse
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('source', type=Path, help='Ardour jack_portengine.cc')
args = p.parse_args()
source = args.source.read_text()
start = source.index('void\nJACKAudioBackend::connect_callback (')
end = source.index('\nbool\nJACKAudioBackend::connected (', start)
callback = source[start:end]
harness = r'''
#include <cassert>
#include <string>
#include <iostream>
using jack_port_id_t = unsigned;
struct jack_port_t { unsigned id; } ports[] = {{1}, {2}};
unsigned scenario = 0;
jack_port_t* jack_port_by_id (void*, unsigned id) {
    if ((scenario == 1 && id == 1) || (scenario == 2 && id == 2)) return nullptr;
    return &ports[id-1];
}
const char* jack_port_name (jack_port_t* p) {
    if (!p || (scenario == 3 && p->id == 1) || (scenario == 4 && p->id == 2)) return nullptr;
    return p->id == 1 ? "source:out" : "destination:in";
}
struct Manager {
    bool removing = false, connection = false;
    unsigned calls = 0;
    bool port_remove_in_progress () { return removing; }
    void connect_callback (const std::string& a, const std::string& b, bool c) {
        assert (a == "source:out" && b == "destination:in");
        connection = c; ++calls;
    }
};
struct JACKAudioBackend {
    Manager manager;
    void connect_callback (jack_port_id_t, jack_port_id_t, int);
};
#define GET_PRIVATE_JACK_POINTER(name) void* name = nullptr
'''
harness += callback
harness += r'''
int main () {
    JACKAudioBackend backend;
    for (scenario = 1; scenario <= 4; ++scenario) {
        backend.connect_callback (1, 2, 0);
        backend.connect_callback (1, 2, 1);
        assert (backend.manager.calls == 0);
    }
    scenario = 0;
    backend.connect_callback (1, 2, 1);
    assert (backend.manager.calls == 1 && backend.manager.connection);
    backend.connect_callback (1, 2, 0);
    assert (backend.manager.calls == 2 && !backend.manager.connection);
    backend.manager.removing = true;
    backend.connect_callback (1, 2, 1);
    assert (backend.manager.calls == 2);
    std::cout << "Missing ports/names, valid connect/disconnect, removal guard: PASS\n";
}
'''
with tempfile.TemporaryDirectory(prefix='juju-jack-test-') as directory:
    root = Path(directory)
    cpp, exe = root/'callback.cc', root/'callback-test'
    cpp.write_text(harness)
    subprocess.run(['g++', '-std=c++17', '-O1', '-Wall', '-Wextra',
                    str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
