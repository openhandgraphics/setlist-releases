import hashlib,importlib.util,json,tempfile,threading,time,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import app,installation,update_monitor,updater

spec=importlib.util.spec_from_file_location('setlist_setup',Path(__file__).parent.parent/'setlist-installer/setup.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

class InstallTests(unittest.TestCase):
    def package(self,root,bad=False):
        package=root/'payload.zip'
        with zipfile.ZipFile(package,'w') as z:
            z.writestr('Setlist.exe',b'MZnew');z.writestr('Licenses/license.txt','license')
            if bad:z.writestr('../escape.txt','no')
        return package,hashlib.sha256(package.read_bytes()).hexdigest()

    def test_install_and_reinstall_preserve_settings_and_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=root/'SetlistDesktop';data.mkdir();settings=data/'session.json';settings.write_text('preserved')
            package,digest=self.package(root)
            target=Path(setup.install(package,digest,root/'Programs',make_shortcuts=False))
            first=installation.read(target.parent)
            setup.install(package,digest,root/'Programs',make_shortcuts=False)
            self.assertEqual(installation.read(target.parent),first)
            self.assertEqual(settings.read_text(),'preserved')
            self.assertEqual(target.read_bytes(),b'MZnew')
            self.assertEqual(len(list((target.parent/'.setlist-updates').glob('previous-*.exe'))),1)

    def test_invalid_packages_do_not_replace_installed_app(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'Programs'/'Setlist';base.mkdir(parents=True);exe=base/'Setlist.exe';exe.write_bytes(b'MZold')
            package,digest=self.package(root,bad=True)
            for checksum in ('0'*64,digest):
                with self.assertRaises(ValueError):setup.install(package,checksum,root/'Programs',make_shortcuts=False)
                self.assertEqual(exe.read_bytes(),b'MZold');self.assertFalse((root/'escape.txt').exists())

    def test_setup_refuses_downgrade(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'Programs'/'Setlist';base.mkdir(parents=True);installation.record(base,'99.0.0')
            package,digest=self.package(root)
            with self.assertRaisesRegex(ValueError,'newer'):setup.install(package,digest,root/'Programs',make_shortcuts=False)

    def test_update_launch_failure_restores_history_and_exe(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);exe=root/'Setlist.exe';exe.write_bytes(b'MZold');installation.record(root,'1.6.0');old=installation.read(root)
            stage=root/'.setlist-updates';stage.mkdir();candidate=stage/'new.exe';candidate.write_bytes(b'MZnew')
            with patch.object(updater.subprocess,'Popen',side_effect=OSError('test')):
                with self.assertRaises(OSError):updater.replace_app(candidate,exe,hashlib.sha256(b'MZnew').hexdigest(),release_version='1.6.1')
            self.assertEqual(exe.read_bytes(),b'MZold');self.assertEqual(installation.read(root),old)

class NotificationTests(unittest.TestCase):
    def wait(self,m):
        for _ in range(200):
            if not m.info()['checking']:return
            time.sleep(.01)
        self.fail('check did not finish')

    def test_new_release_notifies_without_downloading_or_blocking_tasks(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            a=app.App();a.task={'state':'running','kind':'build'}
            release={'version':'99.0.0','available':True,'notes':'Test'}
            with patch.object(updater,'check',return_value=release) as check,patch.object(updater,'stage') as stage:
                a.action('backgroundUpdates',{});self.wait(a.updates)
                self.assertTrue(a.action('updateInfo',{})['release']['available']);self.assertEqual(a.task['state'],'running')
                self.assertFalse(a.updates.start());check.assert_called_once();stage.assert_not_called()

    def test_disabled_automatic_allows_manual_check_and_persists(self):
        with tempfile.TemporaryDirectory() as d:
            m=update_monitor.Monitor(d,'1.6.1');m.configure(automatic=False)
            m=update_monitor.Monitor(d,'1.6.1');self.assertFalse(m.start())
            with patch.object(updater,'check',return_value={'version':'1.6.1','available':False}):
                self.assertTrue(m.start(force=True));self.wait(m)
                self.assertEqual(m.info()['message'],'You are up to date.')

    def test_official_source_is_automatic_even_with_old_saved_source(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'updates.json').write_text(json.dumps({'repository':'old/example','automatic':True}))
            m=update_monitor.Monitor(d,'1.6.4')
            with patch.object(updater,'check',return_value={'version':'1.6.4','available':False}) as check:
                m.start();self.wait(m)
                self.assertEqual(check.call_args.args[0],'https://github.com/openhandgraphics/setlist-releases/releases/latest/download/setlist-update.json')
            with self.assertRaises(ValueError):m.configure(repo='other/source')

    def test_offline_is_not_reported_as_up_to_date(self):
        with tempfile.TemporaryDirectory() as d,patch.object(updater,'check',side_effect=OSError('offline')):
            m=update_monitor.Monitor(d,'1.6.1');m.start();self.wait(m)
            self.assertIsNone(m.info()['release']);self.assertIn('Could not check',m.info()['error']);self.assertFalse(m.info()['checking'])

    def test_single_background_request(self):
        gate=threading.Event()
        def delayed(*args):gate.wait(2);return {'version':'1.6.1','available':False}
        with tempfile.TemporaryDirectory() as d,patch.object(updater,'check',side_effect=delayed):
            m=update_monitor.Monitor(d,'1.6.1');self.assertTrue(m.start());self.assertFalse(m.start(force=True));gate.set();self.wait(m)

    def test_update_draft_roundtrip_preserves_saved_library(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)):
            a=app.App();a.root='D:/';a.persist();before=(Path(d)/'session.json').read_bytes()
            draft={'inputTab':'list','drafts':{'list':{'text':'A - B'}},'mode':'library'}
            a.action('saveUpdateDrafts',{'draft':draft});self.assertEqual(a.action('restoreUpdateDrafts',{}),draft)
            self.assertIsNone(a.action('restoreUpdateDrafts',{}));self.assertEqual(before,(Path(d)/'session.json').read_bytes())

if __name__=='__main__':unittest.main()
