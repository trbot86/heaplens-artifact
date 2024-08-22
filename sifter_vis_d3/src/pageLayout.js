import * as d3 from 'd3';
import { colourOfType } from './vis.js';
import objectLayout from './objectFieldLayout.js';
import { getCurrTime } from './dbloader.js';
import { trimString } from './statsTracker.js';
import { mainVis } from './dbloader.js';

const   SORT_PAGE_NUM = 0,
        SORT_CLUSTER = 1,
        SORT_PERF = 2,
        ZOOM_OUT_OBJ_WIDTH = 2;

function pageLayout() {
    let allPageDataOriginal,
        dataDict,
        data,
        dataFields,
        dataPerf,
        sliceScale,
        objLayout,
        statsTracker,
        initTs,
        clusters,
        features,
        perf = undefined;
    let pageSize = 4096,
        cachelineSize = 64,
        pageRectHeight = 32,
        pageRectWidth = 520,
        pageRectBorder = 2,
        sortMode = SORT_PAGE_NUM,
        zoomThreshold = 8192,
        zoomLevel = 0,
        numSubSlices = 32,
        selAddr = 0,
        expandedTypes = undefined,
        cacheSetLayout = undefined;

    function drawPageLayout(selection) {
        clusters = selection.datum().clusters;
        features = selection.datum().features;
        perf = selection.datum().perf;

        const pageNumToEvents = selection.datum().pages;
        const pageAddrToEvents = Object.keys(pageNumToEvents)
                        .reduce((acc, curr) => {
                            acc[curr * pageSize] = pageNumToEvents[curr];
                            return acc;
                        }, {});
        const allEvents = Object.values(pageAddrToEvents)
            .map((d) => d.events)
            .reduce((acc, curr) => acc.concat(curr), []);
        
        const   pages = splitEvents(0, allEvents, pageAddrToEvents, pageSize),
                fields = selection.datum().fields;

        sliceScale = d3.scaleLinear().domain([0, pageSize]).range([0, pageRectWidth]);
        allPageDataOriginal = dataDict = pages;
        data = Object.entries(pages);
        dataFields = fields;

        dataPerf = Object.keys(perf)
                        .filter((d) => Object.keys(dataDict).includes(Math.floor(parseInt(d) / pageSize).toString()))
                        .map((d) => parseInt(d))
                        .reduce((acc, curr) => {
                            acc[Math.floor(curr / pageSize)] ? acc[Math.floor(curr / pageSize)].push([curr, perf[curr]]) :
                                acc[Math.floor(curr / pageSize)] = [[curr, perf[curr]]];
                            return acc;
                        }, {});

        constructPageTabs();
        
        selection.append('svg')
                .attr('id', 'pageLayout')
                .style('width', '100%')
                .style('height', `${Object.keys(pages).length*(pageRectHeight+10)}px`);

        const oldSliceSize = pageSize / Math.pow(numSubSlices, zoomLevel);
        const zoomedOut = oldSliceSize > zoomThreshold;
        refreshObjectLayout(data[0][1].events, data[0][0],
                                        initTs, fields, zoomedOut ? zoomThreshold : oldSliceSize, cachelineSize);
        updatePagesByTimestamp(initTs);
    }

    function constructPageTabs() {
        d3.select('#pageSortTabs').remove();
        const sorters = {'Page #': {'sortFunc': function() {
                if (sortMode = SORT_PERF)
                    objLayout.perfVisible(false);
                data = data.sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
                sortMode = SORT_PAGE_NUM;
            }, 'indent': 37}};

        if (zoomLevel == 0) {
            sorters["Cluster"] = {'sortFunc': function() {
                    if (sortMode = SORT_PERF)
                        objLayout.perfVisible(false);
                    data = data.sort((a, b) => parseInt(a[1].cluster) - parseInt(b[1].cluster));
                    sortMode = SORT_CLUSTER;
                }, 'indent': 50};
        }
        
        sorters["Perf C2C"] = {'sortFunc': function() {
                const perfPageStrings = Object.keys(perf).map((d) => Math.floor(parseInt(d) / pageSize).toString());
                if (sortMode != SORT_PERF) {
                    objLayout.perfVisible(true);
                    data = data.filter((d) => perfPageStrings.includes(d[0])).concat(data.filter((d) => !perfPageStrings.includes(d[0])));
                    sortMode = SORT_PERF;
                }
            }, 'indent': 60};

        const   TAB_WIDTH = 70,
                TAB_HEIGHT = 35,
                LABEL_INDENT = 70;

        let pageSortTabs = d3.select('#pageLayoutDiv')
                .insert('div', ':first-child')
                .attr('id', 'pageSortTabs')
                .style('width', '100%')
                .style('height', `${TAB_HEIGHT + 5}px`)         
                .style('position', 'sticky')
                .style('top', '0px')
                .style('left', '0px')
                .style('background-color', 'white')
                .style('display', 'inline-block');

        pageSortTabs.append('div')
                // .style('width', '20px')
                .style('font-family', 'monospace')
                .style('float', 'left')
                .style('top', '50%')
                .style('transform', 'translateY(-50%)')
                .style('position', 'relative')
                .text('Sorting:');
        
        pageSortTabs.selectAll('.pageTab')
                .data(Object.keys(sorters))
                .enter()
                .append('div')
                .attr('class', 'pageTab')
                .style('width', `${TAB_WIDTH}px`)
                .style('height', `${TAB_HEIGHT}px`)
                .style('position', 'relative')
                .style('top', '50%')
                .style('transform', 'translateY(-50%)')
                .style('border-top-left-radius', (d, i) => i == 0 ? '7px' : '0px')
                .style('border-bottom-left-radius', (d, i) => i == 0 ? '7px' : '0px')
                .style('border-top-right-radius', (d, i) => i == Object.keys(sorters).length - 1 ? '7px' : '0px')
                .style('border-bottom-right-radius', (d, i) => i == Object.keys(sorters).length - 1 ? '7px' : '0px')
                .style('background-color', 'white')
                .style('border', '1px solid #ccc')
                .style('pointer-events', 'visible')
                .style('cursor', 'pointer')
                .style('float', 'left')
                // .style('border-top-left-radius', (d, i) => i == 0 ? '7px' : '0px')
                // .style('border-bottom-left-radius', (d, i) => i == 0 ? '7px' : '0px')
                // .style('border-top-right-radius', (d, i) => i == cacheInfo.length - 1 ? '7px' : '0px')
                // .style('border-bottom-right-radius', (d, i) => i == cacheInfo.length - 1 ? '7px' : '0px')
                .on('click', function(e, d) {
                    sorters[d].sortFunc();
                    updatePagesByTimestamp(getCurrTime());
                })
                .on('mouseover', function() {
                    d3.select(this)
                        .transition()
                        .style('background-color', '#ccc');
                })
                .on('mouseout', function() {
                    d3.select(this)
                        .transition()
                        .style('background-color', 'white');
                })
                .append('p')
                .style('text-align', 'center')
                .style('font-family', 'monospace')
                .style('font-family', 'monospace')
                .style('font-size', '12px')
                .style('alignment-baseline', 'middle')
                .style('pointer-events', 'none')
                .text((d) => d);

        if (zoomLevel > 0) {
            pageSortTabs.append('div')
                    .style('width', `${TAB_WIDTH}px`)
                    .style('height', `${TAB_HEIGHT}px`)
                    .style('position', 'relative')
                    .style('right', '20px')
                    .style('border-radius', '7px')
                    .style('background-color', 'white')
                    .style('border', '1px solid #ccc')
                    .style('pointer-events', 'visible')
                    .style('cursor', 'pointer')
                    .style('float', 'right')
                    .style('top', '50%')
                    .style('transform', 'translateY(-50%)')
                    // .style('border-top-left-radius', (d, i) => i == 0 ? '7px' : '0px')
                    // .style('border-bottom-left-radius', (d, i) => i == 0 ? '7px' : '0px')
                    // .style('border-top-right-radius', (d, i) => i == cacheInfo.length - 1 ? '7px' : '0px')
                    // .style('border-bottom-right-radius', (d, i) => i == cacheInfo.length - 1 ? '7px' : '0px')
                    .on('click', function() {
                        zoomLevel = 0;
                        sliceScale = d3.scaleLinear().domain([0, pageSize]).range([0, pageRectWidth]);
                        dataDict = allPageDataOriginal;
                        data = Object.entries(dataDict);
                        sorters['Page #'].sortFunc();
                        d3.select('#pageLayout')
                            .style('height', `${Object.keys(dataDict).length*(pageRectHeight+10)}px`);
                        updatePagesByTimestamp(getCurrTime());  // TODO: weird hack, not sure how to fix
                        updatePagesByTimestamp(getCurrTime());
                        constructPageTabs();
                        const oldSliceSize = pageSize / Math.pow(numSubSlices, zoomLevel);
                        const zoomedOut = oldSliceSize > zoomThreshold;
                        refreshObjectLayout(data[0][1].events, data[0][0],
                            getCurrTime(), dataFields, zoomedOut ? zoomThreshold : oldSliceSize, cachelineSize);
                    })
                    .on('mouseover', function() {
                        d3.select(this)
                            .transition()
                            .style('background-color', '#ccc');
                    })
                    .on('mouseout', function() {
                        d3.select(this)
                            .transition()
                            .style('background-color', 'white');
                    })
                    .append('p')
                    .style('text-align', 'center')
                    .style('font-family', 'monospace')
                    .style('font-family', 'monospace')
                    .style('font-size', '12px')
                    .style('alignment-baseline', 'middle')
                    .style('pointer-events', 'none')
                    .text('Zoom-');
        }
    }

    function splitEvents(baseAddr, events, keyMap, sliceSize) {
        let currID = 0;
        for (let event of events) {
            let sliceAddr = event.addr - ((event.addr - baseAddr) % sliceSize);
            event.ID = currID++;
            let endOffsetLastObject = ((event.addr - baseAddr) % sliceSize) + event.size;
            let iSlice = sliceAddr + sliceSize;

            while (endOffsetLastObject > sliceSize && keyMap[iSlice]) {
                let newEvent = structuredClone(event);
                newEvent.size = Math.min(endOffsetLastObject - sliceSize, sliceSize);
                newEvent.addr = sliceAddr;
                newEvent.isDup = true;
                newEvent.ID = currID++;
                keyMap[iSlice].events.push(newEvent);
                endOffsetLastObject -= sliceSize;
                iSlice += sliceSize;
            }
        }

        return keyMap;
    }

    function getSliceData(oldSliceAddr, newAddr, newSliceSize) {
        // TODO HAVE TO SPLIT ACROSS "SLICE" BOUNDARIES NOW - take the page calc from vis.js and move here
        let newKeys = new Array(numSubSlices).fill(0).map((item, i) => newAddr + i*newSliceSize);

        // console.log('HERE ARE THE newKeys');
        // console.log(newKeys);
        // console.log('HERE is the oldSliceAddr ', oldSliceAddr);
        // console.log('Here is the newSliceSize', newSliceSize);
        // console.log('Here is oldSliceAddr% newSliceSize', oldSliceAddr % newSliceSize);
        // console.log('dataDict[oldSliceAddr].events[0].addr - newAddr % newSliceSize?');
        // console.log((dataDict[oldSliceAddr].events[0].addr - newAddr) % newSliceSize);
            
        newKeys = newKeys.reduce((acc, curr) => {
                acc[curr] = {events: dataDict[oldSliceAddr].events
                                            .filter((d) => Math.floor((d.addr - newAddr) / newSliceSize) == Math.floor((curr - newAddr) / newSliceSize))};
                return acc;
            }, {});
        return splitEvents(newAddr, dataDict[oldSliceAddr].events, newKeys, newSliceSize);
    }

    function updatePagesByTimestamp(ts) {
        if (ts == undefined)
            ts = getCurrTime();
        objLayout.addElementsByTimestamp(ts);
        const groups = d3.select('#pageLayout')
            .selectAll('.pageGroup')
            .data(data, (d) => (parseInt(d[0])*Math.pow(numSubSlices, zoomLevel)) / pageSize);
        
        const oldSliceSize = pageSize / Math.pow(numSubSlices, zoomLevel);
        const zoomedOut = oldSliceSize > zoomThreshold;
        groups.join(
                (enter) => {
                    let pageGroups = enter.append('g')
                        .attr('class', 'pageGroup')
                        .attr('data-addr', (d) => parseInt(d[0]))
                        .style('transform', (d, i) => `translate(0px, ${i*(pageRectHeight+10)}px)`);
                    pageGroups.append('rect')
                        .attr('class', 'pageBorder')
                        .style('width', `${pageRectWidth}px`)
                        .style('height', `${pageRectHeight}px`)
                        .style('min-height', `${pageRectHeight}px`)
                        .style('stroke-width', pageRectBorder)
                        .style('fill', 'none');
                    const newSliceSize = oldSliceSize / numSubSlices;
                    const sliceWidth = (1/numSubSlices)*pageRectWidth;
                    pageGroups.selectAll('.pageSliceSelector')
                        .data((d) => zoomedOut ? new Array(numSubSlices).fill(0).map((elem, i) => parseInt(d[0]) + newSliceSize*i) : [parseInt(d[0])])
                        .enter()
                        .append('rect')
                        .attr('class', (d) => zoomedOut ? 'pageSliceSelector' : 'wholeSliceSelector')
                        .attr('x', (d, i) => i * sliceWidth)
                        .style('width', (d, i) => `${zoomedOut ? sliceWidth : pageRectWidth}px`)
                        .style('height', `${pageRectHeight}px`)
                        .style('min-height', `${pageRectHeight}px`)
                        .style('fill', 'black')
                        .style('fill-opacity', 0.0)
                        .on('click', function(e, d) {
                            selAddr = d;
                            if (zoomedOut) {
                                zoomLevel++;
                                sliceScale = d3.scaleLinear().domain([0, newSliceSize]).range([0, pageRectWidth]);
                                dataDict = getSliceData(parseInt(this.parentNode.getAttribute('data-addr')), selAddr, newSliceSize);
                                data = Object.entries(dataDict);
                                d3.select('#pageLayout')
                                    .style('height', `${Object.keys(dataDict).length*(pageRectHeight+10)}px`);
                                updatePagesByTimestamp(getCurrTime());  // TODO: weird hack, not sure how to fix
                                updatePagesByTimestamp(getCurrTime());
                                constructPageTabs();
                            }
                            refreshObjectLayout(dataDict[selAddr].events, selAddr, getCurrTime(), dataFields,
                                    zoomedOut ? Math.min(zoomThreshold, newSliceSize) : oldSliceSize, cachelineSize);
                        })
                        .on('mouseover', function() {
                            d3.select(this)
                                .transition()
                                .style('fill-opacity', 0.3);
                        })
                        .on('mouseout', function() {
                            d3.select(this)
                                .transition()
                                .style('fill-opacity', 0.0);
                        });
                
                    pageGroups.append('text')
                        .attr('font-family', 'monospace')
                        .attr('x', '87%')
                        // .attr('y', '37%')
                        .style('font-size', '10px')
                        .style('transform', `translate(0px, 13px)`)
                        .text((d) => `${parseInt(d[0]).toString(16)}`);
                
                    if (zoomLevel == 0) {
                        pageGroups.append('text')
                            .attr('font-family', 'monospace')
                            .attr('x', '87%')
                            // .attr('y', '63%')
                            .style('font-size', '10px')
                            .style('transform', `translate(0px, 23px)`)
                            .text((d) => `cluster: ${d[1].cluster}`)
                            .style('cursor', 'pointer')
                            .on('click', function(e, d, i) {
                                const featWindow = d3.select('body')
                                    .append('div')
                                    .attr('class', 'popup')
                                    .attr('id', 'featurePopup')
                                    .style('display', 'block')
                                    .style('overflow', 'scroll');
                    
                                featWindow.append('i')
                                    .attr('class', 'fa fa-close')
                                    .style('position', 'absolute')
                                    .style('top', '3%')
                                    .style('right', '1%')
                                    .style('font-size', '24px')
                                    .style('color', '#ccc')
                                    .style('cursor', 'pointer')
                                    .on('click', function() {
                                        d3.select('#featurePopup').remove();
                                    });
                    
                                featWindow.selectAll('.featureVector')
                                    .data(clusters[d[1].cluster].page_num)
                                    .enter()
                                    .append('p')
                                    .attr('class', 'featureVector')
                                    .style('position', 'absolute')
                                    .style('left', '10px')
                                    .style('top', (d2, i) => `calc(3% + ${5 + i*20}px)`)
                                    .text((d2) => `${trimString(d2, 20)}: ${Object.entries(features[d2])}`);
                        });
                    }
                },
                (update) => {
                    update.transition()
                        .style('transform', (d, i) => `translate(0px, ${i*(pageRectHeight+10)}px)`);
                },
                (exit) => exit.remove()
            );

        const sliceSize = pageSize / Math.pow(numSubSlices, zoomLevel);
        
        groups.selectAll('.perfHighlight')
            .data((d) => dataPerf[d[0]] ? dataPerf[d[0]] : [])
            .join(
                (enter) => enter.append('rect')
                            .attr('class', 'perfHighlight')
                            .attr('x', (d) => sliceScale(d[0] % sliceSize))
                            .attr('y', 0)
                            .attr('width', sliceScale(cachelineSize))
                            .attr('height', pageRectHeight)
                            .style('visibility', 'hidden'),
                (update) => update.style('visibility', sortMode == SORT_PERF ? 'visible' : 'hidden'),
                (exit) => exit.remove()
            );
        
        const elements = groups.selectAll('.dataObject')
            .data((d) => {
                    const ev = d[1].events.filter((obj) => obj.allocTs <= ts && (obj.freeTs == null || obj.freeTs >= ts))
                                            .map((obj) => {
                                                obj.vis = mainVis.isTypeSampled(obj.type);
                                                return obj;
                                            });
                    // if (ev.length > 0) console.log(ev);
                    const ret = zoomedOut ? getZoomGroups(ev) : ev;
                    return ret;
                },
                (d) => d.ID);
        
        elements.join(
            (enter) => {
                const gp = enter.insert('g', ':first-child')
                    .attr('class', 'dataObject')
                    .style('visibility', (d) => d.vis ? 'visible' : 'hidden');
                gp.append('rect')
                    .attr('class', 'dataObjectRect')
                    .attr('x', (d) => sliceScale(d.addr % sliceSize))
                    .attr('y', 0)
                    .attr('width', (d) => sliceScale(Math.min(d.size, sliceSize - (d.addr % sliceSize))))
                    .attr('height', pageRectHeight)
                    // .style('stroke', 'black')
                    // .style('stroke-width', '1px')
                    .style('fill', (d) => zoomedOut ? d.col : colourOfType[d.type]);
                if (!zoomedOut) {
                    gp.append('line')
                        .attr('x1', (d) => sliceScale(d.addr % sliceSize))
                        .attr('y1', 0)
                        .attr('x2', (d) => sliceScale(d.addr % sliceSize))
                        .attr('y2', pageRectHeight)
                        .style('stroke', 'black');
                    gp.append('line')
                        .attr('x1', (d) => sliceScale((d.addr % sliceSize) + Math.min(d.size, sliceSize - (d.addr % sliceSize))))
                        .attr('y1', 0)
                        .attr('x2', (d) => sliceScale((d.addr % sliceSize) + Math.min(d.size, sliceSize - (d.addr % sliceSize))))
                        .attr('y2', pageRectHeight)
                        .style('stroke', 'black');
                }
            },
            (update) => {
                update.style('visibility', (d) => d.vis ? 'visible' : 'hidden');
                update.select('.dataObjectRect')
                    .style('fill', (d) => zoomedOut ? d.col : colourOfType[d.type]);
            },
            (exit) => exit.remove()
        );
    }

    function getZoomGroups(events) {
        const sliceSize = pageSize / Math.pow(numSubSlices, zoomLevel);
        const displaySize = (sliceSize*ZOOM_OUT_OBJ_WIDTH) / pageRectWidth;
        const chunkTypes = events.reduce((acc, curr) => {
                let ind = Math.floor((curr.addr % sliceSize) / displaySize);
                acc[ind] += curr.size;
                return acc;
            }, new Array(pageRectWidth / ZOOM_OUT_OBJ_WIDTH).fill(0));

        const fullnessScale = d3.scaleLinear().domain([0, Math.ceil(displaySize)]).range(['#d4d4d4', 'black']);
        const ret = chunkTypes.map((d, i) => {
                return {
                    ID: i, //TODO: this is prob wrong
                    addr: i*displaySize,
                    size: displaySize,
                    col: d === 0 ? d3.color('white') : fullnessScale(d)
                };
            });
        return ret;
    }

    function refreshObjectLayout(objects, startAddr, initTs, fields, pageSize=4096, cachelineSize=64,
        x=26, y=40, width=310, height=350) {
        d3.select('#memLayoutDiv').remove();
        let actualHeight = Math.floor((pageSize*height) / (4096));
        let memLayout = d3.select('#visPanels')
            .append('div')
            .attr('id', 'memLayoutDiv')
            .style('width', '100%')
            .style('height', '100%')
            .style('grid-column', 2)
            .style('grid-row', 1)
            .style('overflow-x', 'visible')
            .style('overflow-y', 'scroll')
            .append('svg')
            .attr('id', 'memLayout')
            .style('width', '100%')
            .style('height', `${actualHeight + y + 10}px`);

        objLayout = objectLayout()
            .x(x)
            .y(y)
            .width(width)
            .height(actualHeight)
            .stats(statsTracker)
            .fields(fields)
            .perf(dataPerf)
            .expandedTypes(expandedTypes)
            .cacheSetLayout(cacheSetLayout);
        memLayout.datum({objects: objects,
            startAddr: startAddr,
            initTs: initTs,
            pageSize: pageSize,
            cachelineSize: cachelineSize})
            .call(objLayout);
        objLayout.perfVisible(sortMode == SORT_PERF);
    }

    drawPageLayout.toggleExpandType = function(tp) {
        objLayout.toggleExpandType(tp);
    }

    drawPageLayout.getObjLayout = function() {
        return objLayout;
    }

    drawPageLayout.updatePagesByTimestamp = function(ts) {
        updatePagesByTimestamp(ts);
    }

    drawPageLayout.pageSize = function(val) {
        if (!arguments) return pageSize;
        pageSize = val;
        return drawPageLayout;
    }

    drawPageLayout.cachelineSize = function(val) {
        if (!arguments) return cachelineSize;
        cachelineSize = val;
        return drawPageLayout;
    }

    drawPageLayout.statsTracker = function(val) {
        if (!arguments) return statsTracker;
        statsTracker = val;
        return drawPageLayout;
    }

    drawPageLayout.initTs = function(val) {
        if (!arguments) return initTs;
        initTs = val;
        return drawPageLayout;
    }

    drawPageLayout.expandedTypes = function(val) {
        if (!arguments) return expandedTypes;
        expandedTypes = val;
        return drawPageLayout;
    }

    drawPageLayout.cacheSetLayout = function(val) {
        if (!arguments) return cacheSetLayout;
        cacheSetLayout = val;
        return drawPageLayout;
    }

    return drawPageLayout;
}

export default pageLayout;