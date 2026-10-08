import copy, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
import virtualdj

class VirtualDJTests(unittest.TestCase):
    def fixture(self,root):
        lists=root/'VirtualDJ'/'MyLists';lists.mkdir(parents=True)
        song=root/'Beyoncé & Jay-Z.mp4';song.write_bytes(b'original media')
        old=lists/'Existing.vdjfolder';old.write_bytes(b'<VirtualFolder/>')
        db=lists.parent/'database.xml';db.write_bytes(b'<VirtualDJ_Database><Song><Poi Name="saved loop" /></Song></VirtualDJ_Database>')
        r={'request':{'style':'Weddings'},'songs':[{'id':'1','source':'library','path':str(song),'artist':'Beyoncé & Jay-Z','title':'Déjà Vu'},{'id':'2','source':'suggestion','path':'','artist':'Other','title':'Discovery'}]}
        return lists,db,song,old,r

    def test_native_publication_and_name_collision(self):
        with tempfile.TemporaryDirectory() as d:
            lists,db,song,old,r=self.fixture(Path(d));before={p:p.read_bytes() for p in (db,song,old)}
            with patch('core.discover',return_value=[db]):
                first=virtualdj.publish(r,['1','2'],d);second=virtualdj.publish(r,['1','2'],d)
            self.assertNotEqual(first['path'],second['path'])
            self.assertEqual(first['name'],'Weddings - 2 songs')
            self.assertEqual(second['name'],'Weddings - 2 songs (2)')
            self.assertEqual(Path(first['path']).parent,lists)
            rows=ET.parse(first['path']).findall('song');self.assertEqual(len(rows),2)
            self.assertEqual(rows[0].get('path'),str(song));self.assertEqual(rows[0].get('artist'),'Beyoncé & Jay-Z')
            self.assertEqual(first['suggestions'],1)
            self.assertFalse(Path(rows[1].get('path')).exists())
            self.assertIn('Setlist Missing Songs',rows[1].get('path'))
            self.assertEqual(Path(rows[1].get('path')).name,'Other - Discovery.mp3')
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
            self.assertFalse(list(lists.glob('*.tmp')))
    def test_suggestions_only_creates_missing_entries(self):
        with tempfile.TemporaryDirectory() as d:
            lists,db,song,old,r=self.fixture(Path(d))
            with patch('core.discover',return_value=[db]):saved=virtualdj.publish(r,['2'],d)
            self.assertEqual(saved['local'],0);self.assertEqual(saved['suggestions'],1)
            self.assertFalse(Path(ET.parse(saved['path']).find('song').get('path')).exists())
    def test_disconnected_music_creates_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            lists,db,song,old,r=self.fixture(Path(d));r['songs'][0]['path']=str(Path(d)/'missing.mp3')
            with patch('core.discover',return_value=[db]),self.assertRaises(ValueError):virtualdj.publish(r,['1'],d)
            self.assertEqual(list(lists.iterdir()),[old])
    def test_missing_virtualdj_is_explicit(self):
        with patch('core.discover',return_value=[]),self.assertRaisesRegex(ValueError,'not found'):virtualdj.destination('D:/')
    def test_populated_collection_wins_over_empty(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);lists,db,*_=self.fixture(root)
            empty=root/'settings';(empty/'MyLists').mkdir(parents=True)
            with patch('core.discover',return_value=[empty/'database.xml',db]):self.assertEqual(virtualdj.destination(root),lists)

if __name__=='__main__':unittest.main()
