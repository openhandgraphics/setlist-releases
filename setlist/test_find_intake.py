import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
import music_to_find


class FindIntakeTests(unittest.TestCase):
    def test_preview_is_read_only_and_preserves_import_orientation(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(app, 'DATA', Path(directory)):
            instance=app.App()
            rows=instance.action('previewMusicToFind',{'text':'10-90 - Muscadine Bloodline\nBiblical - Calum Scott\nBiblical - Calum Scott','order':'title-artist'})['rows']
            self.assertEqual([r['title'] for r in rows],['10-90','Biblical','Biblical'])
            self.assertEqual(rows[0]['artist'],'Muscadine Bloodline')
            self.assertFalse(instance.music_to_find.store.path.exists())

    def test_spotify_read_does_not_touch_performance_drafts_or_preferences(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(app,'DATA',Path(directory)):
            instance=app.App();instance.result={'songs':[{'title':'Current'}]};instance.import_draft={'text':'Unfinished playlist'};instance.content_filter='prefer-clean'
            before=copy.deepcopy((instance.result,instance.import_draft,instance.content_filter,instance.task))
            rows=[{'artist':'Artist - With Hyphen','title':'Song - Live'},{'artist':'Artist - With Hyphen','title':'Song - Live'}]
            with patch.object(instance.spotify,'playlist',return_value={'name':'Spotify source','url':'https://open.spotify.com/playlist/'+'a'*22,'rows':rows}):
                result=instance.action('readMusicToFindSpotify',{'url':'https://open.spotify.com/playlist/'+'a'*22})
            self.assertEqual(result['rows'],rows)
            self.assertEqual((instance.result,instance.import_draft,instance.content_filter,instance.task),before)
            self.assertFalse(instance.music_to_find.store.path.exists())
            item=instance.action('createMusicToFind',{'name':result['name'],'rows':result['rows']})
            self.assertEqual([r['title'] for r in item['entries']],['Song - Live','Song - Live'])
            self.assertTrue(all(r['status']=='Needs checking' for r in item['entries']))

    def test_new_bulk_list_never_changes_existing_findings_and_failed_read_unlocks(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(app,'DATA',Path(directory)):
            instance=app.App();store=instance.music_to_find.store
            original=store.create('Original','Song - Artist','title-artist')
            data=store.read();data['lists'][0]['entries'][0].update(status='Have',preference='Clean version preferred',note='Verified original evidence');store.write(data)
            before=copy.deepcopy(store.read()['lists'][0])
            with patch.object(instance.spotify,'playlist',side_effect=ValueError('Connect Spotify first')):
                with self.assertRaisesRegex(ValueError,'Connect Spotify'):instance.action('readMusicToFindSpotify',{'url':'x'})
            self.assertFalse(instance.find_spotify_lock.locked())
            store.create_rows('Next',[{'title':'New','artist':'Artist'}])
            self.assertEqual(store.get(original['id']),before)
            bytes_before=store.path.read_bytes()
            with self.assertRaises(ValueError):store.create_rows('Invalid',[{'title':''}])
            self.assertEqual(store.path.read_bytes(),bytes_before)

    def test_bulk_rows_are_trimmed_and_two_thousand_entries_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            store=music_to_find.Store(directory)
            rows=[{'artist':' Artist ','title':' Song '+str(i)+' '} for i in range(2000)]
            item=store.create_rows('Bulk',rows)
            self.assertEqual(len(item['entries']),2000)
            self.assertEqual(item['entries'][-1]['title'],'Song 1999')
            self.assertEqual(item['entries'][-1]['number'],2000)
            with self.assertRaises(ValueError):store.create_rows('Too many',rows+[rows[0]])
