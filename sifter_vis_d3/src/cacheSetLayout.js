import * as d3 from 'd3';
import { currCacheLineSize } from './timeGraphLayout.js';
import { mainVis } from './dbloader.js';


const CACHE_LAYOUT_WIDTH = '350px';
const CACHE_LAYOUT_WIDTH_FOCUS = '850px';
const FOCUS_ARROW_X = '7px';
const FOCUS_ARROW_Y = '135px';
const CACHE_GROUP_PAD = 1.1;

const CACHE_SIZE_LABELS = {
    B:      1,
    KiB:    1 << 10,
    MiB:    1 << 20
};
const INPUT_BOX_WIDTH = {
    normal: '50px',
    wide:   '70px'
};

/* TODO:
    *   Attempt to auto-detect cache information in memhook application?
    *   Store presets with cache information of processors that have been
        mapped */

function cacheSetLayout() {
    let origObjects = [],
        objects = [],
        cacheInfo = [],
        current = true,
        currTime = 0,
        currCache = {},
        sampledCls = 0,
        mainVis = undefined,
        focused = false,
        pageSize = 4096,
        chosenUnit = 'KiB',
        defaultWidth = 0,
        canvas,
        expandedTypes = undefined,
        fields = undefined,
        bucketData = [],
        allBucketData = [],
        prevIndex = undefined,
        zoomLevel = 1,
        maxSquares = 1024,
        startCs = 0,
        numBuckets = 0,
        getBucketIndexFromTs = undefined;
        // sizeOfBucket = 1;
        // focusCallback = undefined;

    function drawLayout(selection) {
        
        // origObjects = selection.datum();
        // objects = selection.datum();
        // sampledCls = currCacheLineSize;
        canvas = document.createElement('canvas');
    
        let cacheSetTabs = selection.append('div')
            .attr('id', 'cacheSetTabs')
            .style('display', 'inline-block')
            .style('position', 'relative')
            .style('width', '100%')
            .style('height', '22%')
            .style('transform', 'translate(10px, 0px)');
    
        let tabGroup = cacheSetTabs.selectAll('.cacheTab')
            .data(cacheInfo)
            .enter()
            .append('div')
            .attr('class', 'classTab')
            .style('width', '45px')
            .style('height', '37px')
            .style('float', 'left')
            .style('margin', '0px')
            .style('padding', '0px')
            .style('border', '1px solid #ccc')
            .style('background-color', 'white')
            .style('pointer-events', 'visible')
            .style('cursor', 'pointer')
            .style('position', 'relative')
            .style('top', '50%')
            .style('transform', 'translateY(-50%)')
            .style('border-top-left-radius', (d, i) => i == 0 ? '7px' : '0px')
            .style('border-bottom-left-radius', (d, i) => i == 0 ? '7px' : '0px')
            .style('border-top-right-radius', (d, i) => i == cacheInfo.length - 1 ? '7px' : '0px')
            .style('border-bottom-right-radius', (d, i) => i == cacheInfo.length - 1 ? '7px' : '0px')
            .on('click', function(e, d) {
                currCache = d;
                zoomLevel = 1;
                startCs = 0;
                d3.select('#cacheWidthHandle').attr('cx', currCache.currDragX);
                d3.select('#cacheSizeInput')
                    .property('value', Math.floor(parseInt(currCache.size) / CACHE_SIZE_LABELS[chosenUnit]));
                d3.select('#assocInput')
                    .property('value', currCache.associativity);
                // currSize = d.size;
                // currAssoc = d.associativity;
                // currWidth = d.width;
                refreshSquares();
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
            // .attr('text-anchor', 'middle')
            // .attr('x', (d, i) => i*45 + 22)
            // .attr('y', 18)
            .style('font-family', 'monospace')
            .style('font-size', '14px')
            .style('text-align', 'center')
            .style('line-height', '5px')
            // .style('alignment-baseline', 'middle')
            .style('pointer-events', 'none')
            .text((d, i) => `L${i+1}`);

        // Set the current cache to L1 (first cache in cacheInfo)
        currCache = cacheInfo[0];
        // currCacheLineSize = currCache.cls;
        // currAssociativity = currCache.associativity;

        let inputGroup = cacheSetTabs.append('div')
            .style('float', 'left')
            .style('width', '240px')
            .style('height', '74%')
            .style('position', 'relative')
            .style('top', '50%')
            .style('transform', 'translateY(-50%)')
            .style('left', '8px')
            .style('display', 'table');

        // Group consisting of 'cache line size' label and input box
        let cacheSizeGroup = inputGroup.append('div')
            .style('display', 'table-row')
            .style('width', '100%')
            .style('height', '15px')
            .style('position', 'relative');

        cacheSizeGroup.append('div')
            .style('font-family', 'monospace')
            .style('font-size', '12px')
            .text('cache size:')
            .style('display', 'table-cell')
            .style('vertical-align', 'middle');

        // console.log('SIZE VALUE: ', parseInt(currCache.size));
        // console.log('CHOSEN UNIT: ', chosenUnit);
        // console.log('UNIT VALUE: ', CACHE_SIZE_LABELS[chosenUnit]);
        // console.log('INITIAL LABEL: ', Math.floor(parseInt(currCache.size) / CACHE_SIZE_LABELS[chosenUnit]));
        const cacheSizeInputBox = cacheSizeGroup.append('div')
            .style('display', 'table-cell')
            .style('vertical-align', 'middle')
            .append('input')
            .attr('id', 'cacheSizeInput')
            .attr('type', 'number')
            .attr('value', Math.floor(parseInt(currCache.size) / CACHE_SIZE_LABELS[chosenUnit]))
            .style('width', chosenUnit == 'B' ? INPUT_BOX_WIDTH.wide : INPUT_BOX_WIDTH.normal)
            .on('input', function() {
                currCache.size = d3.select(this).property('value') * CACHE_SIZE_LABELS[chosenUnit];
            });

        const unitSelector = cacheSizeGroup.append('div')
            .style('display', 'table-cell')
            .style('vertical-align', 'middle')
            .append('select')
            .attr('id', 'unitSelectorInput')
            .style('left', '4px')
            .on('change', function() {
                let newUnit = d3.select(this).property('value');
                cacheSizeInputBox.style('width', newUnit == 'B' ? INPUT_BOX_WIDTH.wide : INPUT_BOX_WIDTH.normal);
                let oldCacheSizeValue = cacheSizeInputBox.property('value');
                cacheSizeInputBox.property('value', Math.floor((oldCacheSizeValue * CACHE_SIZE_LABELS[chosenUnit]) / CACHE_SIZE_LABELS[newUnit]));
                chosenUnit = newUnit;
            });

        unitSelector.selectAll('option')
            .data(Object.keys(CACHE_SIZE_LABELS))
            .enter()
            .append('option')
            .attr('value', (d) => d)
            .text((d) => d);

        let selector = document.getElementById('unitSelectorInput');
        for (let i, j = 0; i = selector.options[j]; j++) {
            if (i.value == chosenUnit) {
                selector.selectedIndex = j;
                break;
            }
        }

        // Group consisting of 'associativity' label and input box
        let assocGroup = inputGroup.append('div')
            .style('display', 'table-row')
            .style('width', '100%')
            .style('height', '22px')
            .style('position', 'relative');

        assocGroup.append('div')
            .style('font-family', 'monospace')
            .style('font-size', '12px')
            .text('associativity:')
            .style('display', 'table-cell')
            .style('vertical-align', 'middle');

        assocGroup.append('div')
            .style('display', 'table-cell')
            .style('vertical-align', 'middle')
            .append('input')
            .attr('id', 'assocInput')
            .attr('type', 'number')
            .attr('value', parseInt(currCache.associativity))
            .style('width', INPUT_BOX_WIDTH.normal)
            .on('input', function() {
                currCache.associativity = d3.select(this).property('value');
            });


        const pattern = selection.append('svg')
            .attr('id', 'cacheSetSVG')
            .style('width', CACHE_LAYOUT_WIDTH)
            .style('height', '78%')
            .style('overflow', 'visible')
            .append('defs')
            .append('pattern')
            .attr('id', 'pattern-check')
            .attr('x', 0)
            .attr('y', 0)
            .attr('width', 8)
            .attr('height', 8)
            .attr('patternUnits', 'userSpaceOnUse');
        
        pattern.append('rect')
            .attr('x', 0)
            .attr('y', 0)
            .attr('width', 4)
            .attr('height', 4)
            .style('fill', 'black');
        
        pattern.append('rect')
            .attr('x', 4)
            .attr('y', 4)
            .attr('width', 4)
            .attr('height', 4)
            .style('fill', 'black');

        drawToggle();
        drawFocusButton();
        drawWidthHandle();
        allBucketData = computeBucketData();
        bucketData = computeZoomedBucketData();
    }

    function computeBucketData() {
        let numCacheSets = Math.ceil(currCache.size / (currCache.associativity*currCacheLineSize));
        let retBucketData = new Array(numBuckets+2).fill(0).map(() => new Array(numCacheSets).fill(undefined));

        objects.forEach((obj) => {
            const startBucketIndex = getBucketIndexFromTs(obj.allocTs);
            const endBucketIndex = obj.freeTs ? getBucketIndexFromTs(obj.freeTs) : undefined;
            // console.log(`startBucketIndex = ${startBucketIndex}`);
            // console.log('   for the following object:');
            // console.log(obj);
            const [startSet, endSet] = getCacheSetRange(obj, numCacheSets);

            // if (startBucketIndex <= 1 && obj.addr % 4096 == 0) {
            //     console.log('Here is an object in first two buckets:');
            //     console.log(obj);
            //     console.log(`startBucketIndex: ${startBucketIndex}, endBucketIndex: ${endBucketIndex}`);
            //     console.log(`startSet: ${startSet}, endSet: ${endSet}`);
            // }

            let i = startSet;
            let afterFirstLoop = false;
            while (i != (endSet + 1) % numCacheSets || !afterFirstLoop) {     // These should be ACTUAL cache sets, not groups of cache sets
                // if (startBucketIndex <= 1 && obj.addr % 4096 == 0)
                //     console.log(`   Adding 1 to cache set ${i}`);
                if (retBucketData[startBucketIndex][i] == undefined)
                    retBucketData[startBucketIndex][i] = {}
                retBucketData[startBucketIndex][i][obj.type] ?  retBucketData[startBucketIndex][i][obj.type] += 1 : 
                                                                retBucketData[startBucketIndex][i][obj.type] = 1;
                if (endBucketIndex != undefined) {
                    if (retBucketData[endBucketIndex][i] == undefined)
                        retBucketData[endBucketIndex][i] = {}
                    retBucketData[endBucketIndex][i][obj.type] ?    retBucketData[endBucketIndex][i][obj.type] -= 1 : 
                                                                    retBucketData[endBucketIndex][i][obj.type] = -1;
                }
                i = (i + 1) % numCacheSets;
                afterFirstLoop = true;
            };
        });

        return retBucketData;
    }

    function addTypes(a, b) {
        // console.log(`in addTypes:`);
        // console.log(a);
        // console.log(b);
        let c = a ? structuredClone(a) : {};
        if (b) {
            Object.keys(b).forEach((tp) => {
                c[tp] ? c[tp] += b[tp] : c[tp] = b[tp];
            });
        }
        return c;
    }

    function numCacheSetsInView() {
        return currCache.size / (currCache.associativity*Math.pow(currCacheLineSize, zoomLevel));
    }

    function zoomedOut() {
        return numCacheSetsInView() > maxSquares;
    }

    function sumAllTypes(cs, excludeNonVis=false) {
        // if (excludeNonVis) {
        //     console.log('Here are the keys:');
        //     console.log(Object.keys(cs));
        //     Object.keys(cs).forEach((tp) => {
        //         console.log(`Is type ${tp} NOT sampled? ${!mainVis.isTypeSampled(tp)}`);
        //     });
        // }
        return cs ? Object.keys(cs).reduce((acc, curr) => acc + ((excludeNonVis && !mainVis.isTypeSampled(curr)) ? 0 : parseInt(cs[curr])), 0) : 0;
    }

    function mean(data) {
        return data.reduce((acc, curr) => acc + parseInt(curr), 0) / data.length;
    }

    function variance(data) {
        const meanData = mean(data);
        return data.reduce((acc, curr) => acc + Math.pow(parseInt(curr) - meanData, 2), 0) / data.length;
    }

    function computeZoomedBucketData() {
        console.log(`startCs at begin of zoomedBucketData: ${startCs}`);
        const numberOfCacheSetsInCurrentView = currCache.size / (currCache.associativity*Math.pow(currCacheLineSize, zoomLevel));
        const numSetsInGroup = zoomedOut() ? Math.ceil(numberOfCacheSetsInCurrentView / currCacheLineSize) : 1;

        // console.log(`num cs in current view: ${numberOfCacheSetsInCurrentView}, num sets in group: ${numSetsInGroup}`);

        const data = new Array(numBuckets+2).fill(undefined);
        // let prevOccData = undefined;
        const aggData = new Array(numBuckets+2).fill(undefined);
        for (let i = 0; i < numBuckets+2; i++) {
            data[i] = [];
            aggData[i] = [];
            for (let j = 0; j*numSetsInGroup < numberOfCacheSetsInCurrentView; j++) {
                const beginSlice = startCs + (j*numSetsInGroup);
                const endSlice = Math.min(startCs + numberOfCacheSetsInCurrentView, startCs + (j+1)*numSetsInGroup);

                if (i > 0) {
                    data[i].push(allBucketData[i].slice(beginSlice, endSlice).map((cs, k) => addTypes(cs, data[i-1][j][k])));
                    // prevOccData = data[i][j].map((cs) => sumAllTypes(cs));//.map((csum, k) => csum + prevOccData[k]);

                    // if (i <= 3 && j == 0) {
                    //     console.log(`Here is slice of allBucketData time ${i}`);
                    //     console.log(allBucketData[i].slice(beginSlice, endSlice));
                    //     console.log('Here is data[i][j]');
                    //     console.log(data[i][j]);
                    // }
                    
                    const occupancy = data[i][j].map((cs) => sumAllTypes(cs));
                    aggData[i].push({types: addTypes(aggData[i-1].types, data[i][j].reduce((acc, curr) => addTypes(acc, curr), {})),
                                    // occ: occupancy,
                                    variance: variance(occupancy),
                                    maxVal: occupancy.reduce((acc, curr) => Math.max(acc, parseInt(curr)), 0),
                                    startCs: j*numSetsInGroup});
                }
                else {
                    data[i].push(allBucketData[i].slice(beginSlice, endSlice));
                    // prevOccData = data[i][j].map((cs) => sumAllTypes(cs));

                    // if (j == 0) {
                    //     console.log(`Here is slice of allBucketData time ${i}`);
                    //     console.log(allBucketData[i].slice(beginSlice, endSlice));
                    //     console.log('Here is data[i][j]');
                    //     console.log(data[i][j]);
                    // }

                    const occupancy = data[i][j].map((cs) => sumAllTypes(cs));
                    aggData[i].push({types: data[i][j].reduce((acc, curr) => addTypes(acc, curr), {}),
                                    // occ: occupancy,
                                    variance: variance(occupancy),
                                    maxVal: occupancy.reduce((acc, curr) => Math.max(acc, parseInt(curr)), 0),
                                    startCs: j*numSetsInGroup});
                }
            }
        }
        // console.log('data:');
        // console.log(data);
        // console.log('prevOccData:');
        // console.log(prevOccData);
        // console.log('Returned aggData:');
        // console.log(aggData);
        return aggData;
    }

    function getCacheSet(addr, numCacheSets) {
        return Math.floor(addr / currCacheLineSize) % numCacheSets;
    }

    function getCacheSetRange(obj, numCacheSets) {
        let startSet = getCacheSet(obj.addr, numCacheSets);
        let endSet = getCacheSet(obj.addr + obj.size - 1, numCacheSets);
        return [startSet,
            (endSet == startSet && obj.size > currCacheLineSize) || (obj.size >= currCache.size) ? (startSet + numCacheSets - 1) % numCacheSets : endSet];
    }

    function refreshExpandedTypes() {
        objects = [];
        origObjects.forEach((obj) => {
            if (expandedTypes.has(obj.type)) {
                fields[obj.type].map((st) => ({ ID: obj.ID,
                                                        addr: obj.addr + st.offset,
                                                        allocTs: obj.allocTs,
                                                        file: obj.file,
                                                        freeTs: obj.freeTs,
                                                        size: st.size,
                                                        type: st.subtype,
                                                        isSubtype: true
                        })).forEach((st) => objects.push(st));
            }
            else {
                objects.push(obj);
            }
        });
        // objects = origObjects.map((obj) => expandedTypes.has(obj.type) ? [obj] : [obj]);
        //     fields[obj.type].map((st) => ({ ID: obj.ID,
        //                                     addr: obj.addr + st.offset,
        //                                     allocTs: obj.allocTs,
        //                                     file: obj.file,
        //                                     freeTs: obj.freeTs,
        //                                     size: st.size,
        //                                     type: st.subtype,
        //                                     isSubtype: true
        //     })) : [obj]).reduce((acc, curr) => acc.concat(curr), []);
        refreshSquares();
    }

    drawLayout.refreshExpandedTypes = function() {
        refreshExpandedTypes();
    }

    drawLayout.redraw = function() {
        drawSquares(true);
    }

    drawLayout.expandedTypes = function(val) {
        if (!arguments) return expandedTypes;
        expandedTypes = val;
        return drawLayout;
    }

    drawLayout.fields = function(val) {
        if (!arguments) return fields;
        fields = val;
        return drawLayout;
    }

    drawLayout.cacheInfo = function(val) {
        if (!arguments) return cacheInfo;
        cacheInfo = val;
        return drawLayout;
    }

    drawLayout.currTime = function(val) {
        if (!arguments) return currTime;
        currTime = val;
        if (current) drawSquares();
        return drawLayout;
    }

    drawLayout.mainVis = function(val) {
        if (!arguments) return mainVis;
        mainVis = val;
        return drawLayout;
    }

    drawLayout.pageSize = function(val) {
        if (!arguments) return pageSize;
        pageSize = val;
        return drawLayout;
    }

    drawLayout.defaultWidth = function(val) {
        if (!arguments) return defaultWidth;
        defaultWidth = val;
        return drawLayout;
    }

    drawLayout.numBuckets = function(val) {
        if (!arguments) return numBuckets;
        numBuckets = val;
        return drawLayout;
    }

    drawLayout.getBucketIndexFromTs = function(val) {
        if (!arguments) return getBucketIndexFromTs;
        getBucketIndexFromTs = val;
        return drawLayout;
    }

    drawLayout.sizeOfBucket = function(val) {
        if (!arguments) return sizeOfBucket;
        sizeOfBucket = val;
        return drawLayout;
    }

    drawLayout.records = function(val) {
        origObjects = val;
        objects = val;
        return drawLayout;
    }

    // drawLayout.focusCallback = function(val) {
    //     if (!arguments) return focusCallback;
    //     focusCallback = val;
    //     return drawLayout;
    // }

    function drawToggle() {
        d3.select('#toggleGroup').remove();
    
        let toggleGroup = d3.select('#cacheSetSVG')
            .append('g')
            .attr('id', 'toggleGroup')
            .style('transform', 'translate(95px, 92%)');
        
        toggleGroup.append('rect')
            .style('width', '24px')
            .style('height', '5px')
            .style('fill', '#ddd');
        
        toggleGroup.append('circle')
            .attr('class', 'toggle')
            .attr('cx', !current ? 24 : 0)
            .attr('cy', 2.5)
            .attr('r', 10)
            .style('fill', '#ccc')
            .on('click', function() {
                current = !current;
                if (!current) {
                    d3.select(this)
                        .transition()
                        .ease(d3.easeCubicOut)
                        .attr('cx', 24);
                    drawSquares();
                }
                else {
                    d3.select(this)
                        .transition()
                        .ease(d3.easeCubicOut)
                        .attr('cx', 0);
                    drawSquares();
                }
            });
    
        toggleGroup.append('text')
            .attr('x', -70)
            .attr('y', 5)
            .attr('font-family', 'monospace')
            .text('Current');
    
        toggleGroup.append('text')
            .attr('x', 43)
            .attr('y', 5)
            .attr('font-family', 'monospace')
            .text('All events heatmap');
    }

    function drawWidthHandle() {
        d3.select('#cacheSetSVG')
            .append('circle')
            .attr('id', 'cacheWidthHandle')
            .attr('cx', currCache.currDragX)
            .attr('cy', FOCUS_ARROW_Y)
            .attr('r', 10)
            .style('cursor', 'pointer')
            .style('fill', 'url(#crosshatch)')
            .style('visibility', 'hidden')
            .call(d3.drag()
                .on('drag', function(e) {
                    d3.select(this).attr('cx', e.x);
                    currCache.currDragX = e.x;
                    
                    if (Math.floor((currCache.initWidth + e.x - currCache.initDragX) / currCache.sqSize) !=
                        Math.floor(currCache.width / currCache.sqSize)) {
                        currCache.width = currCache.initWidth + e.x - currCache.initDragX;
                        drawSquares();
                    }
                }));
    }

    function drawFocusButton() {
        let focusButtonGroup = d3.select('#cacheSetSVG')
            .append('g')
            .attr('id', 'cacheFocusButtonGroup');

        let gradient = focusButtonGroup.append('defs')
            .append('linearGradient')
            .attr('id', 'cacheFocusGradient')
            .attr('x1', '0%')
            .attr('x2', '100%')
            .attr('y1', '50%')
            .attr('y2', '50%')
            .attr('spreadMethod', 'pad');

        gradient.append('stop')
            .attr('offset', '0%')
            .attr('stop-color', '#ccc')
            .attr('stop-opacity', 1);
        
        gradient.append('stop')
            .attr('offset', '100%')
            .attr('stop-color', 'white')
            .attr('stop-opacity', 1);

        let arrow = d3.symbol()
            .type(d3.symbolTriangle)
            .size(40);

        focusButtonGroup.append('rect')
            .attr('x', 0)
            .attr('y', 5)
            .style('width', '20px')
            .style('height', '265px')
            .style('fill', 'white')
            .style('pointer-events', 'visible')
            .style('cursor', 'pointer')
            .on('click', function(e, d) {
                focused = !focused;
                d3.select('#cacheFocusArrow')
                    .transition()
                    .ease(d3.easeCubicOut)
                    .style('transform', `translate(${FOCUS_ARROW_X}, ${FOCUS_ARROW_Y}) rotate(${focused ? '' : '-'}0.25turn)`);
                if (focused) {
                    d3.select('#cacheWidthHandle').style('visibility', 'visible');
                    d3.select('#cacheSetSVG').style('width', CACHE_LAYOUT_WIDTH_FOCUS);
                }
                else {
                    d3.select('#cacheWidthHandle').style('visibility', 'hidden');
                    d3.select('#cacheSetSVG').style('width', CACHE_LAYOUT_WIDTH);
                }
                mainVis.toggleCacheFocus();
            })
            .on('mouseover', function() {
                d3.select(this)
                    .transition()
                    .style('fill', 'url(#cacheFocusGradient)');
            })
            .on('mouseout', function() {
                d3.select(this)
                    .transition()
                    .style('fill', 'white');
            });

            focusButtonGroup.append('path')
                .attr('id', 'cacheFocusArrow')
                .attr('d', arrow)
                .attr('fill', '#ccc')
                .style('pointer-events', 'none')
                .style('transform', `translate(${FOCUS_ARROW_X}, ${FOCUS_ARROW_Y}) rotate(-0.25turn)`);
    }
    
    // function getSquaresData(allocs) {
    //     let currSize = currCache.size,
    //         currAssoc = currCache.associativity,
    //         currWidth = currCache.width,
    //         cacheLineSize = sampledCls;
    //     let numCacheSets = Math.ceil(currSize / (currAssoc*cacheLineSize));
    //     let squareSize = Math.floor(defaultWidth / Math.sqrt(numCacheSets));
    //     let setsPerRow = Math.floor(currWidth / squareSize);

    //     if (!currCache.sqSize) currCache.sqSize = squareSize;
    
    //     let setMap = allocs.map((obj) => ({cacheline: Math.floor(obj.addr / cacheLineSize) % numCacheSets,
    //         spread: 1 + Math.max(Math.ceil((obj.size - (cacheLineSize - (obj.addr % cacheLineSize))) / cacheLineSize), 0),
    //         type: obj.type}));
    //     let freqMapByType = setMap.reduce((acc, curr) => {
    //         let inc = Math.ceil(curr.spread / numCacheSets);
    //         for (let i = curr.cacheline; i < curr.cacheline + Math.min(numCacheSets, curr.spread); i++) {
    //             let rounded = i - curr.cacheline < curr.spread % numCacheSets ? inc : inc - 1;
    //             let j = i % numCacheSets;
    //             if (!acc[j])
    //                 acc[j] = {};
    //             acc[j][curr.type] ? acc[j][curr.type] += rounded : acc[j][curr.type] = rounded;
    //         }
    //         // acc[curr] ? acc[curr]++ : acc[curr] = 1;
    //         return acc;
    //     }, {});
    //     let freqMap = Object.keys(freqMapByType)
    //         .reduce((acc1, curr1) => {
    //             acc1[curr1] = Object.keys(freqMapByType[curr1])
    //                 .reduce((acc2, curr2) => {
    //                     return acc2 + freqMapByType[curr1][curr2];
    //                 }, 0);
    //             return acc1;
    //         }, {});
            
    
    //     return new Array(numCacheSets).fill(undefined).map((d, i) => 
    //         ({x: (i % setsPerRow)*squareSize,
    //             y: Math.floor(i / setsPerRow)*squareSize,
    //             freq: freqMap[i],
    //             freqByType: freqMapByType[i],
    //             propByType: freqMapByType[i] ? Object.keys(freqMapByType[i])
    //                 .reduce((acc, curr) => {
    //                     acc[curr] = freqMapByType[i][curr] / freqMap[i];
    //                     return acc;
    //                 }, {}) : undefined,
    //             size: squareSize}));
    // }

    function drawSquares(force=false) {
        const bucketIndex = getBucketIndexFromTs(currTime);
        if (bucketIndex == prevIndex && !force)
            return;
        prevIndex = bucketIndex;
        // console.log('bucket data:');
        // console.log(bucketData[bucketIndex]);
        const squaresData = bucketData[bucketIndex].map((sq) => {
            const nsq = structuredClone(sq);
            Object.keys(nsq.types).forEach((tp) => {
                if (!mainVis.isTypeSampled(tp) && !mainVis.isSubtypeSampled(tp)) // TODO subtypes???
                    nsq.types[tp] = 0;
            });
            return nsq;
        });
        // getSquaresData(objects.filter((d) => (current ? d.allocTs <= currTime && (d.freeTs == null || d.freeTs >= currTime) : true)
        //                                                 && (d.isSubtype ? mainVis.isSubtypeSampled(d.type) : mainVis.isTypeSampled(d.type))));
        // let squaresData = getSquaresData(current ? objects.filter(d => d.allocTs <= currTime && (d.freeTs == null || d.freeTs >= currTime)) : objects);
        const maxVal = Math.max(1, Math.max(...squaresData.map((d) => d.maxVal)));
        const maxFreq = Math.max(1, Math.max(...squaresData.map((d) => sumAllTypes(d.types))));
        const heatScale = d3.scaleLinear().domain([0, maxFreq / 2, maxFreq]).range(['white', 'yellow', 'red']);
    
        let cacheLayout = d3.select('#cacheLayout');
    
        if (cacheLayout.empty()) {
            cacheLayout = d3.select('#cacheSetSVG')
                .insert('g', '#toggleGroup')
                .attr('id', 'cacheLayout')
                .style('transform', 'translate(20px, 5px)');
        }

        const numGroups = zoomedOut() ? currCacheLineSize : numCacheSetsInView();
        const squareSize = Math.floor(defaultWidth / Math.sqrt(numGroups));
        const groupsPerRow = Math.floor(currCache.width / squareSize);
    
        const textHeight = 12;
        const buffer = 3;
        cacheLayout.selectAll('rect')
            .data(squaresData)
            .join((enter) => {
                if (zoomedOut()) {
                    enter.append('rect')
                        .attr('x', (d, i) => ((i % groupsPerRow)*squareSize))
                        .attr('y', (d, i) => (Math.floor(i / groupsPerRow)*squareSize))
                        .attr('width', squareSize / CACHE_GROUP_PAD)
                        .attr('height', squareSize / CACHE_GROUP_PAD)
                        .attr('rx', 7)
                        .style('stroke', '#ccc')
                        .style('stroke-width', 0.5)
                        .style('pointer-events', 'none')
                        .style('fill', 'white');
                }
                enter.append('rect')
                    .attr('id', 'dataPatternRect')
                    .attr('x', (d, i) => ((i % groupsPerRow)*squareSize))
                    .attr('y', (d, i) => (Math.floor(i / groupsPerRow)*squareSize))
                    .attr('width', squareSize / (zoomedOut() ? CACHE_GROUP_PAD : 1))
                    .attr('height', squareSize / (zoomedOut() ? CACHE_GROUP_PAD : 1))
                    .attr('rx', zoomedOut() ? 7 : 0)
                    .style('stroke', zoomedOut() ? 'red' : '#ccc')
                    .style('stroke-width', 0.5)
                    .style('pointer-events', 'visible')
                    .style('cursor', zoomedOut() ? 'zoom-in' : 'default')
                    .style('opacity', (d) => (zoomedOut() ? Math.min((d.variance * 2.0) / maxVal, 1.0) : 1.0))
                    .style('fill', function(d, i) {
                        // console.log(`types: `);
                        // console.log(d.types);
                        // console.log(`sumAllTypes: ${sumAllTypes(d.types, true)}`);
                        return zoomedOut() ? 'url(#pattern-check)' : heatScale(sumAllTypes(d.types));
                    })
                    .on('mouseover', function(e, d) {
                        d3.select('#cacheSetHint')
                            .remove();
                        if (Object.keys(d.types).length > 0) {
                            const context = canvas.getContext('2d');
                            context.font = '10px monospace';
                            const labels = zoomedOut() ? [`occupancy variance: ${d.variance}`] : Object.keys(d.types)
                                .filter((tp) => d.types[tp] > 0)
                                .sort((a, b) => d.types[b] - d.types[a])
                                .map((tp) => `${tp}: ${d.types[tp]} (${Math.round((d.types[tp] / sumAllTypes(d.types))*1000)/10}%)`);
                            const textWidth = labels.reduce((acc, curr) => Math.max(acc, context.measureText(curr).width), 0) + 20;
                            let typeGroup = cacheLayout.append('g')
                                .attr('id', 'cacheSetHint')
                                .style('transform', `translate(${d3.pointer(e)[0]}px, ${d3.pointer(e)[1] - (textHeight*labels.length) - buffer}px)`);
                            typeGroup.append('rect')
                                .attr('fill', 'white')
                                .style('position', 'fixed')
                                .style('width', `${textWidth}px`)
                                .style('height', `${labels.length*textHeight + buffer}px`)
                                .style('left', '0px')
                                .style('top', '0px')
                                .style('pointer-events', 'none');
                            typeGroup.selectAll('.cacheSetHintText')
                                .data(labels)
                                .enter()
                                .append('text')
                                .attr('font-family', 'monospace')
                                .style('font-size', '10px')
                                .style('position', 'fixed')
                                .style('top', '0px')
                                .style('left', '0px')
                                .style('transform', (d, i) => `translateY(${(i+1)*textHeight}px)`)
                                .style('pointer-events', 'none')
                                .text((lb) => lb);
                        }
                    })
                    .on('mousemove', function(e, d) {
                        if (Object.keys(d.types).length > 0) {
                            const labels = zoomedOut() ? [`occupancy variance: ${d.variance}`] : Object.keys(d.types)
                                .filter((tp) => d.types[tp] > 0);
                            cacheLayout.select('#cacheSetHint')
                                .style('transform', `translate(${d3.pointer(e)[0]}px, ${d3.pointer(e)[1] - (textHeight*labels.length) - buffer}px)`);
                        }
                    })
                    .on('mouseout', function() {
                        d3.select('#cacheSetHint')
                            .remove();
                    })
                    .on('click', function(e, d) {
                        if (zoomedOut()) {
                            zoomLevel += 1;
                            startCs = d.startCs;
                            refreshSquares();
                        }
                    });
                },
                (update) => {
                    if (zoomedOut()) {
                        update.style('opacity', (d) => Math.min((d.variance * 2.0) / maxVal, 1.0));
                    }
                    else {
                        update.style('fill', (d) => heatScale(sumAllTypes(d.types)));
                    }
                },
                (exit) => exit.remove()
            );
            // .style('transform', 'translate(50px, 85px)');
    }
    
    function refreshSquares() {
        d3.select('#cacheLayout').remove();
        allBucketData = computeBucketData();
        bucketData = computeZoomedBucketData();
        drawSquares(true);
    }

    return drawLayout;
}

export default cacheSetLayout;