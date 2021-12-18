"""
Tools to load and dump factorio blueprints.
"""
import base64
import json
import os
import os.path
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
