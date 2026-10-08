"""Authenticated local media streaming with byte ranges for seeking."""
import mimetypes, os, re
from pathlib import Path
import core

def media_row(result,identifier):
    row=next((r for r in (result or {}).get('songs',[]) if r['id']==str(identifier)),None)
    if not row:
        row=next((c for r in (result or {}).get('songs',[]) for c in r.get('candidates',[]) if c['id']==str(identifier)),None)
    if not row or row['source']!='library':raise ValueError('This is a suggestion, not a downloaded song. There is no local file to play yet.')
    path=Path(row['path'])
    if path.suffix.lower() not in core.MEDIA or not path.is_file():raise ValueError('The music file is unavailable. Reconnect its drive and try again.')
    return row,path

def stream(handler,path):
    try:handle=path.open('rb')
    except OSError:handler.send_error(404,'Music file unavailable');return
    with handle:
        size=os.fstat(handle.fileno()).st_size;start=0;end=size-1
        wanted=handler.headers.get('Range')
        if wanted:
            m=re.fullmatch(r'bytes=(\d*)-(\d*)',wanted)
            if not m or not any(m.groups()):handler.send_error(416);return
            left,right=m.groups()
            if left:start=int(left);end=min(int(right),end) if right else end
            else:start=max(0,size-int(right))
            if start>end or start>=size:
                handler.send_response(416);handler.send_header('Content-Range',f'bytes */{size}');handler.end_headers();return
        handler.send_response(206 if wanted else 200)
        handler.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        handler.send_header('Content-Length',str(max(0,end-start+1)));handler.send_header('Accept-Ranges','bytes');handler.send_header('Cache-Control','no-store')
        if wanted:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        handler.end_headers();handle.seek(start);remaining=end-start+1
        try:
            while remaining:
                chunk=handle.read(min(65536,remaining))
                if not chunk:break
                handler.wfile.write(chunk);remaining-=len(chunk)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
