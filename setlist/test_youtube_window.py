import unittest
from types import SimpleNamespace
from unittest.mock import patch
import app
from youtube_window import search_url


class YouTubeSearchTests(unittest.TestCase):
    def test_only_canonical_searches_are_accepted(self):
        self.assertEqual(search_url('https://www.youtube.com/results?search_query=A%26B'), 'https://www.youtube.com/results?search_query=A%26B')
        for value in (None, 'javascript:alert(1)', 'https://evil.example/results?search_query=x',
                      'https://www.youtube.com@evil.example/results?search_query=x',
                      'https://www.youtube.com/watch?v=abc', 'https://www.youtube.com/results?search_query=',
                      'https://www.youtube.com/results?search_query=x&redirect=evil',
                      'https://www.youtube.com/results?search_query=a&search_query=b'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                search_url(value)

    def test_search_uses_only_the_chrome_bridge(self):
        with patch('webbrowser.open') as browser, patch('subprocess.Popen') as process, patch('chrome_bridge.open_search', return_value={'reused':True,'tabId':1}) as bridge:
            for song in ('first', 'second'):
                result=app.App.action(SimpleNamespace(), 'openYouTube', {'url': 'https://www.youtube.com/results?search_query=' + song})
                self.assertEqual(result['tabId'],1)
            self.assertEqual(bridge.call_count,2)
            browser.assert_not_called()
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
