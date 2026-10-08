import unittest, base64
from unittest.mock import patch
import import_list, spotify_import, photo_import

def track(artist,title,path='song.mp3',version=''):
    return dict(artist=artist,title=title,path=path,source='library',version=version)

class ImportTests(unittest.TestCase):
    def test_formats_order_and_duplicates(self):
        rows=import_list.parse_text('1. ABBA - Dancing Queen\n2. Hello by Adele\n3. Unknown title\n4. ABBA - Dancing Queen')
        self.assertEqual([r['title'] for r in rows],['Dancing Queen','Hello','Unknown title','Dancing Queen'])
        self.assertEqual(import_list.parse_text('Hello - Adele','title-artist')[0]['artist'],'Adele')
        result=import_list.build(rows,[track('ABBA','Dancing Queen')])
        self.assertEqual([r['source'] for r in result['songs']],['library','suggestion','suggestion','library'])
    def test_versions_and_copies_need_review(self):
        rows=import_list.parse_text('Whitney Houston - I Wanna Dance with Somebody')
        result=import_list.build(rows,[track('Whitney Houston','I Wanna Dance with Somebody (Karaoke)')])
        self.assertEqual(result['songs'][0]['source'],'suggestion')
        self.assertEqual(len(result['songs'][0]['candidates']),0)
        result=import_list.build(rows,[track('Whitney Houston','I Wanna Dance with Somebody','a.mp3'),track('Whitney Houston','I Wanna Dance with Somebody','b.mp4')])
        self.assertEqual(result['songs'][0]['source'],'library')
    def test_title_only_never_auto_accepts(self):
        result=import_list.build(import_list.parse_text('Hello'),[track('Adele','Hello')])
        self.assertEqual(result['songs'][0]['source'],'suggestion')
        self.assertEqual(len(result['songs'][0]['candidates']),1)
    def test_links_not_treated_as_songs(self):
        with self.assertRaises(ValueError):import_list.parse_text('https://open.spotify.com/playlist/abc')
        with self.assertRaises(ValueError):spotify_import.playlist_id('https://example.invalid/playlist/'+'a'*22)
    def test_spotify_pages_and_unavailable_items(self):
        c=spotify_import.Client();ident='a'*22
        item=lambda name:{'item':{'name':name,'type':'track','artists':[{'name':'Artist'}]}}
        with patch.object(c,'get',side_effect=[{'name':'My list','snapshot_id':'s'},{'items':[item('First')],'total':2,'next':'next'},{'items':[item('Second')],'total':2,'next':None},{'snapshot_id':'s'}]):
            result=c.playlist('https://open.spotify.com/playlist/'+ident)
        self.assertEqual([r['title'] for r in result['rows']],['First','Second'])
        with patch.object(c,'get',side_effect=[{'name':'My list'},{'items':[{'item':None}],'next':None}]):
            with self.assertRaises(ValueError):c.playlist('spotify:playlist:'+ident)
    def test_oauth_state_rejected(self):
        c=spotify_import.Client();c.redirect='http://127.0.0.1:123/spotify/callback'
        self.assertIn('code_challenge_method=S256',c.begin('a'*32))
        with self.assertRaises(ValueError):c.callback('state=wrong&code=anything')
    def test_photo_invalid_data(self):
        with self.assertRaises(ValueError):photo_import.read_image(base64.b64encode(b'not image').decode())

    def test_shared_signin_pkce_no_secret_and_disconnect(self):
        from urllib.parse import urlparse, parse_qs
        c=spotify_import.Client();c.redirect='http://127.0.0.1:43821/spotify/callback'
        c.access='old';c.expires=10**20
        q=parse_qs(urlparse(c.begin()).query)
        self.assertEqual(q['client_id'],[spotify_import.SHARED_CLIENT_ID])
        self.assertEqual(q['code_challenge_method'],['S256'])
        self.assertNotIn('client_secret',q)
        self.assertFalse(c.connected())
        c.disconnect();self.assertIsNone(c.pending)

    def test_unapproved_account_clears_token(self):
        import io, json
        from urllib.error import HTTPError
        c=spotify_import.Client();c.begin();state=c.pending['state']
        response=io.BytesIO(json.dumps({'access_token':'test','expires_in':3600}).encode())
        with patch.object(spotify_import,'urlopen',side_effect=[response,HTTPError('https://api.spotify.com/v1/me',403,'Forbidden',{},None)]):
            with self.assertRaisesRegex(ValueError,'app access list'):c.callback('state='+state+'&code=test')
        self.assertFalse(c.connected());self.assertEqual(c.access,'')

    def test_approved_account_connects(self):
        import io, json
        c=spotify_import.Client();c.begin();state=c.pending['state']
        responses=[io.BytesIO(json.dumps(x).encode()) for x in [{'access_token':'test','expires_in':3600},{'id':'approved-test-user'}]]
        with patch.object(spotify_import,'urlopen',side_effect=responses):c.callback('state='+state+'&code=test')
        self.assertTrue(c.connected())

if __name__=='__main__':unittest.main()
