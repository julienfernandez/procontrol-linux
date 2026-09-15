"""Bounded, temporary DSP display-address experiment through the existing sender."""
import time
from surface_feedback import ascii8

CANDIDATES = tuple(range(0x0d,0x15)) + tuple(range(0x2d,0x35))

class DSPDisplayProbe:
    def __init__(self, feedback):
        self.feedback=feedback
        self.expires=None
        self.saved={}

    def start(self, now=None):
        if self.expires is not None:
            raise ValueError('Un test afficheur est déjà actif')
        now=time.monotonic() if now is None else now
        for address in CANDIDATES:
            key=('dsp_probe',address)
            self.saved[key]=self.feedback.desired.get(key)
            row=(address & 0x1f)-0x0d+1
            label=f'DSP{row}-'+('B' if address & 0x20 else 'A')
            self.feedback.put(key,bytes([0xf0,0x13,0,0x40,address,0])+ascii8(label)+b'\xf7')
        self.expires=now+120
        return {'ok':True,'duration':120,'candidate_addresses':list(CANDIDATES)}

    def tick(self, now=None):
        now=time.monotonic() if now is None else now
        if self.expires is None or now<self.expires:return
        for key,previous in self.saved.items():
            blank=bytes([0xf0,0x13,0,0x40,key[1],0])+b' '*8+b'\xf7'
            self.feedback.put(key,previous if previous is not None else blank)
        self.saved.clear();self.expires=None
