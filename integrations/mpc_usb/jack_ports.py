#!/usr/bin/env python3
import ctypes as C
import os
from pathlib import Path

class Jack:
    def __init__(self):
        lib = Path(os.environ['MPC_STUDIO_ROOT']) / 'tools/vendor/pipewire-jack/usr/lib/x86_64-linux-gnu/pipewire-0.3/jack/libjack.so.0'
        self.j = C.CDLL(str(lib.resolve()))
        for name, restype, args in [
            ('jack_client_open', C.c_void_p, [C.c_char_p, C.c_int, C.POINTER(C.c_int)]),
            ('jack_get_ports', C.POINTER(C.c_char_p), [C.c_void_p, C.c_char_p, C.c_char_p, C.c_ulong]),
            ('jack_client_close', C.c_int, [C.c_void_p]),
            ('jack_connect', C.c_int, [C.c_void_p, C.c_char_p, C.c_char_p]),
            ('jack_disconnect', C.c_int, [C.c_void_p, C.c_char_p, C.c_char_p]),
            ('jack_port_by_name', C.c_void_p, [C.c_void_p, C.c_char_p]),
            ('jack_port_get_all_connections', C.POINTER(C.c_char_p), [C.c_void_p, C.c_void_p]),
            ('jack_free', None, [C.c_void_p]),
        ]:
            f = getattr(self.j, name); f.restype = restype; f.argtypes = args
        status = C.c_int()
        self.client = self.j.jack_client_open(b'codex-studio-routing', 1, C.byref(status))
        if not self.client:
            raise RuntimeError('Cannot connect to PipeWire JACK: %s' % status.value)

    def strings(self, arr):
        result = []; i = 0
        while arr and arr[i]:
            result.append(arr[i].decode()); i += 1
        if arr: self.j.jack_free(arr)
        return result

    def ports(self):
        return self.strings(self.j.jack_get_ports(self.client, None, None, 0))

    def connections(self, name):
        p = self.j.jack_port_by_name(self.client, name.encode())
        return self.strings(self.j.jack_port_get_all_connections(self.client, p)) if p else []

    def connect(self, source, destination):
        rc = self.j.jack_connect(self.client, source.encode(), destination.encode())
        if rc not in (0, 17): raise RuntimeError((source, destination, rc))

    def disconnect(self, source, destination):
        return self.j.jack_disconnect(self.client, source.encode(), destination.encode())

    def close(self):
        self.j.jack_client_close(self.client)

if __name__ == '__main__':
    j = Jack()
    for p in j.ports():
        print(p)
        for c in j.connections(p): print('  -> ' + c)
    j.close()
