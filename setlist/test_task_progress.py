import unittest
from task_progress import Timing,Update

class TimingTests(unittest.TestCase):
 def setUp(self):self.now=0
 def timing(self,estimate=None):return Timing(estimate,clock=lambda:self.now)
 def advance(self,timer,done,seconds=1,total=100,phase='recordings',known=True):
  self.now+=seconds;timer.update(Update('Working',phase,done,total,final=phase=='recordings',eta_known=known));return timer.snapshot()
 def stable(self,timer,total=100,phase='recordings'):
  self.advance(timer,0,0,total,phase)
  for n in range(1,7):self.advance(timer,n,1,total,phase)
 def test_startup_outlier_excluded_and_history_not_used(self):
  t=self.timing(660);self.assertIsNone(t.snapshot()['etaSeconds'])
  self.advance(t,0,0);self.advance(t,1,30)
  for n in range(2,5):self.assertIsNone(self.advance(t,n)['etaSeconds'])
  s=self.advance(t,5);self.assertEqual(s['etaSeconds'],95);self.assertEqual(s['etaScope'],'task')
 def test_fast_cached_batch_stays_calculating_until_measured(self):
  t=self.timing();self.advance(t,0,0)
  for n in range(1,10):self.assertIsNone(self.advance(t,n*10,.01)['etaSeconds'])
  t.finish('done');self.assertEqual(t.snapshot()['etaState'],'done')
 def test_stage_change_resets_confidence_not_elapsed(self):
  t=self.timing();self.stable(t,phase='scan');self.assertEqual(t.snapshot()['etaScope'],'step')
  s=self.advance(t,0,2,50);self.assertIsNone(s['etaSeconds']);self.assertEqual(s['elapsedSeconds'],8)
  for n in range(1,7):s=self.advance(t,n,total=50)
  self.assertEqual(s['etaSeconds'],44);self.assertEqual(s['etaScope'],'task')
 def test_total_change_and_unknown_target_suppress_stale_eta(self):
  t=self.timing();self.stable(t);s=self.advance(t,7,total=150);self.assertIsNone(s['etaSeconds'])
  s=self.advance(t,8,total=150,known=False);self.assertIsNone(s['progressPercent']);self.assertIsNone(s['etaSeconds'])
 def test_variable_cost_suppresses_then_recovers(self):
  t=self.timing();self.stable(t);s=self.advance(t,7,5);self.assertIsNone(s['etaSeconds'])
  for n in range(8,16):s=self.advance(t,n)
  self.assertEqual(s['etaState'],'estimated')
 def test_no_fake_countdown_and_overrun(self):
  t=self.timing();self.stable(t);eta=t.snapshot()['etaSeconds'];self.now+=1
  self.assertEqual(t.snapshot()['etaSeconds'],eta);self.now+=3
  self.assertEqual(t.snapshot()['etaState'],'overrun');self.assertIsNone(t.snapshot()['etaSeconds']);self.now+=20
  self.assertEqual(t.snapshot()['etaState'],'working')
 def test_cancel_error_completion_and_restart(self):
  for state in ('done','error','stopped'):
   self.now=0;t=self.timing();self.stable(t);t.finish(state);self.now+=30
   self.assertEqual(t.snapshot()['etaState'],state);self.assertIsNone(t.snapshot()['etaSeconds']);self.assertEqual(t.snapshot()['elapsedSeconds'],6)
   fresh=self.timing(90);self.assertEqual(fresh.snapshot()['elapsedSeconds'],0);self.assertIsNone(fresh.snapshot()['etaSeconds'])
 def test_empty_and_unknown_phase_and_clock_monotonic(self):
  t=self.timing();self.advance(t,0,2,0);self.assertIsNone(t.snapshot()['etaSeconds'])
  self.stable(t);t.update('Checking folders');self.assertIsNone(t.snapshot()['progressPercent'])
  elapsed=t.snapshot()['elapsedSeconds'];self.now-=1;self.assertEqual(t.snapshot()['elapsedSeconds'],elapsed)

if __name__=='__main__':unittest.main()
