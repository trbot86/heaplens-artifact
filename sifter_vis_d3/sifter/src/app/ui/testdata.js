import * as d3 from 'd3';

export const testLegendData = {
    colourOfType: {
        'int': d3.color('red'),
        'char': d3.color('blue'),
        'LongTypeName<WithLongTemplateArguments>': d3.color('green'),
        'node_t<long, void*>': d3.color('yellow'),
        'test1': d3.color('pink'),
        'test2': d3.color('orange'),
        'test3': d3.color('purple')
    },
    typeStats: {
        'int': {allocs: 10, pages: 1},
        'char': {allocs: 50, pages: 12},
        'LongTypeName<WithLongTemplateArguments>': {allocs: 24234, pages: 231},
        'node_t<long, void*>': {allocs: 50563457, pages: 15564},
        'test1': {allocs: 244, pages: 21},
        'test2': {allocs: 34, pages: 31},
        'test3': {allocs: 24235, pages: 232}
    }
};