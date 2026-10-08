import copy, hashlib, json, tempfile, unittest
from pathlib import Path
import xml.etree.ElementTree as E
import core

def song(i,**kw):
    row={'title':f'Song {i}','artist':f'Artist {i%13}','path':f'D:/Bombs/{i}.mp3','version':'','genre':'Pop','year':'2002','plays':i,'bpm':100,'duration':180,'playlists':[],'source':'library','url':''}
    row.update(kw);return row

class PlaylistTests(unittest.TestCase):
    def test_featured_artist_variations_are_one_song(self):
        rows=[song(1,artist='Flo Rida',title='Low'),song(2,artist='Flo Rida ft. T-Pain',title='LOW (Lyrics)'),song(3,artist='Flo Rida feat. T-Pain',title='Low')]
        r=core.build(rows,{'count':50,'style':'Bangers'})
        self.assertEqual(len(r['songs']),1)
        self.assertEqual(core.identity(song(1,artist='J Balvin & Willy William f Beyonce',title='Mi Gente')),core.identity(song(2,artist='J Balvin feat. Willy William',title='Mi Gente')))
    def test_exact_sizes_and_formats_dedup(self):
        rows=[song(i) for i in range(300)];rows+=[dict(r,path=r['path']+'.mp4') for r in rows]
        for count in (50,250):
            r=core.build(rows,{'count':count,'style':'Bangers'})
            self.assertEqual(len(r['songs']),count)
            self.assertEqual(len({core.identity(x) for x in r['songs']}),count)
    def test_insufficient_and_no_cross_genre_padding(self):
        r=core.build([song(1,genre='Country',path='D:/Country/a.mp3')],{'count':50,'style':'Norteño'})
        self.assertFalse(r['songs']);self.assertTrue(r['warnings'])
    def test_era_filters_and_keyword(self):
        r=core.build([song(1),song(2,year='1995'),song(3,year='')],{'count':50,'style':'Bangers','era':2000,'brief':'2000s'})
        self.assertEqual([s['title'] for s in r['songs']],['Song 1'])
    def test_seed_priority(self):
        a=song(1,artist='Usher',title='Yeah');b=song(2,artist='Other',title='Random')
        self.assertGreater(core.rank(a,'Bangers','',0)[0],core.rank(b,'Bangers','',0)[0])
    def test_discovery_owned_and_invalid_urls_excluded(self):
        rows=[song(i) for i in range(80)]
        rows.append(song(88,artist='Usher',title='Owned song'))
        def fetch(q):return [{'artistName':q,'trackName':name,'releaseDate':'2004','primaryGenreName':'Pop','trackViewUrl':'https://music.apple.com/us/album/123'} for name in ['Owned song','New one','New two']]
        r=core.build(rows,{'count':50,'style':'Bangers','mode':'discovery'},fetch=fetch)
        self.assertEqual(len(r['songs']),50)
        self.assertTrue(any(s['source']=='suggestion' for s in r['songs']))
        self.assertFalse(any(s['source']=='suggestion' and s['artist']=='Usher' and s['title']=='Owned song' for s in r['songs']))
    def test_offline_discovery_retains_library(self):
        def fail(q):raise OSError('offline')
        r=core.build([song(i) for i in range(50)],{'count':50,'style':'Bangers','mode':'discovery'},fetch=fail)
        self.assertEqual(len(r['songs']),50);self.assertTrue(r['warnings'])
    def test_cancel_stops_without_mutation(self):
        rows=[song(i) for i in range(50)];original=copy.deepcopy(rows)
        def cancel(m):raise InterruptedError('Stopped')
        with self.assertRaises(InterruptedError):core.build(rows,{'count':50},cancel)
        self.assertEqual(rows,original)
    def test_scan_and_export_preserve_bytes_and_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);music=root/'Bombs';music.mkdir();vdj=root/'VirtualDJ';vdj.mkdir()
            p=music/'Beyoncé & Jay-Z - Déjà Vu.mp4';p.write_bytes(b'fixture media bytes')
            db=E.Element('VirtualDJ_Database');s=E.SubElement(db,'Song',FilePath=str(p));E.SubElement(s,'Tags',Author='Beyoncé & Jay-Z',Title='Déjà Vu',Genre='Pop');E.SubElement(s,'Poi',Name='Cue 1',Pos='12.3');E.ElementTree(db).write(vdj/'database.xml',encoding='utf-8')
            before={p:hashlib.sha256(p.read_bytes()).hexdigest(),vdj/'database.xml':hashlib.sha256((vdj/'database.xml').read_bytes()).hexdigest()}
            rows,warnings,dbs=core.scan(root)
            self.assertEqual(len(rows),1)
            r=core.build(rows,{'count':1,'style':'Bangers'})
            for _ in range(2):
                saved=core.export(r,['0'],root,'Test playlist')
                f=Path(saved['folder']);tree=E.parse(f/'Test playlist.vdjfolder');self.assertEqual(tree.find('song').get('path'),str(p))
                self.assertIn(str(p),(f/'Test playlist.m3u').read_text(encoding='utf-8-sig'))
            for file,h in before.items():self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),h)
    def test_missing_media_blocks_export(self):
        with tempfile.TemporaryDirectory() as d:
            r=core.build([song(1)],{'count':1})
            with self.assertRaises(ValueError):core.export(r,['0'],d,'Unsafe')
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_discoveries_never_in_playable_file(self):
        with tempfile.TemporaryDirectory() as d:
            r={'songs':[song(1,id='a',source='suggestion',path='',url='https://music.apple.com/test')]}
            saved=core.export(r,['a'],d,'Discoveries')
            self.assertFalse(list(Path(saved['folder']).glob('*.m3u')))
            self.assertTrue((Path(saved['folder'])/'Read me and suggestions.txt').is_file())
    def test_bad_count(self):
        for n in (0,1001):
            with self.assertRaises(ValueError):core.build([] ,{'count':n})

if __name__=='__main__':unittest.main()
