import tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
import app, import_list, photo_text, virtualdj

PAIRS = [('Calum Scott', 'Biblical'), ('Brandon Lake', 'Gratitude'),
         ('Jonas Brothers', 'Love Me to Heaven'), ('Muscadine Bloodline', '10-90')]


class ImportOrientationTests(unittest.TestCase):
    def test_title_first_default_and_explicit_artist_first(self):
        for order in (None, 'title-artist', 'artist-title'):
            with self.subTest(order=order):
                text = '\n'.join(f'{artist} - {title}' if order == 'artist-title' else f'{title} - {artist}' for artist, title in PAIRS)
                rows = import_list.parse_text(text, order) if order else import_list.parse_text(text)
                self.assertEqual([(r['artist'], r['title']) for r in rows], PAIRS)

    def test_delimiters_by_syntax_duplicates_and_title_only(self):
        rows = import_list.parse_text('1. Biblical — Calum Scott\n2. Gratitude – Brandon Lake\n3. Love Me to Heaven\tJonas Brothers\n4. 10-90 | Muscadine Bloodline\n5. Biblical by Calum Scott\n6. Biblical - Calum Scott')
        self.assertEqual([(r['artist'], r['title']) for r in rows], PAIRS + [PAIRS[0], PAIRS[0]])
        self.assertEqual(import_list.parse_text('10-90 - Muscadine Bloodline', 'title-only')[0]['title'], '10-90 - Muscadine Bloodline')

    def test_photo_normalization_keeps_its_explicit_artist_first_contract(self):
        verified = []
        def verify(artist, title):
            verified.append((artist, title))
            return dict(status='verified', message='', url='')
        photo_text.normalize('Calum Scott - Biblical', [], verify=verify)
        self.assertEqual(verified, [PAIRS[0]])

    def test_api_default_and_override_survive_restart_and_export(self):
        for order in (None, 'artist-title'):
            with self.subTest(order=order), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile = root / 'profile'
                destination = root / 'VirtualDJ' / 'MyLists'
                destination.mkdir(parents=True)
                old = destination / 'Existing.vdjfolder'
                old.write_bytes(b'existing playlist')
                audio = root / 'Calum Scott - Biblical.mp3'
                audio.write_bytes(b'untouched synthetic recording')
                with patch.object(app, 'DATA', profile):
                    instance = app.App()
                    instance.root = directory
                    instance.ensure_library = lambda: None
                    instance.tracks = [dict(artist=PAIRS[0][0], title=PAIRS[0][1], path=str(audio), version='', source='library', plays=1)]
                    text = '\n'.join(f'{artist} - {title}' if order else f'{title} - {artist}' for artist, title in PAIRS)
                    args = dict(text=text, name='Orientation check', mode='discovery')
                    if order: args['order'] = order
                    instance.action('importList', args)
                    deadline = time.monotonic() + 5
                    while instance.task['state'] == 'running' and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertEqual(instance.task['state'], 'done', instance.task)
                    self.assertEqual([(r['artist'], r['title']) for r in instance.result['songs']], PAIRS)
                    self.assertEqual([r['source'] for r in instance.result['songs']], ['library', 'suggestion', 'suggestion', 'suggestion'])
                    restored = app.App()
                    self.assertEqual(restored.result, instance.result)
                    ids = [r['id'] for r in restored.result['songs']]
                    first = virtualdj.publish(restored.result, ids, directory, destination)
                    second = virtualdj.publish(restored.result, ids, directory, destination)
                    exported = ET.parse(first['path']).getroot().findall('song')
                    self.assertEqual([(r.get('artist'), r.get('title')) for r in exported], PAIRS)
                    self.assertEqual(exported[0].get('path'), str(audio))
                    self.assertEqual(Path(exported[3].get('path')).name, 'Muscadine Bloodline - 10-90.mp3')
                    self.assertTrue(all(not Path(r.get('path')).exists() for r in exported[1:]))
                    self.assertNotEqual(first['path'], second['path'])
                    self.assertEqual(old.read_bytes(), b'existing playlist')
                    self.assertEqual(audio.read_bytes(), b'untouched synthetic recording')


if __name__ == '__main__': unittest.main()
