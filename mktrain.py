#!/usr/bin/env python3
"""
Wizard to make a train blueprint for a given Multi-Hop route.
"""
import heapq
import os.path
from typing import Iterable, Sequence, Tuple

import blueprints

PLACES = {
    # Automation ID: Human name
    588: 'Auberge Orbit',
    1151: 'Calidus Outer Belt',
    148: 'Astermore Orbit',
    200: 'Astermore Outer Belt',
    1: 'Foenestra',
}

LINKS = {
    # Clamp/Route Num: (Place ID, Place ID, delta v),
    111: (588, 1151, 2606),
    100: (1151, 200, 10918),
    102: (200, 148, 8620),
    999: (1151, 1, 10464),
}


def produce_graph():
    """
    Generate a traditional digraph from the list of links
    """
    graph = {place: {} for place in PLACES}
    for left, right, deltav in LINKS.values():
        graph[left][right] = deltav
        graph[right][left] = deltav
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
            for route, (left, right, _) in LINKS.items()
        },
        **{
            (right, left): route
            for route, (left, right, _) in LINKS.items()
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


def prompt_for_station(prompt: str) -> str:
    """
    Asks the user for a station name, returns it.
    """
    return input('\n'+prompt)


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


def prompt_for_cargo(prompt: str) -> str:
    """
    Ask the user what cargo the train carries, returns an item name and a normalized name.
    """
    cargo = input('\n'+prompt)
    cargo = cargo.lower().replace(' ', '-')
    pretty_cargo = cargo.replace('-', ' ').title()
    return pretty_cargo, cargo


def icon_list_to_objects(icon_list: Sequence) -> list:
    """
    Generate a list of blueprint icon objects (https://wiki.factorio.com/Blueprint_string_format#Icon_object)

    Args:
        icon_list (Sequence): Icons to make into objects

    Returns:
        list: list of objects
    """
    if isinstance(icon_list, str):
        icon_list = (icon_list,)
    icon_objects = []
    for icon_index, icon in enumerate(icon_list):
        icon_objects.append(
            {
                'index': icon_index + 1,
                'signal': {
                    'name': icon,
                    'type': 'item'
                }
            }
        )
    return icon_objects


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


def schedule_lobby():
    """
    Produce the train stops for a lobby.
    """
    yield {
        'station': '-Lobby',
        'wait_conditions': [
            {
                'compare_type': 'or',
                'ticks': 60,
                'type': 'time',
            },
        ],
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


def schedule_route_hops(hops: Iterable[Tuple[int, int]]):
    """
    Given a list of route numbers, produce the hops.

    This includes all the bookend Lobby stations.
    """
    yield from schedule_lobby()
    for route, dest in hops:
        yield from schedule_ship(route, dest)
        yield from schedule_lobby()


def find_schedule(startname: str, startplace: int, endname: str, endplace: int):
    """
    Given a starting & ending station+place, find a route and produce a schedule
    for it.
    """
    route_there = list(magic_route_finder(startplace, endplace))
    # FIXME: Just reverse route_there
    route_back = list(magic_route_finder(endplace, startplace))

    print("Route:", " -> ".join([
        PLACES[startplace], *[PLACES[p] for _, p in route_there]
    ]))

    yield from schedule_start(startname)
    yield from schedule_route_hops(route_there)
    yield from schedule_end(endname)
    yield from schedule_route_hops(route_back)


def build_blueprint(kind, label, description, schedule, cargo=None):
    """
    Build the actual blueprint schema
    """
    assert kind in ('cargo', 'fluid')
    wagon = f'{kind}-wagon'
    if cargo is None:
        cargo = ['locomotive', wagon]
    cargo_icons = icon_list_to_objects(cargo)
    return {
        'blueprint': {
            'description': description,
            'entities': [
                {
                    'entity_number': 1,
                    'name': 'locomotive',
                    'orientation': 0,
                    'position': {'x': -93, 'y': 180},
                },
                {
                    'entity_number': 2,
                    'inventory': None,
                    'name': wagon,
                    'orientation': 0.5,
                    'position': {'x': -93, 'y': 187},
                },
                {
                    'entity_number': 3,
                    'inventory': None,
                    'name': wagon,
                    'orientation': 0.5,
                    'position': {'x': -93, 'y': 194},
                },
                {
                    'entity_number': 4,
                    'inventory': None,
                    'name': wagon,
                    'orientation': 0.5,
                    'position': {'x': -93, 'y': 201},
                },
                {
                    'entity_number': 5,
                    'inventory': None,
                    'name': wagon,
                    'orientation': 0.5,
                    'position': {'x': -93, 'y': 208},
                },
                {
                    'entity_number': 6,
                    'name': 'locomotive',
                    'orientation': 0.5,
                    'position': {'x': -93, 'y': 215},
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
            'version': 281479274823680,
        }
    }


def main():
    kind = prompt_for_kind('Kind of train: ')
    pretty_cargo, cargo = prompt_for_cargo('What are we carrying? ')
    starting_station = prompt_for_station('Pickup Station: ')
    starting_place = prompt_for_place('Pickup Place: ')
    ending_station = prompt_for_station('Dropoff Station: ')
    ending_place = prompt_for_place('Dropoff Place: ')

    print(f'\nMoving {pretty_cargo} ({cargo})')

    schedule = find_schedule(
        starting_station, starting_place, ending_station, ending_place)

    description = f"""{pretty_cargo} from {PLACES[starting_place]} to {PLACES[ending_place]}"""
    bp = build_blueprint(
        kind, f"{pretty_cargo} to {PLACES[ending_place]}", description, schedule, cargo)
    print("")
    print(blueprints.dumps(bp))
    blueprints.dump(bp, os.path.join('json', f'{cargo}.json'))


if __name__ == '__main__':
    main()
