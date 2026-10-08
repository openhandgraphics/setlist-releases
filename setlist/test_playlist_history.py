import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app

def result(title):
    return {'request':{'name':title},'songs':[{'id':'0','title':'Song A','artist':'Artist A','source':'library'},{'id':'1','title':'Song B','artist':'Artist B','source':'suggestion'}]}

class PlaylistHistoryTests(unittest.TestCase):
    def test_migrates_legacy_session_without_duplication(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            Path(d,'session.json').write_text(json.dumps({'root':d,'result':result('Old set')}))
            a=app.App();self.assertEqual(len(a.action('playlistHistory',{})),1)
            a.persist();a.persist();b=app.App()
            self.assertEqual(len(b.action('playlistHistory',{})),1);self.assertEqual(b.root,d)

    def test_multiple_playlists_survive_restarts_and_open(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            a=app.App();a.result=result('First');a.persist();first=a.result['historyId']
            a.result=result('Second');a.persist();b=app.App()
            self.assertEqual([r['name'] for r in b.action('playlistHistory',{})],['Second','First'])
            b.action('openPlaylist',{'id':first});self.assertEqual(b.result['request']['name'],'First')
            b.result['songs'][0]['title']='Edited';b.persist()
            self.assertEqual(len(b.playlists),2);self.assertEqual(b.action('playlistDetails',{'id':first})['songs'][0]['title'],'Edited')

    def test_delete_and_undo_never_touch_music_or_export(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            root=Path(d);song=root/'song.mp3';export=root/'playlist.vdjfolder';song.write_bytes(b'music');export.write_bytes(b'playlist')
            a=app.App();a.result=result('Saved');a.result['published']={'ids':['0'],'path':str(export)};a.persist();key=a.result['historyId']
            self.assertEqual(a.action('playlistDetails',{'id':key})['count'],1)
            a.action('deletePlaylist',{'id':key});self.assertIsNone(a.result);self.assertFalse(a.action('playlistHistory',{}))
            a=app.App();self.assertFalse(a.action('playlistHistory',{}));a.action('restorePlaylist',{'id':key})
            self.assertEqual(a.action('playlistHistory',{})[0]['name'],'Saved')
            self.assertEqual(song.read_bytes(),b'music');self.assertEqual(export.read_bytes(),b'playlist')

    def test_busy_and_unknown_history_actions_are_blocked(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            a=app.App();a.result=result('Set');a.persist();key=a.result['historyId'];a.task['state']='running'
            for method in ('openPlaylist','deletePlaylist','restorePlaylist'):
                with self.assertRaises(ValueError):a.action(method,{'id':key})
            a.task['state']='done'
            with self.assertRaises(ValueError):a.action('deletePlaylist',{'id':'../../music'})
            self.assertEqual(len(a.action('playlistHistory',{})),1)

if __name__=='__main__':unittest.main()
