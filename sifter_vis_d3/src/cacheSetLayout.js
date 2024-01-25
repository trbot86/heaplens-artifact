import * as d3 from 'd3';
import { getCurrTime, mainVis } from './dbloader.js';


/* TODO:
    *   Implement ability to resize the cache visualization area so that
        patterns may be more easily seen
    *   Attempt to auto-detect cache information in memhook application?
    *   Allow user to input values for cache info
    *   Store presets with cache information of processors that have been
        mapped */

function cacheSetLayout() {
    let objects = [],
        cacheLineSize = 64,
        cacheInfo = [],
        instantaneous = false,
        currTime = 0,
        currCache = {},
        // currSize = 0,
        // currAssoc = 0,
        // currWidth = 0,
        mainVis = undefined,
        focused = false,
        initDragX = 320
        // focusCallback = undefined;

    function drawLayout(selection) {
        
        objects = selection.datum();
    
        let cacheSetTabs = selection.append('g')
            .attr('id', 'cacheSetTabs')
            .style('width', '100%')
            .style('height', '10%');
    
        let tabGroup = cacheSetTabs.selectAll('.cacheTab')
            .data(cacheInfo)
            .enter()
            .append('g')
            .attr('class', 'classTab');

        tabGroup.append('rect')
            .attr('x', (d, i) => i*45)
            .attr('y', 0)
            .attr('width', '45')
            .attr('height', '30')
            .attr('rx', 7)
            .style('fill', 'white')
            .style('stroke', '#ccc')
            .style('stroke-width', '1px')
            .style('pointer-events', 'visible')
            .style('cursor', 'pointer')
            // .style('border-top-left-radius', (d, i) => i == 0 ? '7px' : '0px')
            // .style('border-bottom-left-radius', (d, i) => i == 0 ? '7px' : '0px')
            // .style('border-top-right-radius', (d, i) => i == cacheInfo.length - 1 ? '7px' : '0px')
            // .style('border-bottom-right-radius', (d, i) => i == cacheInfo.length - 1 ? '7px' : '0px')
            .on('click', function(e, d) {
                currCache = d;
                d3.select('#cacheWidthHandle').attr('cx', currCache.currDragX);
                // currSize = d.size;
                // currAssoc = d.associativity;
                // currWidth = d.width;
                refreshSquares();
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
            
        tabGroup.append('text')
            .attr('text-anchor', 'middle')
            .attr('x', (d, i) => i*45 + 22)
            .attr('y', 18)
            .attr('font-family', 'monospace')
            .style('alignment-baseline', 'middle')
            .style('pointer-events', 'none')
            .text((d, i) => `L${i+1}`);
    
        for (let cache of cacheInfo) {
            cache.initWidth = cache.width;
            cache.currDragX = initDragX;
        }
        drawToggle();
        drawFocusButton();
        drawWidthHandle();
        currCache = cacheInfo[0];
        refreshSquares();

    }

    drawLayout.cacheLineSize = function(val) {
        if (!arguments) return cacheLineSize;
        cacheLineSize = val;
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
        if (instantaneous) drawSquares();
        return drawLayout;
    }

    drawLayout.mainVis = function(val) {
        if (!arguments) return mainVis;
        mainVis = val;
        return drawLayout;
    }

    // drawLayout.focusCallback = function(val) {
    //     if (!arguments) return focusCallback;
    //     focusCallback = val;
    //     return drawLayout;
    // }

    function drawToggle() {
        d3.select('#toggleGroup').remove();
    
        let toggleGroup = d3.select('#cacheSetBox')
            .append('g')
            .attr('id', 'toggleGroup')
            .style('transform', 'translate(95px, 85%)');
        
        toggleGroup.append('rect')
            .style('width', '24px')
            .style('height', '5px')
            .style('fill', '#ddd');
        
        toggleGroup.append('circle')
            .attr('class', 'toggle')
            .attr('cx', instantaneous ? 24 : 0)
            .attr('cy', 2.5)
            .attr('r', 10)
            .style('fill', '#ccc')
            .on('click', function() {
                instantaneous = !instantaneous;
                if (instantaneous) {
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
            .text('Summary');
    
        toggleGroup.append('text')
            .attr('x', 43)
            .attr('y', 5)
            .attr('font-family', 'monospace')
            .text('Instantaneous');
    }

    function drawWidthHandle() {
        d3.select('#cacheSetSVG')
            .append('circle')
            .attr('id', 'cacheWidthHandle')
            .attr('cx', initDragX)
            .attr('cy', 220)
            .attr('r', 10)
            .style('cursor', 'pointer')
            .style('fill', 'url(#crosshatch)')
            .style('visibility', 'hidden')
            .call(d3.drag()
                .on('drag', function(e) {
                    d3.select(this).attr('cx', e.x);
                    currCache.currDragX = e.x;
                    
                    if (Math.floor((currCache.initWidth + e.x - initDragX) / currCache.sqSize) !=
                        Math.floor(currCache.width / currCache.sqSize)) {
                        currCache.width = currCache.initWidth + e.x - initDragX;
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
            .attr('y', 90)
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
                    .style('transform', `translate(7px, 220px) rotate(${focused ? '' : '-'}0.25turn)`);
                if (focused) {
                    d3.select('#cacheWidthHandle').style('visibility', 'visible');
                    d3.select('#cacheSetSVG').style('width', '850px');
                }
                else {
                    d3.select('#cacheWidthHandle').style('visibility', 'hidden');
                    d3.select('#cacheSetSVG').style('width', '350px');
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
                .style('transform', 'translate(7px, 220px) rotate(-0.25turn)');
    }
    
    function getSquaresData(allocs) {
        let currSize = currCache.size,
            currAssoc = currCache.associativity,
            currWidth = currCache.width;
        let numCacheSets = Math.ceil(currSize / (currAssoc*cacheLineSize));
        let squareSize = Math.floor(currCache.initWidth / Math.sqrt(numCacheSets));
        let setsPerRow = Math.floor(currWidth / squareSize);

        if (!currCache.sqSize) currCache.sqSize = squareSize;
    
        let setMap = allocs.map((obj) => ({cacheline: Math.floor(obj.addr / cacheLineSize) % numCacheSets,
            spread: 1 + Math.max(Math.ceil((obj.size - (cacheLineSize - (obj.addr % cacheLineSize))) / cacheLineSize), 0)}));
        let freqMap = setMap.reduce((acc, curr) => {
            let inc = Math.ceil(curr.spread / numCacheSets);
            for (let i = curr.cacheline; i < curr.cacheline + Math.min(numCacheSets, curr.spread); i++) {
                let rounded = i - curr.cacheline < curr.spread % numCacheSets ? inc : inc - 1;
                let j = i % numCacheSets;
                acc[j] ? acc[j] += rounded : acc[j] = rounded;
            }
            // acc[curr] ? acc[curr]++ : acc[curr] = 1;
            return acc;
        }, {});
    
        return new Array(numCacheSets).fill(undefined).map((d, i) => 
            ({x: (i % setsPerRow)*squareSize,
                y: Math.floor(i / setsPerRow)*squareSize,
                freq: freqMap[i],
                size: squareSize}));
    }

    function drawSquares() {
        let squaresData = getSquaresData(instantaneous ? objects.filter(d => d.allocTs <= currTime && d.freeTs >= currTime) : objects);
        const heatScale = d3.scaleLinear().domain([0, Math.max(1, Math.max(...squaresData.map(d => d.freq ? d.freq : 0)))]).range(['white', 'red']);
    
        let cacheLayout = d3.select('#cacheLayout');
    
        if (cacheLayout.empty()) {
            cacheLayout = d3.select('#cacheSetBox')
                .insert('g', '#toggleGroup')
                .attr('id', 'cacheLayout')
                .style('transform', 'translate(0px, 50px)');
        }
    
        cacheLayout.selectAll('rect')
            .data(squaresData, d => (d.x, d.y))
            .join(enter => enter.append('rect')
                .attr('x', d => d.x)
                .attr('y', d => d.y)
                .attr('width', d => d.size)
                .attr('height', d => d.size)
                .style('stroke', '#ccc')
                .style('stroke-width', 0.5)
                .style('fill', function(d, i) {
                    return heatScale(d.freq ? d.freq : 0);
                }),
                update => update.style('fill', function(d, i) {
                    return heatScale(d.freq ? d.freq : 0);
                }),
                exit => exit.remove()
            );
            // .style('transform', 'translate(50px, 85px)');
    }
    
    function refreshSquares() {
        d3.select('#cacheLayout').remove();
        drawSquares();
        // drawToggle();
    }

    return drawLayout;
}

export default cacheSetLayout;