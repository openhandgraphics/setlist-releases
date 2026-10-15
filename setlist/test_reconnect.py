import unittest,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
import app
class ReconnectTests(unittest.TestCase):
 def test_saved_library_reconnects_before_import(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
   Path(d,'session.json').write_text(json.dumps({'root':d}),encoding='utf-8')
   state=app.App()
   row=dict(artist='ABBA',title='Dancing Queen',path=str(Path(d,'song.mp3')),source='library',version='')
   Path(row['path']).write_bytes(b'test media')
   with patch.object(app.core,'scan',return_value=([row],[],[])) as scan:
    state.action('importList',{'text':'ABBA - Dancing Queen','order':'artist-title'})
    for _ in range(100):
     if state.task['state']!='running':break
     time.sleep(.01)
    self.assertEqual(state.task['state'],'done',state.task)
    self.assertEqual(state.result['songs'][0]['source'],'library')
    scan.assert_called_once()
 def test_empty_reconnect_has_actionable_error(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
   state=app.App();state.root=d
   with patch.object(app.core,'scan',return_value=([],[],[])):
    with self.assertRaisesRegex(ValueError,'No labeled songs'):state.ensure_library()
if __name__=='__main__':unittest.main()
