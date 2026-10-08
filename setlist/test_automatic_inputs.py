import unittest
import matching,import_list,photo_text

def song(path,plays=0,artist='ABBA',title='Dancing Queen',version=''):
 return dict(path=path,plays=plays,artist=artist,title=title,version=version,source='library')
class AutomaticSelectionTests(unittest.TestCase):
 def test_highest_count_excludes_versions_and_folder(self):
  tracks=[song('one.mp3',1),song('two.mp4',15),song('three.mp3',300,version='Remix'),song('KARAOKE/four.mp4',400),song('five.mp3',20)]
  result=import_list.build(import_list.parse_text('ABBA - Dancing Queen'),tracks)
  self.assertEqual(result['songs'][0]['path'],'five.mp3')
  self.assertIn('20 plays',result['songs'][0]['reason'])
 def test_popularity_cannot_change_artist_or_title(self):
  tracks=[song('wrong.mp3',1000,artist='Someone Else'),song('typo.mp3',900,title='Dancing Quean'),song('right.mp3',1)]
  self.assertEqual(matching.preferred(song('',0),tracks)['path'],'right.mp3')
 def test_zero_counts_tie_stable(self):
  tracks=[song('z.mp3'),song('a.mp3')]
  self.assertEqual(matching.preferred(song(''),tracks)['path'],'a.mp3')
 def test_lyric_channel_is_allowed_and_featured_artists_match(self):
  request=song('',artist='Usher',title='Yeah!')
  row=song('video.mp4',8,artist='Usher feat. Lil Jon Ludacris',title='Yeah!',version='Lyrics - 7clouds')
  self.assertEqual(matching.preferred(request,[row]),row)
class PhotoTextTests(unittest.TestCase):
 def test_reported_split_lines(self):
  raw='2\n3\n4\n5\n6\n7\n8\n9\n12\nHead Over Boots\nMusic video • Jon Pardi\nLas Miradas\nGary Hobbs\nCheck Yes Or No\nMusic video • George Strait\nTe Vez Buena'
  tracks=[song('a',artist='Gary Hobbs',title='Las Miradas')]
  r=photo_text.normalize(raw,tracks)
  self.assertEqual(r['count'],4)
  self.assertEqual(r['text'].splitlines()[:3],['Jon Pardi - Head Over Boots','Gary Hobbs - Las Miradas','George Strait - Check Yes Or No'])
  self.assertEqual(r['uncertain'],['Te Vez Buena'])
 def test_unknown_lines_not_arbitrarily_paired(self):
  r=photo_text.normalize('Hello\nGoodbye')
  self.assertEqual(r['uncertain'],['Hello','Goodbye'])
 def test_existing_pairs_repeats_and_numeric_song(self):
  r=photo_text.normalize('1. ABBA - Dancing Queen\n2. ABBA - Dancing Queen\n1999\nMusic video • Prince')
  self.assertEqual(r['count'],3)
  self.assertEqual(r['text'].splitlines()[-1],'Prince - 1999')
if __name__=='__main__':unittest.main()
