"""Client OSC Ardour complet pour la surface ProControl."""
# SPDX-License-Identifier: GPL-3.0-or-later
import socket
from ardour_transport import ArdourTransport,message
from jog_scheduler import JogScheduler

FEEDBACK_BITS=1+2+16+32+64+8192


class ArdourSurface(ArdourTransport):
    def __init__(self,port,mapper):
        self.mapper=mapper
        self.jog=JogScheduler()
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:
            self.socket.bind(('127.0.0.1',0));self.socket.connect(('127.0.0.1',port));self.socket.setblocking(False)
            # gainmode=2 : fader normalisé ET dB, sans remplacer les noms par le gain.
            self.socket.send(message('/set_surface',0,63,FEEDBACK_BITS,2,8,8,0))
            self.request_catalog()
            self.socket.send(message('/procontrol/plugin_ui/version'))
        except Exception:
            self.socket.close();raise

    def actions(self,actions):
        return self._send_actions(self.jog.actions(actions))

    def flush_jog(self,now=None):
        return self._send_actions(self.jog.flush(now))

    def _send_actions(self,actions):
        result=[]
        for kind,path,values in actions:
            if kind=='osc':
                if path=='/refresh':
                    result.extend(self.refresh())
                else:
                    self.socket.send(message(path,*values));result.append(path)
        return result

    def request_catalog(self):
        # /strip returns a snapshot without recreating observers (unlike legacy
        # /strip/list). Read-only /set_surface is the ordered reply boundary.
        self.socket.send(message('/strip'))
        self.socket.send(message('/set_surface'))

    def refresh(self):
        # Ardour 8.4 refresh_surface destroys/rebuilds observers and has crashed
        # locally. Ethernet recovery uses our cached output, not OSC teardown.
        self.socket.send(message('/transport_speed'))
        return ['/transport_speed']

    def close(self):
        try:self.socket.send(message('/procontrol/plugin_ui/clear'))
        except OSError:pass
        try:self.socket.send(message('/set_surface/feedback',0))
        except OSError:pass
        self.socket.close()
