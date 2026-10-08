import unittest,copy
import core,matching,playlist_request,conversation,artist_style,name_matching
from test_setlist import song
class AccuracyTests(unittest.TestCase):
 def test_artist_typos_and_ambiguous_choices(self):
  self.assertEqual(playlist_request.parse('similar to Alan Jacson')['artistIntent']['seed'],'Alan Jackson')
  self.assertEqual(playlist_request.parse('by Cardi B')['artistIntent']['kind'],'by')
  with self.assertRaisesRegex(ValueError,'Did you mean'):playlist_request.parse('by Cardi V')
  rows=[song(1,artist='Anna Smith'),song(2,artist='Anne Smith')]
  with self.assertRaisesRegex(ValueError,'Did you mean.*Anna Smith.*Anne Smith'):playlist_request.parse('by Anni Smith',rows)
 def test_genre_typo_and_no_arbitrary_artist_guess(self):
  r=playlist_request.parse('50 counrty songs');self.assertEqual(r['style'],'Country');self.assertTrue(r['corrections'])
  with self.assertRaises(ValueError):playlist_request.parse('similar to Fictional Stranger')
 def test_recording_identity_preserves_meaningful_parentheses(self):
  self.assertNotEqual(core.identity(song(1,title='Home (Again)')),core.identity(song(1,title='Home')))
  self.assertEqual(core.identity(song(1,title='Home (Clean)')),core.identity(song(1,title='Home - Dirty')))
 def test_explicit_performance_request_and_studio_preference(self):
  studio=song(1,title='Home',plays=1);live=song(1,title='Home (Live)',version='Live',path='D:/live.mp3',plays=999)
  self.assertEqual(matching.preferred(studio,[live,studio])['path'],studio['path'])
  self.assertIsNone(matching.preferred(live,[studio]))
  self.assertEqual(matching.preferred(live,[studio,live])['path'],live['path'])
 def test_specific_local_evidence_outranks_play_count(self):
  rows=[song(i,artist='Local Seed',genre='Country Honky Tonk',year='1993') for i in range(3)]
  near=song(4,artist='Near Peer',genre='Country Honky Tonk',year='1992',plays=0)
  far=song(5,artist='Far Peer',genre='Country',year='2025',plays=900)
  p=artist_style.profile('Local Seed',rows)
  self.assertGreater(artist_style.rank(near,p)[0],artist_style.rank(far,p)[0])
 def test_count_and_additive_followups_preserve_paths(self):
  rows=[song(i,artist=f'Peer {i}',genre='Country',year='1994') for i in range(180)]
  r=matching.attach(core.build(rows,playlist_request.parse('50 country songs')),rows)
  ids=[x['id'] for x in r['songs']];paths={x['path'] for x in r['songs']}
  out=conversation.refine(r,rows,'make it 100',ids,[ids[0]])
  self.assertTrue(paths<={x['path'] for x in out['songs']});self.assertEqual(len(out['lockedIds']),1)
  out=conversation.refine(out,rows,'make it 75',[x['id'] for x in out['songs']],out['lockedIds']);self.assertEqual(len(out['songs']),75)
  out=conversation.refine(out,rows,'keep these but add more 90s',[x['id'] for x in out['songs']],out['lockedIds']);self.assertEqual(len(out['songs']),100)
  self.assertTrue(paths<={x['path'] for x in out['songs']})
 def test_unknown_content_stays_unknown_and_neutral_uses_plays(self):
  a=song(1,version='Clean',plays=1);b=song(1,version='',plays=9,path='D:/unknown.mp4')
  self.assertEqual(matching.preferred(a,[a,b],None)['path'],b['path'])
  self.assertEqual(matching.content_rating.classify(b)[0],'unknown')
if __name__=='__main__':unittest.main()
