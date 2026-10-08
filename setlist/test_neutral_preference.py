import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import app,content_rating,matching
from test_setlist import song


class NeutralPreferenceTests(unittest.TestCase):
    def test_neutral_ranks_all_labels_by_plays_including_naturally_all_clean(self):
        rows=[song(1,version='Clean',plays=1,path='clean.mp3'),song(1,version='Dirty',plays=2,path='dirty.mp3'),song(1,version='',plays=3,path='unknown.mp3')]
        for winner in reversed(rows):
            self.assertEqual(matching.preferred(rows[0],rows,None)['path'],winner['path'])
            self.assertEqual(matching.preferred(rows[0],rows,'explicit-allowed')['path'],winner['path'])
            rows.remove(winner)

    def test_unset_build_is_allowed_without_hidden_clean_preference(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(app,'DATA',Path(folder)/'settings'):
            clean=Path(folder)/'clean.mp3';dirty=Path(folder)/'dirty.mp3'
            clean.write_bytes(b'media');dirty.write_bytes(b'media')
            a=app.App();self.assertIsNone(a.content_filter)
            a.tracks=[song(1,genre='Banda',version='Clean',plays=1,path=str(clean)),song(1,genre='Banda',version='Dirty',plays=100,path=str(dirty))]
            a.action('setContentFilter',{'contentFilter':'prefer-clean'})
            # A new API request with no choice must not inherit an older draft choice.
            a.action('build',{'prompt':'banda'})
            self.wait(a)
            self.assertIsNone(a.result['request']['contentFilter'])
            self.assertEqual(a.result['songs'][0]['path'],str(dirty))
            a.action('refine',{'message':'prefer clean','keepIds':['0'],'lockedIds':[]})
            self.wait(a);self.assertEqual(a.result['songs'][0]['path'],str(clean))
            a.action('refine',{'message':'make it 5 songs','keepIds':['0'],'lockedIds':[]})
            self.wait(a);self.assertEqual(a.result['request']['contentFilter'],'prefer-clean')
            a.action('refine',{'message':'no preference','keepIds':['0'],'lockedIds':[]})
            self.wait(a);self.assertIsNone(a.result['request']['contentFilter']);self.assertEqual(a.result['songs'][0]['path'],str(dirty))
            a.action('setContentFilter',{'contentFilter':'explicit-allowed'})
            previous=a.result
            a.action('clearEntry',{'inputTab':'description'})
            self.assertIsNone(a.content_filter);self.assertIs(a.result,previous)
            self.assertIsNone(app.App().content_filter)

    def test_legacy_missing_choice_stays_neutral_and_explicit_choice_survives(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(app,'DATA',Path(folder)):
            file=Path(folder)/'session.json'
            file.write_text(json.dumps({'root':folder,'result':None}))
            self.assertIsNone(app.App().content_filter)
            file.write_text(json.dumps({'root':folder,'result':None,'contentFilter':'explicit-allowed'}))
            self.assertEqual(app.App().content_filter,'explicit-allowed')
        self.assertIsNone(content_rating.validate(None))

    def wait(self,a):
        deadline=time.monotonic()+10
        while a.task['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(a.task['state'],'done',a.task)


if __name__=='__main__':unittest.main()
