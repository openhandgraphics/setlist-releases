import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app
from test_setlist import song
class WorkingStateTests(unittest.TestCase):
 def test_selection_favorites_draft_reload_and_creation(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
   a=app.App();a.result={'songs':[song(i,id=str(i)) for i in range(3)],'request':{'name':'Working'}};a.persist()
   created=a.playlists[0]['created'];state=a.action('result',{});args={'revision':state['workingRevision'],'selectedIds':['0','2'],'lockedIds':['2'],'followupDraft':'keep these but add more 90s'}
   self.assertTrue(a.action('saveWorkingState',args));b=app.App();r=b.action('result',{})
   self.assertEqual(r['selectedIds'],['0','2']);self.assertEqual(r['lockedIds'],['2']);self.assertEqual(r['followupDraft'],args['followupDraft']);self.assertEqual(b.playlists[0]['created'],created)
 def test_stale_busy_invalid_states_never_mutate(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
   a=app.App();a.result={'songs':[song(1,id='0')],'request':{}};a.persist();before=copy.deepcopy(a.result)
   args={'revision':a.working_revision(),'selectedIds':['0'],'lockedIds':[],'followupDraft':''}
   for changed in [dict(args,revision='old'),dict(args,selectedIds=['missing']),dict(args,selectedIds='0'),dict(args,followupDraft='x'*2001)]:
    with self.assertRaises(ValueError):a.action('saveWorkingState',changed)
   a.task['state']='running'
   with self.assertRaises(ValueError):a.action('saveWorkingState',args)
   self.assertEqual(a.result,before)
if __name__=='__main__':unittest.main()
