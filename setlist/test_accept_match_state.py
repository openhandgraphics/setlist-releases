import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app

class AcceptMatchStateTests(unittest.TestCase):
    def test_duplicate_confirm_merges_and_preserves_checks_and_favorites(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)/'settings'):
            p=Path(d)/'song.mp4';p.write_bytes(b'unchanged')
            a=app.App()
            existing=dict(id='old',artist='Video channel',title='Usher - U Got It Bad (Lyrics)',path=str(p),source='library')
            candidate=dict(existing,id='request~0')
            a.result={'request':{'contentFilter':None},'songs':[existing,dict(id='unchecked',source='suggestion',artist='Other',title='Other'),dict(id='request',source='suggestion',artist='USHER',title='U Got It Bad',candidates=[candidate])],'selectedIds':['old'],'lockedIds':['old']}
            result=a.action('acceptMatch',dict(id='request',candidate='request~0',keepIds=['old'],lockedIds=['old']))
            self.assertEqual([r['id'] for r in result['songs']],['unchecked','request'])
            self.assertEqual(result['selectedIds'],['request']);self.assertEqual(result['lockedIds'],['request'])
            self.assertEqual(result['songs'][-1]['requestedSong']['artist'],'USHER')
            self.assertIn('combined',result['matchMessage']);self.assertEqual(p.read_bytes(),b'unchanged')
            self.assertEqual(app.App().result['selectedIds'],['request'])

    def test_imported_repeats_remain_and_new_accept_is_selected(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)/'settings'):
            p=Path(d)/'song.mp3';p.write_bytes(b'fixture')
            a=app.App();local=dict(id='0',source='library',artist='Artist',title='Title',path=str(p))
            a.result={'request':{'imported':True},'songs':[local,dict(id='1',source='suggestion',artist='Artist',title='Ttle',candidates=[dict(local,id='1~0')])],'selectedIds':[]}
            r=a.action('acceptMatch',{'id':'1','candidate':'1~0','keepIds':[]})
            self.assertEqual(len(r['songs']),2);self.assertEqual(r['selectedIds'],['1'])

    def test_invalid_or_ineligible_candidate_does_not_mutate_result(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)/'settings'):
            for name,version,setting in [('missing.mp3','',''),('track.wav','',''),('karaoke.mp4','Karaoke',''),('explicit.mp3','Dirty','clean-only')]:
                p=Path(d)/name
                if name!='missing.mp3':p.write_bytes(b'fixture')
                a=app.App();a.result={'request':{'contentFilter':setting or None},'songs':[dict(id='0',artist='A',title='T',source='suggestion',candidates=[dict(id='0~0',artist='A',title='T',path=str(p),version=version)])]}
                before=copy.deepcopy(a.result)
                with self.assertRaises(ValueError):a.action('acceptMatch',{'id':'0','candidate':'0~0'})
                self.assertEqual(a.result,before)

if __name__=='__main__':unittest.main()
