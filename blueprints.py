"""
Tools to load and dump factorio blueprints.
"""
import base64
import json
import os
import os.path
from typing import Dict
import zlib


def loads(blob: str):
    """
    Given a blueprint string, parse it into a JSON structure
    """
    if isinstance(blob, str):
        blob = blob.encode('ascii')
    ver, data = blob[0:1], blob[1:]
    assert ver == b'0'
    compressed = base64.b64decode(data)
    txt = zlib.decompress(compressed)
    return json.loads(txt.decode('utf-8'))


def dumps(data: dict):
    """
    Given a JSON structure, dump into a blueprint string.
    """
    # Thanks agmlego
    json_str = json.dumps(
        data,
        separators=(',', ':'),
        ensure_ascii=False
    ).encode('utf8')
    compressed = zlib.compress(json_str, 9)
    encoded = base64.b64encode(compressed)
    return '0' + encoded.decode('ascii')


def dump(data: dict, filename: str):
    """
    Write the structure to a JSON file for inspection

    Args:
        data (dict): blueprint structure
        filename (str): file to create
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
def histogram(data: dict) -> Dict[str,int]:
    """
    Make a histogram of the items in a blueprint.

    Args:
        data (dict): blueprint structure

    Returns:
        Dict[str,int]: histogram of item:count
    """
    items = {}
    if 'blueprint_book' in data:
        items.update(_book_histogram(data['blueprint_book'],items))
    elif 'blueprint' in data:
        items.update(_blueprint_histogram(data['blueprint'],items))
    
    return items

def _book_histogram(data: dict, items:Dict[str,int]=None) -> Dict[str,int]:
    if items is None:
        items = {}
    
    for blueprint in data['blueprints']:
        if 'blueprint_book' in blueprint:
            items.update(_book_histogram(blueprint['blueprint_book'],items))
        elif 'blueprint' in blueprint:
            items.update(_blueprint_histogram(blueprint['blueprint'],items))

    return items

def _blueprint_histogram(data: dict, items:Dict[str,int]=None) -> Dict[str,int]:
    if items is None:
        items = {}

    if 'entities' in data:
        for entity in data['entities']:
            if entity['name'] not in items:
                items[entity['name']] = 0
            items[entity['name']] += 1
    if 'tiles' in data:
        for tile in data['tiles']:
            if tile['name'] not in items:
                items[tile['name']] = 0
            items[tile['name']] += 1

    return items