"""Placement shared by the portable drivers and their independent checks."""
import json
import os
from pathlib import Path


def configuration():
    return json.loads(Path(os.environ.get('HL_TOPOLOGY', '/campaign/work/topology.json')).read_text())


def node(index):
    return configuration()['nodes'][index]['node']


def cpus(count, index=0):
    values = configuration()['nodes'][index]['cpus'][:count]
    if len(values) != count:
        raise ValueError('Insufficient physical cores; workload is never silently downsized')
    return ','.join(map(str, values))


def rocks_nodes():
    return [entry['node'] for entry in configuration()['nodes']]


def rocks_cpus():
    values = configuration()['rocks_cpus']
    if len(values) != 96:
        raise ValueError('HSL requires 96 allowed CPUs across the selected nodes')
    return ','.join(map(str, values))


def host_name():
    return os.environ['HL_HOST']


def expected_traces(families):
    config=json.loads(Path('/campaign/work/configuration.json').read_text())
    return sum(cell['arm']=='logging' and cell['family'] in families for cell in config['plan'])
