import threading,unittest
from unittest.mock import patch
import app,core,matching,playlist_request
from task_progress import Update
from test_setlist import song

class SelectionEventsTests(unittest.TestCase):
    def test_only_resolved_selection_metadata_is_sent(self):
        tracks=[song(i,genre='Country',artist='Alan Jackson',title=f'Track {i}') for i in range(4)]
        events=[]
        request=playlist_request.parse('4 songs by Alan Jackson',tracks)
        result=matching.attach(core.build(tracks,request),tracks,events.append)
        selected=[e.song for e in events if getattr(e,'song',None)]
        self.assertEqual([s['id'] for s in selected],[s['id'] for s in result['songs']])
        self.assertTrue(all(set(s)=={'id','title','artist','source'} for s in selected))
    def test_bounded_status_and_cancellation(self):
        instance=app.App.__new__(app.App);instance.lock=threading.RLock();instance.cancel=threading.Event();instance.timing=None
        instance.task={'state':'running','id':'test','matches':[],'matchCount':0}
        for i in range(1000):instance.checkpoint(Update('Selected','recordings',i,1000,song={'id':str(i)}))
        self.assertEqual(instance.task['matchCount'],1000);self.assertEqual(len(instance.task['matches']),24)
        self.assertEqual(instance.task['matches'][0]['sequence'],977)
        instance.cancel.set()
        with self.assertRaises(app.Cancelled):instance.checkpoint(Update('Selected','recordings',1001,1001,song={'id':'cancelled'}))
        self.assertEqual(instance.task['matchCount'],1000)

    def test_candidate_activity_is_bounded_and_never_a_confirmed_match(self):
        instance=app.App.__new__(app.App);instance.lock=threading.RLock();instance.cancel=threading.Event();instance.timing=None
        instance.task={'state':'running','matches':[],'matchCount':0}
        for i in range(100):instance.checkpoint(Update('Ranking','rank',i,100,activity={'title':str(i),'artist':'Test'}))
        self.assertEqual(instance.task['matchCount'],0);self.assertEqual(instance.task['activityCount'],100);self.assertEqual(len(instance.task['activity']),24)
        self.assertEqual(instance.task['activity'][-1]['title'],'99')
