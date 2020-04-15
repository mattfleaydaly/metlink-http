"""
Usage:
  metlinkpid-http [--serial=PORT] [--http=HOST:PORT]
  metlinkpid-http (-h | --help)

Options:
  --serial=PORT
      The PID serial port [default: /dev/ttyUSB0].
      Can be set using environment variable METLINKPID_SERIAL.

  --http=HOST:PORT
      The hostname/IP address and port to listen on [default: 127.0.0.1:8080].
      Use an IP address of "0.0.0.0" to listen on all IP addresses.
      Can be set using environment variable METLINKPID_HTTP.

Full documentation online at:
  https://github.com/Lx/python-metlinkpid-http
"""

from sys import stderr, settrace
from threading import Lock, Event, Thread
from urllib.parse import unquote_plus

from envopt import envopt
from flask import Flask, request, jsonify
from metlinkpid import PID
from waitress import serve
from time import sleep

from get_next_departure import get_pids_data

import git
from os import getcwd

import traceback

PING_INTERNAL_SEC = 10

repo = git.Repo(getcwd())
master = repo.head.reference
current_commit = master.commit.hexsha[0:8]
current_message = master.commit.message

class thread_with_trace(Thread):
  def __init__(self, *args, **keywords):
    Thread.__init__(self, *args, **keywords)
    self.killed = False

  def start(self):
    self.__run_backup = self.run
    self.run = self.__run
    Thread.start(self)

  def __run(self):
    settrace(self.globaltrace)
    self.__run_backup()
    self.run = self.__run_backup

  def globaltrace(self, frame, event, arg):
    if event == 'call':
      return self.localtrace
    else:
      return None

  def localtrace(self, frame, event, arg):
    if self.killed:
      if event == 'line':
        raise SystemExit()
    return self.localtrace

  def kill(self):
    self.killed = True

def main():
    global current_station, current_platform, live_thread, current_data
    args = envopt(__doc__, prefix='METLINKPID_')

    current_station = None
    current_platform = None

    live_thread = None
    current_data = {}

    try:
        pid = PID.for_device(args['--serial'])
    except Exception as e:
        print('metlinkpid-http: {}'.format(e))

    pid_lock = Lock()

    app = Flask(__name__)

    @app.route("/")
    def send_message():
        disable_live()
        message = unquote_plus(request.query_string.decode('utf-8'))
        json = {'message': message, 'error': None}
        try:
            with pid_lock:
                pid.send(message)
        except Exception as e:
            json['error'] = str(e)
        return jsonify(json)

    @app.route("/enable-live")
    def enable_live():
        global current_station, current_platform, live_thread
        current_station = request.args.get('station')
        current_platform = request.args.get('platform')
        disable_live()
        live_thread = thread_with_trace(target=send_live_data)
        live_thread.start()
        return jsonify({'message': 'ok', 'error': None})


    @app.route("/disable-live")
    def disable_live():
        global live_thread
        if live_thread:
            live_thread.kill()

        with pid_lock:
            try:
                pid.send('  _  ')
            except Exception as e:
                print('metlinkpid-http: {}'.format(e), file=stderr)
        return jsonify({'message': 'ok', 'error': None})

    @app.route("/get-data")
    def get_data():
        global current_data
        return jsonify(current_data)

    @app.route("/get-version")
    def get_version():
        return jsonify({
            'hash': current_commit,
            'msg': current_message
        })

    ping_event = Event()

    def ping():
        while True:
            with pid_lock:
                try:
                    pid.ping()
                except Exception as e:
                    print('metlinkpid-http: {}'.format(e), file=stderr)
            if ping_event.wait(PING_INTERNAL_SEC):
                break

    def send_live_data():
        last_string = ''
        global current_station, current_platform, live_thread, current_data
        while True:
            pids_string = ''
            data = get_pids_data(current_station, current_platform)
            pids_string = data['data']
            del data['data']
            current_data = data

            if last_string != pids_string:
                with pid_lock:
                    try:
                        pid.send(pids_string)
                    except Exception as e:
                        print('metlinkpid-http: {}'.format(e), file=stderr)
                        print('Tried to send', pids_string)
                last_string = pids_string
            else:
                print('Nothing to do, skipping')
            sleep(30)


    Thread(target=ping).start()
    try:
        serve(app, listen=args['--http'], threads=1)
    finally:
        ping_event.set()


if __name__ == '__main__':
    main()
