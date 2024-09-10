import * as d3 from 'd3';
import { colourOfType } from './vis.js';
import objectLayout from './objectFieldLayout.js';
import { getCurrTime } from './dbloader.js';
import { trimString } from './statsTracker.js';
import { mainVis } from './dbloader.js';

const   SORT_PAGE_NUM = 0,
        SORT_CLUSTER = 1,
        SORT_PERF = 2,
        NUM_OBJS_PER_SUBSLICE = 8,
        SLICE_ADDR = 0,
        OBJ_LIST = 1;

const   tabLabelToCode = {
    'Address': SORT_PAGE_NUM,
    'Cluster': SORT_CLUSTER,
    'Perf C2C': SORT_PERF
};

function pageLayout() {
    let allEvents,
        subsliceAddrToSplitEvents,
        objAddrToSplitEvents,
        pageAddrs,
        dataFields,
        dataPerf,
        sliceScale,
        objLayout,
        statsTracker,
        initTs,
        clusters,
        features,
        perf = undefined,
        pageSize = 4096,
        cachelineSize = 64,
        pageRectHeight = 32,
        pageRectWidth = 520,
        pageRectBorder = 1,
        sortMode = SORT_PAGE_NUM,
        zoomThreshold = 8192,
        zoomLevel = 0,
        numSubSlices = 32,
        selAddr = 0,
        expandedTypes = undefined,
        cacheSetLayout = undefined,
        numBuckets = 0,
        getBucketIndexFromTs,
        bucketData,
        sliceAddrAndObjList,
        pageAddrToEvents,
        pageAddrToCluster;

    function drawPageLayout(selection) {
        clusters = selection.datum().clusters;
        features = selection.datum().features;
        perf = selection.datum().perf;

        const pageNumToEvents = selection.datum().pages;
        pageAddrs = Object.keys(pageNumToEvents).map((pn) => pn*pageSize);
        // ToEvents = Object.keys(pageNumToEvents)
        //                 .reduce((acc, curr) => {
        //                     acc[curr * pageSize] = pageNumToEvents[curr].events;
        //                     return acc;
        //                 }, {});
        pageAddrToCluster = Object.keys(pageNumToEvents)
                        .reduce((acc, curr) => {
                            acc[curr * pageSize] = pageNumToEvents[curr].cluster;
                            return acc;
                        }, {});
        allEvents = [];
        Object.values(pageNumToEvents)
            .map((d) => d.events)
            .forEach((eventList) => eventList.forEach((event) => allEvents.push(event)));

        dataFields = selection.datum().fields;

        sliceAddrAndObjList = Object.entries(
                        pageAddrs.reduce((acc, pageAddr) => {
                            acc[pageAddr] = new Array(numSubSlices*NUM_OBJS_PER_SUBSLICE).fill(0).map((e, i) => parseInt(pageAddr) + i*(pageSize / (numSubSlices*NUM_OBJS_PER_SUBSLICE)));
                            return acc;
                        }, {}))
                        .map((entry) => [entry[0], entry[1], getPageKey(entry[0])]);
        subsliceAddrToSplitEvents = splitEvents(allEvents, pageSize / (zoomedOut() ? numSubSlices : 1));
        objAddrToSplitEvents = splitEvents(allEvents, pageSize / (zoomedOut() ? numSubSlices*NUM_OBJS_PER_SUBSLICE : 1));
        sliceScale = d3.scaleLinear().domain([0, pageSize]).range([0, pageRectWidth]);
        // allObjDataOriginal = objAddrToSplitEvents;
        if (zoomedOut())
            bucketData = getBucketData(Object.entries(objAddrToSplitEvents));

        dataPerf = Object.keys(perf)
                        .filter((d) => Object.keys(objAddrToSplitEvents).includes(Math.floor(parseInt(d) / pageSize).toString()))
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
                .style('height', `${pageAddrs.length*(pageRectHeight+10)}px`);

        selAddr = sliceAddrAndObjList[0][SLICE_ADDR];
        refreshObjectLayout(objAddrToSplitEvents[sliceAddrAndObjList[0][OBJ_LIST][0]] ? objAddrToSplitEvents[sliceAddrAndObjList[0][OBJ_LIST][0]] : [],
                            sliceAddrAndObjList[0][SLICE_ADDR], initTs, dataFields,
                            zoomedOut() ? zoomThreshold : currentSliceSize(), cachelineSize);
        updatePagesByTimestamp(initTs);
    }

    function getBucketData(objs) {
        const ret = {};
        objs.forEach((objAndEvents) => {
            ret[objAndEvents[0]] = new Array(numBuckets+2).fill(0);
            objAndEvents[1].forEach((event) => {
                if (mainVis.isTypeSampled(event.type)) {
                    const startBucket = getBucketIndexFromTs(event.allocTs),
                            endBucket = event.freeTs ? getBucketIndexFromTs(event.freeTs) : undefined;
                    ret[objAndEvents[0]][startBucket] += event.size;
                    if (endBucket)
                        ret[objAndEvents[0]][endBucket] -= event.size;
                }
            });
            for (let i = 1; i < ret[objAndEvents[0]].length; i++)
                ret[objAndEvents[0]][i] += ret[objAndEvents[0]][i-1];
        });
        return ret;
    }

    drawPageLayout.recalculateBuckets = function() {
        if (zoomedOut()) {
            bucketData = getBucketData(Object.entries(objAddrToSplitEvents));
        }
        updatePagesByTimestamp(getCurrTime());
    }

    function zoomedOut() {
        return pageSize / (zoomLevel > 0 ? Math.pow(numSubSlices, 2)*zoomLevel : 1) > zoomThreshold;
    }

    function constructPageTabs() {
        d3.select('#pageSortTabs').remove();
        const sorters = {'Address': {'sortFunc': function() {
                if (sortMode = SORT_PERF)
                    objLayout.perfVisible(false);
                sliceAddrAndObjList = sliceAddrAndObjList.sort((a, b) => parseInt(a[SLICE_ADDR]) - parseInt(b[SLICE_ADDR]));
                sortMode = SORT_PAGE_NUM;
            }, 'indent': 37}};

        if (zoomLevel == 0) {
            sorters['Cluster'] = {'sortFunc': function() {
                    if (sortMode = SORT_PERF)
                        objLayout.perfVisible(false);
                    sliceAddrAndObjList = sliceAddrAndObjList.sort((a, b) => parseInt(pageAddrToCluster[a[SLICE_ADDR]]) - parseInt(pageAddrToCluster[b[SLICE_ADDR]]));
                    sortMode = SORT_CLUSTER;
                }, 'indent': 50};
        }
        
        sorters['Perf C2C'] = {'sortFunc': function() {
                const perfPageStrings = Object.keys(perf).map((d) => Math.floor(parseInt(d) / pageSize).toString());
                if (sortMode != SORT_PERF) {
                    objLayout.perfVisible(true);
                    sliceAddrAndObjList = sliceAddrAndObjList.filter((d) => perfPageStrings.includes(d[SLICE_ADDR]))
                                                            .concat(sliceAddrAndObjList.filter((d) => !perfPageStrings.includes(d[SLICE_ADDR])));
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
                .style('transform', (d, i) => `translate(${10 - i}px, -50%)`)
                .style('border-top-left-radius', (d, i) => i == 0 ? '7px' : '0px')
                .style('border-bottom-left-radius', (d, i) => i == 0 ? '7px' : '0px')
                .style('border-top-right-radius', (d, i) => i == Object.keys(sorters).length - 1 ? '7px' : '0px')
                .style('border-bottom-right-radius', (d, i) => i == Object.keys(sorters).length - 1 ? '7px' : '0px')
                .style('background-color', (d) => tabLabelToCode[d] == sortMode ? '#ccc' : 'white')
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
                    d3.selectAll('.pageTab')
                        .transition()
                        .style('background-color', (d1) => tabLabelToCode[d1] == sortMode ? '#ccc' : 'white');
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
                        .style('background-color', (d) => tabLabelToCode[d] == sortMode ? '#ccc' : 'white');
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
                        sliceAddrAndObjList = Object.entries(
                            pageAddrs.reduce((acc, pageAddr) => {
                                acc[pageAddr] = new Array(numSubSlices*NUM_OBJS_PER_SUBSLICE).fill(0).map((e, i) => parseInt(pageAddr) + i*(pageSize / (numSubSlices*NUM_OBJS_PER_SUBSLICE)));
                                return acc;
                            }, {}))
                            .map((entry) => [entry[0], entry[1], getPageKey(entry[0])]);
                        sliceScale = d3.scaleLinear().domain([0, pageSize]).range([0, pageRectWidth]);
                        subsliceAddrToSplitEvents = splitEvents(allEvents, pageSize / (zoomedOut() ? numSubSlices : 1));
                        objAddrToSplitEvents = splitEvents(allEvents, pageSize / (zoomedOut() ? numSubSlices*NUM_OBJS_PER_SUBSLICE : 1));
                        if (zoomedOut())
                            bucketData = getBucketData(Object.entries(objAddrToSplitEvents));
                        sortMode = SORT_PAGE_NUM;
                        sorters['Address'].sortFunc();
                        // d3.selectAll('.pageTab')
                        //     .transition()
                        //     .style('background-color', (d1) => tabLabelToCode[d1] == sortMode ? '#ccc' : 'white');
                        d3.select('#pageLayout')
                            .style('height', `${pageAddrs.length*(pageRectHeight+10)}px`);
                        // updatePagesByTimestamp(getCurrTime());  // TODO: weird hack, not sure how to fix
                        updatePagesByTimestamp(getCurrTime());
                        constructPageTabs();
                        // const oldSliceSize = pageSize / Math.pow(numSubSlices, zoomLevel);
                        // const zoomedOut = oldSliceSize > zoomThreshold;
                        refreshObjectLayout(objAddrToSplitEvents[sliceAddrAndObjList[0][OBJ_LIST][0]] ? objAddrToSplitEvents[sliceAddrAndObjList[0][OBJ_LIST][0]] : [],
                            sliceAddrAndObjList[0][SLICE_ADDR], getCurrTime(), dataFields,
                            zoomedOut() ? zoomThreshold : pageSize / Math.pow(numSubSlices, 2)*(zoomLevel), cachelineSize);
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

    function splitEvents(events, sliceSize) {
        let currID = 0;
        const sliceAddrToEventMap = {};
        if (!events)
            return {}
        events.forEach((event) => {
            let sliceAddr = Math.floor(event.addr / sliceSize) * sliceSize;
            event.ID = currID++;
            let endOffsetLastObject = (event.addr % sliceSize) + event.size;
            
            if (!sliceAddrToEventMap[sliceAddr])
                sliceAddrToEventMap[sliceAddr] = [];
            sliceAddrToEventMap[sliceAddr].push(event);

            let nextSliceAddr = sliceAddr + sliceSize;
            while (endOffsetLastObject > sliceSize) {
                let newEvent = structuredClone(event);
                newEvent.size = Math.min(endOffsetLastObject - sliceSize, sliceSize);
                newEvent.addr = nextSliceAddr;
                newEvent.isDup = true;
                newEvent.ID = currID++;
                if (!sliceAddrToEventMap[nextSliceAddr])
                    sliceAddrToEventMap[nextSliceAddr] = [];
                sliceAddrToEventMap[nextSliceAddr].push(newEvent);
                endOffsetLastObject -= sliceSize;
                nextSliceAddr += sliceSize;
            }
        });

        return sliceAddrToEventMap;
    }

    function currentSliceSize() {
        return pageSize / (zoomLevel > 0 ? Math.pow(numSubSlices, 2)*(zoomLevel) : 1);
    }

    function getObjData(spaceUsed, index) {
        const objCapacity = currentSliceSize() / (numSubSlices*NUM_OBJS_PER_SUBSLICE);
        // const displaySize = pageRectWidth / (numSubSlices*NUM_OBJS_PER_SUBSLICE);
        const fullnessScale = d3.scaleLinear().domain([0, Math.ceil(objCapacity)]).range(['#d4d4d4', 'black']);
        return {
            ID: index, //TODO: this is prob wrong
            addr: index*objCapacity,
            size: objCapacity,
            col: spaceUsed === 0 ? d3.color('white') : fullnessScale(spaceUsed)
        };
    }

    function updatePagesByTimestamp(ts) {
        if (ts == undefined)
            ts = getCurrTime();
        objLayout.addElementsByTimestamp(ts);
        const groups = d3.select('#pageLayout')
            .selectAll('.pageGroup')
            .data(sliceAddrAndObjList, (d) => d[2]);
        
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
                        .style('stroke-width', (d) => parseInt(d[0]) == parseInt(selAddr) ? pageRectBorder + 2 : pageRectBorder)
                        .style('fill', 'none');
                    const oldSliceSize = pageSize / (zoomLevel > 0 ? Math.pow(numSubSlices, 2)*(zoomLevel) : 1);
                    const newSliceSize = pageSize / (Math.pow(numSubSlices, 2)*(zoomLevel + 1));
                    const sliceWidth = pageRectWidth / numSubSlices;
                    pageGroups.selectAll('.pageSliceSelector')
                        .data((d) => zoomedOut() ? new Array(numSubSlices).fill(0).map((en, i) => parseInt(d[0]) + i*(oldSliceSize / numSubSlices)) : [parseInt(d[0])])
                        .enter()
                        .append('rect')
                        .attr('class', 'pageSliceSelector')
                        .attr('x', (d, i) => i * sliceWidth)
                        .style('width', (d, i) => `${zoomedOut() ? sliceWidth : pageRectWidth}px`)
                        .style('height', `${pageRectHeight}px`)
                        .style('min-height', `${pageRectHeight}px`)
                        .style('fill', 'black')
                        .style('cursor', zoomedOut() ? 'zoom-in' : 'pointer')
                        .style('fill-opacity', 0.0)
                        .on('click', function(e, d) {
                            selAddr = d;
                            if (zoomedOut()) {
                                zoomLevel++;
                                sliceAddrAndObjList = new Array(numSubSlices).fill(0)
                                    .map((entry, i) => zoomedOut() ? [parseInt(selAddr) + i*newSliceSize,
                                                    new Array(numSubSlices*NUM_OBJS_PER_SUBSLICE).fill(0).map((e, j) => parseInt(selAddr) + i*(newSliceSize) + j*(newSliceSize / (numSubSlices*NUM_OBJS_PER_SUBSLICE))),
                                                    getPageKey(parseInt(selAddr) + i*newSliceSize)] : 
                                        [parseInt(selAddr) + i*newSliceSize, [], getPageKey(parseInt(selAddr) + i*newSliceSize)]);
                                    // .reduce((acc, sliceAddr) => {
                                    //     acc[sliceAddr] = zoomedOut() ? new Array(numSubSlices*NUM_OBJS_PER_SUBSLICE).map((e, i) => parseInt(sliceAddr) + i*(newSliceSize / (numSubSlices*NUM_OBJS_PER_SUBSLICE))) :
                                    //                                     [sliceAddr];
                                    //     return acc;
                                    // }, {});
                                // sliceToSubObjAddrs[selAddr].reduce((acc, sliceAddr) => {
                                //     acc[sliceAddr] = zoomedOut() ? new Array(numSubSlices*NUM_OBJS_PER_SUBSLICE).map((e, i) => sliceAddr + i*(pageSize / (Math.pow(numSubSlices, zoomLevel + 1)*NUM_OBJS_PER_SUBSLICE))) :
                                //                                     [sliceAddr];
                                //     return acc;
                                // }, {});
                                objAddrToSplitEvents = splitEvents(subsliceAddrToSplitEvents[selAddr], newSliceSize / (zoomedOut() ? numSubSlices*NUM_OBJS_PER_SUBSLICE : 1));
                                subsliceAddrToSplitEvents = splitEvents(subsliceAddrToSplitEvents[selAddr], newSliceSize / (zoomedOut() ? numSubSlices : 1));
                                sliceScale = d3.scaleLinear().domain([0, newSliceSize]).range([0, pageRectWidth]);
                                //getSliceData(parseInt(this.parentNode.getAttribute('data-addr')), selAddr, newSliceSize);
                                if (zoomedOut())
                                    bucketData = getBucketData(Object.entries(objAddrToSplitEvents));

                                // console.log(`New zoomLevel: ${zoomLevel}`);
                                // console.log(`zoomedOut? ${zoomedOut()}`);
                                // console.log(`New slice size: ${newSliceSize}`);
                                // console.log('New sliceAddrAndObjList:');
                                // console.log(sliceAddrAndObjList);
                                // console.log('New objAddrToSplitEvents:');
                                // console.log(objAddrToSplitEvents);
                                // console.log('New subsliceAddrToSplitEvents:');
                                // console.log(subsliceAddrToSplitEvents);
                                d3.select('#pageLayout')
                                    .style('height', `${Object.keys(sliceAddrAndObjList).length*(pageRectHeight+10)}px`);
                                // updatePagesByTimestamp(getCurrTime());  // TODO: weird hack, not sure how to fix
                                updatePagesByTimestamp(getCurrTime());
                                constructPageTabs();
                            }
                            const gp = d3.select('#pageLayout')
                                .selectAll('.pageGroup');
                            gp.select('.pageBorder')
                                .style('stroke-width', (d1) => parseInt(d1[0]) == parseInt(selAddr) ? pageRectBorder + 2 : pageRectBorder);
                            gp.select('.pageLabel')
                                .style('font-weight', (d1) => parseInt(d1[0]) == parseInt(selAddr) ? 'bold' : 'normal');

                            refreshObjectLayout(subsliceAddrToSplitEvents[selAddr] ? subsliceAddrToSplitEvents[selAddr] : [],
                                    selAddr, getCurrTime(), dataFields,
                                    zoomedOut() ? zoomThreshold : currentSliceSize(), cachelineSize);
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
                        .attr('class', 'pageLabel')
                        .attr('font-family', 'monospace')
                        .attr('x', '87%')
                        // .attr('y', '37%')
                        .style('font-size', '10px')
                        .style('font-weight', (d) => parseInt(d[0]) == parseInt(selAddr) ? 'bold' : 'normal')
                        .style('transform', `translate(0px, 13px)`)
                        .text((d) => `${parseInt(d[0]).toString(16)}`);
                
                    if (zoomLevel == 0) {
                        pageGroups.append('text')
                            .attr('font-family', 'monospace')
                            .attr('x', '87%')
                            // .attr('y', '63%')
                            .style('font-size', '10px')
                            .style('transform', `translate(0px, 23px)`)
                            .text((d) => `cluster: ${pageAddrToCluster[d[0]]}`)
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

        const sliceSize = currentSliceSize();
        
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
                (update) => update.style('visibility', sortMode == SORT_PERF ? 'inherit' : 'hidden'),
                (exit) => exit.remove()
            );
        
        const elements = d3.select('#pageLayout')
            .selectAll('.pageGroup')
            .selectAll('.dataObject')
            .data((d) => {
                    const retData = zoomedOut() ? d[1].map((objAddr, i) => {
                        return getObjData(bucketData[objAddr] ? bucketData[objAddr][getBucketIndexFromTs(ts)] : 0, i);
                    }) : 
                        (subsliceAddrToSplitEvents[parseInt(d[0])] ? subsliceAddrToSplitEvents[parseInt(d[0])] : [])
                            .filter((obj) => obj.allocTs <= ts && (obj.freeTs == null || obj.freeTs >= ts))
                                                .map((obj) => {
                                                    obj.vis = mainVis.isTypeSampled(obj.type);
                                                    return obj;
                                                })
                                                .sort((a, b) => b.allocTs - a.allocTs);
                    return retData;
                },
                (d) => d.ID)
                .order();
        
        elements.join(
            (enter) => {
                const gp = enter.insert('g', ':first-child')
                    .attr('class', 'dataObject')
                    .style('visibility', (d) => (d.vis || zoomedOut()) ? 'inherit' : 'hidden');
                gp.append('rect')
                    .attr('class', 'dataObjectRect')
                    .attr('x', (d) =>  sliceScale(d.addr % sliceSize))
                    .attr('y', 0)
                    .attr('width', (d) => sliceScale(Math.min(d.size, sliceSize - (d.addr % sliceSize))))
                    .attr('height', pageRectHeight)
                    // .style('stroke', 'black')
                    // .style('stroke-width', '1px')
                    .style('fill', (d) => zoomedOut() ? d.col : colourOfType[d.type]);
                if (!zoomedOut()) {
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
                update.style('visibility', (d) => (d.vis || zoomedOut()) ? 'inherit' : 'hidden');
                update.select('.dataObjectRect')
                    .style('fill', (d) => zoomedOut() ? d.col : colourOfType[d.type]);
            },
            (exit) => exit.remove()
        );
    }

    function getPageKey(pageAddr) {
        return (1 + parseInt(pageAddr))*(1 + zoomLevel);
    }

    // function getZoomGroups(events) {
    //     const sliceSize = pageSize / Math.pow(numSubSlices, zoomLevel);
    //     const displaySize = (sliceSize*NUM_OBJS_PER_SUBSLICE) / pageRectWidth;
    //     const chunkTypes = events.reduce((acc, curr) => {
    //             let ind = Math.floor((curr.addr % sliceSize) / displaySize);
    //             acc[ind] += curr.size;
    //             return acc;
    //         }, new Array(pageRectWidth / NUM_OBJS_PER_SUBSLICE).fill(0));

    //     const fullnessScale = d3.scaleLinear().domain([0, Math.ceil(displaySize)]).range(['#d4d4d4', 'black']);
    //     const ret = chunkTypes.map((d, i) => {
    //             return {
    //                 ID: i, //TODO: this is prob wrong
    //                 addr: i*displaySize,
    //                 size: displaySize,
    //                 col: d === 0 ? d3.color('white') : fullnessScale(d)
    //             };
    //         });
    //     return ret;
    // }

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
            .style('position', 'relative')
            .style('z-index', 3)
            .append('svg')
            .attr('id', 'memLayout')
            .style('width', '100%')
            .style('height', `${actualHeight + y + 10}px`)
            .style('position', 'relative')
            .style('visibility', 'inherit');

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
        memLayout.datum({objects: objects.filter((obj) => obj.type != null),
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

    drawPageLayout.numBuckets = function(val) {
        if (!arguments) return numBuckets;
        numBuckets = val;
        return drawPageLayout;
    }

    drawPageLayout.getBucketIndexFromTs = function(val) {
        if (!arguments) return getBucketIndexFromTs;
        getBucketIndexFromTs = val;
        return drawPageLayout;
    }

    return drawPageLayout;
}

export default pageLayout;