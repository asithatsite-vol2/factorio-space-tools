#!/usr/bin/env python3
"""
Wizard to make a train blueprint for a given Multi-Hop route.
"""
import heapq
import os.path
import struct
import sys
from csv import DictReader
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pyperclip
from colorhash import ColorHash

import blueprints
import colors

FACTORIO_VERSION = int.from_bytes(
    struct.pack('<HHHH',
                1, 1, 49, 0
                ),
    byteorder='little',
    signed=False)


PLACES = {
    # Automation ID: Human name
    587: 'Auberge',
    588: 'Auberge Orbit',
    1151: 'Calidus Outer Belt',
    148: 'Astermore Orbit',
    200: 'Astermore Outer Belt',
    1: 'Foenestra',
    1139: 'Mara',
    1112: 'Darkflare',
    564: 'Calidus Orbit',
    1147: 'Njord',
    159: 'Ezra',
    160: 'Ezra Orbit',
    585: 'Magaera',
    586: 'Magaera Orbit',
}


MHL_LINKS = {
    # Clamp/Route Num: (Place ID, Place ID, delta v),
    111: (588, 1151, 2606),
    100: (1151, 200, 10918),
    102: (200, 148, 8620),
    999: (1151, 1, 10464),
    115: (1139, 1151, 6390),
    998: (1, 1112, 10000),
    120: (588, 564, 7711),
    119: (564, 1151, 8817),
    118: (588, 1147, 850),
    101: (200, 160, 6977),
    112: (1151, 586, 3006),
    113: (588, 586, 400),
}

ELEVATORS = [
    # (name, bottom ID, top ID)
    ('Auberge', 587, 588),
    ('Ezra', 159, 160),
    ('Magaera', 585, 586),
]


COLORS = {place: ColorHash(f'{id}: {place}') for id, place in PLACES.items()}


def produce_graph():
    """
    Generate a traditional digraph from the list of links
    """
    graph = {place: {} for place in PLACES}
    for left, right, deltav in MHL_LINKS.values():
        graph[left][right] = deltav
        graph[right][left] = deltav
    for _, bottom, top in ELEVATORS:
        graph[bottom][top] = 50
        graph[top][bottom] = 50
    return graph


def dijkstra(graph, node):
    # Pulled from https://medium.com/nerd-for-tech/graph-traversal-in-python-bfs-dfs-dijkstra-a-star-parallel-comparision-dd4132ec323a
    # Honestly, not sure this was a good life choice
    # Graph is {node id: {linked node id: weight}}
    # node is the starting place
    distances = {node: float('inf') for node in graph}
    distances[node] = 0
    came_from = {node: None for node in graph}
    queue = [(0, node)]

    while queue:
        current_distance, current_node = heapq.heappop(queue)
        # relaxation
        for next_node, weight in graph[current_node].items():
            distance_temp = current_distance + weight
            if distance_temp < distances[next_node]:
                distances[next_node] = distance_temp
                came_from[next_node] = current_node
                heapq.heappush(queue, (distance_temp, next_node))
    return distances, came_from


def _dijkstra_route(starting: int, ending: int):
    """
    Produces a sequence of place IDs going from ending to starting.

    Yes this is backwards. Deal with it.
    """
    _, came_from = dijkstra(produce_graph(), starting)
    step = ending
    while step != starting:
        yield step
        step = came_from[step]
    yield step


def magic_route_finder(starting: int, ending: int) -> Iterable[Tuple[int, int]]:
    """
    Produces a sequence of (route ID, place ID) that'll get you from starting to
    ending.
    """
    link_index = {
        **{
            (left, right): route
            for route, (left, right, _) in MHL_LINKS.items()
        },
        **{
            (right, left): route
            for route, (left, right, _) in MHL_LINKS.items()
        },
        **{
            (top, bottom): 'elevator'
            for _, bottom, top in ELEVATORS
        },
        **{
            (bottom, top): 'elevator'
            for _, bottom, top in ELEVATORS
        },
    }
    route = list(_dijkstra_route(starting, ending))
    route.reverse()
    steps = [route[i:i+2] for i in range(len(route) - 1)]
    for start, end in steps:
        yield link_index[start, end], end


def prompt_for_place(prompt: str) -> int:
    """
    Ask the user to pick a place, returns the place ID
    """
    print('')
    for num, name in PLACES.items():
        print(f"{num}: {name}")
    while True:
        txt = input(prompt)
        try:
            num = int(txt)
        except ValueError:
            print("Must be integer")
            continue
        else:
            if num not in PLACES:
                print("Must be one of the places")
                continue
            else:
                return num


def prompt_for_station(prompt: str, default: str = '') -> str:
    """
    Asks the user for a station name, returns it.
    """
    station = input(f'\n{prompt}[{default}] ')
    if len(station) > 0:
        return station
    else:
        return default


def prompt_for_kind(prompt: str) -> str:
    """
    Ask the user if they want solids or liquids, returns either 'cargo' or 'fluid'.
    """
    while True:
        kind = input('\n'+prompt)
        if kind in ('cargo', 'fluid'):
            return kind
        else:
            print("Must be 'cargo' or 'fluid'")


def prompt_for_cargo(prompt: str) -> tuple[list, list]:
    """
    Ask the user what cargo the train carries, returns item names
    """
    input_cargo = input('\n'+prompt).split(',')
    cargo = []
    for item in input_cargo:
        item = item.strip().lower().replace(' ', '-')
        cargo.append(item)
    return cargo


def make_pretty_cargo(cargo: Sequence[str]) -> List[str]:
    """
    Make a list of human-readable cargo names based on item strings

    Args:
        cargo (Sequence[str]): strings of cargo as Factorio item names

    Returns:
        List[str]: same strings in titlecase, without prefixes, and with spaces instead of dashes
    """
    pretty_cargo = []
    DROP_PREFIXES = ('aai-', 'se-')
    for item in cargo:
        for prefix in DROP_PREFIXES:
            item = item.replace(prefix, '')
        pretty_item = item.replace('-', ' ').title()
        pretty_cargo.append(pretty_item)
    return pretty_cargo


def icon_list_to_objects(icon_list: Sequence, kind: str) -> list:
    """
    Generate a list of blueprint icon objects (https://wiki.factorio.com/Blueprint_string_format#Icon_object)

    Args:
        icon_list (Sequence): Icons to make into objects

    Returns:
        list: list of objects
    """
    if kind == 'cargo':
        kind = 'item'
    elif kind != 'fluid':
        kind = 'virtual'
    if isinstance(icon_list, str):
        icon_list = (icon_list,)
    icon_objects = []
    for icon_index, icon in enumerate(icon_list):
        icon_objects.append(
            {
                'index': icon_index + 1,
                'signal': {
                    'name': icon,
                    'type': kind
                }
            }
        )
    return icon_objects


def get_route_list(schedule: Sequence) -> list:
    """
    Generate a list of pretty route numbers

    Args:
        schedule (Sequence): schedule

    Returns:
        list: list of routes taken
    """
    routes = []
    for station in schedule:
        name = station['station']
        if 'Boarding' in name:
            continue
        elif 'se-space-elevator' in name:
            if 'Elevator' not in routes:
                routes.append('Elevator')
        elif 'Rt' in name:
            route = f'Route {name[2:]}'
            if route not in routes:
                routes.append(route)
    return routes


def make_grammar_list(items: Sequence[str]) -> str:
    """
    Make a grammatically-correct string from a list of strings

    Args:
        items (Sequence[str]): list of strings

    Returns:
        str: grammatically-correct string of strings in list
    """
    if len(items) == 0:
        return ''
    elif len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return ' and '.join(items)
    else:
        return ', '.join(items[:-1]) + ', and ' + items[-1]


def make_bullet_list(items: Sequence[str]) -> str:
    if len(items) == 0:
        return ''
    else:
        return '* ' + '\n* '.join(items)


def make_description(cargo: Sequence[str], source: str, destination: str, schedule: Sequence) -> str:
    routes = make_grammar_list(get_route_list(schedule))
    if len(cargo) > 3:
        return f'From {source} to {destination} via {routes}:\n{make_bullet_list(cargo)}'
    else:
        return f"""{make_grammar_list(cargo)} from {source} to {destination} via {routes}"""


def make_label(cargo: Sequence[str], destination: str) -> str:
    if len(cargo) > 3:
        WORDS = {}
        for item in cargo:
            for word in item.split(' '):
                if word not in WORDS.keys():
                    WORDS[word] = 1
                else:
                    WORDS[word] += 1
        best_word = max(WORDS, key=WORDS.get)
        return f'{best_word} misc. to {destination}'
    else:
        return f"{make_grammar_list(cargo)} to {destination}"


def schedule_start(name: str):
    """
    Produce the train stops for pickup
    """
    yield {
        'station': name,
        'wait_conditions': [
            {'compare_type': 'or', 'type': 'full'},
        ],
    }


def schedule_end(name: str):
    """
    Produce the train stops for drop off.
    """
    yield {
        'station': name,
        'wait_conditions': [
            {'compare_type': 'or', 'type': 'empty'},
        ]
    }


def schedule_lobby(delay: int = 60) -> Dict[str, Any]:
    """
    Produce the train stops for a lobby.

    Args:
        delay (int, optional): waiting time at lobby in ticks.. Defaults to 60(1s).

    Yields:
        Dict[str,Any]: station JSON object
    """
    yield {
        'station': '-Lobby',
        'wait_conditions': [
            {
                'compare_type': 'or',
                'ticks': delay,
                'type': 'time',
            },
        ] if delay else [],
    }


def schedule_ship(route: int, dest: int):
    """
    Produce the train stops for a ship traversal.
    """

    yield {'station': f'Boarding Rt{route}'}
    yield {
        'station': f'Rt{route}',
        'wait_conditions': [
            {
                'compare_type': 'or',
                'condition': {
                    'comparator': '=',
                    'constant': dest,
                    'first_signal': {'name': 'signal-A', 'type': 'virtual'},
                },
                'type': 'circuit',
            },
        ],
    }


def schedule_elevator_ascent(name: str) -> Iterable[Dict[str, str]]:
    """
    Produce the train stops for an elevator ascent

    Args:
        name (str): surface with the elevator

    Yields:
        Dict[str,str]: schedule stops
    """
    yield {'station': f'[img=entity/se-space-elevator]  {name} ↑'}


def schedule_elevator_descent(name: str) -> Iterable[Dict[str, str]]:
    """
    Produce the train stops for an elevator descent

    Args:
        name (str): surface with the elevator

    Yields:
        Dict[str,str]: schedule stops
    """
    yield {'station': f'[img=entity/se-space-elevator]  {name} ↓'}


def schedule_elevator(dest) -> Iterable[Dict[str, str]]:
    """
    Produce the train stops for an elevator traversal.

    Args:
        dest (int): surface with the elevator

    Yields:
        Dict[str,str]: schedule stops
    """
    for name, bottom, top in ELEVATORS:
        if bottom == dest:
            yield from schedule_elevator_descent(name)
            return
        elif top == dest:
            yield from schedule_elevator_ascent(name)
            return
    else:
        assert False, f"Can't find the elevator for {dest} anymore???"


def schedule_route_hops(hops: Iterable[Tuple[int, int]]):
    """
    Given a list of route numbers, produce the hops.

    This includes all the bookend Lobby stations.
    """
    for i, (route, dest) in enumerate(hops):
        if i == 0 and route != 'elevator':
            yield from schedule_lobby()
        if route == 'elevator':
            yield from schedule_elevator(dest)
            yield from schedule_lobby(delay=0)
        else:
            yield from schedule_ship(route, dest)
            yield from schedule_lobby()


def find_schedule(startname: str, startplace: int, endname: str, endplace: int):
    """
    Given a starting & ending station+place, find a route and produce a schedule
    for it.
    """
    route_there = list(magic_route_finder(startplace, endplace))
    route_back = list(magic_route_finder(endplace, startplace))

    print("Route:", " -> ".join([
        PLACES[startplace], *[f"{PLACES[p]} ({rt})" for rt, p in route_there]
    ]))

    yield from schedule_start(startname)
    yield from schedule_route_hops(route_there)
    yield from schedule_end(endname)
    yield from schedule_route_hops(route_back)


def build_blueprint(kind, schedule, source, destination, cargo=None, pretty_cargo=None, color=None):
    """
    Build the actual blueprint schema
    """
    assert kind in ('cargo', 'fluid')
    wagon = f'{kind}-wagon'
    if cargo is None:
        cargo = ['locomotive', wagon]
    if pretty_cargo is None:
        pretty_cargo = make_pretty_cargo(cargo)
    cargo_icons = icon_list_to_objects(cargo, kind)[:4]
    if color is None:
        r, g, b = (1, 1, 1)
    else:
        r, g, b = colors.colorhash_to_srgb(color).get_value_tuple()

    label = make_label(pretty_cargo, destination)
    description = make_description(pretty_cargo, source, destination, schedule)
    return {
        'blueprint': {
            'description': description,
            'entities': [
                {
                    'entity_number': 1,
                    'name': 'locomotive',
                    'orientation': 0.75,
                    'position': {'x': -381.99609375, 'y': -81},
                    'color': {'r': r, 'g': g, 'b': b, 'a': 0.49803921580314636},
                },
                {
                    'entity_number': 2,
                    'inventory': None,
                    'name': wagon,
                    'orientation': 0.25,
                    'position': {'x': -374.99609375, 'y': -81},
                },
                {
                    'entity_number': 3,
                    'inventory': None,
                    'name': wagon,
                    'orientation': 0.25,
                    'position': {'x': -367.99609375, 'y': -81},
                },
                {
                    'entity_number': 4,
                    'inventory': None,
                    'name': wagon,
                    'orientation': 0.25,
                    'position': {'x': -360.99609375, 'y': -81},
                },
                {
                    'entity_number': 5,
                    'inventory': None,
                    'name': wagon,
                    'orientation': 0.25,
                    'position': {'x': -353.99609375, 'y': -81},
                },
                {
                    'entity_number': 6,
                    'name': 'locomotive',
                    'orientation': 0.25,
                    'position': {'x': -346.99609375, 'y': -81},
                    'color': {'r': r, 'g': g, 'b': b, 'a': 0.49803921580314636},
                },
            ],
            'icons': cargo_icons,
            'item': 'blueprint',
            'label': label,
            'schedules': [
                {
                    'locomotives': [1, 6],
                    'schedule': [*schedule],
                },
            ],
            'version': FACTORIO_VERSION,
        }
    }


def main(kind=None, cargo=None,
         starting_station=None, starting_place=None,
         ending_station=None, ending_place=None,
         copy=True):
    if kind is None:
        kind = prompt_for_kind('Kind of train: ')
    if cargo is None:
        cargo = prompt_for_cargo('What are we carrying? ')
    pretty_cargo = make_pretty_cargo(cargo)
    if starting_station is None:
        starting_station = prompt_for_station(
            'Pickup Station: ', f'{pretty_cargo[0]} Pickup')
    if starting_place is None:
        starting_place = prompt_for_place('Pickup Place: ')
    if ending_station is None:
        ending_station = prompt_for_station(
            'Dropoff Station: ', f'{pretty_cargo[0]} Drop')
    if ending_place is None:
        ending_place = prompt_for_place('Dropoff Place: ')

    print(f'\nMoving {pretty_cargo} ({cargo})')

    schedule = list(find_schedule(
        starting_station, starting_place, ending_station, ending_place))

    bp = build_blueprint(kind, schedule, PLACES[starting_place],
                         PLACES[ending_place], cargo, pretty_cargo, COLORS[PLACES[ending_place]])
    print("")

    if copy:
        bp_string = blueprints.dumps(bp)
        print(bp_string)

        pyperclip.copy(bp_string)
        print("")
        print("Copied to clipboard")

    blueprints.dump(bp, os.path.join(
        'json', PLACES[ending_place], f'{ending_station}.json'))
    return bp


if __name__ == '__main__':
    if len(sys.argv) > 1:
        csvfile = sys.argv[1]
        with open(csvfile) as f:
            surfaces = {}
            mhl_book = {
                'blueprint_book':
                {
                    'item': 'blueprint-book',
                    'label': 'Multi-Hop Logistics Trains',
                    'description': 'Multi-Hop Trains generated by https://github.com/AstraLuma/factorio-space-tools mktrain.py',
                    'active_index': 0,
                    'version': FACTORIO_VERSION,
                    'blueprints': []
                }
            }
            for row in DictReader(f):
                if row['Manual?'] == "Yes":
                    continue
                if row['End Place'] not in surfaces.keys():
                    index = len(mhl_book['blueprint_book']['blueprints'])
                    surfaces[row['End Place']] = index
                    mhl_book['blueprint_book']['blueprints'].append(
                        {
                            'index': index,
                            'blueprint_book':
                            {
                                'item': 'blueprint-book',
                                'label': f'To {row["End Place"]}',
                                'description': f'Trains destined for {row["End Place"]}',
                                'active_index': 0,
                                'version': FACTORIO_VERSION,
                                'blueprints': []
                            }
                        }
                    )
                book = mhl_book['blueprint_book']['blueprints'][surfaces[row['End Place']]
                                                                ]['blueprint_book']

                train = main(
                    kind=row['Kind'],
                    cargo=[c.strip().lower().replace(' ', '-')
                           for c in row['Cargo'].split(',')],
                    starting_station=row['Start Station'],
                    starting_place=int(row['Start ID']),
                    ending_station=row['End Station'],
                    ending_place=int(row['End ID'])
                )
                train['index'] = len(book['blueprints'])
                book['blueprints'].append(train)
            bp_string = blueprints.dumps(mhl_book)
            print(bp_string)

            pyperclip.copy(bp_string)

            print("")
            print("Copied to clipboard")
            blueprints.dump(mhl_book, os.path.join('json', 'mhl_book.json'))
    else:
        main()
