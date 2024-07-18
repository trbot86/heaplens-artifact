import * as d3 from 'd3';
import legendLayout from './legend.js';
import cacheSetLayout from './cacheSetLayout.js';
import pageLayout from './pageLayout.js';
import timeGraphLayout from './timeGraphLayout.js';
import StatsTracker from './statsTracker.js';
import { pageSize } from './timeGraphLayout.js';
import { currCacheLineSize } from './cacheSetLayout.js';

export const colourOfType = {};
const TIMEGRAPH_TRANSLATE_Y = 15;

export function binarySearchSuccessor(arr, v, start=undefined, end=undefined) {
    if (!arr) return null;
    if (arr[arr.length - 1] < v) return [arr[arr.length - 1], arr.length - 1];
    if (start == undefined) {
        start = 0;
        end = arr.length - 1;
    }

    if (end - start <= 1) {
        return arr[start] > v ? [arr[start], start] : [arr[end], end];
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
    #fname;
    #initTs;
    #graphLayout;
    #timeGraphChart;
    #cacheSetChart;
    #pageLayoutChart;
    #typesToShowOnGraph;
    #typesToSample;
    #tsToIndexMap;
    #data;
    #zoomed;
    #zoomTs;
    #cacheFocus;
    #statsTracker;
    #origMinTs;
    #origMaxTs;
    #cacheInfo;

    constructor(fname, data) {
        console.log('Number of points in input: ', Object.keys(data['pts']).reduce((acc, curr) => acc + data.pts[curr].length, 0));
        this.#fname = fname;
        // const types = [...new Set(data['records'].map((rec) => rec.type))];
        const types = Object.keys(data['pts']);
        const colScale = d3.scaleSequential()
                            .domain([0, types.length])
                            .interpolator(d3.interpolateRainbow);
        let col = 0;
        for (let type of types) {
            colourOfType[type] = colScale(col);
            col++;
        }

        this.#cacheInfo = [
            {associativity: 8, size: 32768, width: 270, initWidth: 270, currDragX: 320, initDragX: 320},
            {associativity: 8, size: 2097152, width: 270, initWidth: 270, currDragX: 320, initDragX: 320},
            {associativity: 8, size: 4194304, width: 270, initWidth: 270, currDragX: 320, initDragX: 320}
        ];

        this.#data = data;
        this.#zoomed = false;
        this.#cacheFocus = false;
        this.#zoomTs = {'startTs': 0, 'endTs': 0};
        this.#typesToShowOnGraph = types.reduce((acc, curr) => {
            acc[curr] = true;
            return acc
        }, {});
        this.#typesToSample = types.reduce((acc, curr) => {
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
        this.#statsTracker = new StatsTracker(types, data['stats']);


        // const changeTs = types.reduce((chMap, type) => {
        //     if (data['changes'][type]) {
        //         chMap[type] = data['changes'][type].map((d) => data['pts'][type][d - 1]);
        //     }
        //     return chMap;
        // }, {});

        // delete data['pts']['gstats_t::gstats_thread_data'];
        this.createNewGraphLayoutElement();

        let allTs = Object.keys(data.pts).reduce((acc, curr) => acc.concat(data.pts[curr]), [])
                    .map((pt) => pt.ts)
                    .filter((d) => !isNaN(d));
        /*  Note: cannot use spread syntax (...allTs) here because this would give too many
            arguments for Math.min/max */
        this.#origMinTs = allTs.reduce((acc, curr) => Math.min(acc, curr), Infinity);
        this.#origMaxTs = allTs.reduce((acc, curr) => Math.max(acc, curr), -1);

        this.#timeGraphChart = timeGraphLayout().y(TIMEGRAPH_TRANSLATE_Y)
                                    .minTs(this.#origMinTs)
                                    .maxTs(this.#origMaxTs);
        this.#graphLayout.datum({pts: data.pts, changes: data.changes})
                        .call(this.#timeGraphChart);

        // this.#graphLayout = TimeGraphLayout.build(data['pts'], data['changes']);

        d3.select('#visPanels')
            .append('div')
            .attr('id', 'legendLayout')
            .style('width', '85%')
            .style('height', '50%')
            .style('grid-column', 3)
            .style('grid-row', 2)
            .style('justify-self', 'start')
            .style('position', 'relative')
            .style('top', '10px')
            // .style('overflow', 'hidden')
            .datum(colourOfType)
            .call(legendLayout());
    }

    getGraphLayout() {
        return this.#timeGraphChart;
    }

    createNewGraphLayoutElement() {
        this.#graphLayout = d3.select('#visPanels')
            .append('div')
            .attr('id', 'graphLayoutDiv')
            .attr('width', '100%')
            .attr('height', '100%')
            .style('position', 'relative')
            .style('grid-column', '1 / 3')
            .style('grid-row', 2);
        // this.#graphLayout = d3.select('#visPanels')
        //     .append('svg')
        //     .attr('id', 'graphLayout')
        //     .style('width', '100%')
        //     .style('height', '100%')
        //     .style('grid-column', '1 / 3')
        //     .style('grid-row', 2)
        //     .style('justify-self', 'end');
    }

    reconstructGraphLayout() {
        // this.#graphLayout.remove();
        // this.createNewGraphLayoutElement();
        const filteredTypes = Object.keys(this.#typesToShowOnGraph).filter((t) => this.#typesToShowOnGraph[t]);
        const filteredPts = filteredTypes.reduce((acc, curr) => {
            acc[curr] = this.#data['pts'][curr];
            return acc;
        }, {});

        // const numPtsRemoved = filteredTypes.reduce((rmMap, type) => {
        //     rmMap[type] = this.#data['pts'][type].length - filteredPtsLow[type].length;
        //     return rmMap;
        // }, {});

        // const filteredPts = filteredTypes.reduce((acc, curr) => {
        //     acc[curr] = this.#zoomed ? filteredPtsLow[curr].filter((d) => d.ts <= this.#zoomTs.endTs) : this.#data['pts'][curr];
        //     return acc;
        // }, {});
        const filteredChanges = [];
        // filteredTypes.reduce((acc, curr) => {
        //     if (this.#data['changes'][curr]) {
        //         if (!this.#zoomed) {
        //             acc[curr] = this.#data['changes'][curr];
        //         }
        //         else if (filteredPts[curr].length > 0) {
        //             acc[curr] = this.#data['changes'][curr].filter((d) => d >= this.#tsToIndexMap[curr][filteredPts[curr][0].ts] &&
        //                 d <= this.#tsToIndexMap[curr][filteredPts[curr][filteredPts[curr].length - 1].ts]).map((index) => {
        //                     return index - numPtsRemoved[curr];
        //                 });
        //         }
        //     }
        //     return acc;
        // }, {});

        // this.#timeGraphChart = timeGraphLayout().y(TIMEGRAPH_TRANSLATE_Y);
        this.#graphLayout.datum({pts: filteredPts, changes: filteredChanges})
                        .call(this.#timeGraphChart);
    }

    changeVisOfType(type) {
        this.#typesToShowOnGraph[type] = !this.#typesToShowOnGraph[type];
        this.reconstructGraphLayout();
    }

    getVisOfType(type) {
        return this.#typesToShowOnGraph[type];
    }

    getSampleVector() {
        return this.#typesToSample;
    }

    changeTypeSampled(type) {
        this.#typesToSample[type] = !this.#typesToSample[type];
        // TODO add a warning telling user to resample?
    }

    isTypeSampled(type) {
        return this.#typesToSample[type];
    }

    zoom(startTs, endTs) {
        this.#zoomed = true;
        this.#zoomTs.startTs = parseInt(startTs);
        this.#zoomTs.endTs = parseInt(endTs);
        this.reconstructGraphLayout();
    }

    unzoom() {
        this.#zoomed = false;
        this.#timeGraphChart.minTs(this.#origMinTs)
                            .maxTs(this.#origMaxTs);
        this.reconstructGraphLayout();
    }

    isCacheFocus() {
        return this.#cacheFocus;
    }

    toggleCacheFocus() {
        this.#cacheFocus = !this.#cacheFocus;
        if (this.#cacheFocus) {
            d3.select('#pageLayoutDiv')
                .style('visibility', 'hidden');
            d3.select('#memLayout')
                .style('visibility', 'hidden');
            d3.select('#cacheSetLayout')
                .style('grid-column', 2);
        }
        else {
            d3.select('#pageLayoutDiv')
                .style('visibility', 'visible');
            d3.select('#memLayout')
                .style('visibility', 'visible');
            d3.select('#cacheSetLayout')
                .style('grid-column', 3);
        }
    }

    constructPageVis(data, currCacheLineSize) {
        let pages = data.page_num_events;

        // let currID = 0;

        // for (let [page, attrs] of Object.entries(pages)) {
        //     page = parseInt(page);
        //     attrs.events.sort((a, b) => a.alloc_ts - b.alloc_ts);
           
        //     for (let event of attrs.events) {
        //         event.isDup = false;
        //         event.ID = currID++;
        //         let endOffsetLastObject = (event.addr % pageSize) + event.size;
        //         let iPage = page + 1;

        //         while (endOffsetLastObject > pageSize && pages[iPage]) {
        //             /*  NOTE: at this point, we rely on the fact that the objects are sorted in ascending order
        //                 by the address. Actually I don't think this is true anymore?? */
        //             let newEvent = structuredClone(event);
        //             newEvent.size = Math.min(endOffsetLastObject - pageSize, pageSize);
        //             newEvent.addr = iPage * pageSize;
        //             // newObj.alloc_addr = (objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) -
        //             //     ((objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) % pageSize);
        //             newEvent.isDup = true;
        //             newEvent.ID = currID++;

        //             pages[iPage].events.push(newEvent);
        //             // objs[objs.length - 1].alloc_size -= newObj.alloc_size;
        //             endOffsetLastObject -= pageSize;
        //             iPage++;
        //         }
        //     }
        // }

        this.#cacheSetChart = cacheSetLayout()
            .pageSize(pageSize)
            .cacheInfo(this.#cacheInfo)
            .defaultWidth(270)
            .mainVis(this);
        d3.select('#visPanels')
            .insert('div', '#memLayoutDiv')
            .attr('id', 'cacheSetLayout')
            .style('width', '530px')
            .style('height', '100%')
            .style('grid-column', 3)
            .style('grid-row', 1)
            .style('overflow', 'visible')
            .style('transform', 'translateX(10px)')
            .datum(Object.values(pages).reduce((acc, curr) => acc.concat(curr.events), []))
            .call(this.#cacheSetChart);

        this.#pageLayoutChart = pageLayout()
            .pageSize(pageSize)
            .cachelineSize(currCacheLineSize)
            .statsTracker(this.#statsTracker)
            .initTs(this.#initTs);
        d3.select('#visPanels')
            .append('div')
            .attr('id', 'pageLayoutDiv')
            .style('width', '620px')
            .style('height', '100%')
            .style('grid-column', 1)
            .style('grid-row', 1)
            .style('position', 'relative')
            .style('left', '30px')
            .style('overflow', 'auto')
            .datum({
                pages: pages,
                clusters: data.clusters,
                features: data.features,
                fields: data.fields,
                perf: data.perf
            })
            .call(this.#pageLayoutChart);

        // cacheSetLayout(Object.values(pagesJoined).reduce((acc, curr) => acc.concat(curr['events']), []), 64, {associativity: 8, size: 32768},
        //                                                                             {associativity: 8, size: 2097152},
        //                                                                             {associativity: 8, size: 4194304});

        this.#timeGraphChart.callbacks([this.#pageLayoutChart.updatePagesByTimestamp,
                                        this.#cacheSetChart.currTime]);
    }

    getFileName() {
        return this.#fname;
    }

    static build(fname, data) {
        d3.select('body')
            .append('g')
            .attr('id', 'visPanels');

        return new MainVisualization(fname, data);
    }
}

export default MainVisualization;