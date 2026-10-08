import copy,unittest
from unittest.mock import patch
import core,matching,playlist_request,artist_style,conversation
from test_setlist import song

class ArtistStyleTests(unittest.TestCase):
    def fixture(self,genre,seed):
        return [song(i,artist=seed if i<10 else f'Peer {i%12}',title=f'Track {i}',genre=genre,year='1993',path=f'D:/test/{i}.mp3') for i in range(100)]
    def build(self,prompt,rows):
        request=playlist_request.parse(prompt,rows);request['mode']='discovery';request['contentFilter']=None
        return matching.attach(core.build(rows,request,fetch=lambda q:self.fail('Network request')),rows)
    def test_all_five_phrases_count_variety_and_local_only(self):
        for seed,genre in [('Cardi B','Hip-Hop/Rap'),('Alan Jackson','Country')]:
            rows=self.fixture(genre,seed)+[song(900,artist='Unrelated',genre='Classical')]
            for phrase in ['in the genre of','same genre as','in the style of','same style as','similar to']:
                with self.subTest(seed=seed,phrase=phrase):
                    result=self.build(f'Please give me 50 songs {phrase} {seed}',rows)
                    self.assertEqual(len(result['songs']),50);self.assertEqual(result['request']['mode'],'library')
                    self.assertGreater(len({r['artist'] for r in result['songs']}),5)
                    self.assertNotIn('Unrelated',{r['artist'] for r in result['songs']})
                    self.assertTrue(all(a['artist']!=b['artist'] for a,b in zip(result['songs'],result['songs'][1:])))
    def test_by_artist_and_collaborations_do_not_leak_peers(self):
        rows=self.fixture('Country','Alan Jackson')
        rows.append(song(999,artist='Alan Jackson feat. Friend',genre='Country'))
        for phrase in ['50 songs by Alan Jackson','50 by Alan Jackson']:
            r=self.build(phrase,rows);self.assertEqual(len(r['songs']),11)
            self.assertTrue(all(artist_style.is_artist(x,'Alan Jackson') for x in r['songs']))
            self.assertTrue(any('Found 11' in w for w in r['warnings']))
    def test_seed_absent_known_presets_and_unknowns(self):
        rows=self.fixture('Country','Peer Artist')
        r=self.build('50 songs similar to Alan Jackson',rows);self.assertEqual(len(r['songs']),50)
        self.assertIn('preset',r['method'])
        for text in ['50 songs similar to Made Up Unknown','50 songs by Made Up Unknown']:
            with self.assertRaisesRegex(ValueError,'not recognized'):self.build(text,rows)
    def test_metadata_supports_artist_outside_presets_and_rejects_sparse_tags(self):
        rows=self.fixture('Shoegaze','New Local Artist')
        r=self.build('50 songs same style as New Local Artist',rows)
        self.assertEqual(len(r['songs']),50);self.assertIn('Shared shoegaze',r['method'])
        for row in rows:row['genre']='Top 40'
        with self.assertRaisesRegex(ValueError,'Not enough consistent'):self.build('similar to New Local Artist',rows)
    def test_shortfall_does_not_fill_with_unrelated_music(self):
        rows=[song(i,artist='Alan Jackson',genre='Country') for i in range(2)]+[song(99,artist='Other',genre='Classical')]
        r=self.build('50 songs similar to Alan Jackson',rows)
        self.assertEqual(len(r['songs']),2);self.assertTrue(any('No other eligible artists' in w for w in r['warnings']))
    def test_media_karaoke_and_neutral_recording_versions(self):
        rows=self.fixture('Country','Alan Jackson')
        for suffix,version in [('.wav',''),('.mp4','Karaoke'),('.mp3','Instrumental')]:
            rows.append(song(800,artist='Bad Match',genre='Country',path='D:/bad'+suffix,version=version))
        clean=song(1001,artist='Peer 1',genre='Country',version='Clean',plays=1,path='D:/clean.mp3')
        dirty=dict(clean,version='Dirty',plays=100,path='D:/dirty.mp3');rows.extend([clean,dirty])
        r=self.build('100 songs in the style of Alan Jackson',rows)
        self.assertNotIn('Bad Match',{x['artist'] for x in r['songs']})
        self.assertEqual(next(x for x in r['songs'] if x['title']==clean['title'])['path'],'D:/dirty.mp3')
        request=playlist_request.parse('100 songs similar to Alan Jackson',rows);request['contentFilter']='prefer-clean'
        r=matching.attach(core.build(rows,request),rows)
        self.assertEqual(next(x for x in r['songs'] if x['title']==clean['title'])['path'],'D:/clean.mp3')
    def test_natural_filler_band_name_and_unsupported_extra_words(self):
        for text in ['50 songs in the style of say Alan Jackson please','50 songs same genre as Alan Jackson or something like that','similar to Brooks & Dunn']:
            self.assertEqual(playlist_request.parse(text)['artistIntent']['kind'],'similar')
        with self.assertRaises(ValueError):playlist_request.parse('similar to Alan Jackson and also jazz')
    def test_sequence_avoids_repeat_when_feasible(self):
        rows=[song(i,artist='A') for i in range(4)]+[song(i,artist=a) for i,a in enumerate(['B','C','D'],20)]
        rows=artist_style.sequence(rows)
        self.assertTrue(all(a['artist']!=b['artist'] for a,b in zip(rows,rows[1:])))

class ConversationalCorrectionTests(unittest.TestCase):
    def test_exact_spoken_correction_and_union(self):
        text="I want a playlist of 80s, maybe some 90s, and put some country in there as well. Make it 50 songs, or, you know what, 100 songs."
        r=playlist_request.parse(text);self.assertEqual(r['count'],100);self.assertFalse(r['yearRanges']);self.assertTrue(r['anyOf'])
        rows=[song(1,genre='Country',year='2020'),song(2,genre='Pop',year='1984'),song(3,genre='Rock',year='1994'),song(4,genre='Classical',year='2020')]
        self.assertEqual(len(core.build(rows,r)['songs']),3)
    def test_explicit_restrictions_and_last_count(self):
        for text in ['50 country songs from the 80s, actually 100 songs','50 songs in the style of Alan Jackson, actually 100 songs']:
            self.assertEqual(playlist_request.parse(text)['count'],100)
        self.assertEqual(playlist_request.parse('country from the 80s and 90s')['anyOf'],[])
        self.assertEqual(playlist_request.parse('80s rock only')['anyOf'],[])
        self.assertEqual(playlist_request.parse('50 songs of 80s, 90s and country, actually 100 songs')['count'],100)
        self.assertTrue(playlist_request.parse('50 songs of 80s, 90s and country, actually 100 songs')['anyOf'])
        with self.assertRaises(ValueError):playlist_request.parse('50 country songs, actually 1001 songs')
    def test_followup_count_instead_preserves_artist_context(self):
        rows=ArtistStyleTests().fixture('Country','Alan Jackson');r=core.build(rows,playlist_request.parse('100 songs similar to Alan Jackson',rows))
        out=conversation.refine(r,rows,'make it 50 instead',[x['id'] for x in r['songs']],[])
        self.assertEqual(len(out['songs']),50);self.assertEqual(out['request']['artistIntent']['seed'],'Alan Jackson')
        with self.assertRaisesRegex(ValueError,'artist genre profile'):conversation.refine(r,rows,'less country',[x['id'] for x in r['songs']],[])

if __name__=='__main__':unittest.main()
