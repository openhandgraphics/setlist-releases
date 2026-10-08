"""Conservative title/artist verification using the existing iTunes catalog."""
import time
from urllib.parse import urlparse
import core


class Verifier:
    def __init__(self, checkpoint=lambda message: None, fetch=None, interval=3.1):
        self.checkpoint=checkpoint;self.fetch=fetch or core.catalog
        self.interval=interval;self.next_call=0;self.cache={};self.unavailable=False

    def __call__(self, artist, title):
        key=(core.norm(artist),core.norm(title))
        if key in self.cache:return self.cache[key]
        result={'status':'unverified','message':'No exact catalog match; check this pair.','url':''}
        if not artist or not title:return result
        if self.unavailable:
            return dict(result,message='Online lookup unavailable; check this pair.')
        self.checkpoint('Checking artist and title online: '+title[:80])
        while time.monotonic()<self.next_call:
            self.checkpoint('Checking artist and title online: '+title[:80])
            time.sleep(min(.1,max(0,self.next_call-time.monotonic())))
        try:rows=self.fetch(artist+' '+title)
        except Exception:
            self.unavailable=True
            return dict(result,message='Online lookup unavailable; check this pair.')
        finally:self.next_call=time.monotonic()+self.interval
        self.checkpoint('Checking catalog results: '+title[:80])
        for row in rows:
            if (core.norm(row.get('artistName','')),core.norm(row.get('trackName','')))!=key:continue
            url=row.get('trackViewUrl','');parsed=urlparse(url)
            if parsed.scheme!='https' or parsed.hostname not in ('music.apple.com','itunes.apple.com'):continue
            result={'status':'verified','message':'Artist and title verified in the Apple music catalog.','url':url}
            break
        self.cache[key]=result
        return result
