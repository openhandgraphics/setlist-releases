import unittest
import playlist_request,core,matching
from test_setlist import song
class OccasionTests(unittest.TestCase):
 def test_exact_sweet_sixteen_duration(self):
  for t in ['three hours of music for a sweet 16','three hours of sweet 16 songs','3 hours for a sweet-sixteen','three hours for a sweeet 16']:
   q=playlist_request.parse(t);self.assertEqual(q['targetDurationSeconds'],10800);self.assertIsNone(q['count']);self.assertEqual(q['occasion']['name'],'Sweet 16');self.assertTrue(q['occasion']['usedDefault'])
 def test_occasions_and_conservative_spelling(self):
  names={'quinceañera':'Quinceañera','quincenera':'Quinceañera','50th birthday':'Birthday','fiftieth birthday':'Birthday','birhtday':'Birthday','wedding reception':'Wedding','weddding':'Wedding','graduation':'Graduation','school dance':'School dance','prom':'School dance','25th anniversary':'Anniversary','Christmas party':'Holiday party','Halloween party':'Holiday party','corporate party':'Corporate party','house party':'House party','galactic wizard bash':'General party'}
  for text,name in names.items():
   with self.subTest(text=text):
    q=playlist_request.parse('20 songs for a '+text);self.assertEqual(q['count'],20);self.assertEqual(q['occasion']['name'],name);self.assertTrue(q['occasion']['usedDefault']);self.assertNotIn('contentFilter',q)
 def test_ages_and_dates_are_not_counts_or_eras(self):
  for text in ['music for a 50th birthday','music for a sweet 16','music for a quinceañera','music for a quince 15','music for a graduation class of 2026','music for a birthday on 2026-10-08','music for a birthday for a 50 year old']:
   q=playlist_request.parse(text);self.assertEqual(q['count'],50);self.assertFalse(q['yearRanges']);self.assertNotIn('targetDurationSeconds',q)
 def test_explicit_genres_eras_and_artists_override(self):
  for text,styles in [('20 country songs for a wedding',['Country']),('20 R&B songs for a sweet 16',['R&B']),('20 songs from the 90s for a 50th birthday',['Era']),('20 songs from 1998 for a quinceañera',['Era'])]:
   q=playlist_request.parse(text);self.assertEqual(q['styles'],styles);self.assertFalse(q['occasion']['usedDefault']);self.assertEqual(q['count'],20)
  q=playlist_request.parse('20 songs by Alan Jackson for a sweet 16');self.assertEqual(q['artistIntent']['kind'],'by');self.assertFalse(q['occasion']['usedDefault'])
 def test_exact_release_year_and_milestone_separate(self):
  q=playlist_request.parse('20 songs from 1998 for a 50th birthday');self.assertEqual(q['yearRanges'],[[1998,1998]]);self.assertEqual(q['count'],20)
 def test_unrecognized_nonoccasion_still_clarifies(self):
  with self.assertRaises(ValueError):playlist_request.parse('purple umbrellas')
 def test_general_default_is_marked_and_not_ethnic(self):
  birthday=playlist_request.parse('music for a birthday');quince=playlist_request.parse('music for a quinceañera');self.assertEqual(birthday['styles'],quince['styles']);self.assertIn('starting point',quince['occasionNote']);self.assertNotIn('Norteño',quince['styles'])
 def test_neutral_and_requested_recording_preference_survive(self):
  tracks=[song(i,genre='Pop') for i in range(30)]
  for setting in [None,'prefer-clean','explicit-allowed']:
   q=playlist_request.parse('20 songs for a sweet 16',tracks);q['contentFilter']=setting;r=matching.attach(core.build(tracks,q),tracks);self.assertEqual(r['request']['contentFilter'],setting)
if __name__=='__main__':unittest.main()
