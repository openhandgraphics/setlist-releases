"""Non-blocking release checks; never download or restart automatically."""
import json,re,threading,time
from datetime import datetime
from pathlib import Path
import updater

DEFAULT_REPOSITORY='openhandgraphics/setlist-releases'

def repository(value):
    value=str(value).strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}',value):
        raise ValueError('Enter the GitHub repository as owner/repository.')
    return value

class Monitor:
    def __init__(self,data,current):
        self.data=Path(data);self.current=current;self.lock=threading.RLock()
        self.release=None;self.error='';self.checking=False;self.last_checked='';self.last_attempt=0
        self.config={'repository':DEFAULT_REPOSITORY,'automatic':True}
        try:
            saved=json.loads((self.data/'updates.json').read_text(encoding='utf-8'))
            self.config['automatic']=saved.get('automatic',True) is not False
        except (OSError,ValueError,TypeError):pass

    def info(self):
        with self.lock:
            message=('Checking for updates…' if self.checking else self.error or
                     ('Version '+self.release['version']+' is available.' if self.release and self.release['available'] else
                      'You are up to date.' if self.release else 'Ready to check for updates.'))
            return dict(self.config,current=self.current,release=dict(self.release) if self.release else None,
                        message=message,checking=self.checking,lastChecked=self.last_checked,error=self.error)

    def configure(self,repo=None,automatic=None):
        with self.lock:
            if self.checking:raise ValueError('Wait for the update check to finish.')
            if repo is not None:
                if repo!=DEFAULT_REPOSITORY:raise ValueError('Setlist updates use the official source automatically.')
            if automatic is not None:self.config['automatic']=bool(automatic)
            self.data.mkdir(parents=True,exist_ok=True)
            temp=self.data/'updates.tmp';temp.write_text(json.dumps(self.config),encoding='utf-8');temp.replace(self.data/'updates.json')
        return self.info()

    def start(self,force=False):
        with self.lock:
            if self.checking:return False
            if not force and (not self.config['automatic'] or (self.last_attempt and time.monotonic()-self.last_attempt<21600)):return False
            self.checking=True;self.last_attempt=time.monotonic();self.error=''
            repo=self.config['repository']
        def run():
            try:
                release=updater.check('https://github.com/'+repo+'/releases/latest/download/setlist-update.json',self.current)
                with self.lock:self.release=release;self.last_checked=datetime.now().astimezone().isoformat(timespec='seconds')
            except Exception:
                with self.lock:self.error='Could not check for updates. Your app still works; try again when you’re online.'
            finally:
                with self.lock:self.checking=False
        threading.Thread(target=run,daemon=True).start()
        return True
