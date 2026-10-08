import math,unittest
import core,playlist_request,matching,duration_target,conversation
from test_setlist import song
class DurationTargetTests(unittest.TestCase):
 def rows(self,n=150,duration=240):
  return [song(i,artist=f'Artist {i}',title=f'Song {i}',genre='R&B',duration=duration) for i in range(n)]
 def build(self,prompt,rows=None):
  rows=self.rows() if rows is None else rows
  q=playlist_request.parse(prompt,rows);q['mode']='library'
  return matching.attach(core.build(rows,q,fetch=lambda _:self.fail('No network for duration')),rows)
 def test_numeric_spoken_and_abbreviated_targets(self):
  for phrase,seconds in [('30 minutes',1800),('thirty minutes',1800),('45min',2700),('forty-five minutes',2700),('one hour',3600),('1h',3600),('three hours',10800),('two hours',7200),('two-hour',7200),('2 hours',7200),('90 minutes',5400),('an hour and a half',5400),('half an hour',1800),('1 hour 30 minutes',5400)]:
   with self.subTest(phrase=phrase):
    q=playlist_request.parse('find '+phrase+' of R&B');self.assertEqual(q['targetDurationSeconds'],seconds);self.assertIsNone(q['count']);self.assertEqual(q['style'],'R&B')
 def test_approved_rounding_and_count_parity(self):
  for phrase,count in [('30 minutes',23),('45 minutes',33),('1 hour',44),('two hours',87),('three hours',129)]:
   r=self.build('find '+phrase+' of R&B');self.assertEqual(len(r['songs']),count);self.assertEqual(r['requested'],count);self.assertEqual(r['durationSummary']['shortfallSeconds'],0)
  self.assertEqual(len(self.build('50 R&B songs')['songs']),50)
  self.assertEqual(len(self.build('find 87 R&B songs')['songs']),87)
  self.assertEqual(playlist_request.parse('87 90s R&B songs')['count'],87)
 def test_no_default_count_cap(self):
  r=self.build('4 hours of R&B',self.rows(200));self.assertEqual(len(r['songs']),173)
 def test_short_tracks_increase_base_before_extra_choices(self):
  r=self.build('30 minutes of R&B',self.rows(100,60));self.assertEqual(r['durationSummary']['baseSongCount'],30);self.assertEqual(len(r['songs']),38)
  self.assertTrue(all(duration_target.estimate(x)<=x['duration'] for x in r['songs']))
 def test_unknown_lengths_are_explicit_estimates(self):
  r=self.build('30 minutes of R&B',self.rows(40,0));self.assertEqual(len(r['songs']),23);self.assertEqual(r['durationSummary']['actualSeconds'],0);self.assertEqual(r['durationSummary']['unknownLengths'],23);self.assertTrue(any('unknown full lengths' in w for w in r['warnings']))
 def test_shortfall_and_spares_are_distinct(self):
  r=self.build('two hours of R&B',self.rows(10));self.assertEqual(len(r['songs']),10);self.assertEqual(r['durationSummary']['shortfallSeconds'],6150)
  r=self.build('two hours of R&B',self.rows(75));self.assertEqual(len(r['songs']),75);self.assertEqual(r['durationSummary']['shortfallSeconds'],0);self.assertTrue(any('fewer spare' in w for w in r['warnings']))
 def test_mixed_genres_and_eras_retain_duration(self):
  q=playlist_request.parse('45 minutes of 80s, 90s and country');self.assertEqual(q['targetDurationSeconds'],2700);self.assertTrue(q['anyOf'])
 def test_count_and_duration_conflict_never_silently_falls_back(self):
  for p in ['50 songs for two hours of R&B','two hours with 87 R&B songs','two hours of R&B and 50 songs','zero hours of country','a couple hours of country','25 hours of country','0 minutes of country']:
   with self.subTest(p=p),self.assertRaises(ValueError):playlist_request.parse(p)
 def test_only_final_selected_recordings_emit_events(self):
  rows=self.rows(100);events=[];q=playlist_request.parse('30 minutes of R&B');r=matching.attach(core.build(rows,q),rows,events.append)
  self.assertEqual([e.song['id'] for e in events if getattr(e,'song',None)],[x['id'] for x in r['songs']]);self.assertEqual(len({core.identity(x) for x in r['songs']}),23)
 def test_duration_timing_counts_selected_work_not_candidate_pool(self):
  rows=self.rows(300);events=[];q=playlist_request.parse('three hours of R&B');r=matching.attach(core.build(rows,q),rows,events.append)
  work=[e for e in events if getattr(e,'phase',None)=='recordings']
  self.assertEqual(work[0].total,129);self.assertFalse(work[0].eta_known)
  self.assertEqual(work[-1].completed,129);self.assertEqual(work[-1].total,129);self.assertTrue(work[-1].eta_known)
  self.assertTrue(all(e.total==129 for e in work));self.assertEqual(len(r['songs']),129)
 def test_duration_uses_preferred_recording_length(self):
  rows=self.rows(50,240)
  for row in list(rows):rows.append(dict(row,path=row['path'].replace('.mp3','-clean.mp3'),title=row['title']+' (Clean)',version='Clean',duration=60))
  q=playlist_request.parse('30 minutes of R&B');q['contentFilter']='prefer-clean';r=matching.attach(core.build(rows,q),rows)
  self.assertEqual(r['durationSummary']['baseSongCount'],30);self.assertEqual(len(r['songs']),38);self.assertTrue(all(x['duration']==60 for x in r['songs']))
 def test_version_refine_and_explicit_count_from_duration(self):
  rows=self.rows(100);r=self.build('30 minutes of R&B',rows);ids=[x['id'] for x in r['songs']]
  r=conversation.refine(r,rows,'no preference',ids,[]);self.assertEqual(r['request']['targetDurationSeconds'],1800)
  r=conversation.refine(r,rows,'make it 10',[x['id'] for x in r['songs']],[]);self.assertEqual(len(r['songs']),10);self.assertNotIn('targetDurationSeconds',r['request']);self.assertNotIn('durationSummary',r)
 def test_single_letter_artist_is_not_a_duration(self):
  rows=self.rows(2);rows[0]['artist']='M People'
  q=playlist_request.parse('2 songs by M People',rows);self.assertEqual(q['count'],2)
 def test_selection_plan_uses_real_short_track_target(self):
  rows=self.rows(100,60);events=[];q=playlist_request.parse('30 minutes of R&B');r=matching.attach(core.build(rows,q),rows,events.append)
  selected=[e for e in events if getattr(e,'song',None)];self.assertEqual(len(selected),38);self.assertEqual(selected[-1].selection_plan,{'target':38,'minimum':False});self.assertEqual(selected[0].selection_plan,{'target':23,'minimum':True})
if __name__=='__main__':unittest.main()
