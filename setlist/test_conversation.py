import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import app,conversation,core,playlist_request
from test_setlist import song


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tracks=[]
        for i in range(100):
            self.tracks.append(song(i,artist=f'Banda Artist {i}',genre='Banda',year='2020',path=f'D:/Banda/{i}.mp3',bpm=80+i))
            self.tracks.append(song(i+100,artist=f'Throwback Artist {i}',genre='Throwback',year='2000',path=f'D:/Throwbacks/{i}.mp3',bpm=80+i))
            self.tracks.append(song(i+200,artist=f'Retro Artist {i}',genre='Rock',year='1984',path=f'D:/Rock/{i}.mp3',bpm=80+i))
        self.result=core.build(self.tracks,playlist_request.parse('banda, throwbacks and 80s',self.tracks))
        self.result['historyId']='test'

    def refine(self,message,result=None,keep=None,locks=None):
        previous=result or self.result
        return conversation.refine(previous,self.tracks,message,keep if keep is not None else [r['id'] for r in previous['songs']],locks or [])

    def test_more_less_and_context(self):
        more=self.refine('Can you give me more banda')
        self.assertGreater(sum(r['genre']=='Banda' for r in more['songs']),sum(r['genre']=='Banda' for r in self.result['songs']))
        less=self.refine('less 80s',more)
        self.assertLess(sum(r['year']=='1984' for r in less['songs']),sum(r['year']=='1984' for r in more['songs']))
        self.assertEqual(len(less['conversation']),2)
        self.assertEqual(less['historyId'],'test')
        self.assertEqual(len(less['songs']),50)

    def test_protected_and_unchecked_survive_reindex_and_followups(self):
        keep=[r['id'] for r in self.result['songs']][1:]
        excluded=core.identity(self.result['songs'][0]);pinned=core.identity(self.result['songs'][1])
        result=self.refine('more banda',keep=keep,locks=[keep[0]])
        result=self.refine('make it 60 songs',result,locks=result['lockedIds'])
        self.assertIn(pinned,[core.identity(r) for r in result['songs']])
        self.assertNotIn(excluded,[core.identity(r) for r in result['songs']])
        self.assertEqual(len(result['lockedIds']),1)
        self.assertEqual(len(result['songs']),60)

    def test_keep_these_songs_tempo_and_unknown_bpm(self):
        self.result['songs'][0]['bpm']=0
        result=self.refine('keep these songs but more upbeat')
        self.assertEqual({core.identity(r) for r in result['songs']},{core.identity(r) for r in self.result['songs']})
        self.assertEqual(len(result['lockedIds']),50)
        self.assertEqual(result['songs'][-1]['bpm'],0)
        self.assertIn('does not reliably',result['conversation'][-1]['reply'])
        for r in self.result['songs']:r['bpm']=0
        with self.assertRaisesRegex(ValueError,'known BPM'):self.refine('more upbeat')

    def test_explicit_era_constraint_is_preserved(self):
        result=core.build(self.tracks,playlist_request.parse('rock from the 80s'))
        changed=self.refine('more rock',result)
        self.assertTrue(all(r['year']=='1984' for r in changed['songs']))
        again=self.refine('less rock',changed)
        self.assertTrue(all(r['year']=='1984' for r in again['songs']))

    def test_unsupported_and_conflicting_requests_do_not_mutate(self):
        before=copy.deepcopy(self.result)
        for message in ['play the good ones','more banda but make it clean','less jazz','make it 0 songs','remove every bad song']:
            with self.subTest(message=message),self.assertRaises(ValueError):self.refine(message)
        with self.assertRaisesRegex(ValueError,'kept during changes'):
            self.refine('make it 5 songs',locks=[r['id'] for r in self.result['songs'][:6]])
        self.assertEqual(self.result,before)
        with self.assertRaisesRegex(ValueError,'Every song'):
            self.refine('more banda',locks=[r['id'] for r in self.result['songs']])

    def test_empty_category_exclusions_and_no_network(self):
        with patch('core.catalog',side_effect=AssertionError('No external calls')):
            result=self.refine('add Tejano')
        self.assertEqual(len(result['songs']),50)
        self.assertTrue(any('No local matches for Tejano' in w for w in result['warnings']))

    def test_api_undo_restores_order_selections_and_no_export(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(app,'DATA',Path(folder)):
            for i,row in enumerate(self.tracks):
                path=Path(folder)/f'{i}.mp3';path.write_bytes(b'test media');row['path']=str(path)
            self.result=core.build(self.tracks,playlist_request.parse('banda, throwbacks and 80s',self.tracks))
            self.result['historyId']='test'
            api=app.App();api.tracks=self.tracks;api.result=copy.deepcopy(self.result)
            keep=[r['id'] for r in api.result['songs']][2:]
            with patch('virtualdj.publish') as publish:
                api.action('refine',{'message':'more banda','keepIds':keep,'lockedIds':[keep[0]]})
                deadline=time.monotonic()+10
                while api.task['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
                self.assertEqual(api.task['state'],'done')
                self.assertTrue(api.action('result',{})['canUndo'])
                result=api.action('undoRefinement',{})
                self.assertEqual(result['songs'],self.result['songs'])
                self.assertEqual(result['selectedIds'],keep)
                self.assertEqual(result['lockedIds'],[keep[0]])
                self.assertFalse(result['canUndo'])
                publish.assert_not_called()


if __name__=='__main__':unittest.main()
