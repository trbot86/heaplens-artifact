import * as d3 from 'd3';
import { colourOfType } from './vis.js';
import { mainVis } from './dbloader.js';
import { SettingsPopup } from './settingsPopup.js';

export let pageSize = 4096;
export let currCacheLineSize = 64;

function timeGraphLayout() {
    let x = 70,
        y = 0,
        width = 800,
        height = 280,
        xScale = undefined,
        yScale = undefined,
        tabPosition = {x: x, y: y + height, min: 0, max: 0},
        timeChangeCallbacks = [],
        initialized = false,
        sampleInfo = {algorithm: 'agglomerative',
                    runLength: 5,
                    numRuns: 3,
                    buckets: 1000},
        minTs = 0,
        maxTs = 0,
        boundaryBuffer = 0,
        allPts = undefined,
        maxSizeSum = 0,
        zoomed = false,
        leftHandle = undefined,
        rightHandle = undefined,
        moveHandle = undefined,
        region = undefined,
        handleWidth = 8,
        sampledBuckets = undefined,
        selPageSize = 0;

    const allPageSizes = ['4KiB', '8KiB', '2MiB', '1GiB'];
    const numericPageSizes = [4096, 8192, 2097152, 1073741824]

    function drawTimeGraphLayout(selection) {
        const   points = selection.datum().pts,
                changePts = selection.datum().changes,
                lines = {};
        
        allPts = Object.keys(points).reduce((acc, curr) => acc.concat(points[curr]), []);
        maxSizeSum = allPts.map((pt) => pt.size).reduce((max, s) => Math.max(max, s), 0);

        // if (!initialized || zoomed) {
        // minTs = allPts.map((pt) => pt.ts).reduce((min, t) => Math.min(min, t), allPts[0].ts);
        // maxTs = allPts.map((pt) => pt.ts).reduce((max, t) => Math.max(max, t), allPts[0].ts);
        boundaryBuffer = 0.0;
        // }

        for (let type of Object.keys(points)) {
            lines[type] = [[minTs - boundaryBuffer, 0]];
            for (let i = 0; i < points[type].length; i++) {
                lines[type].push([points[type][i].ts, lines[type][2 * i][1]]);
                lines[type].push([points[type][i].ts, points[type][i].size]);
            }
            lines[type].push([maxTs + boundaryBuffer, lines[type][lines[type].length - 1][1]]);
        }

        let oldLeftValue = initialized ? parseInt(xScale.invert(leftHandle.attr('x'))) : undefined;
        let oldRightValue = initialized ? xScale.invert(parseInt(rightHandle.attr('x')) + handleWidth) : undefined;

        xScale = d3.scaleLinear().domain([minTs - boundaryBuffer, maxTs + boundaryBuffer]).range([0, width]);
        let xAxis = d3.axisBottom(xScale).tickSize(5).tickValues([]);//.tickValues(d3.range(minTs - boundaryBuffer, maxTs + boundaryBuffer,
            //Math.floor((maxTs - minTs + 2*boundaryBuffer) / 10))).tickFormat(d3.format('d'));

        /*  If the graph has been initialized, then this is being called due to a (un)zoom.
            Want the left/right edges of the sample region to remain at the same timestamp.
            When unzooming, need to consider the old scale, but when zooming, just set the
            left/right edges of sample region to edges of graph. */
        if (!zoomed && initialized) {
            updateSampleRegion(xScale(oldLeftValue), xScale(oldRightValue));
        }
        else if (initialized) {
            updateSampleRegion(xScale.range()[0], xScale.range()[1]);
        }

        yScale = d3.scaleLinear().domain([1.05 * maxSizeSum, 0]).range([0, height]);
        let yAxis = d3.axisLeft(yScale);
        yAxis.tickValues(d3.range(0, maxSizeSum+1, 
            Math.pow(2, Math.floor(Math.log2(0.1*maxSizeSum)))
            )).tickFormat(d3.format('d'));

        if (!initialized) {
            d3.select('#graphLayout').remove();
            const svgGroup = selection.append('svg')
                    .attr('id', 'graphLayout')
                    .style('width', `100%`)
                    .style('height', `70%`)
                    .style('position', 'relative')
                    .style('top', '0px')
                    .style('left', '0px');
            const xAxisGroup = svgGroup.append('g')
                    .attr('id', 'graphLayoutXAxis')
                    .style('transform', `translate(${x}px, ${y + height}px)`);
            const yAxisGroup = svgGroup.append('g')
                    .attr('id', 'graphLayoutYAxis')
                    .style('transform', `translate(${x}px, ${y}px)`);
            const defs = svgGroup.append('defs');
            const linGradr = defs.append('linearGradient')
                    .attr('id', 'handleGradientr')
                    .attr('x1', '0%')
                    .attr('x2', '100%')
                    .attr('y1', '50%')
                    .attr('y2', '50%');
            linGradr.append('stop')
                    .attr('offset', '0%')
                    .attr('stop-color', '#ccc')
                    .attr('stop-opacity', '0.0');
            linGradr.append('stop')
                    .attr('offset', '100%')
                    .attr('stop-color', '#ccc')
                    .attr('stop-opacity', '0.5');
            const linGradl = defs.append('linearGradient')
                    .attr('id', 'handleGradientl')
                    .attr('x1', '100%')
                    .attr('x2', '0%')
                    .attr('y1', '50%')
                    .attr('y2', '50%');
            linGradl.append('stop')
                    .attr('offset', '0%')
                    .attr('stop-color', '#ccc')
                    .attr('stop-opacity', '0.0');
            linGradl.append('stop')
                    .attr('offset', '100%')
                    .attr('stop-color', '#ccc')
                    .attr('stop-opacity', '0.5');

            xAxisGroup.call(xAxis);
                        // .selectAll('text')
                        // .attr('dx', '5em')
                        // .attr('dy', '0.7em')
                        // .style('transform', 'rotate(0.12turn');
            yAxisGroup.call(yAxis);
        }

        d3.select('#timeGraphCanvas').remove();
        const canvas = selection.insert('canvas', '#graphLayout')
                .attr('id', 'timeGraphCanvas')
                .attr('width', width + x)
                .attr('height', height + y)
                .style('position', 'absolute')
                .style('top', '0px')
                .style('left', '0px');
        const context = canvas.node().getContext('2d');
        
        context.translate(x, y);

        const line = d3.line()
                    .x((d) => xScale(d[0]))
                    .y((d) => yScale(d[1]))
                    .context(context);

        context.clearRect(0, 0, width, height);
        for (let type of Object.keys(points)) {
            context.beginPath();
            line(lines[type]);
            context.lineWidth = 1;
            context.opacity = 1;
            context.strokeStyle = colourOfType[type];
            context.stroke();
            context.closePath();
        }

        if (!initialized) {
            selection.append('div')
                .attr('id', 'graphLayoutBottomBar')
                .style('width', '100%')
                .style('height', '100%')
                .style('left', '75px')
                .style('position', 'relative')
                .style('display', 'table-row');
            changeRegions(changePts);
            sampleRegion();
            sampledBuckets = sampleInfo.buckets;
            // slider(xScale(minTs - boundaryBuffer));
            let ts = getCurrTime();
            for (let func of timeChangeCallbacks) func(ts);
        }

        initialized = true;
    }

    function updateSampleRegion(newLeft, newRight) {
        region.attr('x', newLeft)
            .attr('width', newRight - newLeft);
        leftHandle.attr('x', newLeft);
        rightHandle.attr('x', newRight - handleWidth);
        moveHandle.attr('x', newLeft + handleWidth)
            .attr('width', newRight - newLeft - (2*handleWidth));
    }

    function sampleRegion() {
        const initRegionWidth = width;
        const sampleButtonWidth = 70;
        let settingsPopup = undefined;

        region = d3.select('#graphLayout')
                        .append('rect')
                        .attr('x', xScale(xScale.domain()[0]))
                        .attr('y', 0)
                        .attr('width', initRegionWidth)
                        .attr('height', height)
                        .style('fill', '#ccc')
                        .style('opacity', 0.3)
                        .style('transform', `translate(${x}px, ${y}px)`);
        
        let initLeftDiff = 0.0;
        leftHandle = d3.select('#graphLayout')
                        .append('rect')
                        .attr('x', xScale(xScale.domain()[0]))
                        .attr('y', 0)
                        .attr('width', handleWidth)
                        .attr('height', height)
                        .style('fill', 'url(#handleGradientl)')
                        // .style('fill', '#ff0000')
                        // .style('opacity', 1.0)
                        .style('cursor', 'ew-resize')
                        .style('pointer-events', 'visible')
                        .style('transform', `translate(${x}px, ${y}px)`)
                        .call(d3.drag()
                            .on('start', function(event) {
                                const intLeftHandleX = parseInt(leftHandle.attr('x'));
                                initLeftDiff = event.x - intLeftHandleX - x;
                            })
                            .on('drag', function(event) {
                                const adjustEventX = event.x - x - initLeftDiff;
                                const intRegionWidth = parseInt(region.attr('width'));
                                const intRegionX = parseInt(region.attr('x'));
                                if (adjustEventX >= xScale(xScale.domain()[0]) && adjustEventX <= intRegionX + intRegionWidth - 2*handleWidth) {
                                    const nWidth = intRegionWidth + intRegionX - adjustEventX;
                                    region.attr('x', adjustEventX)
                                            .attr('width', nWidth);
                                    moveHandle.attr('x', adjustEventX + handleWidth)
                                            .attr('width', nWidth - 2*handleWidth);
                                    leftHandle.attr('x', adjustEventX);
                                }
                            }));

        let initRightDiff = 0.0;
        rightHandle = d3.select('#graphLayout')
                        .append('rect')
                        .attr('x', xScale(xScale.domain()[0]) + initRegionWidth - handleWidth)
                        .attr('y', 0)
                        .attr('width', handleWidth)
                        .attr('height', height)
                        .style('fill', 'url(#handleGradientr)')
                        // .style('fill', '#ff0000')
                        // .style('opacity', 1.0)
                        .style('cursor', 'ew-resize')
                        .style('pointer-events', 'visible')
                        .style('transform', `translate(${x}px, ${y}px)`)
                        .call(d3.drag()
                            .on('start', function(event) {
                                const intRightHandleX = parseInt(rightHandle.attr('x')) + handleWidth;
                                initRightDiff = event.x - intRightHandleX - x;
                            })
                            .on('drag', function(event) {
                                const adjustEventX = event.x - x - initRightDiff;
                                const intRegionX = parseInt(region.attr('x'));
                                if (adjustEventX <= xScale(xScale.domain()[1]) && adjustEventX >= intRegionX + 2*handleWidth) {
                                    const nWidth = adjustEventX - intRegionX;
                                    region.attr('width', nWidth);
                                    moveHandle.attr('width', nWidth - 2*handleWidth);
                                    rightHandle.attr('x', adjustEventX - handleWidth);
                                }
                            }));

        let initMoveDiff = 0.0;
        moveHandle = d3.select('#graphLayout')
                        .append('rect')
                        .attr('x', xScale(xScale.domain()[0]) + handleWidth)
                        .attr('y', 0)
                        .attr('width', initRegionWidth - 2*handleWidth)
                        .attr('height', height)
                        .style('fill', '#00ff0c')
                        .style('opacity', 0.0)
                        .style('cursor', 'move')
                        .style('pointer-events', 'visible')
                        .style('transform', `translate(${x}px, ${y}px)`)
                        .call(d3.drag()
                            .on('start', function(event) {
                                const intRegionX = parseInt(region.attr('x'));
                                initMoveDiff = event.x - intRegionX - x;
                            })
                            .on('drag', function(event) {
                                const intRegionWidth = parseInt(region.attr('width'));
                                const adjustEventX = event.x - x - initMoveDiff;
                                if (adjustEventX + intRegionWidth <= xScale(xScale.domain()[1]) && adjustEventX >= xScale(xScale.domain()[0])) {
                                    region.attr('x', adjustEventX);
                                    moveHandle.attr('x', adjustEventX + handleWidth);
                                    leftHandle.attr('x', adjustEventX);
                                    rightHandle.attr('x', adjustEventX + intRegionWidth - handleWidth);
                                }
                            }));
        
        
        function requestSample(startTs, endTs, alg, rlen, numRuns, numBuckets) {
            console.log('start ts: ', startTs);
            console.log('end ts: ', endTs);
            console.log('sample info: ', alg, rlen, numRuns, numBuckets);
            console.log('body: ', JSON.stringify(mainVis.getSampleVector()));

            console.log('timeGraphLayout, here is the cls: ', currCacheLineSize);

            fetch(`/run-sampler/${mainVis.getFileName()}-${startTs}-${endTs}-${numericPageSizes[selPageSize]}-${currCacheLineSize}-${alg}-${rlen}-${numRuns}-${numBuckets}`, {
                    method: "POST",
                    mode: "cors",
                    cache: "no-cache",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    redirect: "follow",
                    referrerPolicy: "no-referrer",
                    body: JSON.stringify(mainVis.getSampleVector())
                })
                .then((sampleResponse) => sampleResponse.json())
                .then((sampleData) => {
                    pageSize = numericPageSizes[selPageSize];
                    console.log('Data received from server.');
                    d3.select('#pageLayoutDiv').remove();
                    d3.select('#cacheSetLayout').remove();
                    d3.select('#memLayoutDiv').remove();
    
                    if (mainVis.isCacheFocus()) mainVis.toggleCacheFocus();
                    // console.log('Here is the sample data:');
                    // console.log(sampleData);
                    mainVis.constructPageVis(sampleData, currCacheLineSize);
                    slider(parseInt(leftHandle.attr('x')), parseInt(rightHandle.attr('x')) + handleWidth);
                    let ts = getCurrTime();
                    for (let func of timeChangeCallbacks) func(ts);
                    d3.select('#sampleLoadingAnim')
                        .remove();
                    d3.select('#sampleButtonText')
                        .style('visibility', 'visible');
                    d3.select('#sampleButton')
                        .style('pointer-events', 'visible');
                })
                .catch((error) => {
                    console.error('Error: ', error);
                });
        }

        const buttonInfo = {
            'Settings': {
                callback: function() {
                    d3.select('#settingsPopup')
                        .transition()
                        .style('visibility', 'visible');
                },
                id: 'settingsButton'
            },
            'Sample': {
                callback: function() {
                    d3.select('#sampleButton')
                        .style('pointer-events', 'none')
                        .append('div')
                        .attr('id', 'sampleLoadingAnim')
                        .attr('class', 'loadingAnim')
                        .style('position', 'absolute')
                        .style('width', '20px')
                        .style('height', '20px')
                        .style('top', '-5px');
                    d3.select('#sampleButtonText')
                        .style('visibility', 'hidden');
                    let startTs = Math.floor(xScale.invert(parseInt(leftHandle.attr('x'))));
                    let endTs = Math.floor(xScale.invert(parseInt(rightHandle.attr('x')) + handleWidth));
                    sampledBuckets = sampleInfo.buckets;
                    requestSample(startTs, endTs, sampleInfo.algorithm, sampleInfo.runLength, sampleInfo.numRuns, sampleInfo.buckets);
                },
                id: 'sampleButton'
            },
            'Zoom+': {
                callback: function() {
                    minTs = parseInt(xScale.invert(parseInt(leftHandle.attr('x'))));
                    maxTs = parseInt(xScale.invert(parseInt(rightHandle.attr('x')) + handleWidth));
                    zoomed = true;
                    mainVis.zoom();
                },
                id: 'zoominButton'
            },
            'Zoom-': {
                callback: function() {
                    zoomed = false;
                    mainVis.unzoom();
                },
                id: 'zoomOutButton'
            }
        }

        d3.select('#graphLayoutBottomBar')
            .selectAll('.graphLayoutBottomBarButton')
            .data(Object.keys(buttonInfo))
            .enter()
            .append('div')
            .attr('class', 'graphLayoutBottomBarButton')
            .style('display', 'table-cell')
            .style('position', 'relative')
            .style('width', `${sampleButtonWidth}px`)
            .style('height', '100%')
            .style('margin', '0px')
            .style('padding', '0px')
            .append('div')
            .attr('id', (d) => buttonInfo[d].id)
            .style('width', '100%')
            .style('height', '30px')
            .style('position', 'absolute')
            .style('top', '50%')
            .style('left', '0px')
            .style('transform', 'translateY(-50%)')
            .style('margin', '0px')
            .style('padding', '0px')
            .style('border', '1px solid #ccc')
            .style('background-color', 'white')
            .style('cursor', 'pointer')
            .style('pointer-events', 'visible')
            .style('border-top-left-radius', (d, i) => i == 0 ? '7px' : '0px')
            .style('border-bottom-left-radius', (d, i) => i == 0 ? '7px' : '0px')
            .style('border-top-right-radius', (d, i) => i == Object.keys(buttonInfo).length - 1 ? '7px' : '0px')
            .style('border-bottom-right-radius', (d, i) => i == Object.keys(buttonInfo).length - 1 ? '7px' : '0px')
            .on('click', function(e, d) {
                buttonInfo[d].callback();
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
            .attr('id', (d) => `${buttonInfo[d].id}Text`)
            .style('font-family', 'monospace')
            .style('font-size', '12px')
            .style('text-align', 'center')
            .style('line-height', '5px')
            .style('pointer-events', 'none')
            .text((d) => d);

        if (!initialized) settingsPopup = SettingsPopup.build(sampleInfo);

        // Group consisting of 'cache line size' label and input box
        let clsGroup = d3.select('#graphLayoutBottomBar')
            .append('div')
            .style('display', 'table-cell')
            .style('width', '210px')
            .style('height', '100%')
            .style('position', 'relative')
            .append('div')
            .style('display', 'inline-block')
            // .style('padding', '10px')
            .style('width', '100%')
            .style('height', '100%')
            .style('position', 'absolute');

        clsGroup.append('div')
            .style('font-family', 'monospace')
            .style('font-size', '12px')
            .text('cache line size:')
            .style('float', 'left')
            .style('position', 'relative')
            .style('top', '50%')
            .style('left', '20px')
            .style('transform', 'translateY(-50%)');

        clsGroup.append('input')
            .attr('id', 'cacheLineSizeInput')
            .attr('type', 'number')
            .attr('value', currCacheLineSize)
            .attr('min', 32)
            .attr('max', 256)
            .attr('step', 32)
            .style('float', 'left')
            .style('position', 'relative')
            .style('top', '50%')
            .style('left', '30px')
            .style('transform', 'translateY(-50%)')
            .style('width', '45px')
            .on('input', function() {
                currCacheLineSize = d3.select(this).property('value');
            });

        const pageSizeSelectorGroup = d3.select('#graphLayoutBottomBar')
            .append('div')
            .style('display', 'table-cell')
            .style('width', '210px')
            .style('height', '90px')
            .style('position', 'relative');

        pageSizeSelectorGroup.append('p')
            .style('position', 'absolute')
            .style('left', '50%')
            .style('transform', 'translateX(-50%)')
            .style('font-family', 'monospace')
            .text('Page size:');

        pageSizeSelectorGroup.append('input')
            .attr('id', 'pageSizeSelector')
            .attr('type', 'range')
            .attr('value', 0)
            .attr('max', 3)
            .attr('step', 1)
            .style('position', 'absolute')
            .style('left', '50%')
            .style('top', '30px')
            .style('transform', 'translateX(-50%)')
            .on('input', function() {
                pageSizeLabels.select(`#pageSizeLabel-${selPageSize}`)
                    .style('border', 'none');
                selPageSize = parseInt(this.value);
                pageSizeLabels.select(`#pageSizeLabel-${selPageSize}`)
                    .style('border', '1px solid #ccc');
            });

        const pageSizeLabels = pageSizeSelectorGroup.append('div')
            .style('display', 'inline-block')
            .style('width', '187px')
            .style('height', '30px')
            .style('position', 'relative')
            .style('left', '50%')
            .style('top', '58px')
            .style('transform', 'translateX(-50%)');

        pageSizeLabels.selectAll('.pageSizeLabel')
            .data(allPageSizes)
            .enter()
            .append('div')
            .attr('id', (d, i) => `pageSizeLabel-${i}`)
            .attr('class', 'pageSizeLabel')
            .style('border', (d, i) => i == selPageSize ? '1px solid #ccc' : 'none')
            .append('div')
            .style('font-family', 'monospace')
            // .style('position', 'absolute')
            // .style('left', '50%')
            // .style('transform', 'translateX(-50%)')
            .style('display', 'table-cell')
            .style('vertical-align', 'middle')
            .style('text-align', 'center')
            .text((d) => d);
    }

    function changeRegions(changePts) {
        const tsDistanceThreshold = Math.floor(0.03 * (xScale.domain()[1] - xScale.domain()[0]));
        const regions = [];
        const buffer = Math.floor(0.02 * width);
        for (let type of Object.keys(changePts)) {
            let i = 0;
            while (i < changePts[type].length) {
                let leftEdge = changePts[type][i];
                while (i + 1 < changePts[type].length && (points[type][changePts[type][i + 1] - 1].ts - points[type][changePts[type][i] - 1].ts) <= tsDistanceThreshold) {
                    i++;
                }
                let rightEdge = changePts[type][i];
                regions.push({'left': leftEdge - 1, 'right': rightEdge - 1, 'type': type});
                i++;
            }
        }

        d3.select('#graphLayout')
            .selectAll('.changeRegion')
            .data(regions)
            .enter()
            .append('rect')
            .attr('class', 'changeRegion')
            .attr('x', (d) => {
                return xScale(points[d.type][d.left].ts) - buffer;
            })
            .attr('y', 0)
            .attr('width', (d) => {
                return xScale(xScale.domain()[0] + points[d.type][d.right].ts - points[d.type][d.left].ts) + buffer;
            })
            .attr('height', height)
            .style('transform', `translate(${x}px, ${y}px)`);
    }

    function getCurrTime() {
        return xScale.invert(tabPosition.x);
    }

    function updateTab() {
        let newX = tabPosition.x + x;
        d3.select('#bottomTab')
            .style('transform', d => `translate(${newX}px, ${d.y + 10}px)`);
        d3.select('#topTab')
            .style('transform', d => `translate(${newX}px, ${d.y - height - 10}px)  rotate(0.5turn)`);
        d3.select('#tabLine')
            .style('transform', d => `translate(${newX}px, 0px)`);
    }

    function handleDrag(e) {
        e.subject.x = Math.max(Math.min(e.x, e.subject.max), e.subject.min);
        updateTab();
        let ts = getCurrTime();
        for (let func of timeChangeCallbacks) func(ts);
    }

    function getSizeOfBucket() {
        return Math.floor((xScale.domain()[1] - xScale.domain()[0]) / sampledBuckets);
    }

    function getBucketIndexFromTs(ts) {
        // return (ts - xScale.domain()[0]) / getSizeOfBucket();
        const sizeOfBucket = getSizeOfBucket();
        // console.log(`   sizeOfBucket: ${sizeOfBucket}`);
        // console.log(`   ts: ${ts}`);
        // console.log(`   val: ${Math.round((ts - xScale.domain()[0]) / sizeOfBucket)}`);
        return Math.ceil((ts - xScale.domain()[0]) / sizeOfBucket);
    }

    // function getNearestBucketTs(ts) {
    //     // tabPosition.x = (Math.round((tabPosition.x - xScale.range()[0]) * (sampledBuckets / (xScale.range()[1] - xScale.range()[0]))) *
    //         // ((xScale.range()[1] - xScale.range()[0]) / sampledBuckets)) + xScale.range()[0];
    //     const sizeOfBucket = getSizeOfBucket();
    //     console.log(`   sizeOfBucket: ${sizeOfBucket}`);
    //     console.log(`   ts: ${ts}`);
    //     console.log(`   val: ${Math.round((ts - xScale.domain()[0]) / sizeOfBucket)}`);
    //     return (Math.round((ts - xScale.domain()[0]) / sizeOfBucket)*sizeOfBucket) + xScale.domain()[0];
    // }

    function snapToBucket(e) {
        const currTime = getCurrTime();
        let newTs = (getBucketIndexFromTs(currTime)*getSizeOfBucket()) + xScale.domain()[0];
        // console.log(`Snapping to bucket index: ${getBucketIndexFromTs(currTime)}`);
        // console.log(`ts: ${newTs}`);
        tabPosition.x = xScale(newTs);
        // tabPosition.x = (Math.round((tabPosition.x - xScale.range()[0]) * (sampledBuckets / (xScale.range()[1] - xScale.range()[0]))) *
            // ((xScale.range()[1] - xScale.range()[0]) / sampledBuckets)) + xScale.range()[0];
        updateTab();
        // let ts = getCurrTime();
        for (let func of timeChangeCallbacks) func(newTs);
    }

    function slider(minPos, maxPos) {
        d3.select('#dragTab').remove();

        tabPosition.x = minPos;
        tabPosition.min = minPos;
        tabPosition.max = maxPos;
        const colour = 'rgb(148, 148, 148)';
        let tab = d3.symbol()
            .type(d3.symbolTriangle)
            .size(60);

        let tabGroup = d3.select('#graphLayout')
            .append('g')
            // .datum(tabPosition)
            .attr('id', 'dragTab');
            // .attr('transform', d => `translate(${d.x}, ${d.y})`);

        tabGroup.append('line')
            .datum(tabPosition)
            .attr('id', 'tabLine')
            .style('stroke', colour)
            .style('stroke-width', 2)
            .attr('x1', 0)
            .attr('y1', y - 10)
            .attr('x2', 0)
            .attr('y2', y + height + 10)
            .style('transform', (d) => `translate(${d.x + x}px, 0px)`);

        tabGroup.append('path')
            .datum(tabPosition)
            .attr('id', 'bottomTab')
            .attr('d', tab)
            .attr('stroke', colour)
            .attr('fill', colour)
            .style('transform', (d) => `translate(${d.x + x}px, ${d.y + 10}px)`)
            .call(d3.drag()
                .on('drag', handleDrag)
                .on('end', snapToBucket));

        tabGroup.append('path')
            .datum(tabPosition)
            .attr('id', 'topTab')
            .attr('d', tab)
            .attr('stroke', colour)
            .attr('fill', colour)
            .style('transform', (d) => `translate(${d.x + x}px, ${d.y - height - 10}px) rotate(0.5turn)`)
            .call(d3.drag()
                .on('drag', handleDrag)
                .on('end', snapToBucket));
    }

    drawTimeGraphLayout.x = function(val) {
        if (!arguments.length) return x;
        x = val;
        tabPosition.x = x;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.y = function(val) {
        if (!arguments.length) return y;
        y = val;
        tabPosition.y = y + height;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.width = function(val) {
        if (!arguments.length) return width;
        width = val;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.height = function(val) {
        if (!arguments.length) return height;
        height = val;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.sampleInfo = function(val) {
        if (!arguments.length) return sampleInfo;
        sampleInfo = val;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.callbacks = function(val) {
        if (!arguments.length) return timeChangeCallbacks;
        timeChangeCallbacks = val;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.getCurrTime = function() {
        return xScale.invert(tabPosition.x);
    }

    // drawTimeGraphLayout.getNearestBucketTs = function(ts) {
    //     return getNearestBucketTs(ts);
    // }

    drawTimeGraphLayout.getBucketIndexFromTs = function(ts) {
        return getBucketIndexFromTs(ts);
    }

    drawTimeGraphLayout.sizeOfBucket = function(ts) {
        return getSizeOfBucket();
    }

    // drawTimeGraphLayout.zoom = function() {
    //     zoomed = true;
    //     return drawTimeGraphLayout;
    // }

    // drawTimeGraphLayout.unzoom = function() {
    //     zoomed = false;
    //     return drawTimeGraphLayout;
    // }

    drawTimeGraphLayout.minTs = function(val) {
        if (!arguments.length) return minTs;
        minTs = val;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.maxTs = function(val) {
        if (!arguments.length) return maxTs;
        maxTs = val;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.sampleInfo = function(val) {
        if (!arguments.length) return sampleInfo;
        sampleInfo = val;
        return drawTimeGraphLayout;
    }

    return drawTimeGraphLayout;
}

export default timeGraphLayout;