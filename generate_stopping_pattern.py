import json
import os

__dirname = os.path.dirname(os.path.realpath(__file__))
lines = json.load(open(__dirname + '/lines.json', 'r'))

northern_group = [
'Craigieburn',
'Sunbury',
'Upfield',
'Werribee',
'Williamstown',
'Showgrounds/Flemington'
]

cross_city_group = [
'Werribee',
'Williamstown',
'Frankston'
]

gippsland_lines = [
'Bairnsdale',
'Traralgon'
]

city_loop_stations = [
'Southern Cross',
'Parliament',
'Flagstaff',
'Melbourne Central'
]

def get_route_stops(route_name):
    if route_name in ['Pakenham', 'Traralgon', 'Bairnsdale']:
        return lines['Gippsland']
    if route_name == 'Cranbourne':
        return lines['Cranbourne']
    if route_name == 'Belgrave':
        return lines['Belgrave']
    if route_name == 'Lilydale':
        return lines['Lilydale']
    if route_name == 'Alamein':
        return lines['Alamein']
    if route_name in ['Craigieburn', 'Seymour', 'Shepparton']:
        return lines['Shepparton']
    if route_name == 'Albury':
        return lines['Albury']
    if route_name == 'Maryborough':
        return lines['Maryborough']
    if route_name in ['Ballarat', 'Ararat']:
        return lines['Ararat']
    if route_name in ['Geelong', 'Warrnambool']:
        return lines['Warrnambool']
    if route_name == 'Werribee':
        return lines['Werribee']
    if route_name == 'Williamstown':
        return lines['Williamstown']
    if route_name == 'Sandringham':
        return lines['Sandringham']
    if route_name == 'Upfield':
        return lines['Upfield']
    if route_name in ['Frankston', 'Stony Point']:
        return lines['Stony Point']
    if route_name in ['Sunbury', 'Bendigo', 'Echuca']:
        return lines['Echuca']
    if route_name == 'Swan Hill':
        return lines['Swan Hill']
    if route_name == 'Glen Waverley':
        return lines['Glen Waverley']
    if route_name == 'Mernda':
        return lines['Mernda']
    if route_name == 'Hurstbridge':
        return lines['Hurstbridge']

def get_express_sections(stopping_pattern, relevant_stops):
    express_parts = []

    last_main_match = 0

    for scheduled_stop in stopping_pattern:
        match_index = -1
        for stop in relevant_stops:
            match_index += 1
            if stop == scheduled_stop:
                if match_index != last_main_match:
                    express_part = relevant_stops[last_main_match:match_index]
                    express_parts.append(express_part)
                last_main_match = match_index + 1
                break

    return express_parts

def generate_stopping_pattern(route_name, stopping_pattern, is_up, from_stop):
    route_stops = get_route_stops(route_name).copy()

    if is_up:
        route_stops.reverse()

    via_city_loop = 'Parliament' in stopping_pattern or 'Flagstaff' in stopping_pattern
    if via_city_loop:
        city_loop_stops = list(filter(lambda stop: stop in city_loop_stations, stopping_pattern))
        route_stops = list(filter(lambda stop: stop not in city_loop_stations, route_stops))

        if is_up:
            route_stops = route_stops[:-1] + city_loop_stops + ['Flinders Street']
        else:
            route_stops = ['Flinders Street'] + city_loop_stops + route_stops[1:]
    else:
        route_stops = list(filter(lambda stop: stop not in city_loop_stations, route_stops))
        if route_name in northern_group:
            if is_up:
                route_stops = route_stops[:-1] + ['Southern Cross', 'Flinders Street']
            else:
                route_stops = ['Flinders Street', 'Southern Cross'] + route_stops[1:]

    start_index = stopping_pattern.index(from_stop)
    stopping_pattern = stopping_pattern[start_index:]

    via_city_loop = 'Parliament' in stopping_pattern or 'Flagstaff' in stopping_pattern
    via_fss = not is_up and 'Flinders Street' in stopping_pattern and from_stop != 'Flinders Street'

    relevant_stops = route_stops[route_stops.index(stopping_pattern[0]):route_stops.index(stopping_pattern[-1]) + 1]
    express_parts = get_express_sections(stopping_pattern, relevant_stops)

    destination = stopping_pattern[-1]

    if len(express_parts) == 0:
        stopping_pattern = 'Stops All Stations'
        if via_city_loop and from_stop == 'Flinders Street':
            stopping_pattern += ' via City Loop'
        elif via_fss:
            stopping_pattern += ' via Flinders Street'
        return {
            "stopping_pattern": stopping_pattern,
            "stopping_type": 'Stops All Stations'
        }
    if len(express_parts) == 1 and len(express_parts[0]) == 1:
        stopping_pattern = 'Stops All Stations Except {}'.format(express_parts[0][0])
        stopping_type = 'All Except {}'.format(express_parts[0][0])
        if via_city_loop and from_stop == 'Flinders Street':
            stopping_pattern += ' via City Loop'
        elif via_fss:
            stopping_pattern += ' via Flinders Street'
        else:
            stopping_pattern = stopping_type
        return {
            "stopping_pattern": stopping_pattern,
            "stopping_type": stopping_type
        }

    last_stop = None
    texts = []

    express_count = 0

    for (i, express_sector) in enumerate(express_parts):
        express_count += len(express_sector)

        first_express_stop = express_sector[0]
        last_express_stop = express_sector[-1]

        prev_stop = relevant_stops[relevant_stops.index(first_express_stop) - 1]
        next_stop = relevant_stops[relevant_stops.index(last_express_stop) + 1]

        if last_stop:
            if i == len(express_parts) - 1 and next_stop == destination:
                texts.append('then Runs Express from {} to {}'.format(prev_stop, next_stop))
            elif last_stop == prev_stop:
                texts.append('{} to {}'.format(prev_stop, next_stop))
            else:
                texts.append('Stops All Stations from {} to {}'.format(last_stop, prev_stop))
                texts.append('Runs Express from {} to {}'.format(prev_stop, next_stop))
        else:
            if from_stop == prev_stop:
                texts.append('Runs Express to {}'.format(next_stop))
            else:
                texts.append('Stops All Stations to {}'.format(prev_stop))
                texts.append('Runs Express from {} to {}'.format(prev_stop, next_stop))

        last_stop = next_stop

    if relevant_stops[relevant_stops.index(last_stop) + 1] != destination:
        texts.append('then Stops All Stations to {}'.format(destination))

    joined = ', '.join(texts)
    if via_city_loop and from_stop == 'Flinders Street':
        joined += ' via City Loop'
    elif via_fss:
        joined += ' via Flinders Street'

    stoppingType = ''

    if express_count == 0:
        stoppingType = 'Stops All Stations'
    elif express_count < 5:
        stoppingType = 'Limited Express'
    else:
        stoppingType = 'Express Service'

    return {
        "stopping_pattern": joined,
        "stopping_type": stoppingType
    }
