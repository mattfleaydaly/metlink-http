import wave
import os
import json
__dirname = os.path.dirname(os.path.realpath(__file__))

config = json.load(open(__dirname + '/config.json', 'r'))
station_codes = json.load(open(__dirname + '/station_codes.json', 'r'))
audio_path = config['audio_path']

def get_service_files(scheduled_hour, scheduled_minute, destination):
    hour_12 = str(int(scheduled_hour) % 12)

    departure_time = []

    minute_file = 'time/minutes/min_{}'.format(scheduled_minute)
    hour_file = 'time/the_hour/the_{}'.format('0' + hour_12 if int(hour_12) < 10 else hour_12)
    if scheduled_minute == '00':
        if scheduled_hour == '0':
            minute_file = 'time/on_hour/midnight'
            departure_time = [minute_file]
        elif int(scheduled_hour) < 12:
            minute_file = 'time/on_hour/am'
        elif scheduled_hour == '12':
            minute_file = 'time/on_hour/noon'
            departure_time = [minute_file]
        else:
            minute_file = 'time/on_hour/pm'

    if len(departure_time) == 0:
        if hour_file == 'time/the_hour/the_00':
            hour_file = 'time/the_hour/the_12'

        departure_time = [
            hour_file, minute_file
        ]

    return departure_time + ['station/dst/{}_dst'.format(station_codes[destination])]

def create_metro_audio(files, name):
    full_files = files + [
        'tone/pause3', 'tone/dtmf_s', 'tone/dtmf_s'
    ]

    parts = []
    for segment in full_files:
        w = wave.open(audio_path + segment + '.wav', 'rb')
        parts.append([w.getparams(), w.readframes(w.getnframes())])
        w.close()

    output = wave.open(__dirname + '/{}.wav'.format(name), 'wb')
    output.setparams(parts[0][0])
    for part in parts:
        output.writeframes(part[1])
    output.close()
