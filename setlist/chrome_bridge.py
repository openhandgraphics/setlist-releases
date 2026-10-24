"""On-demand local pipe client. No browser automation, network listener or tab scanning."""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from multiprocessing.connection import Client
import chrome_foreground

LOCK = threading.Lock()


def config_path():
    override = os.environ.get('SETLIST_CHROME_BRIDGE_CONFIG')
    return Path(override) if override else Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Setlist/ChromeBridge/bridge-config.json'


def read_config(path=None):
    try:
        value = json.loads((Path(path) if path else config_path()).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError('The Setlist Chrome companion is not installed. Copy the search address for now.') from exc
    if (value.get('schema') != 1 or not re.fullmatch('[a-p]{32}', value.get('extension_id', '')) or
            not re.fullmatch(r'\\\\\.\\pipe\\SetlistYouTube-[0-9a-f]{32}', value.get('pipe', '')) or
            not re.fullmatch('[0-9a-f]{64}', value.get('token', ''))):
        raise ValueError('The Setlist Chrome connection settings are invalid. Reconnect the companion.')
    return value


def exchange(config, payload):
    connection = Client(config['pipe'], family='AF_PIPE')
    try:
        foreground = None
        if payload.get('kind') == 'search':
            foreground = chrome_foreground.handoff(connection.fileno(), config.get('chrome_path'),
                                                   str(config_path().parent/'SetlistChromeHost.exe'))
        connection.send_bytes(json.dumps(dict(payload, token=config['token']), separators=(',', ':')).encode('utf-8'))
        if not connection.poll(10):
            raise ValueError('Chrome did not confirm this search. Check your YouTube tab before trying again; no second tab was opened automatically.')
        response = json.loads(connection.recv_bytes(16384).decode('utf-8'))
        if not isinstance(response, dict) or response.get('id') != payload['id']:
            raise ValueError('Chrome returned an invalid confirmation. Check the existing YouTube tab before trying again.')
        if response.get('ok') is not True:
            raise ValueError(str(response.get('error', 'The Chrome search could not be confirmed.'))[:350])
        if foreground is not None:response['foregroundHandoff'] = foreground
        return response
    finally:
        connection.close()


def open_search(url):
    if not LOCK.acquire(timeout=1):
        raise ValueError('The previous YouTube search is still opening. Please wait.')
    started = time.perf_counter()
    try:
        config = read_config()
        payload = {'kind': 'search', 'id': secrets.token_hex(16), 'url': url}
        try:
            result = exchange(config, payload)
        except (FileNotFoundError, ConnectionRefusedError):
            # Start normal Chrome only if it is closed. Never relaunch an already-running
            # browser merely because its extension is disabled or disconnected.
            running = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/FO', 'CSV', '/NH'],
                                     capture_output=True, text=True, creationflags=0x08000000, timeout=4)
            chrome = Path(config.get('chrome_path', ''))
            if 'chrome.exe' in running.stdout.lower() or not chrome.is_file() or chrome.name.lower() != 'chrome.exe':
                raise ValueError('Open the Setlist YouTube companion in Chrome and choose Connect. Your existing tabs have been left alone.')
            subprocess.Popen([str(chrome)], creationflags=0x08000000)
            deadline = time.monotonic() + 10
            while True:
                try:
                    result = exchange(config, payload)
                    break
                except (FileNotFoundError, ConnectionRefusedError):
                    if time.monotonic() >= deadline:
                        raise ValueError('Chrome opened, but the companion is not connected. Choose Connect in the Setlist YouTube companion.')
                    time.sleep(.2)
        result['clientMs'] = round((time.perf_counter() - started) * 1000, 2)
        return result
    except (OSError, EOFError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('The Chrome connection ended without confirmation. Check your YouTube tab before trying again.') from exc
    finally:
        LOCK.release()
