import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app, matching, playback
import core, import_list

def song(artist, title, path='test.mp3'):
    return dict(artist=artist,title=title,path=path,source='library',version='')

class MatchingTests(unittest.TestCase):
    def test_karaoke_video_clues_and_cdg_excluded_but_lyrics_allowed(self):
        for row in (song('Artist','Song','D:/Karaoke/Song.mp4'),song('Sing King','Song','video.mp4'),song('Artist','Song (No Vocals)','video.mp4'),dict(song('Artist','Song'),hasCdg=True)):
            self.assertFalse(matching.eligible_recording(row))
        self.assertTrue(matching.eligible_recording(song('Artist','Song (Lyrics)','D:/Videos/Song.mp4')))

    def test_short_title_misspelling_and_transposition_remain_possible(self):
        request=song('Prince','Kiss')
        rows=[song('Prnce','Kis','miss.mp3'),song('Prince','Ksis','swap.mp3')]
        self.assertEqual({r['path'] for r in matching.candidates(request,rows)},{'miss.mp3','swap.mp3'})
        self.assertEqual(len(matching.candidates(song('Prince','Kiss'),[song('Prince','Kisx')])),1)
        self.assertIsNone(matching.preferred(request,rows))

    def test_scan_includes_unindexed_file_beside_existing_database(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);vdj=root/'VirtualDJ';vdj.mkdir()
            (vdj/'database.xml').write_text('<VirtualDJ_Database/>')
            media=root/'Prince - Kiss.mp3';media.write_bytes(b'fixture media')
            quarantine=root/'_DJ Organizer Quarantine';quarantine.mkdir();(quarantine/'Prince - Kiss.mp3').write_bytes(b'quarantined')
            tracks,_,_=core.scan(root)
            self.assertEqual(len(tracks),1);self.assertEqual(tracks[0]['path'],str(media))
            self.assertEqual(tracks[0]['artist'],'Prince')

    def test_combined_labels_and_reversed_filename_are_candidates(self):
        request=song('Da Krazy Pimpz','Te Vez Buena')
        rows=[song('YouTube channel','DA KRAZY PIMPZ - TE VEZ BUENA','a.mp3'),song('','unknown','TE VEZ BUENA - DA KRAZY PIMPZ.mp3')]
        self.assertIsNone(matching.preferred(request,rows))
        self.assertEqual(len(matching.candidates(request,rows)),2)
        self.assertEqual(rows[0]['artist'],'YouTube channel')

    def test_blank_vdj_labels_recovered_and_case_insensitive(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'DA KRAZY PIMPZ -TE VEZ BUENA.mp3'
            path.write_bytes(b'fixture media')
            row=song('','',str(path))
            core.recover_labels(row,path)
            self.assertEqual(row['title'],'TE VEZ BUENA')
            self.assertEqual(row['artist'],'DA KRAZY PIMPZ')
            result=import_list.build([{'artist':'Da Krazy Pimpz','title':'Te Vez Buena'}],[row])
            self.assertEqual(result['songs'][0]['source'],'library')
            self.assertEqual(path.read_bytes(),b'fixture media')

    def test_filename_does_not_override_conflicting_label(self):
        row=song('Different Artist','','ignored')
        with patch('mutagen.File',return_value=None):
            core.recover_labels(row,Path('Artist - Title.mp3'))
        self.assertEqual(row['title'],'')

    def test_typos_and_reversed_labels(self):
        request=song('Whitney Houston','I Wanna Dance with Somebody')
        rows=[song('Whitny Houston','I Wanna Dance with Somebdy'),
              song('I Wanna Dance with Somebody','Whitney Houston','reversed.mp3')]
        self.assertEqual(len(matching.candidates(request,rows)),2)

    def test_same_title_different_artist_is_not_match(self):
        self.assertEqual(matching.candidates(song('Adele','Hello'),[song('Lionel Richie','Hello')]),[])

    def test_version_warning_and_no_automatic_substitution(self):
        r=song('Whitney Houston','I Wanna Dance with Somebody');r.update(id='0',source='suggestion',path='')
        result=matching.attach({'songs':[r]},[song('Whitney Houston','I Wanna Dance with Somebody (Karaoke)')])
        self.assertEqual(result['songs'][0]['source'],'suggestion')
        self.assertEqual(r['candidates'],[])

    def test_preview_and_explicit_accept_preserve_media(self):
        with tempfile.TemporaryDirectory() as d, patch.object(app,'DATA',Path(tempfile.mkdtemp())):
            path=Path(d)/'song.mp3';path.write_bytes(b'unchanged media')
            r=song('Whitney Houston','I Wanna Dance with Somebody');r.update(id='0',source='suggestion',path='')
            a=app.App();a.result=matching.attach({'songs':[r]},[song('Whitny Houston','I Wanna Dance with Somebody',str(path))])
            self.assertEqual(playback.media_row(a.result,'0~0')[1],path)
            with self.assertRaises(ValueError):a.action('acceptMatch',{'id':'0','candidate':'invalid'})
            a.action('acceptMatch',{'id':'0','candidate':'0~0'})
            self.assertEqual(a.result['songs'][0]['source'],'library')
            self.assertEqual(a.result['songs'][0]['requestedSong']['artist'],'Whitney Houston')
            self.assertEqual(path.read_bytes(),b'unchanged media')

if __name__=='__main__':unittest.main()
