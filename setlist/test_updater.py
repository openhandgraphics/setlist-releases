import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import updater

class UpdaterTests(unittest.TestCase):
    def test_versions_and_manifest(self):
        release={'app':'Setlist','version':'1.10.0','url':'https://github.com/example/setlist/releases/download/v1.10.0/Setlist.exe','sha256':'a'*64}
        with patch.object(updater,'read_url',return_value=json.dumps(release).encode()):
            self.assertTrue(updater.check('https://example.com/feed','1.9.0')['available'])
            self.assertFalse(updater.check('https://example.com/feed','1.10.0')['available'])
        with self.assertRaises(ValueError):updater.https('http://example.com/app.exe')
        with self.assertRaises(ValueError):updater.version('../../file')
    def test_mismatch_leaves_old_app_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'Setlist.exe';target.write_bytes(b'MZold')
            stage=Path(folder)/'.setlist-updates';stage.mkdir();new=stage/'new.exe';new.write_bytes(b'MZnew')
            with self.assertRaises(ValueError):updater.replace_app(new,target,'0'*64,launch=False)
            self.assertEqual(target.read_bytes(),b'MZold')
    def test_install_keeps_backup_and_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'Setlist.exe';target.write_bytes(b'MZold')
            settings=Path(folder)/'session.json';settings.write_text('unchanged')
            stage=Path(folder)/'.setlist-updates';stage.mkdir();new=stage/'new.exe';new.write_bytes(b'MZnew')
            backup=updater.replace_app(new,target,hashlib.sha256(b'MZnew').hexdigest(),launch=False)
            self.assertEqual(target.read_bytes(),b'MZnew');self.assertEqual(backup.read_bytes(),b'MZold')
            self.assertEqual(settings.read_text(),'unchanged')
    def test_failed_restart_restores_old_app(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'Setlist.exe';target.write_bytes(b'MZold')
            stage=Path(folder)/'.setlist-updates';stage.mkdir();new=stage/'new.exe';new.write_bytes(b'MZnew')
            with patch.object(updater.subprocess,'Popen',side_effect=OSError('Could not launch')):
                with self.assertRaises(OSError):updater.replace_app(new,target,hashlib.sha256(b'MZnew').hexdigest())
            self.assertEqual(target.read_bytes(),b'MZold')
    def test_unexpected_target_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'Setlist.exe';target.write_bytes(b'MZold')
            new=Path(folder)/'new.exe';new.write_bytes(b'MZnew')
            with self.assertRaises(ValueError):updater.replace_app(new,target,hashlib.sha256(b'MZnew').hexdigest(),False)
            self.assertEqual(target.read_bytes(),b'MZold')

if __name__=='__main__':unittest.main()
