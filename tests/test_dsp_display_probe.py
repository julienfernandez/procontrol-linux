import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from dsp_display_probe import DSPDisplayProbe,CANDIDATES
from surface_feedback import SurfaceFeedback
from surface_map import SurfaceMap
class DisplayProbeTests(unittest.TestCase):
 def test_labels_and_expiration(self):
  f=SurfaceFeedback(SurfaceMap());p=DSPDisplayProbe(f);p.start(10)
  self.assertEqual(len(f.queue),16)
  self.assertIn(b'DSP1-A  ',f.queue[('dsp_probe',13)])
  self.assertIn(b'DSP8-B  ',f.queue[('dsp_probe',52)])
  self.assertFalse(set(CANDIDATES)&(set(range(8))|set(range(32,40))))
  p.tick(129);self.assertIsNotNone(p.expires)
  p.tick(130);self.assertIsNone(p.expires)
  self.assertTrue(all(body[6:-1]==b' '*8 for body in f.queue.values()))
 def test_overlap_refused_and_previous_restored(self):
  f=SurfaceFeedback(SurfaceMap());p=DSPDisplayProbe(f)
  f.put(('dsp_probe',13),b'previous');p.start(1)
  with self.assertRaises(ValueError):p.start(2)
  p.tick(121);self.assertEqual(f.queue[('dsp_probe',13)],b'previous')
