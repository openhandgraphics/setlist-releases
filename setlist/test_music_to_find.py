import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import app
import core
import music_to_find as find


class ChecklistTests(unittest.TestCase):
    def test_create_preserves_duplicates_original_order_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            store=find.Store(directory)
            text='1. 10-90 - Muscadine Bloodline\n2. Biblical - Calum Scott\n3. Biblical - Calum Scott'
            created=store.create('Songs to find',text,'title-artist')
            self.assertEqual([r['number'] for r in created['entries']],[1,2,3])
            self.assertEqual([r['original'] for r in created['entries']],text.splitlines())
            self.assertEqual([r['title'] for r in created['entries']],['10-90','Biblical','Biblical'])
            self.assertEqual(find.Store(directory).get(created['id']),created)
            self.assertEqual(len(list(Path(directory).iterdir())),1)

    def test_corrupt_store_and_failed_write_do_not_replace_existing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            store=find.Store(directory);store.path.write_text('{broken')
            with self.assertRaises(ValueError):store.create('test','Song - Artist','title-artist')
            self.assertEqual(store.path.read_text(),'{broken')
            store.path.unlink();store.create('first','Song - Artist','title-artist')
            before=store.path.read_bytes()
            with patch.object(Path,'replace',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):store.create('second','Next - Artist','title-artist')
            self.assertEqual(store.path.read_bytes(),before)
            self.assertEqual(list(Path(directory).glob('*.tmp')),[])

    def test_statuses_are_conservative_and_preferences_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def track(title,**extra):
                path=root/(title+'.mp3');path.write_bytes(b'unchanged synthetic recording')
                return dict(title=title,artist='Artist',path=str(path),version='',**extra)
            tracks=[track('Found'),track('Filename',labelSource='filename'),track('Special')]
            entries=[dict(number=i,artist='Artist',title=title,original=title,status='Needs checking',note='',matches=[])
                     for i,title in enumerate(['Found','Filename','Special','Missing','Missing'],1)]
            entries[2]['preference']='Radio Edit preferred'
            original=copy.deepcopy(entries)
            result=find.check_entries(entries,tracks,False)
            self.assertEqual([r['status'] for r in result],['Have','Needs checking','Needs checking','Not found','Not found'])
            self.assertEqual(entries,original)
            self.assertEqual(result[2]['preference'],'Radio Edit preferred')
            self.assertEqual([r['number'] for r in result],[1,2,3,4,5])
            self.assertEqual(find.check_entries(entries,tracks,True)[3]['status'],'Needs checking')
            Path(tracks[0]['path']).unlink()
            self.assertNotEqual(find.check_entries(entries,tracks,False)[0]['status'],'Have')

    def test_recheck_only_writes_checklist_and_keeps_concurrent_created_list(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(app,'DATA',Path(directory)):
            instance=app.App();instance.root=directory
            instance.result={'songs':[{'id':'playing','artist':'Artist','title':'Current'}], 'request':{'name':'Current set'}}
            original_result=copy.deepcopy(instance.result)
            session=Path(directory)/'session.json';session.write_bytes(b'untouched saved playlist and preferences')
            playlist=Path(directory)/'Existing.vdjfolder';playlist.write_bytes(b'existing playlist')
            item=instance.action('createMusicToFind',dict(name='First',text='Song - Artist',order='title-artist'))
            gate=threading.Event();entered=threading.Event()
            def scan(*args,**kwargs):
                self.assertEqual(kwargs,{'include_playlists':False});entered.set();gate.wait(3)
                return [],[],[]
            with patch.object(core,'scan',side_effect=scan):
                instance.action('recheckMusicToFind',{'id':item['id']});self.assertTrue(entered.wait(3))
                instance.action('createMusicToFind',dict(name='Second',text='Other - Artist',order='title-artist'))
                gate.set();self.wait(instance.music_to_find)
            saved=instance.action('musicToFind',{})
            self.assertEqual(saved['job']['state'],'done')
            self.assertEqual(len(saved['lists']),2)
            self.assertEqual(saved['lists'][0]['entries'][0]['status'],'Not found')
            self.assertEqual(instance.result,original_result)
            self.assertEqual(session.read_bytes(),b'untouched saved playlist and preferences')
            self.assertEqual(playlist.read_bytes(),b'existing playlist')
            self.assertEqual(instance.task['state'],'idle')

    def test_cancel_or_failed_scan_keeps_last_verified_results(self):
        with tempfile.TemporaryDirectory() as directory:
            service=find.Service(directory);item=service.store.create('List','Song - Artist','title-artist')
            before=service.store.path.read_bytes()
            def cancel(root,checkpoint,**kwargs):
                service.stop();checkpoint('Stopping')
            for scan,state in [(cancel,'stopped'),(OSError('drive unavailable'),'error')]:
                with patch.object(core,'scan',side_effect=scan):service.start(item['id'],directory);self.wait(service)
                self.assertEqual(service.info()['job']['state'],state)
                self.assertEqual(service.store.path.read_bytes(),before)

    def test_checklist_scan_skips_playlist_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'Artist - Song.mp3').write_bytes(b'synthetic media')
            (root/'database.xml').write_text('<VirtualDJ_Database/>')
            lists=root/'MyLists';lists.mkdir();(lists/'Unread.vdjfolder').write_text('not xml')
            with patch.object(Path,'rglob',side_effect=AssertionError('must not enumerate playlists')):
                tracks,warnings,databases=core.scan(root,include_playlists=False)
            self.assertEqual(len(tracks),1)

    def test_real_recheck_finds_new_fixture_file_without_dropping_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);library=root/'library';library.mkdir()
            first=library/'first.mp3';first.write_bytes(b'first unchanged fixture')
            second=library/'second.mp3'
            def database(include_second):
                import xml.etree.ElementTree as ET
                tree=ET.Element('VirtualDJ_Database')
                for file,title in [(first,'First')]+([(second,'Second')] if include_second else []):
                    node=ET.SubElement(tree,'Song',FilePath=str(file))
                    ET.SubElement(node,'Tags',Author='Artist',Title=title)
                (library/'database.xml').write_bytes(ET.tostring(tree))
            database(False)
            service=find.Service(root/'profile')
            item=service.store.create('Keep all entries','First - Artist\nSecond - Artist\nFirst - Artist','title-artist')
            service.start(item['id'],str(library));self.wait(service)
            self.assertEqual([r['status'] for r in service.store.get(item['id'])['entries']],['Have','Not found','Have'])
            second.write_bytes(b'new synthetic fixture');database(True)
            service.start(item['id'],str(library));self.wait(service)
            updated=service.store.get(item['id'])
            self.assertEqual([r['status'] for r in updated['entries']],['Have']*3)
            self.assertEqual([r['original'] for r in updated['entries']],[r['original'] for r in item['entries']])
            self.assertEqual(first.read_bytes(),b'first unchanged fixture')

    @staticmethod
    def wait(service):
        deadline=time.monotonic()+5
        while service.info()['job']['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
        if service.info()['job']['state']=='running':raise AssertionError('check did not finish')


if __name__=='__main__':unittest.main()
