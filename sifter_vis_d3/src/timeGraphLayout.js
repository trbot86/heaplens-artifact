import * as d3 from 'd3';
import { colourOfType } from './vis.js';
import { mainVis } from './dbloader.js';
import { SettingsPopup } from './settingsPopup.js';


function timeGraphLayout() {
    let x = 70,
        y = 20,
        width = 800,
        height = 280,
        xScale = undefined,
        yScale = undefined,
        tabPosition = {x: x, y: y + height, min: 0, max: 0},
        timeChangeCallbacks = [],
        initialized = false,
        sampleInfo = {algorithm: 'dbscan',
                    runLength: 3,
                    numRuns: 2,
                    buckets: 5000},
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
        sampledBuckets = undefined;

    function drawTimeGraphLayout(selection) {
        // console.log(selection.datum().pts);
        const   points = selection.datum().pts,
                changePts = selection.datum().changes,
                lines = {};
        
        allPts = Object.keys(points).reduce((acc, curr) => acc.concat(points[curr]), []);
        maxSizeSum = allPts.map((pt) => pt.size).reduce((max, s) => Math.max(max, s), 0);

        // if (!initialized || zoomed) {
        minTs = allPts.map((pt) => pt.ts).reduce((min, t) => Math.min(min, t), allPts[0].ts);
        maxTs = allPts.map((pt) => pt.ts).reduce((max, t) => Math.max(max, t), allPts[0].ts);
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

        let oldLeftValue = initialized ? xScale.invert(leftHandle.attr('x')) : undefined;
        let oldRightValue = initialized ? xScale.invert(rightHandle.attr('x') + handleWidth) : undefined
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
            console.log('CALLED ZOOM');
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
                    .style('height', `100%`)
                    .style('position', 'absolute')
                    .style('top', '0px')
                    .style('left', '0px');
            const xAxisGroup = svgGroup.append('g')
                    .attr('id', 'graphLayoutXAxis')
                    .style('transform', `translate(${x}px, ${y + height}px)`);
            const yAxisGroup = svgGroup.append('g')
                    .attr('id', 'graphLayoutYAxis')
                    .style('transform', `translate(${x}px, ${y}px)`);

            xAxisGroup.call(xAxis);
                        // .selectAll('text')
                        // .attr('dx', '5em')
                        // .attr('dy', '0.7em')
                        // .style('transform', 'rotate(0.12turn');
            yAxisGroup.call(yAxis);
        }

        d3.select('#timeGraphCanvas').remove();
        const canvas = selection.append('canvas')
                .attr('id', 'timeGraphCanvas')
                .attr('width', width + x)
                .attr('height', height + y);
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
            changeRegions(changePts);
            sampleRegion();
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
        let sampleButton, settingsPopup = undefined;
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
                        .style('fill', '#ff0000')
                        .style('opacity', 0.0)
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
                        .style('fill', '#ff0000')
                        .style('opacity', 0.0)
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
            console.log('body: ', JSON.stringify(mainVis.getSampleVector()))
            fetch(`/run-sampler/${mainVis.getFileName()}-${startTs}-${endTs}-${alg}-${rlen}-${numRuns}-${numBuckets}`, {
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
                    console.log('Data received from server.');
                    d3.select('#pageLayout').remove();
                    d3.select('#cacheSetBox').remove();
    
                    mainVis.constructPageVis(sampleData);
                    slider(parseInt(leftHandle.attr('x')), parseInt(rightHandle.attr('x')) + handleWidth);
                })
                .catch((error) => {
                    console.error('Error: ', error);
                });
        }

        const sampleButtonGroup = d3.select('#graphLayout')
                        .append('g')
                        .style('transform', `translate(${x}px, ${y}px)`);
        
        sampleButton = sampleButtonGroup.append('rect')
                        .attr('x', (width / 2) - sampleButtonWidth)
                        .attr('y', height + 40)
                        .attr('width', sampleButtonWidth)
                        .attr('height', 30)
                        .attr('rx', 7)
                        .attr('ry', 7)
                        .style('fill', 'white')
                        .style('stroke', '#ccc')
                        .style('stroke-width', '1px')
                        .style('cursor', 'pointer')
                        .style('pointer-events', 'visible')
                        .on('click', function() {
                            let startTs = Math.floor(xScale.invert(parseInt(leftHandle.attr('x'))));
                            let endTs = Math.floor(xScale.invert(parseInt(rightHandle.attr('x')) + handleWidth));
                            sampledBuckets = sampleInfo.buckets;
                            requestSample(startTs, endTs, sampleInfo.algorithm, sampleInfo.runLength, sampleInfo.numRuns, sampleInfo.buckets);
                        })
                        .on('mouseover', function() {
                            d3.select(this)
                                .transition()
                                .style('fill', '#ccc');
                        })
                        .on('mouseout', function() {
                            d3.select(this)
                                .transition()
                                .style('fill', 'white');
                        });

        sampleButtonGroup.append('text')
                        .attr('text-anchor', 'middle')
                        .attr('x', parseInt(sampleButton.attr('x')) + (sampleButtonWidth / 2))
                        .attr('y', parseInt(sampleButton.attr('y')) + 18.5)
                        .attr('font-family', 'monospace')
                        .style('alignment-baseline', 'middle')
                        .style('pointer-events', 'none')
                        .text('Sample');

        const zoomButtonGroup = d3.select('#graphLayout')
                        .append('g')
                        .style('transform', `translate(${x}px, ${y}px)`);

        const zoomButton = zoomButtonGroup.append('rect')
                        .attr('x', parseInt(sampleButton.attr('x')) + sampleButtonWidth + 15)
                        .attr('y', parseInt(sampleButton.attr('y')))
                        .attr('width', sampleButtonWidth)
                        .attr('height', 30)
                        .attr('rx', 7)
                        .attr('ry', 7)
                        .style('fill', 'white')
                        .style('stroke', '#ccc')
                        .style('stroke-width', '1px')
                        .style('cursor', 'pointer')
                        .style('pointer-events', 'visible')
                        .on('click', function() {
                            minTs = xScale.invert(parseInt(leftHandle.attr('x')));
                            maxTs = xScale.invert(parseInt(rightHandle.attr('x')) + handleWidth);
                            mainVis.zoom(minTs, maxTs);
                        })
                        .on('mouseover', function() {
                            d3.select(this)
                                .transition()
                                .style('fill', '#ccc');
                        })
                        .on('mouseout', function() {
                            d3.select(this)
                                .transition()
                                .style('fill', 'white');
                        });;

        zoomButtonGroup.append('text')
                        .attr('x', parseInt(zoomButton.attr('x')) + (sampleButtonWidth / 2))
                        .attr('y', parseInt(zoomButton.attr('y')) + 18.5)
                        .attr('text-anchor', 'middle')
                        .attr('font-family', 'monospace')
                        .style('alignment-baseline', 'middle')
                        .style('pointer-events', 'none')
                        .text('Zoom+');

        const unzoomButtonGroup = d3.select('#graphLayout')
                        .append('g')
                        .style('transform', `translate(${x}px, ${y}px)`);

        const unzoomButton = unzoomButtonGroup.append('rect')
                        .attr('x', parseInt(sampleButton.attr('x')) + 2*(sampleButtonWidth + 15))
                        .attr('y', parseInt(sampleButton.attr('y')))
                        .attr('width', sampleButtonWidth)
                        .attr('height', 30)
                        .attr('rx', 7)
                        .attr('ry', 7)
                        .style('fill', 'white')
                        .style('stroke', '#ccc')
                        .style('stroke-width', '1px')
                        .style('cursor', 'pointer')
                        .style('pointer-events', 'visible')
                        .on('click', function() {
                            minTs = allPts.map((pt) => pt.ts).reduce((min, t) => Math.min(min, t), allPts[0].ts);
                            maxTs = allPts.map((pt) => pt.ts).reduce((max, t) => Math.max(max, t), allPts[0].ts);
                            mainVis.unzoom();
                        })
                        .on('mouseover', function() {
                            d3.select(this)
                                .transition()
                                .style('fill', '#ccc');
                        })
                        .on('mouseout', function() {
                            d3.select(this)
                                .transition()
                                .style('fill', 'white');
                        });;

        unzoomButtonGroup.append('text')
                        .attr('x', parseInt(unzoomButton.attr('x')) + (sampleButtonWidth / 2))
                        .attr('y', parseInt(unzoomButton.attr('y')) + 18.5)
                        .attr('text-anchor', 'middle')
                        .attr('font-family', 'monospace')
                        .style('alignment-baseline', 'middle')
                        .style('pointer-events', 'none')
                        .text('Zoom-');

        const settingsButtonGroup = d3.select('#graphLayout')
                        .append('g')
                        .style('transform', `translate(${x}px, ${y}px)`);

        const settingsButton = settingsButtonGroup.append('rect')
                        .attr('x', parseInt(sampleButton.attr('x')) - sampleButtonWidth - 15)
                        .attr('y', parseInt(sampleButton.attr('y')))
                        .attr('width', sampleButtonWidth)
                        .attr('height', 30)
                        .attr('rx', 7)
                        .attr('ry', 7)
                        .style('fill', 'white')
                        .style('stroke', '#ccc')
                        .style('stroke-width', '1px')
                        .style('cursor', 'pointer')
                        .style('pointer-events', 'visible')
                        .on('click', function() {
                            d3.select('#settingsPopup')
                                .transition()
                                .style('display', 'block');
                        })
                        .on('mouseover', function() {
                            d3.select(this)
                                .transition()
                                .style('fill', '#ccc');
                        })
                        .on('mouseout', function() {
                            d3.select(this)
                                .transition()
                                .style('fill', 'white');
                        });;

        settingsButtonGroup.append('text')
                        .attr('x', parseInt(settingsButton.attr('x')) + (sampleButtonWidth / 2))
                        .attr('y', parseInt(settingsButton.attr('y')) + 18.5)
                        .attr('text-anchor', 'middle')
                        .attr('font-family', 'monospace')
                        .style('alignment-baseline', 'middle')
                        .style('pointer-events', 'none')
                        .text('Settings');

        if (!initialized) settingsPopup = SettingsPopup.build(sampleInfo);
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
        // console.log(e);
        // tabPosition.x += e.dx;
        e.subject.x = Math.max(Math.min(e.x, e.subject.max), e.subject.min);
        updateTab();
        let ts = getCurrTime();
        for (let func of timeChangeCallbacks) func(ts);
        // addElementsByTimestamp(ts);
        // updatePagesByTimestamp(ts);
    }

    function snapToBucket(e) {
        tabPosition.x = (Math.round((tabPosition.x - xScale.range()[0]) * (sampledBuckets / (xScale.range()[1] - xScale.range()[0]))) *
            ((xScale.range()[1] - xScale.range()[0]) / sampledBuckets)) + xScale.range()[0];
        updateTab();
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

    drawTimeGraphLayout.zoom = function() {
        zoomed = true;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.unzoom = function() {
        zoomed = false;
        return drawTimeGraphLayout;
    }

    return drawTimeGraphLayout;
}

export default timeGraphLayout;