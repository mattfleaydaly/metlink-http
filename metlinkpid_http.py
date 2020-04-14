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

from sys import stderr
from threading import Lock, Event, Thread
from urllib.parse import unquote_plus

from envopt import envopt
from flask import Flask, request, jsonify
from metlinkpid import PID
from waitress import serve

from get_next_departure import generate_pids_string

PING_INTERNAL_SEC = 10


def main():
    global current_station, current_platform, live_thread
    args = envopt(__doc__, prefix='METLINKPID_')

    current_station = None
    current_platform = None
    last_string = None

    live_thread = None

    try:
        pid = PID.for_device(args['--serial'])
    except Exception as e:
        exit('metlinkpid-http: {}'.format(e))

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
        if live_thread:
            live_thread.stop()
        live_thread = Thread(target=send_live_data)
        live_thread.start()


    @app.route("/disable-live")
    def disable_live():
        global live_thread
        if live_thread:
            live_thread.stop()

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
        while True:
            pids_string = generate_pids_string(current_station, current_platform)
            if last_string != pids_string:
                with pid_lock:
                    try:
                        pid.send(pids_string)
                    except Exception as e:
                        print('metlinkpid-http: {}'.format(e), file=stderr)
                last_string = pids_string
            else:
                print('Nothing to do, skipping')
            time.sleep(30)


    Thread(target=ping).start()
    try:
        serve(app, listen=args['--http'], threads=1)
    finally:
        ping_event.set()


if __name__ == '__main__':
    main()
