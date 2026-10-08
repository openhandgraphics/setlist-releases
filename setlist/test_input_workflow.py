import unittest, tempfile, time
from pathlib import Path
from unittest.mock import patch
import app, import_list

class InputWorkflowTests(unittest.TestCase):
    def test_clear_survives_restart_and_preserves_playlists(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            a=app.App();a.ensure_library=lambda:None
            a.action('importList',{'text':'Artist - Song','mode':'discovery'})
            for _ in range(200):
                if a.task['state']!='running':break
                time.sleep(.01)
            self.assertEqual(a.task['state'],'done')
            a.action('saveUpdateDrafts',{'draft':{'inputTab':'list','drafts':{'list':{'text':'Artist - Song'},'description':{'text':'90s pop'}}}})
            history=a.action('playlistHistory',{})
            a.action('clearEntry',{'inputTab':'list'})
            b=app.App()
            self.assertTrue(b.action('status',{})['entryCleared'])
            self.assertEqual(b.action('playlistHistory',{}),history)
            restored=b.action('restoreUpdateDrafts',{})
            self.assertEqual(restored['drafts']['list'],{})
            self.assertEqual(restored['drafts']['description']['text'],'90s pop')

    def test_import_mode_preserves_requested_rows_and_blocks_missing_exports(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            a=app.App();a.ensure_library=lambda:None
            rows=[{'artist':'Missing Artist','title':'Missing Song'}]
            for mode in ('library','discovery'):
                a.action('importList',{'rows':rows,'mode':mode})
                for _ in range(200):
                    if a.task['state']!='running':break
                    time.sleep(.01)
                self.assertEqual(a.task['state'],'done',a.task)
                self.assertEqual(a.result['request']['mode'],mode)
                self.assertEqual(a.result['request']['entries'],rows)
                self.assertEqual(len(a.result['songs']),1)
                if mode=='library':
                    for action in ('saveDJ','saveVirtualDJ','save'):
                        with self.assertRaisesRegex(ValueError,'My Library Only'):
                            a.action(action,{'ids':['0'],'approved':True})
                else:
                    with patch.object(app.core,'export',return_value={'folder':d}) as export:
                        a.action('save',{'ids':['0'],'destination':d,'name':'Test'})
                        export.assert_called_once()

    def test_fresh_install_connects_without_client_id(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            a=app.App()
            with patch.object(a.spotify,'begin',return_value='https://accounts.spotify.com/authorize') as begin,patch.object(app.webbrowser,'open'):
                a.action('spotifyConnect',{})
                begin.assert_called_once_with(app.spotify_import.SHARED_CLIENT_ID)
            self.assertEqual(a.action('spotifyStatus',{}),{'connected':False})
            a.action('spotifyDisconnect',{})

    def test_structured_pairs_preserve_hyphens(self):
        rows=import_list.validate_rows([{'artist':'Artist - Duo','title':'Title - Part II'}])
        self.assertEqual(rows[0],{'artist':'Artist - Duo','title':'Title - Part II'})
        for bad in ([],[{'title':''}],['bad'],[{'title':'x'*1001}]):
            with self.assertRaises(ValueError):import_list.validate_rows(bad)

    def test_tab_draft_attribution_is_isolated(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            a=app.App();a.ensure_library=lambda:None
            a.import_draft={'url':'https://open.spotify.com/playlist/wrong'}
            a.import_drafts['correct']={'url':'https://open.spotify.com/playlist/right'}
            for draft_id,expected in [(None,False),('correct',True)]:
                a.action('importList',{'rows':[{'artist':'A','title':'B - C'}],'draftId':draft_id})
                for _ in range(200):
                    if a.task['state']!='running':break
                    time.sleep(.01)
                self.assertEqual(a.task['state'],'done',a.task)
                self.assertEqual(a.result['request']['entries'][0]['title'],'B - C')
                self.assertEqual(bool(a.result.get('sources')),expected)
                if expected:self.assertTrue(a.result['sources'][0]['url'].endswith('/right'))

if __name__=='__main__':unittest.main()
