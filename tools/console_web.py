"""Cached read model for web clients. Only the daemon owns live console actions."""
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import threading
import time
from console_layout import layout
from console_presets import PresetStore
from surface_settings import rpc


class ConsoleController:
    def __init__(self,root):
        self.root=root;self.store=PresetStore(root);self.lock=threading.Lock()
        self.cached={'ok':False,'error':'Connexion à la Gateway…','events':[]};self.at=0.

    def model(self):return dict(layout=layout(),store=self.store.view())

    def state(self,cursor=0):
        # A shared cache bounds daemon RPC load even with several open pages.
        with self.lock:
            now=time.monotonic()
            if now-self.at>=.20:
                try:
                    response=rpc(self.root/'run','control.sock',dict(command='mapping',action='state',cursor=self.cached.get('cursor',0)),timeout=.3)
                    response['received_at']=time.time()
                    self.cached=response
                except (OSError,ValueError) as exc:self.cached=dict(ok=False,error='Gateway indisponible : '+str(exc),events=[])
                self.at=now
            return self.cached

    def request(self,request):
        if not isinstance(request,dict):raise ValueError('Objet requis')
        action=request.get('action')
        if action in ('state','learn_start','learn_stop','learn_heartbeat','associate','probe','probe_stop','activate','rollback'):
            reply=rpc(self.root/'run','control.sock',dict(request,command='mapping'))
            if not reply.get('ok'):raise ValueError(reply.get('error','Opération refusée'))
            return reply
        return self.store.mutate(request)
