from ptv_api import ptv_api
from dateutil.tz import gettz
import datetime
import time
import sys
import json
from generate_stopping_pattern import generate_stopping_pattern
import os
from metlinkpid import DisplayMessage, PID
import wave

import traceback

__dirname = os.path.dirname(os.path.realpath(__file__))
config = json.load(open(__dirname + '/config.json', 'r'))
stations = json.load(open(__dirname + '/stations.json', 'r'))
station_codes = json.load(open(__dirname + '/station_codes.json', 'r'))

key = config['key']
dev_id = config['dev_id']
generate_audio = config['generate_audio']
audio_path = config['audio_path']

aus_mel = gettz('Australia/Melbourne')

city_loop_stations = [
'Southern Cross',
'Parliament',
'Flagstaff',
'Melbourne Central'
]


class NoTrains(Exception):
  def __init__(self, *args, **keywords):
    Exception.__init__(self, *args, **keywords)

def write_audio(platform, scheduled_hour, scheduled_minute, destination, stopping_pattern_audio):
    greeting = None
    if int(scheduled_hour) < 12:
        greeting = 'item/item01'
    elif int(scheduled_hour) < 17:
        greeting = 'item/item02'
    else:
        greeting = 'item/item03'

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
        if scheduled_hour == '0':
            hour_file = 'time/the_hour/the_12'

        departure_time = [
            hour_file, minute_file
        ]

    intro = [
        'tone/chime',
        greeting,
        'tone/pause3'
    ]
    service_data = [
        'platform/next/pn_{}'.format('0' + platform if int(platform) < 10 else platform),
    ] + departure_time + [
        'station/dst/{}_dst'.format(station_codes[destination])
    ] + stopping_pattern_audio

    full_pattern = intro + service_data + [
        'tone/pause3'
    ] + service_data

    parts = []
    for segment in full_pattern:
        w = wave.open(audio_path + segment + '.wav', 'rb')
        parts.append([w.getparams(), w.readframes(w.getnframes())])
        w.close()

    output = wave.open('output.wav', 'wb')
    output.setparams(parts[0][0])
    for part in parts:
        output.writeframes(part[1])
    output.close()

_DISPLAY_WIDTH = 120
_CHARS_BY_WIDTH = {
    3: b'.',
    4: b'I1: ',
    5: b'0-',
    6: b'ABCDEFGHJKLMNOPQRSTUVWXYZ23456789',
}
_WIDTHS_BY_CHAR = {}
for width, chars in _CHARS_BY_WIDTH.items():
    for char in chars:
        _WIDTHS_BY_CHAR[char] = width

def pixel_width(string):
    width = 0
    for char in string:
        if char not in _WIDTHS_BY_CHAR:
            raise ValueError('unknown width for character "%s"' % char)
        width += _WIDTHS_BY_CHAR[char]
    return width

def fix_right_justification(bytestring):
    if rb'\R' not in bytestring:
        return bytestring
    left_start = 7
    left_end = bytestring.index(rb'\R', left_start)
    right_start = left_end + len(rb'\R')
    right_end = bytestring.index(
        b'\n', right_start
    ) if b'\n' in bytestring[right_start:] else bytestring.index(
        b'\r', right_start)
    left = bytestring[left_start:left_end]
    right = bytestring[right_start:right_end]
    left_width = pixel_width(left)
    right_width = pixel_width(right)
    padding_width = _DISPLAY_WIDTH - 2 - left_width - right_width
    padding = b''
    space_width = _WIDTHS_BY_CHAR[ord(' ')]
    while padding_width >= space_width:
        padding += b' '
        padding_width -= space_width
    while padding_width > 0:
        padding += b'\xff'
        padding_width -= 1
    return bytestring[:left_end] + padding + bytestring[right_start:]

def date(iso):
    return datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=aus_mel)

def break_time(time):
    time = date(time)
    iso_time = str(time)

    hour = time.hour
    minute = time.minute

    hour_offset = int(iso_time[-5:-3])
    hour += hour_offset
    hour %= 24
    if minute < 10:
        minute = '0' + str(minute)
    else:
        minute = str(minute)

    return {
        'hour': str(hour),
        'minute': minute
    }

def format_time(time):
    time = date(time)
    iso_time = str(time)

    hour = time.hour
    minute = time.minute
    hour_offset = int(iso_time[-5:-3])
    hour += hour_offset
    hour %= 12
    if minute < 10:
        minute = '0' + str(minute)
    else:
        minute = str(minute)
    return '{}:{}'.format(str(hour), minute)

def time_diff(iso):
    millis_now = int(round(time.time()))
    other_time = date(iso)
    hour_offset = int(str(other_time)[-5:-3])
    time_millis = other_time.timestamp() + hour_offset * 60 * 60

    millisecond_diff = (time_millis - millis_now)

    return int(millisecond_diff // 60)

def get_stopping_pattern(run_id, is_up, from_stop):
    url = '/v3/pattern/run/{}/route_type/0?expand=stop'.format(run_id)
    pattern_payload = ptv_api(url, dev_id, key)
    departures = pattern_payload['departures']
    stops = pattern_payload['stops']

    departures.sort(key=lambda departure: date(departure['scheduled_departure_utc']))
    stopping_pattern = list(map(lambda departure: stops[str(departure['stop_id'])]['stop_name'], departures))

    if 'Jolimont-MCG' in stopping_pattern:
        stopping_pattern[stopping_pattern.index('Jolimont-MCG')] = 'Jolimont'

    if 'Flinders Street' in stopping_pattern:
        if is_up:
            fss_index = stopping_pattern.index('Flinders Street')
            stopping_pattern = stopping_pattern[0:fss_index + 1]
        else:
            fss_index = stopping_pattern.index('Flinders Street')
            stop_index = stopping_pattern.index(from_stop)
            if fss_index < stop_index:
                stop_index = fss_index
            stopping_pattern = stopping_pattern[stop_index:]

    return stopping_pattern

def transform(departure):
    if departure['route_id'] == 13:
        if departure['stop_id'] == 1073:
            departure['platform_number'] = '3'
        else:
            departure['platform_number'] = '1'

    if 'RRB-RUN' in departure['flags']:
        departure['platform_number'] = 'RRB'

    return departure

def get_next_departure_for_platform(station_name, platform):
    stopGTFSID = stations[station_name]
    url = '/v3/departures/route_type/0/stop/{}?gtfs=true&max_results=5&expand=run&expand=route'.format(stopGTFSID)
    departures_payload = ptv_api(url, dev_id, key)
    if 'departures' not in departures_payload:
        print(departures_payload)
        raise Exception(departures_payload)
    departures = departures_payload['departures']
    runs = departures_payload['runs']
    routes = departures_payload['routes']

    departures = list(map(transform, departures))

    platform_departures = departures
    if platform != 'all':
        platform_departures = list(filter(lambda departure: departure['platform_number'] == platform, departures))
    rrb_departures = list(filter(lambda departure: departure['platform_number'] == 'RRB', departures))

    platform_departures.sort(key=lambda departure: date(departure['scheduled_departure_utc']))

    if len(platform_departures):
        next_departure = platform_departures[0]
        run_data = runs[str(next_departure['run_id'])]
        vehicle_descriptor = run_data['vehicle_descriptor'] or { 'id': None }
        train_descriptor = vehicle_descriptor['id']
        route_name = routes[str(next_departure['route_id'])]['route_name']

        is_up = next_departure['direction_id'] == 1
        if next_departure['route_id'] == '13':
            is_up = next_departure['direction_id'] == 5

        stopping_pattern = get_stopping_pattern(next_departure['run_id'], is_up, station_name)
        stopping_pattern_data = generate_stopping_pattern(route_name, stopping_pattern, is_up, station_name)

        stopping_pattern_info = stopping_pattern_data['text']
        stopping_pattern_audio = stopping_pattern_data['audio']

        stopping_pattern_text = stopping_pattern_info['stopping_pattern']
        stopping_type = stopping_pattern_info['stopping_type']

        scheduled_departure_utc = next_departure['scheduled_departure_utc']
        estimated_departure_utc = next_departure['estimated_departure_utc']

        if time_diff(scheduled_departure_utc) > 420:
            raise Exception('NO TRAINS DEPART_FROM THIS PLATFORM')

        destination = stopping_pattern[-1]

        if generate_audio:
            time_parts = break_time(scheduled_departure_utc)
            write_audio(next_departure['platform_number'], time_parts['hour'], time_parts['minute'], destination, stopping_pattern_audio)

        if is_up and 'Parliament' in stopping_pattern and station_name not in city_loop_stations:
            destination = 'City Loop'

        return {
            "td": train_descriptor,
            "scheduled_departure_utc": scheduled_departure_utc,
            "estimated_departure_utc": estimated_departure_utc,
            "destination": destination,
            "stopping_pattern": stopping_pattern_text,
            "stopping_type": stopping_type
        }

    elif len(rrb_departures):
        raise NoTrains('NO TRAINS OPERATING_REPLACEMENT BUSES|H1^_HAVE BEEN ARRANGED')
    else:
        raise NoTrains('NO TRAINS DEPART_FROM THIS PLATFORM')

def get_pids_data(station_name, platform):
    next_departure = None
    try:
        next_departure = get_next_departure_for_platform(station_name, platform)
    except NoTrains as e:
        data = str(e)
        first_page = data.split('|')[0]
        lines = first_page.split('_')
        top = lines[0]
        bottom = None
        if len(lines) == 2:
            bottom = lines[1]

        return {
            "data": data,
            "type": "manual",
            "top": top,
            "bottom": bottom
        }

    scheduled_departure_utc = next_departure['scheduled_departure_utc']
    estimated_departure_utc = next_departure['estimated_departure_utc']
    destination = next_departure['destination']
    stopping_pattern = next_departure['stopping_pattern']
    stopping_type = next_departure['stopping_type']

    actual_departure_utc = estimated_departure_utc or scheduled_departure_utc

    time_to_departure = time_diff(actual_departure_utc)
    if time_to_departure <= 0:
        time_to_departure = 'NOW'
    else:
        time_to_departure = str(time_to_departure)

    destination = destination.upper()
    if destination == 'FLINDERS STREET':
        destination = 'FLINDERS ST'
    if destination == 'SOUTHERN CROSS':
        destination = 'STHN CROSS'
    if destination == 'UPPER FERNTREE GULLY':
        destination = 'UPPER F.T.G'

    is_all_except = 'All Except' in stopping_pattern

    scheduled_departure = format_time(scheduled_departure_utc)
    bottom_row = stopping_type
    if is_all_except:
        bottom_row = stopping_pattern

    pids_string = 'V20^{} {}~{}_{}'.format(scheduled_departure, destination, time_to_departure, bottom_row)
    if stopping_pattern != 'Stops All Stations' and not is_all_except:
        pids_string += '|H0^_  {}'.format(stopping_pattern)

    msg = DisplayMessage.from_str(pids_string).to_bytes()
    return {
        "data": fix_right_justification(msg),
        "scheduled": scheduled_departure,
        "destination": destination,
        "actual": time_to_departure,
        "pattern": stopping_pattern
    }
