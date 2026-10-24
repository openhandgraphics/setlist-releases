"""Dated acquisition checklists, independent of performance playlists and media."""
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import threading
import uuid

import core
import import_list
import matching

STATUSES = ('Have', 'Needs checking', 'Not found')


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def validate(data):
    if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('lists'), list) or len(data['lists']) > 100:
        raise ValueError('Music to Find data could not be read. The saved file has been left unchanged.')
    ids = set()
    for item in data['lists']:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in ids or
                not isinstance(item.get('name'), str) or not isinstance(item.get('createdAt'), str) or
                not isinstance(item.get('entries'), list) or not 1 <= len(item['entries']) <= 2000):
            raise ValueError('A saved checklist is invalid. The saved file has been left unchanged.')
        ids.add(item['id'])
        for index, row in enumerate(item['entries'], 1):
            if (not isinstance(row, dict) or row.get('number') != index or
                    any(not isinstance(row.get(k), str) for k in ('artist', 'title', 'original', 'note')) or
                    not row['title'].strip() or row.get('status') not in STATUSES):
                raise ValueError('A saved song is invalid. The saved file has been left unchanged.')
    return data


class Store:
    def __init__(self, folder):
        self.path = Path(folder) / 'music-to-find.json'
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            if not self.path.exists():
                return {'schema': 1, 'lists': []}
            try:
                return validate(json.loads(self.path.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError, KeyError) as exc:
                raise ValueError('Music to Find data could not be read. The saved file has been left unchanged.') from exc

    def write(self, data):
        validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name('music-to-find-' + uuid.uuid4().hex + '.tmp')
        try:
            with temp.open('x', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temp.replace(self.path)
        finally:
            temp.unlink(missing_ok=True)

    def create(self, name, text, order):
        return self.create_rows(name, import_list.parse_text(text, order))

    def create_rows(self, name, rows):
        if not isinstance(name, str) or not name.strip() or len(name) > 90:
            raise ValueError('Give this checklist a name, up to 90 characters.')
        clean = import_list.validate_rows(rows)
        entries = [dict(number=i, original=(rows[i-1].get('original') if isinstance(rows[i-1].get('original'), str) else
                                          r['title'] + (' - ' + r['artist'] if r['artist'] else '')),
                        artist=r['artist'], title=r['title'],
                        status='Needs checking', note='Not checked yet.', matches=[]) for i, r in enumerate(clean, 1)]
        item = dict(id=uuid.uuid4().hex, name=name.strip(), createdAt=now(), checkedAt=None,
                    entries=entries, coverage=None)
        with self.lock:
            data = self.read()
            if len(data['lists']) >= 100:
                raise ValueError('This profile already has 100 checklists.')
            data['lists'].append(item)
            self.write(data)
        return copy.deepcopy(item)

    def get(self, key):
        item = next((i for i in self.read()['lists'] if i['id'] == key), None)
        if item is None:
            raise ValueError('Choose a saved Music to Find list.')
        return item

    def checked(self, original, entries, coverage):
        with self.lock:
            data = self.read()
            item = next((i for i in data['lists'] if i['id'] == original['id']), None)
            if item is None or item['entries'] != original['entries']:
                raise ValueError('This checklist changed. Reopen it before checking again.')
            item.update(entries=entries, checkedAt=now(), coverage=coverage)
            self.write(data)


def check_entries(entries, tracks, limited, checkpoint=lambda message: None):
    """Conservative file/label evidence; never substitutes or drops requested rows."""
    checked = copy.deepcopy(entries)
    by_identity = {}
    for track in tracks:
        by_identity.setdefault(core.identity(track), []).append(track)
    for row in checked:
        checkpoint('Checking song ' + str(row['number']) + ' of ' + str(len(entries)))
        exact = [t for t in by_identity.get(core.identity(row), []) if Path(t.get('path', '')).is_file()]
        certain = [t for t in exact if not row.get('preference') and not t.get('labelSource') and core.norm(t['artist']) == core.norm(row['artist']) and
                   core.norm(t['title']) == core.norm(row['title']) and matching.eligible_recording(t) and
                   matching.performance(t) == matching.performance(row) and
                   (not row.get('version') or core.norm(row['version']) == core.norm(t.get('version', '')))]
        possible = exact or [t for t in matching.candidates(row, tracks) if Path(t.get('path', '')).is_file()]
        choices = certain or possible
        row['matches'] = [{key: t.get(key, '') for key in ('artist', 'title', 'version', 'path', 'labelSource')}
                          for t in choices[:5]]
        if certain:
            row.update(status='Have', note='Local file with matching artist/title labels. Listen to confirm the recording and clean/explicit version; audio was not inspected.')
        elif possible:
            row.update(status='Needs checking', note='Possible local recording: labels, version, karaoke/remix, or format need review. No substitution was made.')
        elif limited:
            row.update(status='Needs checking', note='No matching labeled file found, but this check has coverage gaps. See the coverage notes.')
        else:
            row.update(status='Not found', note='No matching searchable labels in the checked folder. Other drives, archives, unlabeled files and recording versions may need a manual check.')
    return checked


class Service:
    def __init__(self, folder):
        self.store = Store(folder)
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.job = {'state': 'idle', 'message': '', 'listId': None}

    def info(self):
        with self.lock:
            return dict(self.store.read(), job=copy.deepcopy(self.job))

    def stop(self):
        self.cancel.set()
        return True

    def start(self, key, root):
        original = self.store.get(key)
        if not root or not Path(root).is_dir():
            raise ValueError('Connect your selected library folder before rechecking.')
        with self.lock:
            if self.job['state'] == 'running':
                raise ValueError('A checklist check is already running.')
            self.cancel.clear()
            self.job = dict(state='running', message='Reading the selected library folder.', listId=key)

        def checkpoint(message):
            if self.cancel.is_set():
                raise InterruptedError('Check stopped. Previous results were kept.')
            with self.lock:
                self.job['message'] = str(message)

        def run():
            try:
                tracks, warnings, databases = core.scan(root, checkpoint, include_playlists=False)
                unlabeled = sum(bool(not t.get('artist') or not t.get('title') or t.get('labelSource')) for t in tracks)
                coverage = dict(root=str(Path(root).resolve()), files=len(tracks), databases=databases,
                                warnings=warnings, limited=bool(warnings or unlabeled),
                                summary='Selected folder only; VirtualDJ labels, embedded tags and filenames. No audio inspection, other drives or archive contents. Symbolic links and excluded system/quarantine folders are skipped.')
                if unlabeled:
                    coverage['warnings'] = warnings + [f'{unlabeled} files have incomplete or filename-derived labels.']
                rows = check_entries(original['entries'], tracks, coverage['limited'], checkpoint)
                checkpoint('Saving checklist results.')
                self.store.checked(original, rows, coverage)
                with self.lock:
                    self.job.update(state='done', message='Check complete. Every original song has been kept.')
            except InterruptedError as exc:
                with self.lock:
                    self.job.update(state='stopped', message=str(exc))
            except Exception as exc:
                with self.lock:
                    self.job.update(state='error', message=str(exc) + ' Previous results were kept.')
        threading.Thread(target=run, daemon=True).start()
        return True
