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
import json

from get_next_departure import get_pids_data

from timeouts import set_timeout

import git
from os import getcwd, path

import subprocess
import audio

# from playsound import playsound
# import simpleaudio

PING_INTERNAL_SEC = 10

repo = git.Repo(getcwd())
master = repo.head.reference
current_commit = master.commit.hexsha[0:8]
current_message = master.commit.message

__dirname = path.dirname(path.realpath(__file__))
config = json.load(open(__dirname + '/config.json', 'r'))

play_announcements = config['generate_audio']

audio_command = config['audio_command']

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

current_station = None
current_platform = None

current_timeout = None

live_thread = None
current_data = {}

services_played = []
delays_played = []

def main():
    global current_station, current_platform, live_thread, current_data
    args = envopt(__doc__, prefix='METLINKPID_')

    try:
        pid = PID.for_device(args['--serial'])
        pid.send('Ready...')
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

        if current_timeout:
            current_timeout.kill()


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

    @app.route("/enable-audio")
    def enable_audio():
        global play_announcements
        with open('config.json', 'w') as f:
            config['generate_audio'] = True
            play_announcements = True
            json.dump(config, f, indent=2)
        return jsonify({ 'message': 'ok' })

    @app.route("/disable-audio")
    def disable_audio():
        global play_announcements
        with open('config.json', 'w') as f:
            config['generate_audio'] = False
            play_announcements = False
            json.dump(config, f, indent=2)
        return jsonify({ 'message': 'ok' })

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

    def play_audio(path):
        subprocess.Popen(audio_command + [path])

    def play_announcement():
        global current_data, services_played

        minutes_to_dep = current_data['minutes_to_dep']
        scheduled_minutes_to_dep = current_data['scheduled_minutes_to_dep']
        train_delay = minutes_to_dep - scheduled_minutes_to_dep
        service_id = current_data['service_id']

        if train_delay < 5 or minutes_to_dep < 2:
            remaining = (minutes_to_dep - 2) * 60
            if remaining > 0:
                sleep(remaining)
            if service_id not in services_played:
                services_played.append(service_id)
                print('Playing', service_id)
                play_audio(__dirname + '/output.wav')
                services_played = services_played[-20:]
        else:
            remaining = scheduled_minutes_to_dep * 60
            if remaining > 0:
                sleep(remaining)
            if service_id not in delays_played:
                delays_played.append(service_id)

                service_files = audio.get_service_files(current_data['scheduled_hour'], current_data['scheduled_minute'], current_data['raw_dest'])

                padded_minutes_to_dep = '0' + str(round(minutes_to_dep)) if minutes_to_dep < 10 else str(round(minutes_to_dep))

                message_data = service_files + [
                    'item/qitem06',
                    'time/dept_min/dep{}_m'.format(padded_minutes_to_dep)
                ]

                platform = current_data['platform']
                padded_platform = ('0' + str(platform)) if platform < 10 else str(platform)

                data = [
                    'tone/chime', 'platform/attn/pltatn{}'.format(padded_platform), 'tone/pause3'
                ] + message_data + ['tone/pause3'] + message_data

                audio.create_metro_audio(data, 'output-delay')

                print('Playing delayed', service_id)
                play_audio(__dirname + '/output-delay.wav')
                services_played = services_played[-20:]

    def schedule_announcement():
        global current_data, current_timeout
        if current_timeout:
            current_timeout.kill()

        current_timeout = None

        two_minutes_before = current_data['scheduled_minutes_to_dep'] - 2

        current_timeout = set_timeout(play_announcement, two_minutes_before * 60)

    def send_live_data():
        last_string = ''
        global current_station, current_platform, live_thread, current_data
        while True:
            pids_string = ''
            data = get_pids_data(current_station, current_platform)
            pids_string = data['data']
            del data['data']
            current_data = data

            if data['data_type'] == 'auto':
                schedule_announcement()

            if last_string != pids_string:
                with pid_lock:
                    try:
                        pid.send(pids_string)
                    except Exception as e:
                        print('metlinkpid-http: {}'.format(e), file=stderr)
                        # print('Tried to send', pids_string)
                last_string = pids_string
            else:
                print('Nothing to do, skipping')
            sleep(30)


    Thread(target=ping).start()

    with pid_lock:
      try:
          pid.send('Ready...')
          def clear():
            sleep(5)
            pid.send('  ')
          Thread(target=clear).start()
      except Exception as e:
          print('metlinkpid-http: {}'.format(e), file=stderr)

    try:
        serve(app, listen=args['--http'], threads=1)
    finally:
        ping_event.set()


if __name__ == '__main__':
    main()
