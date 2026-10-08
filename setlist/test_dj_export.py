import tempfile,unittest,struct
from pathlib import Path
from unittest.mock import patch
import app,dj_destination,serato_export

class DJExportTests(unittest.TestCase):
    def fixture(self,d):
        root=Path(d);vdj=root/'VirtualDJ'/'MyLists';vdj.mkdir(parents=True)
        serato=root/'_Serato_'/'Subcrates';serato.mkdir(parents=True)
        music=root/'Beyoncé.mp3';music.write_bytes(b'unchanged audio and cues')
        existing=serato/'Old.crate';existing.write_bytes(b'old crate')
        result={'request':{'name':'My Party'},'songs':[dict(id='1',artist='Beyoncé',title='Song',path=str(music),source='library'),dict(id='2',artist='Missing',title='Song',path='',source='suggestion')]}
        return vdj,serato,music,existing,result

    def test_serato_records_order_unicode_missing_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            vdj,serato,music,old,r=self.fixture(d)
            r['songs'].append(dict(r['songs'][0],id='3'))
            first=serato_export.publish(r,['1','2','3'],d,serato)
            second=serato_export.publish(r,['1','2','3'],d,serato)
            self.assertNotEqual(first['path'],second['path'])
            data=Path(first['path']).read_bytes()
            self.assertEqual(data[:4],b'vrsn')
            size=struct.unpack('>I',data[4:8])[0]
            self.assertEqual(data[8:8+size].decode('utf-16-be'),'1.0/Serato ScratchLive Crate')
            self.assertEqual(serato_export.read_paths(data),[music.relative_to(music.anchor).as_posix()]*2)
            self.assertIn('Missing - Song',Path(first['missingReport']).read_text())
            self.assertEqual(music.read_bytes(),b'unchanged audio and cues');self.assertEqual(old.read_bytes(),b'old crate')
            self.assertFalse(list(serato.glob('*.tmp')))

    def test_missing_only_and_disconnected_tracks_write_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            vdj,serato,music,old,r=self.fixture(d)
            with self.assertRaises(ValueError):serato_export.publish(r,['2'],d,serato)
            music.unlink()
            with self.assertRaises(ValueError):serato_export.publish(r,['1'],d,serato)
            self.assertEqual(list(serato.iterdir()),[old])

    def test_saved_destination_and_software_survive_restart(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)/'settings'):
            vdj,serato,*_=self.fixture(d);a=app.App()
            a.action('setDJDestination',{'software':'virtualdj','path':str(vdj)})
            a.action('setDJDestination',{'software':'serato','path':str(serato)})
            b=app.App();self.assertEqual(b.dj_software,'serato')
            self.assertEqual(b.action('djDestination',{})['path'],str(serato.resolve()))
            b.action('setDJDestination',{'software':'virtualdj'})
            self.assertEqual(b.action('djDestination',{})['path'],str(vdj.resolve()))
            with patch.object(dj_destination,'candidates',return_value=[]):
                b.action('setDJDestination',{'automatic':True})
                self.assertFalse(b.action('djDestination',{})['available'])

    def test_invalid_folder_and_missing_saved_path_do_not_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):dj_destination.validate('serato',d)
            with self.assertRaises(ValueError):dj_destination.validate('virtualdj',d)
            with patch.object(dj_destination,'candidates',return_value=[d]):
                info=dj_destination.info('virtualdj',d,{'virtualdj':str(Path(d)/'gone'/'MyLists')})
                self.assertFalse(info['available']);self.assertTrue(info['manual'])

    def test_export_to_both_and_changed_destination_not_suppressed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)/'settings'):
            vdj,serato,music,old,r=self.fixture(d);a=app.App();a.result=r;a.root=d
            for software,path in [('virtualdj',vdj),('serato',serato)]:
                a.action('setDJDestination',{'software':software,'path':str(path)})
                args=dict(ids=['1','2'],approved=True,software=software,destination=str(path.resolve()))
                first=a.action('saveDJ',args);second=a.action('saveDJ',args)
                self.assertEqual(first['path'],second['path']);self.assertEqual(first['software'],software)
            with self.assertRaisesRegex(ValueError,'destination changed'):
                a.action('saveDJ',dict(args,destination=d))

    def test_ambiguous_detection_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)/'settings'):
            vdj,serato,music,old,r=self.fixture(d);a=app.App();a.result=r
            with patch.object(dj_destination,'candidates',return_value=[str(vdj),str(vdj)]):
                with self.assertRaisesRegex(ValueError,'More than one'):
                    a.action('saveDJ',{'ids':['1'],'approved':True})

if __name__=='__main__':unittest.main()
