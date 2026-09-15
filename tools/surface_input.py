"""Clavier ALPHA/pavé et clics X11, libération explicite des entrées possédées."""
# SPDX-License-Identifier: GPL-3.0-or-later
import ctypes as C


class XInput:
    def __init__(self,pointer):
        self.pointer=pointer;self.x=pointer.x;self.test=pointer.test;self.display=pointer.display
        self.x.XStringToKeysym.argtypes=[C.c_char_p];self.x.XStringToKeysym.restype=C.c_ulong
        self.x.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];self.x.XKeysymToKeycode.restype=C.c_ubyte
        self.x.XkbKeycodeToKeysym.argtypes=[C.c_void_p,C.c_ubyte,C.c_int,C.c_int]
        self.x.XkbKeycodeToKeysym.restype=C.c_ulong
        self.x.XQueryKeymap.argtypes=[C.c_void_p,C.c_char_p]
        self.test.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
        self.test.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
        self.keys={};self.codes={};self.buttons=set();self.events=0

    def resolve(self,name):
        symbol=self.x.XStringToKeysym(name.encode('ascii'))
        if not symbol:raise ValueError(f'Keysym inconnu : {name}')
        code=self.x.XKeysymToKeycode(self.display,symbol)
        if not code:raise ValueError(f'Touche absente du clavier X11 : {name}')
        # La session est fr/latin9 ; chercher le symbole dans le groupe actif standard.
        for level in range(4):
            if self.x.XkbKeycodeToKeysym(self.display,code,0,level)==symbol:
                aux=[]
                if level&1:aux.append(int(self.x.XKeysymToKeycode(self.display,self.x.XStringToKeysym(b'Shift_L'))))
                if level&2:aux.append(int(self.x.XKeysymToKeycode(self.display,self.x.XStringToKeysym(b'ISO_Level3_Shift'))))
                return int(code),aux
        raise ValueError(f'Symbole hors du groupe clavier courant : {name}')

    def acquire(self,code):
        if code in self.codes:
            count,owned=self.codes[code];self.codes[code]=(count+1,owned);return
        bitmap=C.create_string_buffer(32);self.x.XQueryKeymap(self.display,bitmap)
        owned=not bool(bitmap.raw[code//8]&(1<<(code%8)))
        if owned:self.test.XTestFakeKeyEvent(self.display,code,1,0)
        self.codes[code]=(1,owned)

    def release(self,code):
        count,owned=self.codes[code]
        if count>1:self.codes[code]=(count-1,owned)
        else:
            if owned:self.test.XTestFakeKeyEvent(self.display,code,0,0)
            del self.codes[code]

    def key(self,name,on):
        if on:
            if name in self.keys:return
            code,aux=self.resolve(name)
            for item in aux+[code]:self.acquire(item)
            self.keys[name]=aux+[code]
        elif name in self.keys:
            for code in reversed(self.keys.pop(name)):self.release(code)

    def release_all(self):
        for name in list(self.keys):self.key(name,False)
        for number in self.buttons:self.test.XTestFakeButtonEvent(self.display,number,0,0)
        self.buttons.clear();self.x.XFlush(self.display)

    def apply(self,action):
        kind,target,values=action
        if kind=='key':self.key(target,bool(values[0]))
        elif kind=='text':self.key(target,True);self.key(target,False)
        elif kind=='button':
            number=int(target);on=bool(values[0])
            if number not in (1,3):return
            if on and number not in self.buttons:
                self.test.XTestFakeButtonEvent(self.display,number,1,0);self.buttons.add(number)
            elif not on and number in self.buttons:
                self.test.XTestFakeButtonEvent(self.display,number,0,0);self.buttons.remove(number)
        elif kind=='release_all':self.release_all()
        else:return
        self.events+=1;self.x.XFlush(self.display)
