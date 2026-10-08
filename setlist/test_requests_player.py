import json, tempfile, threading, time, unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import app, playlist_request, core
from test_setlist import song

class RequestTests(unittest.TestCase):
    def test_multiple_decades(self):
        r=playlist_request.parse("Make me 50 white girl sing-alongs from the '80s, '90s and 2000s")
        self.assertEqual(r['count'],50);self.assertEqual(r['style'],'Pop sing-alongs')
        self.assertEqual(r['yearRanges'],[[1980,1989],[1990,1999],[2000,2009]])
    def test_decade_range(self):
        r=playlist_request.parse('I need 250 bangers from the 80s through the 2000s')
        self.assertEqual(r['yearRanges'],[[1980,2009]]);self.assertEqual(r['count'],250)
    def test_words_and_exclusions(self):
        r=playlist_request.parse('Give me fifty songs for a wedding, no country')
        self.assertEqual(r['count'],50);self.assertIn('country',r['exclude'])
    def test_unknown_request_does_not_silently_pick_random_music(self):
        with self.assertRaises(ValueError):playlist_request.parse('purple umbrellas')
    def test_multi_era_build(self):
        r=playlist_request.parse('50 pop songs from the 80s and 2000s')
        data=core.build([song(1,year='1984'),song(2,year='1997'),song(3,year='2004')],r)
        self.assertEqual({x['year'] for x in data['songs']},{'1984','2004'})

class PlayerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.dataPatch=patch.object(app,'DATA',self.root/'settings');self.dataPatch.start()
        self.api=app.App();self.file=self.root/'audio.mp3';self.file.write_bytes(b'0123456789abcdefghij')
        self.api.result={'songs':[song(1,id='1',path=str(self.file))]}
        self.server,self.token=app.serve(self.api);threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.dataPatch.stop();self.temp.cleanup()
    def test_media_range_and_unauthorized_access(self):
        req=Request(self.url+'/media/'+self.token+'/1',headers={'Range':'bytes=4-8'})
        with urlopen(req) as res:self.assertEqual(res.status,206);self.assertEqual(res.read(),b'45678');self.assertEqual(res.headers['Content-Range'],'bytes 4-8/20')
        with self.assertRaises(HTTPError):urlopen(self.url+'/media/wrong/1')
        with self.assertRaises(HTTPError):urlopen(Request(self.url+'/media/'+self.token+'/1',headers={'Range':'bytes=100-200'}))
    def test_preview_does_not_launch_windows_player(self):
        with patch('os.startfile',side_effect=AssertionError('External player opened')):
            data=self.api.action('preview',{'id':'1'})
        self.assertEqual(data['id'],'1');self.assertFalse(data['video'])
    def test_approval_required(self):
        with patch('virtualdj.publish') as publish,self.assertRaisesRegex(ValueError,'Review'):
            self.api.action('saveVirtualDJ',{'ids':['1']})
        publish.assert_not_called()
    def test_build_does_not_publish_even_if_old_client_requests_autoadd(self):
        self.api.tracks=[song(1,path=str(self.file))]
        with patch('virtualdj.publish') as publish:
            self.api.action('build',{'count':1,'style':'Bangers','autoAdd':True})
            deadline=time.monotonic()+5
            while self.api.task['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(self.api.task['state'],'done');publish.assert_not_called()

if __name__=='__main__':unittest.main()
