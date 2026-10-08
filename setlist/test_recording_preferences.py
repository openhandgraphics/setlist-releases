import copy,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import app,content_rating,conversation,core,matching,playlist_request
from test_setlist import song


class RecordingPreferenceTests(unittest.TestCase):
    def test_clean_explicit_unknown_and_conflict(self):
        for version,rating in [('Clean','clean'),('Explicit - Dirty','explicit'),('','unknown'),('Clean - Warning Content','unknown'),('Clean Dirty','unknown')]:
            self.assertEqual(content_rating.classify(song(1,version=version))[0],rating)
        self.assertEqual(content_rating.classify(song(1,title='Clean',artist='Clean Bandit'))[0],'unknown')
        self.assertEqual(content_rating.classify(song(1,title='Song (Clean Edit)'))[0],'clean')

    def test_prefer_clean_before_plays_with_dirty_unknown_fallback(self):
        clean=song(1,version='Clean',plays=1,path='D:/clean.mp3')
        dirty=song(1,version='Dirty',plays=900,path='D:/dirty.mp4')
        for tracks,expected in [([dirty,clean],'D:/clean.mp3'),([dirty],'D:/dirty.mp4'),([song(1,path='D:/unknown.mp3')],'D:/unknown.mp3')]:
            result=core.build(tracks,{'style':'Bangers','contentFilter':'prefer-clean'})
            matching.attach(result,tracks)
            self.assertEqual(result['songs'][0]['path'],expected)
        self.assertEqual(matching.preferred(clean,[clean,dirty],'explicit-allowed')['path'],dirty['path'])

    def test_forbidden_formats_and_recognized_karaoke(self):
        for path in ('D:/a.wav','D:/a.flac','D:/a.zip','D:/a.cdg','D:/Karaoke/a.mp4'):
            self.assertFalse(matching.eligible_recording(song(1,path=path)))
        for row in (song(1,path='D:/a.mp4',version='Karaoke'),song(1,path='D:/a.mp3',title='Song (Karaoke Version)'),song(1,path='D:/a.mp4',genre='Karaoke'),song(1,path='D:/a.mp3',hasCdg=True)):
            self.assertFalse(matching.eligible_recording(row))
        self.assertTrue(matching.eligible_recording(song(1,path='D:/Music/Drake - Karaoke.MP3',artist='Drake',title='Karaoke',genre='R&B')))
        self.assertTrue(matching.eligible_recording(song(1,path='D:/a.MP4',title='Song (Lyrics)')))

    def test_clean_karaoke_or_wav_cannot_replace_dirty_mp3(self):
        dirty=song(1,version='Dirty',path='D:/real.mp3')
        tracks=[dirty,song(1,version='Clean Karaoke',plays=999,path='D:/bad.mp4'),song(1,version='Clean',plays=999,path='D:/bad.wav')]
        result=matching.attach({'songs':[dict(dirty,id='0')],'request':{'contentFilter':'prefer-clean'},'warnings':[]},tracks)
        self.assertEqual(result['songs'][0]['path'],dirty['path'])
        self.assertEqual(result['songs'][0]['contentRating'],'explicit')

    def test_app_build_followup_persistence_and_export_guard(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(app,'DATA',Path(folder)/'profile'):
            tracks=[]
            for i,(ext,version,plays) in enumerate([('.mp3','Clean',1),('.mp4','Dirty',50),('.mp4','Clean Karaoke',500),('.wav','Clean',1000)]):
                path=Path(folder)/f'{i}{ext}';path.write_bytes(b'test media')
                tracks.append(song(1,artist='Banda MS',genre='Banda',version=version,plays=plays,path=str(path)))
            a=app.App();a.tracks=tracks
            a.action('build',{'prompt':'banda','contentFilter':'prefer-clean'})
            self.wait(a);self.assertEqual(a.result['songs'][0]['path'],tracks[0]['path'])
            a.action('refine',{'message':'make it 10 songs','keepIds':['0'],'lockedIds':[]})
            self.wait(a);self.assertEqual(a.result['songs'][0]['path'],tracks[0]['path'])
            self.assertEqual(a.result['request']['contentFilter'],'prefer-clean')
            self.assertEqual(app.App().content_filter,'prefer-clean')
            a.action('setContentFilter',{'contentFilter':'explicit-allowed'})
            self.assertEqual(app.App().content_filter,'explicit-allowed')
            bad=dict(tracks[2],id='0');a.result={'songs':[bad],'request':{}}
            with patch('virtualdj.publish') as publish,self.assertRaisesRegex(ValueError,'MP3/MP4'):
                a.action('saveDJ',{'ids':['0'],'approved':True})
            publish.assert_not_called()
            self.assertFalse(matching.eligible_recording(song(2,path=str(Path(folder)/'missing.mp3')),require_file=True))

    def wait(self,a):
        deadline=time.monotonic()+10
        while a.task['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(a.task['state'],'done',a.task)


if __name__=='__main__':unittest.main()
