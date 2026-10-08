"""Read-only Spotify imports using OAuth PKCE; tokens live only in memory."""
import base64, hashlib, json, re, secrets, time
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Public OAuth identifier, never a client secret. Spotify controls the user allowlist.
SHARED_CLIENT_ID = 'abe950bc4f1340f18ec10361e5e54822'

def playlist_id(value):
    value=str(value).strip()
    if value.startswith('spotify:playlist:'):ident=value.split(':')[-1]
    else:
        p=urlparse(value)
        if p.scheme!='https' or p.hostname!='open.spotify.com':raise ValueError('Paste the full open.spotify.com/playlist/... link from Spotify Share.')
        match=re.fullmatch(r'/(?:intl-[^/]+/)?playlist/([A-Za-z0-9]{22})/?',p.path)
        ident=match.group(1) if match else ''
    if not re.fullmatch(r'[A-Za-z0-9]{22}',ident):raise ValueError('This is not a Spotify playlist link.')
    return ident

class Client:
    def __init__(self):self.pending=None;self.access='';self.expires=0;self.redirect=''
    def begin(self,client_id=SHARED_CLIENT_ID):
        if not re.fullmatch(r'[a-fA-F0-9]{32}',client_id):raise ValueError('Paste the Client ID from your Spotify developer app (not a client secret).')
        self.disconnect()
        verifier=secrets.token_urlsafe(48);state=secrets.token_urlsafe(32)
        self.pending=dict(client_id=client_id,verifier=verifier,state=state,created=time.monotonic())
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        return 'https://accounts.spotify.com/authorize?'+urlencode(dict(client_id=client_id,response_type='code',redirect_uri=self.redirect,scope='playlist-read-private playlist-read-collaborative',state=state,code_challenge_method='S256',code_challenge=challenge,show_dialog='true'))
    def disconnect(self):
        self.pending=None;self.access='';self.expires=0
    def callback(self,query):
        q=parse_qs(query);p=self.pending
        if not p or time.monotonic()-p['created']>600 or not secrets.compare_digest(q.get('state',[''])[0],p['state']):raise ValueError('Connection expired or invalid. Return to Setlist and connect again.')
        self.pending=None
        if q.get('error'):raise ValueError('Spotify connection was cancelled. You can still paste songs or use a photo.')
        code=q.get('code',[''])[0]
        if not code:raise ValueError('Spotify did not return an authorization code.')
        body=urlencode(dict(grant_type='authorization_code',code=code,redirect_uri=self.redirect,client_id=p['client_id'],code_verifier=p['verifier'])).encode()
        try:
            with urlopen(Request('https://accounts.spotify.com/api/token',data=body,headers={'Content-Type':'application/x-www-form-urlencoded'}),timeout=20) as r:data=json.load(r)
        except Exception:raise ValueError('Spotify could not connect. Check the app Client ID and redirect URI, then retry.')
        self.access=data['access_token'];self.expires=time.monotonic()+int(data.get('expires_in',3600))-30
        try:self.get('me')
        except Exception:
            self.disconnect()
            raise
    def connected(self):return bool(self.access and time.monotonic()<self.expires)
    def get(self,path):
        if not self.connected():raise ValueError('Connect Spotify first. The connection lasts for this session until Spotify expires it.')
        try:
            with urlopen(Request('https://api.spotify.com/v1/'+path,headers={'Authorization':'Bearer '+self.access}),timeout=20) as r:return json.load(r)
        except HTTPError as e:
            if e.code==403:
                if path=='me':raise ValueError('Spotify has not approved this account for Setlist. Ask the Setlist owner to add your Spotify account email to the app access list. You do not need to create a developer app. You can also paste songs or use a photo.')
                raise ValueError('Spotify did not allow this playlist. Use one you own or collaborate on. Otherwise paste its songs or use a photo.')
            if e.code==401:self.access='';raise ValueError('Spotify connection expired. Connect again.')
            if e.code==429:raise ValueError('Spotify is busy. Wait '+e.headers.get('Retry-After','60')+' seconds and try again.')
            raise ValueError('Spotify could not read the playlist. Check the link and try again.')
    def playlist(self,link,checkpoint=lambda m:None):
        ident=playlist_id(link);rows=[];offset=0
        meta=self.get('playlists/'+ident);snapshot=meta.get('snapshot_id')
        while True:
            checkpoint(f'Reading Spotify songs {offset+1} onward...')
            page=self.get(f'playlists/{ident}/items?limit=50&offset={offset}&market=US')
            if int(page.get('total',0))>2000:raise ValueError('Use a playlist of 2,000 songs or fewer.')
            items=page.get('items',[])
            for item in items:
                track=item.get('item') or item.get('track') or {}
                if track.get('type') not in (None,'track') or not track.get('name'):
                    raise ValueError(f'Spotify item {len(rows)+1} is unavailable or is not a song. Import a pasted list to retain and correct this item.')
                rows.append({'title':track['name'],'artist':', '.join(a['name'] for a in track.get('artists',[]) if a.get('name')),'url':track.get('external_urls',{}).get('spotify','')})
            if not page.get('next'):break
            if not items or len(rows)>=2000:raise ValueError('Spotify returned an incomplete playlist. Nothing was imported. Try again.')
            offset+=len(items)
        if snapshot and self.get('playlists/'+ident).get('snapshot_id')!=snapshot:raise ValueError('The Spotify playlist changed while importing. Try again to keep the correct order.')
        if not rows:raise ValueError('That playlist has no readable songs.')
        return {'name':meta.get('name','Spotify requests'),'rows':rows,'text':'\n'.join(r['artist']+' - '+r['title'] for r in rows),'url':'https://open.spotify.com/playlist/'+ident}
