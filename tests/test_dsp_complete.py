import unittest
import test_eq_editor as fixture

class DSPCompleteTests(unittest.TestCase):
 setUp=fixture.EQTests.setUp
 action=fixture.EQTests.action
 load=fixture.EQTests.load
 start=fixture.EQTests.start
 def test_compare_armed_and_swap_restore_and_target_guard(self):
  self.start();original=self.eq.value('gain')
  self.assertEqual(self.eq.handle('compare',[]),[])
  self.eq.handle('turn',[1,8]);changed=self.eq.value('gain');self.assertNotEqual(original,changed)
  writes=self.eq.handle('compare',[]);self.assertTrue(writes);self.assertEqual(self.eq.value('gain'),original)
  self.eq.handle('compare',[]);self.assertEqual(self.eq.value('gain'),changed)
  self.r.revision+=1;self.assertEqual(self.eq.handle('compare',[]),[])
 def test_create_select_enable_suspend(self):
  self.assertEqual(self.eq.command(bytes.fromhex('90 04 55')),[('eq','library',[])])
  result=self.eq.handle('library',[]);self.assertEqual(self.eq.mode,'library')
  self.assertIn(('osc','/strip/select',[1,0]),result)
  self.eq.exit();self.start()
  self.assertEqual(self.eq.handle('deactivate',[]),[('osc','/strip/plugin/deactivate',[1,1])])
  self.assertEqual(self.eq.handle('activate',[]),[('osc','/strip/plugin/activate',[1,1])])
 def test_compare_requires_fresh_data(self):
  self.start();self.eq.handle('compare',[]);self.now+=2
  self.assertEqual(self.eq.handle('compare',[]),[])
 def test_parameter_buttons_change_values_and_boolean(self):
  self.start();self.eq.mode='params';self.eq.family=None
  self.eq.params={'Test':dict(id=1,low=0,high=10,value=5,flags=128,choices={})}
  self.eq.handle('parameter_up',[0]);self.assertGreater(self.eq.params['Test']['value'],5)
  self.eq.handle('parameter_down',[0]);self.assertAlmostEqual(self.eq.params['Test']['value'],5)
  self.eq.params={'Test':dict(id=1,low=0,high=1,value=0,flags=192,choices={})}
  self.eq.handle('parameter_up',[0]);self.assertEqual(self.eq.params['Test']['value'],1)
  self.eq.handle('parameter_down',[0]);self.assertEqual(self.eq.params['Test']['value'],0)

 def test_master_bypass_browser_targets_cursor(self):
  self.start();self.eq.mode='browse';self.eq.cursor=1
  self.eq.plugins=[(1,'First',True),(2,'Second',True)]
  self.assertEqual(self.eq.handle('bypass',[]),[('osc','/strip/plugin/deactivate',[1,2])])
 def test_info_and_compare_open_browser_outside_dsp(self):
  for key in (1,9):self.assertEqual(self.eq.command(bytes([0x90,key,0x55])),[('eq','browse',[])])
 def test_operation_display_has_priority_over_info(self):
  from channel_group_display import context_frames
  self.start();self.eq.info=True;self.eq.create_pending=('pending',)
  self.assertEqual(context_frames(self.m,self.eq,True),('AJOUT...',))
