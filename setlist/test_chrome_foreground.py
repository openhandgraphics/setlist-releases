from pathlib import Path
import unittest
import os
from unittest.mock import patch
import chrome_foreground,chrome_bridge

CHROME=str(Path('fixture/chrome.exe').resolve())
HOST=str(Path('fixture/SetlistChromeHost.exe').resolve())

class FakeWindows:
    def __init__(self):self.paths={11:HOST,12:HOST,13:CHROME};self.foreground=90;self.grants=[]
    def server_pid(self,handle):return 11
    def parents(self):return {11:12,12:13}
    def process_path(self,pid):return self.paths[pid]
    def foreground_pid(self):return self.foreground
    def allow(self,pid):self.grants.append(pid);return True

class ForegroundTests(unittest.TestCase):
    def test_grants_exact_pipe_owning_chrome_on_every_click(self):
        api=FakeWindows()
        for _ in range(3):self.assertEqual(chrome_foreground.handoff(123,CHROME,HOST,api,90),{'granted':True,'browserPid':13})
        self.assertEqual(api.grants,[13,13,13])

    def test_does_not_steal_focus_from_another_application(self):
        api=FakeWindows();api.foreground=71
        self.assertFalse(chrome_foreground.handoff(123,CHROME,HOST,api,90)['granted'])
        self.assertEqual(api.grants,[])

    def test_windows_native_messaging_launcher_is_validated(self):
        api=FakeWindows();api.paths[13]=str(Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/cmd.exe');api.paths[14]=CHROME
        api.parents=lambda:{11:12,12:13,13:14}
        self.assertEqual(chrome_foreground.handoff(123,CHROME,HOST,api,90),{'granted':True,'browserPid':14})
        api.paths[13]=str(Path('unrelated/cmd.exe').resolve())
        self.assertIsNone(chrome_foreground.handoff(123,CHROME,HOST,api,90)['browserPid'])

    def test_rejects_other_native_host_or_parent_process(self):
        for pid in (11,12,13):
            api=FakeWindows();api.paths[pid]=str(Path('unrelated/application.exe').resolve())
            self.assertIsNone(chrome_foreground.handoff(123,CHROME,HOST,api,90)['browserPid'])
            self.assertEqual(api.grants,[])

    def test_windows_failure_does_not_fail_song_navigation(self):
        api=FakeWindows()
        with patch.object(api,'server_pid',side_effect=OSError('Pipe closed')):
            self.assertEqual(chrome_foreground.handoff(123,CHROME,HOST,api,90),{'granted':False,'browserPid':None})

    def test_handoff_precedes_search_message_but_never_status(self):
        events=[]
        class Connection:
            def fileno(self):return 123
            def send_bytes(self,value):events.append('send')
            def poll(self,timeout):return True
            def recv_bytes(self,limit):return b'{"id":"request","ok":true}'
            def close(self):pass
        with patch.object(chrome_bridge,'Client',return_value=Connection()),patch.object(chrome_foreground,'handoff',side_effect=lambda *a:events.append('handoff') or {'granted':True,'browserPid':13}):
            for _ in range(3):chrome_bridge.exchange({'pipe':'fixture','token':'secret','chrome_path':CHROME},{'kind':'search','id':'request'})
            self.assertEqual(events,['handoff','send']*3)
            events.clear();chrome_bridge.exchange({'pipe':'fixture','token':'secret'},{'kind':'status','id':'request'})
            self.assertEqual(events,['send'])
