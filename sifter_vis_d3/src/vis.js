import * as d3 from 'd3';
import legendLayout from './legend.js';
import cacheSetLayout from './cacheSetLayout.js';
import pageLayout from './pageLayout.js';
import timeGraphLayout from './timeGraphLayout.js';

/* TODO:
    *   Add ability to 'zoom in' to individual panels */

export const colourOfType = {};

function binarySearchSuccessor(arr, v, start=undefined, end=undefined) {
    if (!arr || arr[arr.length - 1] < v) return null;
    if (start == undefined) {
        start = 0;
        end = arr.length - 1;
    }

    if (end - start <= 1) {
        return arr[start] > v ? arr[start] : arr[end];
    }

    let mid = Math.floor((start + end) / 2);
    if (v > arr[mid]) {
        return binarySearchSuccessor(arr, v, mid + 1, end);
    }
    else {
        return binarySearchSuccessor(arr, v, start, mid);
    }
}

class MainVisualization {
    #initTs;
    #graphLayout;
    #timeGraphChart;
    #typesToShowOnGraph;
    #tsToIndexMap;
    #data;
    #zoomed;
    #zoomTs;

    constructor(data) {
        console.log('Number of records in input: ', data['records'].length);
        const types = [...new Set(data['records'].map((rec) => rec.type))];
        const colScale = d3.scaleSequential()
                            .domain([0, types.length])
                            .interpolator(d3.interpolateRainbow);
        let col = 0;
        for (let type of types) {
            colourOfType[type] = colScale(col);
            col++;
        }

        this.#data = data;
        this.#zoomed = false;
        this.#zoomTs = {'startTs': 0, 'endTs': 0};
        this.#typesToShowOnGraph = types.reduce((acc, curr) => {
            acc[curr] = true;
            return acc
        }, {});
        this.#tsToIndexMap = types.reduce((acc, curr) => {
            acc[curr] = data['pts'][curr].reduce((tsmap, elem, i) => {
                tsmap[elem.ts] = i + 1;
                return tsmap;
            }, {});
            return acc;
        }, {});



        // const changeTs = types.reduce((chMap, type) => {
        //     if (data['changes'][type]) {
        //         chMap[type] = data['changes'][type].map((d) => data['pts'][type][d - 1]);
        //     }
        //     return chMap;
        // }, {});

        // console.log(data['pts']);
        // console.log(data['changes']);
        // console.log(this.#tsToIndexMap);
        
        // delete data['pts']['gstats_t::gstats_thread_data'];
        this.createNewGraphLayoutElement();

        this.#timeGraphChart = timeGraphLayout();
        this.#graphLayout.datum({pts: data.pts, changes: data.changes})
                        .call(this.#timeGraphChart);

        // this.#graphLayout = TimeGraphLayout.build(data['pts'], data['changes']);

        legendLayout();
    }

    getGraphLayout() {
        return this.#timeGraphChart;
    }

    createNewGraphLayoutElement() {
        this.#graphLayout = d3.select('#visPanels')
            .append('svg')
            .attr('id', 'graphLayout')
            .style('width', '100%')
            .style('height', '100%')
            .style('grid-column', '1 / 3')
            .style('grid-row', 2)
            .style('justify-self', 'end');
    }

    reconstructGraphLayout() {
        this.#graphLayout.remove();
        this.createNewGraphLayoutElement();
        const filteredTypes = Object.keys(this.#typesToShowOnGraph).filter((t) => this.#typesToShowOnGraph[t]);
        const filteredPtsLow = filteredTypes.reduce((acc, curr) => {
            acc[curr] = this.#zoomed ? this.#data['pts'][curr].filter((d) => d.ts >= this.#zoomTs.startTs) : this.#data['pts'][curr];
            return acc;
        }, {});
        const numPtsRemoved = filteredTypes.reduce((rmMap, type) => {
            rmMap[type] = this.#data['pts'][type].length - filteredPtsLow[type].length;
            return rmMap;
        }, {});

        const filteredPts = filteredTypes.reduce((acc, curr) => {
            acc[curr] = this.#zoomed ? filteredPtsLow[curr].filter((d) => d.ts <= this.#zoomTs.endTs) : this.#data['pts'][curr];
            return acc;
        }, {});
        const filteredChanges = filteredTypes.reduce((acc, curr) => {
            if (this.#data['changes'][curr]) {
                if (!this.#zoomed) {
                    acc[curr] = this.#data['changes'][curr];
                }
                else if (filteredPts[curr].length > 0) {
                    acc[curr] = this.#data['changes'][curr].filter((d) => d >= this.#tsToIndexMap[curr][filteredPts[curr][0].ts] &&
                        d <= this.#tsToIndexMap[curr][filteredPts[curr][filteredPts[curr].length - 1].ts]).map((index) => {
                            return index - numPtsRemoved[curr];
                        });
                }
            }
            return acc;
        }, {});

        // console.log(this.#data['pts']);
        // console.log(filteredPts);
        // console.log(filteredChanges);
        // console.log(numPtsRemoved);
        this.#timeGraphChart = timeGraphLayout();
        this.#graphLayout.datum({pts: filteredPts, changes: filteredChanges})
                        .call(this.#timeGraphChart);
    }

    /* ISSUE: reconstructing the graph layout causes the sample settings to be lost */

    changeVisOfType(type) {
        this.#typesToShowOnGraph[type] = !this.#typesToShowOnGraph[type];
        this.reconstructGraphLayout();
    }

    zoom(startTs, endTs) {
        this.#zoomed = true;
        this.#zoomTs.startTs = startTs;
        this.#zoomTs.endTs = endTs;
        this.reconstructGraphLayout();
    }

    unzoom() {
        this.#zoomed = false;
        this.reconstructGraphLayout();
    }

    constructPageVis(pages) {
        const pageSize = 4096;

        let pagesJoined = {};

        for (let page of Object.keys(pages)) {
            pagesJoined[parseInt(page)] = {'events': [], 'cluster': pages[page]['cluster']};
        }
        let currID = 0;
        let allJoined = [];

        for (let [page, attrs] of Object.entries(pages)) {
            page = parseInt(page);
            attrs.events.sort((a, b) => a.ts - b.ts);
            let allocs = attrs.events.filter((event) => event.is_alloc == 1);
            let freesMap = attrs.events.filter((event) => event.is_alloc == 0).reduce((acc, curr) => {
                acc[curr.addr] ? acc[curr.addr].push(curr.ts) : acc[curr.addr] = [curr.ts];
                return acc;
            }, {});
            
            let joined = [];
            for (let allocEvent of allocs) {
                let freeTime = binarySearchSuccessor(freesMap[allocEvent.addr], allocEvent.ts);
                joined.push({'file': allocEvent.file,
                            'size': allocEvent.size,
                            'addr': allocEvent.addr,
                            'type': allocEvent.type,
                            'allocTs': allocEvent.ts,
                            'freeTs': freeTime,
                            'isDup': false,
                            'ID': currID});
                currID++;
            }
            
            pagesJoined[page]['events'] = pagesJoined[page]['events'].concat(joined);

            for (let event of pagesJoined[page]['events']) {
                let endOffsetLastObject = (event.addr % pageSize) + event.size;
                let iPage = page + 1;
                while (endOffsetLastObject > pageSize && pagesJoined[iPage]) {
                    /*  NOTE: at this point, we rely on the fact that the objects are sorted in ascending order
                        by the address. */
                    let newEvent = structuredClone(event);
                    newEvent.size = Math.min(endOffsetLastObject - pageSize, pageSize);
                    newEvent.addr = iPage * pageSize;
                    // newObj.alloc_addr = (objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) -
                    //     ((objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) % pageSize);
                    newEvent.isDup = true;
                    newEvent.ID = currID;
                    currID++;

                    pagesJoined[iPage]['events'].push(newEvent);
                    // objs[objs.length - 1].alloc_size -= newObj.alloc_size;
                    endOffsetLastObject -= pageSize;
                    iPage++;
                }
            }
        }

        pageLayout(pagesJoined, this.#initTs, pageSize);
        // console.log(Object.values(pagesJoined));
        cacheSetLayout(Object.values(pagesJoined).reduce((acc, curr) => acc.concat(curr['events']), []), 64, {associativity: 8, size: 32768},
                                                                                    {associativity: 8, size: 2097152},
                                                                                    {associativity: 8, size: 4194304});
    }

    static build(data) {
        d3.select('body')
            .append('g')
            .attr('id', 'visPanels');

        return new MainVisualization(data);
    }
}

export default MainVisualization;