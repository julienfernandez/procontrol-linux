#!/usr/bin/env python3
"""Fenêtre locale de validation ; ne reçoit que les événements qui lui sont destinés."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk,GLib

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--log',type=Path,required=True)
args=p.parse_args();records=[]
def record(kind,**details):
    records.append({'utc':datetime.now(timezone.utc).isoformat(),'event':kind,**details})
    args.log.write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n')
window=Gtk.Window(title='ProControl — test clavier et clics')
window.set_default_size(760,320);window.set_border_width(22)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=16);window.add(box)
label=Gtk.Label(label='ALPHA → lettres du CHANNEL MATRIX • SHIFT → majuscules\nPavé numérique → chiffres • ALPHA à nouveau → sélection de pistes')
box.pack_start(label,False,False,0)
entry=Gtk.Entry();entry.set_placeholder_text('Tape ici avec la ProControl…')
box.pack_start(entry,False,False,0)
entry.connect('changed',lambda widget:record('text',text=widget.get_text()))
entry.connect('key-press-event',lambda widget,event:record('key_press',name=Gdk.keyval_name(event.keyval)))
entry.connect('key-release-event',lambda widget,event:record('key_release',name=Gdk.keyval_name(event.keyval)))
area=Gtk.EventBox();area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.BUTTON_RELEASE_MASK)
click_label=Gtk.Label(label='Zone de test : clic gauche ou clic droit ici');area.add(click_label)
def click(widget,event):
    record('mouse',button=int(event.button),type=str(event.type))
    click_label.set_text(f'Bouton {int(event.button)} reçu — {event.type.value_nick}')
    return True
area.connect('button-press-event',click);area.connect('button-release-event',click)
box.pack_start(area,True,True,0)
button=Gtk.Button(label='Fermer le test');button.connect('clicked',lambda *_:window.destroy())
box.pack_start(button,False,False,0)
window.connect('destroy',lambda *_:Gtk.main_quit())
window.show_all();window.present();entry.grab_focus()
record('opened');GLib.timeout_add_seconds(300,lambda:window.destroy() or False)
Gtk.main();record('closed')
