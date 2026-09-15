import json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from dsp_controls import decode_dsp, dsp_text

class DSPControlTests(unittest.TestCase):
    def test_all_captured_press_release_pairs(self):
        evidence=json.loads((ROOT/'docs/dsp-buttons-confirmed.json').read_text())
        self.assertEqual(len(evidence['buttons']),24)
        for button in evidence['buttons']:
            for field,pressed in [('press_hex',True),('release_hex',False)]:
                self.assertEqual(decode_dsp(bytes.fromhex(button[field])),
                    {'kind':'button','row':button['row'],'position':button['position'],'pressed':pressed})
    def test_encoder_sign_and_rows(self):
        for row in range(1,9):
            for value in (0x3f,0x40,0x41,0x42):
                self.assertEqual(decode_dsp(bytes([0xb0,0x4c+row,value])),
                    {'kind':'encoder','row':row,'delta':value-64})
    def test_other_controls_and_malformed_are_not_dsp(self):
        for value in ('90 00 4c','90 00 55','90 03 4d','90 00 cd','b0 4d c1','b0 40 41','90 00','90 00 4d 00'):
            self.assertIsNone(decode_dsp(bytes.fromhex(value)))

    def test_confirmed_display_addresses_and_ascii(self):
        evidence=json.loads((ROOT/'docs/dsp-displays-confirmed.json').read_text())
        for display in evidence['displays']:
            command=dsp_text(display['row'],display['label'])
            self.assertEqual(command[:6],bytes([0xf0,0x13,0,0x40,display['address'],0]))
            self.assertEqual(command[6:-1],display['label'].encode().ljust(8,b' '))
            self.assertEqual(command[-1],0xf7)
        self.assertEqual(dsp_text(1,'Fréquence')[6:-1],b'Frequenc')
        for invalid in (0,9,True,1.5):
            with self.assertRaises(ValueError):dsp_text(invalid,'test')
