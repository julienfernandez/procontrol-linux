#!/usr/bin/env python3
"""Small loopback-only settings UI; no raw Ethernet or elevated privileges."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import os
import signal
import subprocess
import sys
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
from surface_settings import load,save,validate,rpc
from studio_control import StudioController
from console_web import ConsoleController

ROOT=Path(__file__).resolve().parents[1]

class App:
    def __init__(self, root=ROOT):
        self.root=Path(root);self.runtime=self.root/'run';self.path=self.root/'settings.json';self.lock=threading.Lock()
        self.studio=StudioController(self.root)
        self.console=ConsoleController(self.root)
    def state(self):
        data={}
        for name,file in [('daemon','status.json'),('pointer','pointer-status.json')]:
            try:
                p=self.runtime/file;s=json.loads(p.read_text())
                if time.time()-p.stat().st_mtime>5:s['running']=False
                data[name]=s
            except (OSError,ValueError):data[name]={'running':False}
        data['saved']=load(self.path)
        data['sources']=data['daemon'].get('stereo',{}).get('sources',[])
        return data
    def update(self, values):
        if not isinstance(values,dict) or set(values)-{'pointer_gain','jog_gain','meter_assignments','revision'}:
            raise ValueError('Champs de réglage inconnus')
        with self.lock:
            current=load(self.path)
            if values.get('revision')!=current['revision']:raise ValueError('Réglages modifiés ailleurs ; recharge la page')
            proposed=dict(current);proposed.update(values);proposed['revision']+=1;proposed=validate(proposed)
            return self.persist(proposed)
    def persist(self, proposed):
        save(self.path,proposed)
        applied={}
        for name,sock in [('daemon','control.sock'),('pointer','pointer.sock')]:
            try:applied[name]=rpc(self.runtime,sock,{'command':'configure','settings':proposed})
            except (OSError,ValueError) as exc:applied[name]={'ok':False,'error':str(exc)}
        return {'saved':proposed,'applied':applied}
    def meter_test(self, values):
        if not isinstance(values,dict) or set(values)!={'address'}:raise ValueError('Adresse requise')
        address=values['address']
        if type(address) is not int or not (8<=address<32 or 40<=address<64):raise ValueError('Adresse de grand vumètre invalide')
        response=rpc(self.runtime,'control.sock',{'command':'meter_test','address':address})
        if not response.get('ok'):raise ValueError(response.get('error','Test refusé'))
        return response
    def calibrate(self, values):
        if not isinstance(values,dict) or set(values)!={'revision','column','address','confirmed'}:raise ValueError('Calibration incomplète')
        if values['confirmed'] is not True:raise ValueError('Observation physique requise')
        column=values['column']
        if type(column) is not int or not 0<=column<6:raise ValueError('Colonne invalide')
        with self.lock:
            current=load(self.path)
            if values['revision']!=current['revision']:raise ValueError('Réglages modifiés ailleurs ; recharge la page')
            current['meter_addresses'][column]=values['address'];current['revision']+=1
            return self.persist(validate(current))

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def output(self,status,body,ctype='application/json; charset=utf-8'):
        if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)
    def allowed(self,write=False):
        hosts={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if self.headers.get('Host') not in hosts:return False
        if write:
            origin=self.headers.get('Origin')
            if origin is not None and origin not in {'http://'+h for h in hosts}:return False
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return False
        return True
    def do_GET(self):
        if not self.allowed():return self.output(403,{'error':'Hôte non autorisé'})
        path=urlsplit(self.path).path
        if path=='/api/console/model':return self.output(200,self.server.app.console.model())
        if path=='/api/console/state':return self.output(200,self.server.app.console.state())
        if path=='/api/console/events':
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-store');self.end_headers()
            last=None;last_cursor=None
            try:
                # Bounded connection duration; EventSource reconnects automatically.
                for _ in range(240):
                    state=self.server.app.console.state()
                    state=dict(state)
                    events=state.get('events',[])
                    if last_cursor is not None and events and events[0]['id']>last_cursor+1:state['gap']=True
                    encoded=json.dumps(state,ensure_ascii=False)
                    if encoded!=last:
                        self.wfile.write(('data: '+encoded+'\n\n').encode());self.wfile.flush();last=encoded;last_cursor=state.get('cursor')
                    time.sleep(.25)
            except (BrokenPipeError,ConnectionResetError):pass
            return
        if path=='/api/state':return self.output(200,self.server.app.state())
        if path=='/api/studio':return self.output(200,self.server.app.studio.state())
        if path=='/api/studio/logs':return self.output(200,self.server.app.studio.logs())
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        files.update({'/mapping':('mapping.html','text/html; charset=utf-8'),'/mapping.js':('mapping.js','text/javascript; charset=utf-8'),'/mapping.css':('mapping.css','text/css; charset=utf-8')})
        if path not in files:return self.output(404,{'error':'Introuvable'})
        name,ctype=files[path];self.output(200,(self.server.app.root/'web'/name).read_bytes(),ctype)
    def do_POST(self):
        if not self.allowed(True):return self.output(403,{'error':'Origine non autorisée'})
        actions={'/api/settings':self.server.app.update,'/api/meter-test':self.server.app.meter_test,'/api/calibration':self.server.app.calibrate,'/api/studio/action':self.server.app.studio.request}
        actions['/api/console/action']=self.server.app.console.request
        if self.path not in actions:return self.output(404,{'error':'Introuvable'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=65536:raise ValueError('Requête trop grande ou vide')
            result=actions[self.path](json.loads(self.rfile.read(length)))
            self.output(200,result)
        except (ValueError,TypeError,KeyError) as exc:self.output(400,{'error':str(exc)})
        except OSError as exc:self.output(503,{'error':'Écriture impossible : '+str(exc)})

def serve(root=ROOT,port=8765):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True;server.app=App(root)
    return server

def process_status():
    try:
        pid=int((ROOT/'run/web.pid').read_text())
        argv=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        active=str(Path(__file__).resolve()).encode() in argv and b'_run' in argv
        return {'pid':pid,'running':active,'url':'http://127.0.0.1:8765'}
    except (OSError,ValueError):return {'running':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('start','status','stop','_run'),nargs='?',default='start')
    p.add_argument('--port',type=int,default=8765);args=p.parse_args();state=process_status()
    if args.action=='status':print(json.dumps(state));return
    if args.action=='stop':
        if state['running']:
            os.kill(state['pid'],signal.SIGTERM)
            for _ in range(250):
                if not process_status()['running']:break
                time.sleep(.1)
            else:raise RuntimeError('Arrêt web encore en cours ; aucune seconde instance lancée')
        return
    if args.action=='start':
        if state['running']:print(json.dumps(state));return
        (ROOT/'run').mkdir(exist_ok=True)
        with (ROOT/'run/web.log').open('w') as log:
            child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'_run','--port',str(args.port)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        for _ in range(50):
            time.sleep(.05)
            state=process_status()
            if state.get('pid')==child.pid and state['running']:print(json.dumps(state));return
            if child.poll() is not None:raise RuntimeError((ROOT/'run/web.log').read_text()[-1000:])
        raise RuntimeError('Serveur sans état publié')
    server=serve(port=args.port)
    server.app.studio.start()
    def stop_server(signum,frame):
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,stop_server)
    (ROOT/'run/web.pid').write_text(str(os.getpid()))
    print(f'ProControl : http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.app.studio.close();server.server_close();(ROOT/'run/web.pid').unlink(missing_ok=True)

if __name__=='__main__':main()
