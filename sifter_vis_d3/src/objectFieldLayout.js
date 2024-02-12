import * as d3 from 'd3';
import { colourOfType } from './vis.js';
import { typeInfoPopup, trimString } from './statsTracker.js';


function objectLayout() {
    let memLayout, data, xScale, yScale, pageSize, statsTracker = undefined;
    let x = 30,
        y = 40,
        width = 290,
        height = 290;

    function drawObjectLayout(selection) {
        let objects = selection.datum().objects,
            startAddr = selection.datum().startAddr,
            initTs = selection.datum().initTs,
            pageSize = selection.datum().pageSize,
            cachelineSize = selection.datum().cachelineSize;
        memLayout = selection;

        // let memLayoutAxes = memLayout.append('g')
        //     .attr('id', 'memLayoutAxes');
        
        memLayout.append('g')
            .attr('id', 'blockGroup')
            .style('transform', `translate(${typeof x == 'string' ? x : x + 'px'}, ${typeof y == 'string' ? y : y + 'px'})`);
        let yAxisGridGroup = memLayout.append('g')
            .attr('id', 'memLayoutYAxisGrid')
            .style('transform', `translate(${typeof x == 'string' ? x : x + 'px'}, ${typeof y == 'string' ? y : y + 'px'})`);
        let xAxisGroup = memLayout.append('g')
            .attr('id', 'memLayoutXAxisGroup')
            .style('transform', `translate(${typeof x == 'string' ? x : x + 'px'}, ${typeof y == 'string' ? y : y + 'px'})`);
        let yAxisGroup = memLayout.append('g')
            .attr('id', 'memLayoutYAxisGroup')
            .style('transform', `translate(${typeof x == 'string' ? x : x + 'px'}, ${typeof y == 'string' ? y : y + 'px'})`);

        xScale = d3.scaleLinear().domain([0, cachelineSize]).range([0, width]);
        let xAxis = d3.axisTop(xScale);
        xAxis.tickValues(d3.range(0, cachelineSize+1, 8)).tickFormat(d3.format('d'));

        yScale = d3.scaleLinear().domain([0, cachelineSize]).range([0, height]);
        let yAxis = d3.axisLeft(yScale);
        yAxis.tickValues(d3.range(0, cachelineSize+1, 8)).tickFormat(d3.format('d'));
        let yAxisGrid = d3.axisLeft(yScale).tickSize(-height).tickValues(d3.range(0, cachelineSize, 1)).tickFormat('');

        xAxisGroup.call(xAxis);
        yAxisGroup.call(yAxis);
        yAxisGridGroup.call(yAxisGrid);

        data = splitBlocks(objects, startAddr, pageSize, cachelineSize);
        addElementsByTimestamp(initTs);
    }

    drawObjectLayout.addElementsByTimestamp = function(ts) {
        addElementsByTimestamp(ts);
    }

    function addElementsByTimestamp(ts) {
        if (!memLayout) return;
        let elements = memLayout.select('#blockGroup')
            .selectAll('.zoomDataObject')
            .data(data.filter((d) => d.start <= ts && (d.end == null || d.end >= ts)),
                (d) => d.id);
    
        let enterElements = elements.enter()
            .append('g')
            .attr('class', 'zoomDataObject');
        enterElements.append('rect')
            .attr('class', (d) => `block-${d.trimType}`)
            .attr('x', (d) => xScale(d.x))
            .attr('y', (d) => yScale(d.y))
            .attr('width', (d) => xScale(d.width))
            .attr('height', (d) => yScale(d.height))
            .style('fill', (d) => d.colour)
            .style('pointer-events', 'visible')
            .on('mouseover', function(e, d) {
                memLayout.selectAll(`.block-${d.trimType}`)
                    .transition()
                    .style('fill', d3.color(d.colour).darker(2));

                let type = trimString(d.type, 18);
                let typeHintSvg = memLayout.append('svg')
                        .attr('id', 'typeHint')
                        .attr('data-type', type)
                        .attr('x', d3.pointer(e)[0] - 2*type.length - 10)
                        .attr('y', d3.pointer(e)[1] + 40)
                        .style('width', `${3*type.length}px`)
                        .style('height', '20px');
                typeHintSvg.append('rect')
                        .attr('x', 6)
                        .attr('y', 0)
                        .attr('width', 6.5*type.length)
                        .attr('height', 14)
                        .style('fill', 'white')
                        .style('pointer-events', 'none');
                        
                typeHintSvg.append('text')
                        .attr('x', type.length)
                        .attr('y', 8)
                        .attr('font-family', 'monospace')
                        .style('font-size', '10px')
                        .style('pointer-events', 'none')
                        .text(type);
                
                memLayout.append('g')
                        .attr('id', 'statsPopup')
                        .call(typeInfoPopup().x('95%')
                                .y('14%')
                                .width(260)
                                .type(d.type)
                                .lineSpace(12)
                                .maxChars(20)
                                .textLines(statsTracker.getColocRatios(d.type))
                                );
            })
            .on('mousemove', function(e, d) {
                let typeHint = memLayout.select('#typeHint');
                typeHint.attr('x', d3.pointer(e)[0] - 2*typeHint.attr('data-type').length - 10)
                    .attr('y', d3.pointer(e)[1] + 40);
            })
            .on('mouseout', function(e, d) {
                memLayout.select('#typeHint')
                    .remove();
                memLayout.selectAll(`.block-${d.trimType}`)
                    .transition()
                    .style('fill', d.colour);
                memLayout.select('#statsPopup')
                    .remove();
            });
        enterElements.append('line')
            .attr('x1', (d) => xScale(d.x))
            .attr('y1', (d) => yScale(d.y) - yScale(yScale.domain()[0]-1))
            .attr('x2', (d) => xScale(d.x))
            .attr('y2', (d) => yScale(d.y) - yScale(yScale.domain()[0]-1) + yScale(yScale.domain()[0]-d.height))
            .style('visibility', (d) => d.isBegin ? 'inherit' : 'hidden')
            .style('stroke', 'black')
            .style('stroke-width', '1px');
        enterElements.append('line')
            .attr('x1', (d) => xScale(d.x + d.width))
            .attr('y1', (d) => yScale(d.y) - yScale(yScale.domain()[0]-1))
            .attr('x2', (d) => xScale(d.x + d.width))
            .attr('y2', (d) => yScale(d.y) - yScale(yScale.domain()[0]-1) + yScale(yScale.domain()[0]-d.height))
            .style('visibility', (d) => d.isEnd ? 'inherit' : 'hidden')
            .style('stroke', 'black')
            .style('stroke-width', '1px');
    
        elements.exit().remove();
    }

    function splitBlocks(objects, startPage, pageSize, cachelineSize) {
        const pageBlocks = [];
        const startAddr = startPage * pageSize;
        // const startAddr = objects[0].alloc_addr - (objects[0].alloc_addr % cachelineSize);
        
        for (let i = 0; i < objects.length; i++) {
            let obj = objects[i];
            let trimType = obj.type.replace(/[^a-zA-Z]+/g, '');
            let col = colourOfType[obj.type];
            const normAddr = (obj.addr - startAddr);
            const begin = normAddr % cachelineSize;
            let startBlock = {  type: obj.type,
                                trimType: trimType,
                                id: i*3,
                                x: begin,
                                y: Math.floor(normAddr / cachelineSize),
                                width: Math.min(obj.size, cachelineSize - begin),
                                height: 1,
                                start: obj.allocTs,
                                end: obj.freeTs,
                                colour: col,
                                isBegin: !obj.isDup
                                };
            if (obj.size > cachelineSize - begin) {
                startBlock.isEnd = false;
                // let midHeight = Math.floor(Math.min(obj.alloc_size - cachelineSize + begin,
                //                                     pageSize - (obj.alloc_addr % pageSize) + cachelineSize - begin) / cachelineSize);
                let midHeight = Math.floor((obj.size - cachelineSize + begin) / cachelineSize);
                let pageRem = Math.floor((pageSize - ((obj.addr % pageSize) + cachelineSize - begin)) / cachelineSize);
                
                if (midHeight > pageRem) midHeight = pageRem;
                // else midHeight -= 1;
                
                if (obj.size >= 2*cachelineSize - begin && midHeight > 0) {
                    pageBlocks.push({type: obj.type,
                                    trimType: trimType,
                                    id: i*3 + 1,
                                    x: 0,
                                    y: Math.floor(normAddr / cachelineSize) + 1,
                                    width: cachelineSize,
                                    height: midHeight,
                                    start: obj.allocTs,
                                    end: obj.freeTs,
                                    colour: col,
                                    isStart: false,
                                    isEnd: false
                                    });
                }
                let leftover = (obj.size - cachelineSize + begin) % cachelineSize;
                if (midHeight != pageRem && leftover > 0) {
                    pageBlocks.push({type: obj.type,
                                    trimType: trimType,
                                    id: i*3 + 2,
                                    x: 0,
                                    y: Math.floor(normAddr / cachelineSize) + midHeight + 1,
                                    width: leftover,
                                    height: 1,
                                    start: obj.allocTs,
                                    end: obj.freeTs,
                                    colour: col,
                                    isStart: false,
                                    isEnd: true
                                    });
                }
            }
            else {
                startBlock.isEnd = true;
            }
            pageBlocks.push(startBlock);
        }
        return pageBlocks;
    }

    drawObjectLayout.x = function(val) {
        if (!arguments) return x;
        x = val;
        return drawObjectLayout;
    }

    drawObjectLayout.y = function(val) {
        if (!arguments) return y;
        y = val;
        return drawObjectLayout;
    }

    drawObjectLayout.width = function(val) {
        if (!arguments) return width;
        width = val;
        return drawObjectLayout;
    }

    drawObjectLayout.height = function(val) {
        if (!arguments) return height;
        height = val;
        return drawObjectLayout;
    }

    drawObjectLayout.stats = function(val) {
        if (!arguments) return statsTracker;
        statsTracker = val;
        return drawObjectLayout;
    }

    return drawObjectLayout;
}

export default objectLayout;