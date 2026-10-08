"""Read photos locally with Windows OCR. No uploads to external services."""
import base64, json, os, subprocess, sys, tempfile
from pathlib import Path

def read_image(encoded):
    if os.name!='nt':raise ValueError('Photo reading needs Windows 10 or 11.')
    try:data=base64.b64decode(encoded,validate=True)
    except Exception:raise ValueError('Choose a valid PNG or JPG image.')
    if not 0<len(data)<=12*1024*1024:raise ValueError('Choose a photo smaller than 12 MB.')
    extension='.png' if data.startswith(b'\x89PNG\r\n\x1a\n') else '.jpg' if data.startswith(b'\xff\xd8\xff') else ''
    if not extension:raise ValueError('Use a PNG or JPG photo.')
    script=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'PhotoReader.exe'
    with tempfile.TemporaryDirectory(prefix='setlist-photo-') as folder:
        path=Path(folder)/('photo'+extension);path.write_bytes(data)
        run=subprocess.run([str(script),str(path)],capture_output=True,timeout=75,creationflags=0x08000000)
        if run.returncode:
            raise ValueError('Windows could not read this image. Try a clearer PNG/JPG or paste the text. '+run.stderr.decode('utf-8',errors='replace')[:250])
        result={'text':run.stdout.decode('utf-8-sig')}
        if not result.get('text','').strip():raise ValueError('No text found. Try a sharper photo or paste the songs.')
        return result['text']
