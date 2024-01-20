import * as d3 from 'd3';
import { colourOfType } from './vis.js';
import { addElementsByTimestamp } from './objectFieldLayout.js';
import { updatePagesByTimestamp } from './pageLayout.js';
import { instantaneous, drawLayout } from './cacheSetLayout.js';
import { mainVis } from './dbloader.js';
import { SettingsPopup } from './settingsPopup.js';

const XAXIS_LENGTH = 800;
const YAXIS_LENGTH = 280;
const LAYOUT_TRANSLATE_X = 70;
const LAYOUT_TRANSLATE_Y = 20;


function timeGraphLayout() {
    let x = 70,
        y = 20,
        width = 800,
        height = 280,
        xScale = undefined,
        yScale = undefined,
        tabPosition = {x: 0, y: 0};

    function drawTimeGraphLayout(selection) {
        tabPosition = {x: x, y: y + height};
        let leftSampleIntervalPos = 0,
            rightSampleIntervalPos = 0;
        const sampleInfo = {algorithm: 'dbscan',
                            runLength: 3,
                            numRuns: 2};
        console.log('SELECTION: ', selection);
        const   points = selection.data()[0].pts,
                changePts = selection.data()[0].changes,
                allPts = Object.keys(points).reduce((acc, curr) => acc.concat(points[curr]), []),
                maxSizeSum = allPts.map((pt) => pt.size).reduce((max, s) => Math.max(max, s), 0),
                minTs = allPts.map((pt) => pt.ts).reduce((min, t) => Math.min(min, t), allPts[0].ts),
                maxTs = allPts.map((pt) => pt.ts).reduce((max, t) => Math.max(max, t), allPts[0].ts),
                boundaryBuffer = Math.floor((maxTs - minTs)*0.03),
                lines = {},
                graphLayoutAxes = selection.append('g')
                                            .attr('id', 'graphLayoutAxes');
        
        graphLayoutAxes.append('g')
            .attr('id', 'graphLayoutXAxis')
            .style('transform', `translate(${x}px, ${y + height}px)`);
        graphLayoutAxes.append('g')
            .attr('id', 'graphLayoutYAxis')
            .style('transform', `translate(${x}px, ${y}px)`);

        for (let type of Object.keys(points)) {
            lines[type] = [[minTs - boundaryBuffer, 0]];
            for (let i = 0; i < points[type].length; i++) {
                lines[type].push([points[type][i].ts, lines[type][2 * i][1]]);
                lines[type].push([points[type][i].ts, points[type][i].size]);
            }
            lines[type].push([maxTs + boundaryBuffer, lines[type][lines[type].length - 1][1]]);
        }

        xScale = d3.scaleLinear().domain([minTs - boundaryBuffer, maxTs + boundaryBuffer]).range([0, XAXIS_LENGTH]);
        let xAxis = d3.axisBottom(xScale).tickSize(5).tickValues([]);//.tickValues(d3.range(minTs - boundaryBuffer, maxTs + boundaryBuffer,
            //Math.floor((maxTs - minTs + 2*boundaryBuffer) / 10))).tickFormat(d3.format('d'));

        yScale = d3.scaleLinear().domain([1.05 * maxSizeSum, 0]).range([0, YAXIS_LENGTH]);
        let yAxis = d3.axisLeft(yScale);
        yAxis.tickValues(d3.range(0, maxSizeSum+1, 
            Math.pow(2, Math.floor(Math.log2(0.1*maxSizeSum)))
            )).tickFormat(d3.format('d'));

        d3.select('#graphLayoutXAxis').call(xAxis);
                    // .selectAll('text')
                    // .attr('dx', '5em')
                    // .attr('dy', '0.7em')
                    // .style('transform', 'rotate(0.12turn');
        d3.select('#graphLayoutYAxis').call(yAxis);

        changeRegions();
        sampleRegion();

        for (let type of Object.keys(points)) {
            d3.select('#graphLayout')
                .append('path')
                .datum(lines[type])
                .attr('class', 'line')
                .attr('fill', 'none')
                .attr('stroke', colourOfType[type])
                .attr('stroke-width', 1)
                .attr('transform', `translate(${x}, ${y})`)
                .attr('d', d3.line()
                            .x(d => xScale(d[0]))
                            .y(d => yScale(d[1]))
                );
        }

        function changeRegions() {
            const tsDistanceThreshold = Math.floor(0.03 * (xScale.domain()[1] - xScale.domain()[0]));
            const regions = [];
            const buffer = Math.floor(0.02 * XAXIS_LENGTH);
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
                .style('fill', '#ccfff3')
                .style('transform', `translate(${x}px, ${y}px)`);
        }
    
        function sampleRegion() {
            const initRegionWidth = Math.floor(0.1 * width);
            const handleWidth = 8;
            const sampleButtonWidth = 53;
            let moveHandle, sampleButton, settingsPopup = undefined;
            const region = selection.append('rect')
                            .attr('x', xScale(xScale.domain()[0]))
                            .attr('y', 0)
                            .attr('width', initRegionWidth)
                            .attr('height', height)
                            .style('fill', '#ccc')
                            .style('opacity', 0.5)
                            .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);
            
            let initLeftDiff = 0.0;
            const leftHandle = selection.append('rect')
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
                                    initLeftDiff = event.x - intLeftHandleX - LAYOUT_TRANSLATE_X;
                                })
                                .on('drag', function(event) {
                                    const adjustEventX = event.x - LAYOUT_TRANSLATE_X - initLeftDiff;
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
            const rightHandle = selection.append('rect')
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
                                    // console.log('adjust X: ', adjustEventX);
                                    // console.log('old x: ', intRegionX);
                                    // console.log('scale max: ', myXScale(myXScale.domain()[1]));
                                    if (adjustEventX <= xScale(xScale.domain()[1]) && adjustEventX >= intRegionX + 2*handleWidth) {
                                        const nWidth = adjustEventX - intRegionX;
                                        region.attr('width', nWidth);
                                        moveHandle.attr('width', nWidth - 2*handleWidth);
                                        rightHandle.attr('x', adjustEventX - handleWidth);
                                    }
                                }));
    
            let initMoveDiff = 0.0;
            moveHandle = selection.append('rect')
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
            
            const sampleButtonGroup = selection.append('g')
                            .style('transform', `translate(${x}px, ${y}px)`);
            
            sampleButton = sampleButtonGroup.append('rect')
                            .attr('x', ((xScale((xScale.domain()[0])) + initRegionWidth) / 2) - (sampleButtonWidth / 2))
                            .attr('y', height + 90)
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
                                console.log('start ts: ', startTs);
                                console.log('end ts: ', endTs);
                                console.log('sample info: ', sampleInfo);
                                fetch(`/run-sampler/${startTs}-${endTs}-${sampleInfo.algorithm}-${sampleInfo.runLength}-${sampleInfo.numRuns}`)
                                    .then((sampleResponse) => sampleResponse.json())
                                    .then((sampleData) => {
                                        console.log('Data received from server.');
                                        d3.select('#pageLayout').remove();
                                        d3.select('#cacheSetBox').remove();
    
                                        mainVis.constructPageVis(sampleData);
                                        leftSampleIntervalPos = parseInt(leftHandle.attr('x'));
                                        rightSampleIntervalPos = parseInt(rightHandle.attr('x')) + handleWidth;
                                        slider();
                                    })
                                    .catch((error) => {
                                        console.error('Error: ', error);
                                    });
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
                                mainVis.zoom(xScale.invert(parseInt(leftHandle.attr('x'))), xScale.invert(parseInt(rightHandle.attr('x')) + handleWidth));
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
                            .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);
    
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
                            .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);
    
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
    
            settingsPopup = SettingsPopup.build(sampleInfo);
        }

        function getCurrTime() {
            return xScale.invert(tabPosition.x);
        }

        function updateTab() {
                let newX = tabPosition.x + x;
                // TODO: Should be able to group these selections somehow
                d3.select('#bottomTab')
                    .style('transform', d => `translate(${newX}px, ${d.y + 10}px)`);
                d3.select('#topTab')
                    .style('transform', d => `translate(${newX}px, ${d.y - height - 10}px)  rotate(0.5turn)`);
                d3.select('#tabLine')
                    .style('transform', d => `translate(${newX}px, 10px)`);
        }
    
        function handleDrag(e) {
            // console.log(e);
            // tabPosition.x += e.dx;
            e.subject.x = Math.max(Math.min(e.x,
                rightSampleIntervalPos), 
                leftSampleIntervalPos);
            updateTab();
            let ts = getCurrTime();
            addElementsByTimestamp(ts);
            updatePagesByTimestamp(ts);
            if (instantaneous) drawLayout(ts);
        }
    
        function slider() {
            d3.select('#dragTab').remove();
    
            tabPosition.x = leftSampleIntervalPos;
            const colour = 'rgb(148, 148, 148)';
            let tab = d3.symbol()
                .type(d3.symbolTriangle)
                .size(60);
    
            let tabGroup = selection.append('g')
                // .datum(tabPosition)
                .attr('id', 'dragTab');
                // .attr('transform', d => `translate(${d.x}, ${d.y})`);
    
            tabGroup.append('line')
                .datum(tabPosition)
                .attr('id', 'tabLine')
                .style('stroke', colour)
                .style('stroke-width', 2)
                .attr('x1', 0)
                .attr('y1', 0)
                .attr('x2', 0)
                .attr('y2', 300)
                .style('transform', (d) => `translate(${d.x + x}px, 10px)`);
    
            tabGroup.append('path')
                .datum(tabPosition)
                .attr('id', 'bottomTab')
                .attr('d', tab)
                .attr('stroke', colour)
                .attr('fill', colour)
                .style('transform', (d) => `translate(${d.x + x}px, ${d.y + 10}px)`)
                .call(d3.drag()
                    .on('drag', handleDrag));
    
            tabGroup.append('path')
                .datum(tabPosition)
                .attr('id', 'topTab')
                .attr('d', tab)
                .attr('stroke', colour)
                .attr('fill', colour)
                .style('transform', (d) => `translate(${d.x + x}px, ${d.y - height - 10}px) rotate(0.5turn)`)
                .call(d3.drag()
                    .on('drag', handleDrag));
        }
    }

    drawTimeGraphLayout.x = function(val) {
        if (!arguments.length) return x;
        x = val;
        return drawTimeGraphLayout;
    }

    drawTimeGraphLayout.y = function(val) {
        if (!arguments.length) return y;
        y = val;
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

    drawTimeGraphLayout.getCurrTime = function() {
        return xScale.invert(tabPosition.x);
    }

    return drawTimeGraphLayout;
}

export default timeGraphLayout;


// class TimeGraphLayout {
//     #xScale;
//     #xAxis;
//     #yScale;
//     #yAxis;
//     #tabPosition;
//     #leftSampleIntervalPos;
//     #rightSampleIntervalPos;
//     #settingsPopup;

//     constructor(points, changePts) {
//         this.#tabPosition = {x: 70, y: 310};
//         const allPts = Object.keys(points).reduce((acc, curr) => acc.concat(points[curr]), []);
//         const maxSizeSum = allPts.map((pt) => pt.size).reduce((max, s) => Math.max(max, s), 0);
//         const minTs = allPts.map((pt) => pt.ts).reduce((min, t) => Math.min(min, t), allPts[0].ts);
//         const maxTs = allPts.map((pt) => pt.ts).reduce((max, t) => Math.max(max, t), allPts[0].ts);
//         const boundaryBuffer = Math.floor((maxTs - minTs)*0.03);

//         const lines = {};
//         for (let type of Object.keys(points)) {
//             lines[type] = [[minTs - boundaryBuffer, 0]];
//             for (let i = 0; i < points[type].length; i++) {
//                 lines[type].push([points[type][i].ts, lines[type][2 * i][1]]);
//                 lines[type].push([points[type][i].ts, points[type][i].size]);
//             }
//             lines[type].push([maxTs + boundaryBuffer, lines[type][lines[type].length - 1][1]]);
//         }

//         this.#xScale = d3.scaleLinear().domain([minTs - boundaryBuffer, maxTs + boundaryBuffer]).range([0, XAXIS_LENGTH]);
//         this.#xAxis = d3.axisBottom(this.#xScale).tickSize(5).tickValues(d3.range(minTs - boundaryBuffer, maxTs + boundaryBuffer,
//             Math.floor((maxTs - minTs + 2*boundaryBuffer) / 10))).tickFormat(d3.format('d'));

//         this.#yScale = d3.scaleLinear().domain([1.05 * maxSizeSum, 0]).range([0, YAXIS_LENGTH]);
//         this.#yAxis = d3.axisLeft(this.#yScale);
//         this.#yAxis.tickValues(d3.range(0, maxSizeSum+1, 
//             Math.pow(2, Math.floor(Math.log2(0.1*maxSizeSum)))
//             )).tickFormat(d3.format('d'));

//         d3.select('#graphLayoutXAxis').call(this.#xAxis)
//                     .selectAll('text')
//                     .attr('dx', '5em')
//                     .attr('dy', '0.7em')
//                     .style('transform', 'rotate(0.12turn');
//         d3.select('#graphLayoutYAxis').call(this.#yAxis);

//         // slider();

//         this.changeRegions(points, changePts);
//         this.sampleRegion();

//         for (let type of Object.keys(points)) {
//             d3.select('#graphLayout')
//                 .append('path')
//                 .datum(lines[type])
//                 .attr('class', 'line')
//                 .attr('fill', 'none')
//                 .attr('stroke', colourOfType[type])
//                 .attr('stroke-width', 1)
//                 .attr('transform', `translate(${LAYOUT_TRANSLATE_X}, ${LAYOUT_TRANSLATE_Y})`)
//                 .attr('d', d3.line()
//                             .x(d => this.#xScale(d[0]))
//                             .y(d => this.#yScale(d[1]))
//                 );
//         }
//     }

//     changeRegions(points, changePts) {
//         const tsDistanceThreshold = Math.floor(0.03 * (this.#xScale.domain()[1] - this.#xScale.domain()[0]));
//         const regions = [];
//         const buffer = Math.floor(0.02 * XAXIS_LENGTH);
//         for (let type of Object.keys(changePts)) {
//             let i = 0;
//             while (i < changePts[type].length) {
//                 let leftEdge = changePts[type][i];
//                 while (i + 1 < changePts[type].length && (points[type][changePts[type][i + 1] - 1].ts - points[type][changePts[type][i] - 1].ts) <= tsDistanceThreshold) {
//                     i++;
//                 }
//                 let rightEdge = changePts[type][i];
//                 regions.push({'left': leftEdge - 1, 'right': rightEdge - 1, 'type': type});
//                 i++;
//             }
//         }

//         // console.log(points);
//         // console.log(regions);

//         d3.select('#graphLayout')
//             .selectAll('.changeRegion')
//             .data(regions)
//             .enter()
//             .append('rect')
//             .attr('class', 'changeRegion')
//             .attr('x', (d) => {
//                 // console.log('type: ', d.type);
//                 // console.log('left: ', d.left);
//                 return this.#xScale(points[d.type][d.left].ts) - buffer;
//             })
//             .attr('y', 0)
//             .attr('width', (d) => {
//                 // console.log('right: ', points[d.type][d.right].ts);
//                 // console.log('left: ', points[d.type][d.left].ts);
//                 // console.log('domain: ', this.#xScale.domain()[0]);
//                 return this.#xScale(this.#xScale.domain()[0] + points[d.type][d.right].ts - points[d.type][d.left].ts) + buffer;
//             })
//             .attr('height', YAXIS_LENGTH)
//             .style('fill', '#ccfff3')
//             .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);
//     }

//     sampleRegion() {
//         const initRegionWidth = Math.floor(0.1 * XAXIS_LENGTH);
//         const handleWidth = 8;
//         const myXScale = this.#xScale;
//         const sampleButtonWidth = 53;
//         let moveHandle, sampleButton = undefined;
//         const region = d3.select('#graphLayout')
//                         .append('rect')
//                         .attr('x', this.#xScale(this.#xScale.domain()[0]))
//                         .attr('y', 0)
//                         .attr('width', initRegionWidth)
//                         .attr('height', YAXIS_LENGTH)
//                         .style('fill', '#ccc')
//                         .style('opacity', 0.5)
//                         .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);
        
//         let initLeftDiff = 0.0;
//         const leftHandle = d3.select('#graphLayout')
//                         .append('rect')
//                         .attr('x', myXScale(myXScale.domain()[0]))
//                         .attr('y', 0)
//                         .attr('width', handleWidth)
//                         .attr('height', YAXIS_LENGTH)
//                         .style('fill', '#ff0000')
//                         .style('opacity', 0.0)
//                         .style('cursor', 'ew-resize')
//                         .style('pointer-events', 'visible')
//                         .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`)
//                         .call(d3.drag()
//                             .on('start', function(event) {
//                                 const intLeftHandleX = parseInt(leftHandle.attr('x'));
//                                 initLeftDiff = event.x - intLeftHandleX - LAYOUT_TRANSLATE_X;
//                             })
//                             .on('drag', function(event) {
//                                 const adjustEventX = event.x - LAYOUT_TRANSLATE_X - initLeftDiff;
//                                 const intRegionWidth = parseInt(region.attr('width'));
//                                 const intRegionX = parseInt(region.attr('x'));
//                                 if (adjustEventX >= myXScale(myXScale.domain()[0]) && adjustEventX <= intRegionX + intRegionWidth - 2*handleWidth) {
//                                     const nWidth = intRegionWidth + intRegionX - adjustEventX;
//                                     region.attr('x', adjustEventX)
//                                             .attr('width', nWidth);
//                                     moveHandle.attr('x', adjustEventX + handleWidth)
//                                             .attr('width', nWidth - 2*handleWidth);
//                                     leftHandle.attr('x', adjustEventX);
//                                 }
//                             }));

//         let initRightDiff = 0.0;
//         const rightHandle = d3.select('#graphLayout')
//                         .append('rect')
//                         .attr('x', myXScale(myXScale.domain()[0]) + initRegionWidth - handleWidth)
//                         .attr('y', 0)
//                         .attr('width', handleWidth)
//                         .attr('height', YAXIS_LENGTH)
//                         .style('fill', '#ff0000')
//                         .style('opacity', 0.0)
//                         .style('cursor', 'ew-resize')
//                         .style('pointer-events', 'visible')
//                         .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`)
//                         .call(d3.drag()
//                             .on('start', function(event) {
//                                 const intRightHandleX = parseInt(rightHandle.attr('x')) + handleWidth;
//                                 initRightDiff = event.x - intRightHandleX - LAYOUT_TRANSLATE_X;
//                             })
//                             .on('drag', function(event) {
//                                 const adjustEventX = event.x - LAYOUT_TRANSLATE_X - initRightDiff;
//                                 const intRegionX = parseInt(region.attr('x'));
//                                 // console.log('adjust X: ', adjustEventX);
//                                 // console.log('old x: ', intRegionX);
//                                 // console.log('scale max: ', myXScale(myXScale.domain()[1]));
//                                 if (adjustEventX <= myXScale(myXScale.domain()[1]) && adjustEventX >= intRegionX + 2*handleWidth) {
//                                     const nWidth = adjustEventX - intRegionX;
//                                     region.attr('width', nWidth);
//                                     moveHandle.attr('width', nWidth - 2*handleWidth);
//                                     rightHandle.attr('x', adjustEventX - handleWidth);
//                                 }
//                             }));

//         let initMoveDiff = 0.0;
//         moveHandle = d3.select('#graphLayout')
//                         .append('rect')
//                         .attr('x', myXScale(myXScale.domain()[0]) + handleWidth)
//                         .attr('y', 0)
//                         .attr('width', initRegionWidth - 2*handleWidth)
//                         .attr('height', YAXIS_LENGTH)
//                         .style('fill', '#00ff0c')
//                         .style('opacity', 0.0)
//                         .style('cursor', 'move')
//                         .style('pointer-events', 'visible')
//                         .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`)
//                         .call(d3.drag()
//                             .on('start', function(event) {
//                                 const intRegionX = parseInt(region.attr('x'));
//                                 initMoveDiff = event.x - intRegionX - LAYOUT_TRANSLATE_X;
//                             })
//                             .on('drag', function(event) {
//                                 const intRegionWidth = parseInt(region.attr('width'));
//                                 const adjustEventX = event.x - LAYOUT_TRANSLATE_X - initMoveDiff;
//                                 if (adjustEventX + intRegionWidth <= myXScale(myXScale.domain()[1]) && adjustEventX >= myXScale(myXScale.domain()[0])) {
//                                     region.attr('x', adjustEventX);
//                                     moveHandle.attr('x', adjustEventX + handleWidth);
//                                     leftHandle.attr('x', adjustEventX);
//                                     rightHandle.attr('x', adjustEventX + intRegionWidth - handleWidth);
//                                 }
//                             }));
        
//         const sampleButtonGroup = d3.select('#graphLayout')
//                         .append('g')
//                         .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);
        
//         sampleButton = sampleButtonGroup
//                         .append('rect')
//                         .attr('x', ((myXScale((myXScale.domain()[0])) + initRegionWidth) / 2) - (sampleButtonWidth / 2))
//                         .attr('y', YAXIS_LENGTH + 90)
//                         .attr('width', sampleButtonWidth)
//                         .attr('height', 30)
//                         .attr('rx', 7)
//                         .attr('ry', 7)
//                         .style('fill', 'white')
//                         .style('stroke', '#ccc')
//                         .style('stroke-width', '1px')
//                         .style('cursor', 'pointer')
//                         .style('pointer-events', 'visible')
//                         .on('click', function() {
//                             let startTs = Math.floor(myXScale.invert(parseInt(leftHandle.attr('x'))));
//                             let endTs = Math.floor(myXScale.invert(parseInt(rightHandle.attr('x')) + handleWidth));
//                             console.log('start ts: ', startTs);
//                             console.log('end ts: ', endTs);
//                             fetch(`/run-sampler/${startTs}-${endTs}`)
//                                 .then((sampleResponse) => sampleResponse.json())
//                                 .then((sampleData) => {
//                                     console.log('Data received from server.');
//                                     d3.select('#pageLayout').remove();
//                                     d3.select('#cacheSetBox').remove();

//                                     mainVis.constructPageVis(sampleData);
//                                     mainVis.getGraphLayout().setLeftSampleIntervalPos(parseInt(leftHandle.attr('x')));
//                                     mainVis.getGraphLayout().setRightSampleIntervalPos(parseInt(rightHandle.attr('x')) + handleWidth)
//                                     mainVis.getGraphLayout().slider();
//                                 })
//                                 .catch((error) => {
//                                     console.error('Error: ', error);
//                                 });
//                         })
//                         .on('mouseover', function() {
//                             d3.select(this)
//                                 .transition()
//                                 .style('fill', '#ccc');
//                         })
//                         .on('mouseout', function() {
//                             d3.select(this)
//                                 .transition()
//                                 .style('fill', 'white');
//                         });

//         sampleButtonGroup.append('text')
//                         .attr('text-anchor', 'middle')
//                         .attr('x', parseInt(sampleButton.attr('x')) + (sampleButtonWidth / 2))
//                         .attr('y', parseInt(sampleButton.attr('y')) + 18.5)
//                         .attr('font-family', 'monospace')
//                         .style('alignment-baseline', 'middle')
//                         .style('pointer-events', 'none')
//                         .text('Sample');

//         const zoomButtonGroup = d3.select('#graphLayout')
//                         .append('g')
//                         .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);

//         const zoomButton = zoomButtonGroup.append('rect')
//                         .attr('x', parseInt(sampleButton.attr('x')) + sampleButtonWidth + 15)
//                         .attr('y', parseInt(sampleButton.attr('y')))
//                         .attr('width', sampleButtonWidth)
//                         .attr('height', 30)
//                         .attr('rx', 7)
//                         .attr('ry', 7)
//                         .style('fill', 'white')
//                         .style('stroke', '#ccc')
//                         .style('stroke-width', '1px')
//                         .style('cursor', 'pointer')
//                         .style('pointer-events', 'visible')
//                         .on('click', function() {
//                             mainVis.zoom(myXScale.invert(parseInt(leftHandle.attr('x'))), myXScale.invert(parseInt(rightHandle.attr('x')) + handleWidth));
//                         })
//                         .on('mouseover', function() {
//                             d3.select(this)
//                                 .transition()
//                                 .style('fill', '#ccc');
//                         })
//                         .on('mouseout', function() {
//                             d3.select(this)
//                                 .transition()
//                                 .style('fill', 'white');
//                         });;

//         zoomButtonGroup.append('text')
//                         .attr('x', parseInt(zoomButton.attr('x')) + (sampleButtonWidth / 2))
//                         .attr('y', parseInt(zoomButton.attr('y')) + 18.5)
//                         .attr('text-anchor', 'middle')
//                         .attr('font-family', 'monospace')
//                         .style('alignment-baseline', 'middle')
//                         .style('pointer-events', 'none')
//                         .text('Zoom+');

//         const unzoomButtonGroup = d3.select('#graphLayout')
//                         .append('g')
//                         .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);

//         const unzoomButton = unzoomButtonGroup.append('rect')
//                         .attr('x', parseInt(sampleButton.attr('x')) + 2*(sampleButtonWidth + 15))
//                         .attr('y', parseInt(sampleButton.attr('y')))
//                         .attr('width', sampleButtonWidth)
//                         .attr('height', 30)
//                         .attr('rx', 7)
//                         .attr('ry', 7)
//                         .style('fill', 'white')
//                         .style('stroke', '#ccc')
//                         .style('stroke-width', '1px')
//                         .style('cursor', 'pointer')
//                         .style('pointer-events', 'visible')
//                         .on('click', function() {
//                             mainVis.unzoom();
//                         })
//                         .on('mouseover', function() {
//                             d3.select(this)
//                                 .transition()
//                                 .style('fill', '#ccc');
//                         })
//                         .on('mouseout', function() {
//                             d3.select(this)
//                                 .transition()
//                                 .style('fill', 'white');
//                         });;

//         unzoomButtonGroup.append('text')
//                         .attr('x', parseInt(unzoomButton.attr('x')) + (sampleButtonWidth / 2))
//                         .attr('y', parseInt(unzoomButton.attr('y')) + 18.5)
//                         .attr('text-anchor', 'middle')
//                         .attr('font-family', 'monospace')
//                         .style('alignment-baseline', 'middle')
//                         .style('pointer-events', 'none')
//                         .text('Zoom-');

//         const settingsButtonGroup = d3.select('#graphLayout')
//                         .append('g')
//                         .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);

//         const settingsButton = settingsButtonGroup.append('rect')
//                         .attr('x', parseInt(sampleButton.attr('x')) - sampleButtonWidth - 15)
//                         .attr('y', parseInt(sampleButton.attr('y')))
//                         .attr('width', sampleButtonWidth)
//                         .attr('height', 30)
//                         .attr('rx', 7)
//                         .attr('ry', 7)
//                         .style('fill', 'white')
//                         .style('stroke', '#ccc')
//                         .style('stroke-width', '1px')
//                         .style('cursor', 'pointer')
//                         .style('pointer-events', 'visible')
//                         .on('click', function() {
//                             d3.select('#settingsPopup')
//                                 .transition()
//                                 .style('display', 'block');
//                         })
//                         .on('mouseover', function() {
//                             d3.select(this)
//                                 .transition()
//                                 .style('fill', '#ccc');
//                         })
//                         .on('mouseout', function() {
//                             d3.select(this)
//                                 .transition()
//                                 .style('fill', 'white');
//                         });;

//         settingsButtonGroup.append('text')
//                         .attr('x', parseInt(settingsButton.attr('x')) + (sampleButtonWidth / 2))
//                         .attr('y', parseInt(settingsButton.attr('y')) + 18.5)
//                         .attr('text-anchor', 'middle')
//                         .attr('font-family', 'monospace')
//                         .style('alignment-baseline', 'middle')
//                         .style('pointer-events', 'none')
//                         .text('Settings');

//         this.#settingsPopup = SettingsPopup.build();
//     }

//     setLeftSampleIntervalPos(pos) {
//         this.#leftSampleIntervalPos = pos;
//     }

//     setRightSampleIntervalPos(pos) {
//         this.#rightSampleIntervalPos = pos
//     }

//     getLeftSampleIntervalPos() {
//         return this.#leftSampleIntervalPos;
//     }

//     getRightSampleIntervalPos() {
//         return this.#rightSampleIntervalPos;
//     }

//     getCurrTime() {
//         return this.#xScale.invert(this.#tabPosition.x);
//     }

//     updateTab() {
//         let newX = this.#tabPosition.x + LAYOUT_TRANSLATE_X;
//         // TODO: Should be able to group these selections somehow
//         d3.select('#bottomTab')
//             .style('transform', d => `translate(${newX}px, ${d.y}px)`);
//         d3.select('#topTab')
//             .style('transform', d => `translate(${newX}px, ${d.y-300}px)  rotate(0.5turn)`);
//         d3.select('#tabLine')
//             .style('transform', d => `translate(${newX}px, 10px)`);
//     }

//     handleDrag(e) {
//         // console.log(e);
//         // tabPosition.x += e.dx;
//         e.subject.x = Math.max(Math.min(e.x, 
//             mainVis.getGraphLayout().getRightSampleIntervalPos()), 
//             mainVis.getGraphLayout().getLeftSampleIntervalPos());
//         mainVis.getGraphLayout().updateTab();
//         let ts = mainVis.getGraphLayout().getCurrTime();
//         addElementsByTimestamp(ts);
//         updatePagesByTimestamp(ts);
//         if (instantaneous) drawLayout(ts);
//     }

//     slider() {
//         d3.select('#dragTab').remove();

//         this.#tabPosition.x = this.#leftSampleIntervalPos;
//         const colour = 'rgb(148, 148, 148)';
//         let tab = d3.symbol()
//             .type(d3.symbolTriangle)
//             .size(60);

//         let tabGroup = d3.select('#graphLayout')
//             .append('g')
//             // .datum(tabPosition)
//             .attr('id', 'dragTab');
//             // .attr('transform', d => `translate(${d.x}, ${d.y})`);

//         tabGroup.append('line')
//             .datum(this.#tabPosition)
//             .attr('id', 'tabLine')
//             .style('stroke', colour)
//             .style('stroke-width', 2)
//             .attr('x1', 0)
//             .attr('y1', 0)
//             .attr('x2', 0)
//             .attr('y2', 300)
//             .style('transform', (d) => `translate(${d.x + LAYOUT_TRANSLATE_X}px, 10px)`);

//         tabGroup.append('path')
//             .datum(this.#tabPosition)
//             .attr('id', 'bottomTab')
//             .attr('d', tab)
//             .attr('stroke', colour)
//             .attr('fill', colour)
//             .style('transform', (d) => `translate(${d.x + LAYOUT_TRANSLATE_X}px, ${d.y}px)`)
//             .call(d3.drag()
//                 .on('drag', this.handleDrag));

//         tabGroup.append('path')
//             .datum(this.#tabPosition)
//             .attr('id', 'topTab')
//             .attr('d', tab)
//             .attr('stroke', colour)
//             .attr('fill', colour)
//             .style('transform', (d) => `translate(${d.x + LAYOUT_TRANSLATE_X}px, ${d.y-300}px) rotate(0.5turn)`)
//             .call(d3.drag()
//                 .on('drag', this.handleDrag));
//     }

//     destroy() {
//         d3.select('#graphLayout').remove();
//     }

//     static build(points, changePts) {
//         // const allocTimes = records.filter((rec) => rec.is_alloc == 1).map((alloc) => alloc.ts);
//         // const freeTimes = records.filter((rec) => rec.is_alloc == 0).map((free) => free.ts);
//         // const minTime = Math.min(...allocTimes);
//         // const maxTime = Math.max(Math.max(...allocTimes), Math.max(...freeTimes));
//         // const boundaryBuffer = Math.floor((maxTime - minTime)*0.03);
//         // const sizes = records.map(obj => obj.size);

//         let graphLayout = d3.select('#visPanels')
//             .append('svg')
//             .attr('id', 'graphLayout')
//             .style('width', '100%')
//             .style('height', '100%')
//             .style('grid-column', '1 / 3')
//             .style('grid-row', 2)
//             .style('justify-self', 'end');

//         let graphLayoutAxes = graphLayout.append('g')
//             .attr('id', 'graphLayoutAxes');
//         graphLayoutAxes.append('g')
//             .attr('id', 'graphLayoutXAxis')
//             .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, 300px)`);
//         graphLayoutAxes.append('g')
//             .attr('id', 'graphLayoutYAxis')
//             .style('transform', `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);

//         return new TimeGraphLayout(points, changePts);
//     }
// }

// export default TimeGraphLayout;