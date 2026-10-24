"""Chrome native host: blocked waits while idle, bounded JSON over a local Windows pipe."""
from pathlib import Path
import hmac
import json
import os
import re
import struct
import sys
import threading
from multiprocessing.connection import Listener

MAX_MESSAGE = 16384


def read_message(stream):
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError('Incomplete native message header')
    length = struct.unpack('<I', header)[0]
    if not 0 < length <= MAX_MESSAGE:
        raise ValueError('Invalid native message size')
    body = bytearray()
    while len(body) < length:
        part = stream.read(length - len(body))
        if not part:
            raise ValueError('Incomplete native message')
        body.extend(part)
    value = json.loads(body.decode('utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Expected native message object')
    return value


def write_message(stream, value):
    data = json.dumps(value, separators=(',', ':')).encode('utf-8')
    if len(data) > MAX_MESSAGE:
        raise ValueError('Native message too large')
    stream.write(struct.pack('<I', len(data)) + data)
    stream.flush()


def main():
    folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    config = json.loads((folder/'bridge-config.json').read_text(encoding='utf-8'))
    expected = 'chrome-extension://' + config['extension_id'] + '/'
    if len(sys.argv) < 2 or sys.argv[1] != expected:
        raise ValueError('Unapproved native-messaging origin')
    if not re.fullmatch(r'\\\\\.\\pipe\\SetlistYouTube-[0-9a-f]{32}', config.get('pipe', '')):
        raise ValueError('Invalid local pipe')
    if not re.fullmatch('[0-9a-f]{64}', config.get('token', '')):
        raise ValueError('Invalid connection secret')
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    incoming, outgoing = sys.stdin.buffer, sys.stdout.buffer
    write_lock = threading.Lock()
    pending = {}
    pending_lock = threading.Lock()
    stopped = threading.Event()
    listener = Listener(config['pipe'], family='AF_PIPE')

    def send(value):
        with write_lock:
            write_message(outgoing, value)

    def serve():
        while not stopped.is_set():
            connection = None
            key = None
            try:
                connection = listener.accept()
                if not connection.poll(2):
                    continue
                request = json.loads(connection.recv_bytes(MAX_MESSAGE).decode('utf-8'))
                if not isinstance(request, dict) or not isinstance(request.get('token'), str) or not hmac.compare_digest(request['token'], config['token']):
                    continue
                key = request.get('id')
                if not isinstance(key, str) or not re.fullmatch('[0-9a-f]{32}', key):
                    continue
                if request.get('kind') not in ('search', 'status'):
                    continue
                if request['kind']=='search' and (not isinstance(request.get('url'), str) or len(request['url'])>12000):
                    continue
                event = threading.Event()
                result = {}
                with pending_lock:
                    pending[key] = (event, result)
                message = {'id': key, 'kind': request['kind']}
                if request['kind']=='search':
                    message['url'] = request['url']
                send(message)
                if not event.wait(8):
                    result.update(id=key, ok=False, error='Chrome did not confirm the search. Check the existing YouTube tab before trying again.')
                connection.send_bytes(json.dumps(result, separators=(',', ':')).encode('utf-8'))
            except (OSError, EOFError, ValueError, UnicodeError):
                pass
            finally:
                if key:
                    with pending_lock:
                        pending.pop(key, None)
                if connection:
                    connection.close()

    threading.Thread(target=serve, daemon=True).start()
    send({'kind':'ready','protocol':1})
    try:
        while True:
            response = read_message(incoming)
            if response is None:
                return
            with pending_lock:
                waiting = pending.get(response.get('id'))
                if waiting and response.get('kind')=='result' and isinstance(response.get('ok'), bool):
                    waiting[1].update(response)
                    waiting[0].set()
    finally:
        stopped.set()
        with pending_lock:
            for key,(event,result) in pending.items():
                result.update(id=key,ok=False,error='The Chrome companion disconnected; no automatic retry was made.')
                event.set()
        listener.close()


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('Setlist Chrome connection: '+str(error),file=sys.stderr)
        sys.exit(1)
