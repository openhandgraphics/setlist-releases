"""Validated YouTube searches sent to the approved normal-Chrome companion."""
from urllib.parse import parse_qs, urlencode, urlsplit
import chrome_bridge


def search_url(value):
    if not isinstance(value, str) or len(value) > 16000:
        raise ValueError('Choose a valid YouTube song search.')
    url = urlsplit(value)
    query = parse_qs(url.query)
    if (url.scheme != 'https' or url.netloc != 'www.youtube.com' or
            url.path != '/results' or url.fragment or set(query) != {'search_query'} or
            len(query['search_query']) != 1):
        raise ValueError('Only YouTube song searches can open here.')
    text = query['search_query'][0].strip()
    if not text or len(text) > 2000:
        raise ValueError('Choose a song to search for.')
    return 'https://www.youtube.com/results?' + urlencode({'search_query': text})


def open_search(value):
    return chrome_bridge.open_search(search_url(value))
