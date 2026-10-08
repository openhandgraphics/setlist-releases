import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app,playlist_history
from test_playlist_history import result
class TimestampTests(unittest.TestCase):
 def test_creation_survives_edit_reload_and_publication(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
   a=app.App();a.result=result('New');a.persist();first=a.action('playlistHistory',{})[0]['created'];self.assertIsNotNone(first)
   a.result['songs'][0]['title']='Edited';a.persist();a.result['published']={'ids':['0'],'software':'virtualdj'};a.persist()
   b=app.App();self.assertEqual(b.action('playlistHistory',{})[0]['created'],first)
 def test_legacy_missing_creation_is_never_invented(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
   Path(d,'session.json').write_text(json.dumps({'result':result('Old')}))
   a=app.App();self.assertIsNone(a.action('playlistHistory',{})[0]['created']);a.result['songs'][0]['title']='Edited';a.persist()
   self.assertIsNone(app.App().action('playlistHistory',{})[0]['created'])
 def test_existing_missing_field_is_safe_and_existing_timestamp_unchanged(self):
  items=[{'id':'saved','updated':'2026-01-01T01:00:00-06:00','result':dict(result('Old'),historyId='saved'),'deleted':False}]
  self.assertIsNone(playlist_history.summary(items[0])['created']);edited=copy.deepcopy(items[0]['result']);edited['request']['name']='Edited';playlist_history.remember(items,edited);self.assertNotIn('created',items[0])
if __name__=='__main__':unittest.main()
