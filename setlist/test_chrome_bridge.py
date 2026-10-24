import io
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import chrome_bridge

host_path=Path(__file__).parent.parent/'chrome-companion/native_host.py'
spec=importlib.util.spec_from_file_location('setlist_native_host_test',host_path)
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


class ChromeBridgeTests(unittest.TestCase):
    def test_native_messages_are_bounded_json_not_pickle(self):
        stream=io.BytesIO();host.write_message(stream,{'kind':'ready','protocol':1});stream.seek(0)
        self.assertEqual(host.read_message(stream),{'kind':'ready','protocol':1})
        for value in (b'x',struct.pack('<I',20000),struct.pack('<I',5)+b'xx',struct.pack('<I',2)+b'[]'):
            with self.subTest(value=value),self.assertRaises((ValueError,UnicodeError)):
                host.read_message(io.BytesIO(value))
        self.assertIsNone(host.read_message(io.BytesIO()))

    def test_configuration_only_allows_local_named_pipe(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json'
            valid={'schema':1,'extension_id':'a'*32,'pipe':r'\\.\pipe\SetlistYouTube-'+'a'*32,'token':'b'*64}
            path.write_text(json.dumps(valid));self.assertEqual(chrome_bridge.read_config(path),valid)
            for field,value in [('pipe',r'\\remote\pipe\other'),('token','short'),('extension_id','evil')]:
                path.write_text(json.dumps(dict(valid,**{field:value})))
                with self.assertRaises(ValueError):chrome_bridge.read_config(path)

    def test_uncertain_result_never_relaunches_chrome(self):
        with patch('chrome_bridge.read_config',return_value={}),patch('chrome_bridge.exchange',side_effect=ValueError('not confirmed')),patch('subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError,'not confirmed'):chrome_bridge.open_search('https://www.youtube.com/results?search_query=x')
            launch.assert_not_called()

    def test_disconnected_running_chrome_is_not_relaunched(self):
        with patch('chrome_bridge.read_config',return_value={}),patch('chrome_bridge.exchange',side_effect=FileNotFoundError()),patch('subprocess.run') as tasklist,patch('subprocess.Popen') as launch:
            tasklist.return_value.stdout='"chrome.exe","42"'
            with self.assertRaisesRegex(ValueError,'choose Connect'):chrome_bridge.open_search('https://www.youtube.com/results?search_query=x')
            launch.assert_not_called()
