"""Per-input timestamp metadata. Never infer it from the rendering machine."""
import json
import math
from pathlib import Path


def validate_timestamp_hz(value):
    if isinstance(value, bool):
        raise ValueError('timestamp_hz must be a positive finite ticks-per-second value')
    try:
        hz = float(value)
    except (TypeError, ValueError):
        raise ValueError('timestamp_hz must be a positive finite ticks-per-second value') from None
    if not math.isfinite(hz) or hz <= 0:
        raise ValueError('timestamp_hz must be a positive finite ticks-per-second value')
    return hz


def clock_path(database):
    return Path(str(database)+'.clock.json')


def read_clock(database):
    path = clock_path(database)
    if not path.exists():
        return {'timestamp_hz': None, 'source': 'unknown', 'display_unit': 'ticks'}
    data = json.loads(path.read_text())
    return {'timestamp_hz': validate_timestamp_hz(data['timestamp_hz']),
            'source': data.get('source','trace metadata'), 'display_unit': 'seconds'}
