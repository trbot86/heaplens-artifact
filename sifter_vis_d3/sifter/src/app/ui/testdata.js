import * as d3 from 'd3';

export const testColourOfType = {
    'int': d3.color('red'),
    'char': d3.color('blue'),
    'LongTypeName<WithLongTemplateArguments>': d3.color('green'),
    'node_t<long, void*>': d3.color('yellow'),
    'test1': d3.color('pink'),
    'test2': d3.color('orange'),
    'test3': d3.color('purple')
};

export const testTypeStats = {
    'int': {allocs: 10, pages: 1},
    'char': {allocs: 50, pages: 12},
    'LongTypeName<WithLongTemplateArguments>': {allocs: 24234, pages: 231},
    'node_t<long, void*>': {allocs: 50563457, pages: 15564},
    'test1': {allocs: 244, pages: 21},
    'test2': {allocs: 34, pages: 31},
    'test3': {allocs: 24235, pages: 232}
};

export const testPageData = {
    0: {
        events: [
            {file: 'a.cpp', line: 0, size: 32, address: 128, allocTs: 223, freeTs: 491, type: 'node_t<long, void*>'},
            {file: 'a.cpp', line: 0, size: 32, address: 192, allocTs: 226, freeTs: 512, type: 'node_t<long, void*>'},
            {file: 'a.cpp', line: 0, size: 32, address: 256, allocTs: 250, freeTs: 521, type: 'node_t<long, void*>'},
            {file: 'a.cpp', line: 0, size: 32, address: 320, allocTs: 310, freeTs: 551, type: 'node_t<long, void*>'}
        ],
        cluster: 0
    },
    4096: {
        events: [
            {file: 'a.cpp', line: 0, size: 8, address: 4096, allocTs: 223, freeTs: 491, type: 'int'},
            {file: 'a.cpp', line: 0, size: 8, address: 6144, allocTs: 226, freeTs: 512, type: 'int'},
            {file: 'a.cpp', line: 0, size: 16, address: 5928, allocTs: 250, freeTs: 521, type: 'test1'},
            {file: 'a.cpp', line: 0, size: 16, address: 5516, allocTs: 310, freeTs: 551, type: 'test2'}
        ],
        cluster: 1
    },
    8192: {
        events: [
            {file: 'a.cpp', line: 0, size: 32, address: 8320, allocTs: 223, freeTs: 300, type: 'node_t<long, void*>'},
            {file: 'a.cpp', line: 0, size: 32, address: 8320, allocTs: 320, freeTs: 400, type: 'node_t<long, void*>'},
            {file: 'a.cpp', line: 0, size: 32, address: 8320, allocTs: 450, freeTs: 521, type: 'node_t<long, void*>'},
            {file: 'a.cpp', line: 0, size: 32, address: 8320, allocTs: 600, freeTs: 651, type: 'node_t<long, void*>'}
        ],
        cluster: 0
    }
};

export const testPerfData = {
    128: {
        hitm: 4.5,
        accesses: 25
    },
    8320: {
        hitm: 9.2,
        accesses: 51
    }
}

export const testLineData = {
    'node_t<long, void*>': [
        {ts: 223, size: 64}, {ts: 226, size: 96}, {ts: 250, size: 128},
        {ts: 300, size: 96}, {ts: 310, size: 128}, {ts: 320, size: 160},
        {ts: 400, size: 128}, {ts: 450, size: 160}, {ts: 491, size: 128},
        {ts: 512, size: 96}, {ts: 521, size: 32}, {ts: 551, size: 0},
        {ts: 600, size: 32}, {ts: 651, size: 0}
    ],
    'test1': [
        {ts: 250, size: 16}, {ts: 521, size: 0}
    ],
    'test2': [
        {ts: 310, size: 16}, {ts: 551, size: 16}
    ],
    'int': [
        {ts: 223, size: 8}, {ts: 226, size: 16}, {ts: 491, size: 8}, {ts: 512, size: 0}
    ]
};

export const testMaxPointsPerLine = 50;

export const testCacheInfo = [
    {name: 'L1', size: 32768, assoc: 8},
    {name: 'L2', size: 2097152, assoc: 8},
    {name: 'L3', size: 4194304, assoc: 8}
];