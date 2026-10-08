import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import core
import playlist_request
from test_setlist import song


class MixedRequestTests(unittest.TestCase):
    def setUp(self):
        self.rows=[song(1,artist='Banda MS',genre='Banda',year='2020',path='D:/Banda/a.mp3'),
                   song(2,artist='Nelly',genre='Hip hop',year='2002'),
                   song(3,artist='80\'s',genre='Pop',year='1984'),
                   song(4,artist='George Strait',genre='Country',year='1995',path='D:/Country/b.mp3'),
                   song(5,artist='Selena',genre='Tejano',year='1994',path='D:/Tejano/c.mp3')]

    def build(self,text,rows=None):
        rows=self.rows if rows is None else rows
        return core.build(rows,playlist_request.parse(text,rows),fetch=lambda q: self.fail('Unexpected network'))

    def test_exact_prompt_and_apostrophes(self):
        for decade in ["80's",'80s','’80s','80’s','1980s','eighties']:
            with self.subTest(decade=decade):
                result=self.build('banda, throwbacks, and '+decade)
                self.assertEqual(result['request']['brief'],'')
                self.assertEqual({r['title'] for r in result['songs']},{'Song 1','Song 2','Song 3'})

    def test_mixed_genres_balanced_without_padding(self):
        rows=self.rows+[song(i,genre='Country',artist='Country Artist '+str(i),path='D:/Country/'+str(i)+'.mp3') for i in range(10,70)]
        result=self.build('10 country and Tejano songs',rows)
        self.assertIn('Selena',[r['artist'] for r in result['songs'][:2]])
        self.assertEqual(len(result['songs']),10)

    def test_missing_bucket_does_not_zero_result(self):
        result=self.build('country and Tejano',self.rows[3:4])
        self.assertEqual(len(result['songs']),1)
        self.assertTrue(any('No local matches for Tejano' in w for w in result['warnings']))

    def test_single_genre_and_decades(self):
        self.assertEqual([r['title'] for r in self.build('banda')['songs']],['Song 1'])
        self.assertEqual([r['title'] for r in self.build('throwbacks')['songs']],['Song 2'])
        self.assertEqual([r['title'] for r in self.build('1980s')['songs']],['Song 3'])
        self.assertEqual({r['year'] for r in self.build('80s and 90s')['songs']},{'1984','1994','1995'})

    def test_explicit_restrictions_and_exclusions(self):
        rows=[song(1,genre='Rock',year='1984'),song(2,genre='Rock',year='2002'),song(3,genre='Country',year='1984')]
        for prompt in ['80s rock only','rock from the 80s']:
            self.assertEqual([r['title'] for r in self.build(prompt,rows)['songs']],['Song 1'])
        result=self.build('banda, throwbacks, and 80s, no country')
        self.assertNotIn('Country',[r['genre'] for r in result['songs']])
        self.assertEqual([r['title'] for r in self.build('throwbacks from the 80s',[song(1,artist='Usher',year='1984')])['songs']],['Song 1'])

    def test_empty_library_and_unknown_request(self):
        result=self.build('banda, throwbacks and 80s',[])
        self.assertEqual(result['songs'],[])
        self.assertTrue(result['warnings'])
        with self.assertRaises(ValueError):self.build('purple umbrellas')

    def test_discovery_queries_all_requested_genres_and_errors_keep_local(self):
        request=playlist_request.parse('country and Tejano',self.rows)
        request['mode']='discovery';queries=[]
        def offline(query):
            queries.append(query)
            raise OSError('offline')
        result=core.build(self.rows,request,fetch=offline)
        self.assertIn('George Strait',queries)
        self.assertIn('Selena',queries)
        self.assertEqual({r['artist'] for r in result['songs']},{'George Strait','Selena'})
        self.assertTrue(any('offline' in w for w in result['warnings']))

    def test_app_workflow_and_scan_error_preserve_previous_result(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(app,'DATA',Path(folder)):
            for i,row in enumerate(self.rows):
                path=Path(folder)/f'{i}.mp3';path.write_bytes(b'test media');row['path']=str(path)
            api=app.App();api.tracks=self.rows
            with patch('core.catalog',side_effect=AssertionError('Network')),patch('virtualdj.publish') as publish:
                api.action('build',{'prompt':"banda, throwbacks, and 80's",'mode':'library'})
                self.wait(api)
                self.assertEqual(api.task['state'],'done')
                self.assertEqual(len(api.result['songs']),3)
                publish.assert_not_called()
            previous=api.result
            api.tracks=[];api.root=folder
            with patch('core.scan',side_effect=OSError('Cannot read library')):
                api.action('build',{'prompt':'banda'})
                self.wait(api)
                self.assertEqual(api.task['state'],'error')
                self.assertIn('Cannot read library',api.task['message'])
                self.assertIs(api.result,previous)

    def wait(self,api):
        deadline=time.monotonic()+10
        while api.task['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
        self.assertNotEqual(api.task['state'],'running')


if __name__=='__main__':unittest.main()
