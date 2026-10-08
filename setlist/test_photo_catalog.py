import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import app, catalog_verify, photo_text, playlist_request


class CatalogPhotoTests(unittest.TestCase):
    def test_spoken_rnb_decade_variants(self):
        for text in ("90's R/B",'90’s R & B','1990s R and B',"nineties R'n'B",'90s R B','give me nineties R and B playlist'):
            with self.subTest(text=text):
                result=playlist_request.parse(text)
                self.assertEqual(result['style'],'R&B');self.assertEqual(result['yearRanges'],[[1990,1999]])
    def verifier(self, rows):
        return catalog_verify.Verifier(fetch=lambda query:rows,interval=0)

    def test_split_spotify_rows_not_in_local_library(self):
        verify=self.verifier([dict(artistName='Jon Pardi',trackName='Head Over Boots',trackViewUrl='https://music.apple.com/us/album/example/123')])
        r=photo_text.normalize('1\nHead Over Boots\nJon Pardi\n2\nUnknown Song\nUnknown Artist',verify=verify,layout='title-artist')
        self.assertEqual(r['text'],'Jon Pardi - Head Over Boots\nUnknown Artist - Unknown Song')
        self.assertEqual(r['count'],2)
        self.assertEqual(r['uncertain'],['Unknown Artist - Unknown Song'])
        self.assertEqual([v['status'] for v in r['verification']],['verified','unverified'])

    def test_wrong_artist_and_close_titles_never_verified(self):
        rows=[dict(artistName='Someone Else',trackName='Hello',trackViewUrl='https://music.apple.com/1'),dict(artistName='Adele',trackName='Hello Again',trackViewUrl='https://music.apple.com/2')]
        self.assertEqual(self.verifier(rows)('Adele','Hello')['status'],'unverified')

    def test_offline_preserves_order_pairs_and_trailing_title(self):
        def offline(query):raise OSError('Offline')
        verify=catalog_verify.Verifier(fetch=offline,interval=0)
        r=photo_text.normalize('Hello\nAdele\nDreams\nFleetwood Mac\nLast title',verify=verify,layout='title-artist')
        self.assertEqual(r['text'],'Adele - Hello\nFleetwood Mac - Dreams\nLast title')
        self.assertEqual(len(r['uncertain']),3)

    def test_duplicates_cache_and_explicit_marker_preserved(self):
        rows=[dict(artistName='Prince',trackName='1999',trackViewUrl='https://music.apple.com/1')]
        with patch.object(catalog_verify.core,'catalog',return_value=rows) as fetch:
            verify=catalog_verify.Verifier(interval=0)
            r=photo_text.normalize('1999\nE\nPrince\n1999\nMusic video • Prince',verify=verify,layout='title-artist')
            self.assertEqual(r['text'],'Prince - 1999\nPrince - 1999');self.assertFalse(r['uncertain'])
            fetch.assert_called_once()

    def test_stop_is_not_swallowed(self):
        def stop(message):raise app.Cancelled()
        with self.assertRaises(app.Cancelled):self.verifier([]).__class__(checkpoint=stop,fetch=lambda q:[],interval=0)('A','B')

    def test_clear_entry_keeps_saved_result_and_library(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            state=app.App();state.root='D:/Music';state.result={'songs':[{'title':'Saved'}]};state.import_draft={'text':'old'}
            state.persist();before=(Path(d)/'session.json').read_bytes()
            state.action('clearEntry',{})
            self.assertIsNone(state.import_draft);self.assertEqual(state.root,'D:/Music')
            restored=app.App()
            self.assertEqual(restored.result,state.result)
            self.assertEqual(restored.root,state.root)
            self.assertTrue(restored.entry_cleared)


if __name__=='__main__':unittest.main()
