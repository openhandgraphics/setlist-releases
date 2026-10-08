import tempfile,unittest,copy
from pathlib import Path
from unittest.mock import patch
import app,virtualdj,dj_destination
import test_dj_export

class ExportFeedbackTests(unittest.TestCase):
    def test_ambiguous_then_confirm_export_and_retry(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)/'profile'):
            vdj,_,music,_,r=test_dj_export.DJExportTests().fixture(d);other=Path(d)/'Other'/'MyLists';other.mkdir(parents=True)
            a=app.App();a.result=r;a.root=d
            with patch.object(dj_destination,'candidates',return_value=[str(vdj),str(other)]):
                args=dict(ids=['1','2'],approved=True,software='virtualdj',destination=str(vdj))
                with self.assertRaisesRegex(ValueError,'More than one'):a.action('saveDJ',args)
                self.assertEqual(list(vdj.iterdir()),[])
                a.action('setDJDestination',{'path':str(vdj)})
                saved=a.action('saveDJ',args);again=a.action('saveDJ',args)
                self.assertEqual(saved,again);self.assertEqual(len(list(vdj.glob('*.vdjfolder'))),1)
                self.assertEqual(music.read_bytes(),b'unchanged audio and cues')

    def test_blank_name_failure_retry_and_missing_path(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)/'profile'):
            vdj,_,music,_,r=test_dj_export.DJExportTests().fixture(d);r['request']['name']=' :<>. '
            a=app.App();a.result=r;a.action('setDJDestination',{'path':str(vdj)})
            args=dict(ids=['1'],approved=True,software='virtualdj',destination=str(vdj))
            with patch.object(virtualdj.tempfile,'mkstemp',side_effect=PermissionError('Destination is read-only')):
                with self.assertRaises(PermissionError):a.action('saveDJ',args)
            self.assertNotIn('published',a.result);self.assertEqual(list(vdj.iterdir()),[])
            with self.assertRaisesRegex(ValueError,'at least one'):a.action('saveDJ',dict(args,ids=[]))
            saved=a.action('saveDJ',args);self.assertEqual(saved['name'],'My playlist - 1 songs')
            before=list(vdj.iterdir());music.unlink()
            with self.assertRaises(ValueError):a.action('saveDJ',args)
            self.assertEqual(list(vdj.iterdir()),before)

if __name__=='__main__':unittest.main()
