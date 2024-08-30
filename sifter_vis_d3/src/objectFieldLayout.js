import * as d3 from 'd3';
import { mainVis } from './dbloader.js';
import { colourOfType, sizeOfType } from './vis.js';
import { typeInfoPopup, trimString } from './statsTracker.js';
import { trimLongTypeName } from './legend.js';


function objectLayout() {
    let memLayout, data, xScale, yScale, pageSize, statsTracker, fields, perf, perfGroup, expandedTypes = undefined;
    let x = 0,
        y = 0,
        width = 300,
        actualHeight = 300,
        prevTs = 0,
        objects,
        startAddr,
        cachelineSize,
        canvas,
        perfVis = false,
        cacheSetLayout = undefined;

    function drawObjectLayout(selection) {
        objects = selection.datum().objects;
        startAddr = selection.datum().startAddr;
        pageSize = selection.datum().pageSize;
        cachelineSize = selection.datum().cachelineSize;
        memLayout = selection;
        canvas = document.createElement('canvas');
        let initTs = selection.datum().initTs;

        perf = perf[startAddr] ? perf[startAddr].map((d) => d[0]) : undefined;

        // let memLayoutAxes = memLayout.append('g')
        //     .attr('id', 'memLayoutAxes');
        
        let xAxisGroup = memLayout.append('g')
            .attr('id', 'memLayoutXAxisGroup')
            .style('transform', `translate(${typeof x == 'string' ? x : x + 'px'}, ${typeof y == 'string' ? y : y + 'px'})`);
        let yAxisGroup = memLayout.append('g')
            .attr('id', 'memLayoutYAxisGroup')
            .style('transform', `translate(${typeof x == 'string' ? x : x + 'px'}, ${typeof y == 'string' ? y : y + 'px'})`);
        memLayout.append('g')
            .attr('id', 'blockGroup')
            .style('transform', `translate(${typeof x == 'string' ? x : x + 'px'}, ${typeof y == 'string' ? y : y + 'px'})`);
        let yAxisGridGroup = memLayout.append('g')
            .attr('id', 'memLayoutYAxisGrid')
            .style('transform', `translate(${typeof x == 'string' ? x : x + 'px'}, ${typeof y == 'string' ? y : y + 'px'})`);
        

        xScale = d3.scaleLinear().domain([0, cachelineSize]).range([0, width]);
        let xAxis = d3.axisTop(xScale);
        xAxis.tickValues(d3.range(0, cachelineSize+1, Math.floor(cachelineSize / 8))).tickFormat(d3.format('d'));

        // let actualHeight = ((pageSize*cachelineSize) / (4096*32))*unitHeight;
        yScale = d3.scaleLinear().domain([0, Math.floor(pageSize / cachelineSize)]).range([0, actualHeight]);
        let yAxis = d3.axisLeft(yScale);
        yAxis.tickValues(d3.range(0, Math.floor(pageSize / cachelineSize)+1, 8)).tickFormat(d3.format('d'));
        let yAxisGrid = d3.axisLeft(yScale).tickSize(-width).tickValues(d3.range(0, Math.floor(pageSize / cachelineSize)+1, 1)).tickFormat('');

        xAxisGroup.call(xAxis);
        yAxisGroup.call(yAxis)
            .select('path')
            .style('stroke', '#ccc');
        yAxisGridGroup.call(yAxisGrid)
            .selectAll('.tick')
            .filter((d, i) => i % 2 === 1)
            .select('line')
            .style('stroke', '#ccc');
        yAxisGridGroup.select('path')
            .style('display', 'none');

        data = splitBlocks(objects, startAddr, pageSize, cachelineSize);
        addElementsByTimestamp(initTs);

        perfGroup = memLayout.append('g')
            .attr('id', 'perfGroup')
            .style('transform', `translate(${typeof x == 'string' ? x : x + 'px'}, ${typeof y == 'string' ? y : y + 'px'})`);
        perfHighlight();
    }

    function perfVisible() {
        perfGroup.selectAll('.perfHighlight')
            .style('visibility', perfVis ? 'inherit' : 'hidden');
    }

    function perfHighlight() {
        perfGroup.selectAll('.perfHighlight')
            .data(perf ? perf : [])
            .enter()
            .append('rect')
            .attr('class', 'perfHighlight')
            .attr('x', xScale(0))
            .attr('y', (d) => yScale(Math.floor((d - (parseInt(startAddr)*pageSize)) / cachelineSize)))
            .attr('width', xScale(cachelineSize))
            .attr('height', yScale(1))
            .style('visibility', perfVis ? 'inherit' : 'hidden');
    }

    drawObjectLayout.addElementsByTimestamp = function(ts) {
        addElementsByTimestamp(ts);
    }

    function addElementsByTimestamp(ts) {
        if (!memLayout) return;
        prevTs = ts;
        // console.log('Here are the objs in objLayout');
        // console.log(data);
        let elements = memLayout.select('#blockGroup')
            .selectAll('.zoomDataObject')
            .data(data.filter((d) => d.start <= ts && (d.end == null || d.end >= ts))
                        .map((obj) => {
                            obj.vis = (obj.isSubtype && mainVis.isSubtypeSampled(obj.type)) || (!obj.isSubtype && mainVis.isTypeSampled(obj.type));
                            return obj;
                        })
                        .sort((a, b) => a.start - b.start),
                (d) => d.id)
            .order()
            .join(
                (enter) => {
                    let enterGroup = enter.append('g')
                        .attr('class', 'zoomDataObject')
                        .style('visibility', (d) => d.vis ? 'inherit' : 'hidden');
                    enterGroup.append('rect')
                        .attr('class', (d) => `block-${d.trimType}`)
                        .attr('x', (d) => xScale(d.x))
                        .attr('y', (d) => yScale(d.y))
                        .attr('width', (d) => xScale(d.width))
                        .attr('height', (d) => yScale(d.height))
                        .style('fill', (d) => expandedTypes.has(d.type) && !d.isSubtype ? 'url(#crosshatch)' : d.colour)
                        // .style('opacity', (d) => expandedTypes.has(d.type) && !d.isSubtype ? 0.3 : 1.0)
                        .style('pointer-events', 'visible')
                        .on('mouseover', function(e, d) {
                            if (!expandedTypes.has(d.type) || d.isSubtype) {
                                memLayout.selectAll(`.block-${d.trimType}`)
                                    .transition()
                                    .style('fill', d3.color(d.colour).darker(2));
                            }

                            let type = trimLongTypeName(d.type, 65);
                            const context = canvas.getContext('2d');
                            context.font = '10px monospace';
                            const textWidth = context.measureText(type).width + 20;

                            let typeHintSvg = d3.select('#memLayoutDiv')
                                    .append('svg')
                                    .attr('class', 'typeHint')
                                    .attr('data-type', type)
                                    // .attr('x', d3.pointer(e)[0])
                                    // .attr('y', d3.pointer(e)[1])
                                    // .attr('x', e.clientX)
                                    // .attr('y', e.clientY - 15)
                                    .style('left', `${e.clientX}px`)
                                    .style('top', `${e.clientY - 15}px`)
                                    .style('position', 'fixed')
                                    .style('width', `${textWidth}px`)
                                    .style('height', '20px')
                                    // .style('transform', `translate(${x}, ${y})`)
                                    .style('overflow', 'visible');
                            typeHintSvg.append('rect')
                                    .attr('x', 0)
                                    .attr('y', 0)
                                    .attr('width', textWidth)
                                    .attr('height', 14)
                                    .style('fill', 'white')
                                    .style('pointer-events', 'none');
                                    
                            typeHintSvg.append('text')
                                    .attr('x', 1)
                                    .attr('y', 9)
                                    .attr('font-family', 'monospace')
                                    .style('font-size', '10px')
                                    .style('pointer-events', 'none')
                                    .text(type);
                        })
                        .on('mousemove', function(e, d) {
                            let typeHint = d3.select('#memLayoutDiv').select('.typeHint');
                            typeHint.style('left', `${e.clientX}px`)
                                .style('top', `${e.clientY - 15}px`);
                        })
                        .on('mouseout', function(e, d) {
                            d3.select('#memLayoutDiv').selectAll('.typeHint')
                                .remove();
                            memLayout.selectAll(`.block-${d.trimType}`)
                                .transition()
                                .style('fill', (d) => expandedTypes.has(d.type) && !d.isSubtype ? 'url(#crosshatch)' : d.colour);
                        })
                        .on('click', function(e, d) {
                            if ((e.ctrlKey || e.metaKey) && !e.altKey) {
                                let textGroup = d3.select('body')
                                    .append('div')
                                    .attr('id', 'statsPopup')
                                    .attr('class', 'popup')
                                    .style('visibility', 'inherit')
                                    .style('text-align', 'center')
                                    .style('height', `${Math.min((1 + statsTracker.getTypes().length) * 19, 400)}px`);
                                textGroup.call(typeInfoPopup().y('10%')
                                                .type(d.type)
                                                .lineSpace(15)
                                                .maxChars(30)
                                                .width('47%')
                                                .height('100%')
                                                .clKind('Single')
                                                .stats(statsTracker));
                                textGroup.call(typeInfoPopup().y('10%')
                                                .type(d.type)
                                                .lineSpace(15)
                                                .maxChars(30)
                                                .width('47%')
                                                .height('100%')
                                                .clKind('Double')
                                                .stats(statsTracker));
                                textGroup.append('i')
                                    .attr('class', 'fa fa-close')
                                    .style('position', 'absolute')
                                    .style('top', '3%')
                                    .style('right', '1%')
                                    .style('font-size', '24px')
                                    .style('color', '#ccc')
                                    .style('cursor', 'pointer')
                                    .on('click', function() {
                                        d3.select('#statsPopup').remove();
                                    });
                            }
                            else if (e.altKey && fields[d.type.replaceAll(' ', '')] && !(e.ctrlKey || e.metaKey)) {
                                memLayout.selectAll('.typeHint')
                                    .remove();
                                toggleExpand(d.type);
                                mainVis.getLegend().redraw();
                            }
                        });
                    enterGroup.append('line')
                        .attr('x1', (d) => xScale(d.x))
                        .attr('y1', (d) => yScale(d.y) - yScale(yScale.domain()[0]-1))
                        .attr('x2', (d) => xScale(d.x))
                        .attr('y2', (d) => yScale(d.y) - yScale(yScale.domain()[0]-1) + yScale(yScale.domain()[0]-d.height))
                        .style('visibility', (d) => d.isBegin ? 'inherit' : 'hidden')
                        .style('stroke', 'black')
                        .style('stroke-width', '1px');
                    enterGroup.append('line')
                        .attr('x1', (d) => xScale(d.x + d.width))
                        .attr('y1', (d) => yScale(d.y) - yScale(yScale.domain()[0]-1))
                        .attr('x2', (d) => xScale(d.x + d.width))
                        .attr('y2', (d) => yScale(d.y) - yScale(yScale.domain()[0]-1) + yScale(yScale.domain()[0]-d.height))
                        .style('visibility', (d) => d.isEnd ? 'inherit' : 'hidden')
                        .style('stroke', 'black')
                        .style('stroke-width', '1px');
                },
                (update) => {
                    update.style('visibility', (d) => d.vis ? 'inherit' : 'hidden');
                    update.selectAll('rect')
                        .transition()
                        .style('fill', (d) => expandedTypes.has(d.type) && !d.isSubtype ? 'url(#crosshatch)' : d.colour);
                },
                (exit) => exit.remove()
            );
    }

    function toggleExpand(tp) {
        if (!expandedTypes.has(tp)) {
            expandedTypes.add(tp);
        }
        else {
            expandedTypes.delete(tp);
        }
        data = splitBlocks(objects, startAddr, pageSize, cachelineSize);
        addElementsByTimestamp(prevTs);
        cacheSetLayout.refreshExpandedTypes();
    }

    function splitBlocks(objects, startAddr, pageSize, cachelineSize) {
        const pageBlocks = [];
        // const startAddr = objects[0].alloc_addr - (objects[0].alloc_addr % cachelineSize);
        
        // console.log('Here is the start addr of the page:');
        // console.log(startAddr);
        for (let i = 0; i < objects.length; i++) {
            let noSpacesType = objects[i].type.replaceAll(' ', '');
            // TODO the following does not work if an object can span more than one page boundary
            let startDiff = (objects[i].size < sizeOfType[objects[i].type] && objects[i].addr == startAddr) ? sizeOfType[objects[i].type] - objects[i].size : 0;
            let objsToAdd = [objects[i]].concat(expandedTypes.has(objects[i].type) && fields[noSpacesType] ? fields[noSpacesType].map(
                (subtype) => ({type: subtype.subtype, addr: objects[i].addr + subtype.offset - startDiff,
                    allocTs: objects[i].allocTs, freeTs: objects[i].freeTs, isDup: (objects[i].isDup || startDiff > 0),
                    size: subtype.size, isSubtype: true})) : []);
            // console.log(objsToAdd);
            for (let obj of objsToAdd) {
                // console.log(obj);
                if (obj.addr + obj.size <= startAddr) {
                    console.log('SKIPPED');
                    console.log(`${obj.addr} + ${obj.size} <= ${startAddr}`);
                    console.log(obj);
                    console.log(`Actual size of type: ${sizeOfType[objects[i].type]}`);
                    console.log(`Size of obj: ${objects[i].size}`);
                    console.log(`Start diff: ${startDiff}`);
                    continue;
                }
                else if (obj.addr < startAddr) {
                    obj.size -= startAddr - obj.addr;
                    obj.addr = startAddr;
                    obj.isDup = true;
                }

                let trimType = obj.type.replace(/[^a-zA-Z]+/g, '');
                let col = colourOfType[obj.type];
                const normAddr = (obj.addr - startAddr);
                const begin = normAddr % cachelineSize;
                let startBlock = {  type: obj.type,
                                    trimType: trimType,
                                    id: obj.type + toString(obj.addr) + toString(obj.allocTs) + '0',
                                    x: begin,
                                    y: Math.floor(normAddr / cachelineSize),
                                    width: Math.min(obj.size, cachelineSize - begin),
                                    height: 1,
                                    start: obj.allocTs,
                                    end: obj.freeTs,
                                    colour: col,
                                    isBegin: !obj.isDup,
                                    isSubtype: obj.isSubtype
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
                                        id: obj.type + toString(obj.addr) + toString(obj.allocTs) + '1',
                                        x: 0,
                                        y: Math.floor(normAddr / cachelineSize) + 1,
                                        width: cachelineSize,
                                        height: midHeight,
                                        start: obj.allocTs,
                                        end: obj.freeTs,
                                        colour: col,
                                        isStart: false,
                                        isEnd: false,
                                        isSubtype: obj.isSubtype
                                        });
                    }
                    let leftover = (obj.size - cachelineSize + begin) % cachelineSize;
                    if (midHeight != pageRem && leftover > 0) {
                        pageBlocks.push({type: obj.type,
                                        trimType: trimType,
                                        id: obj.type + toString(obj.addr) + toString(obj.allocTs) + '2',
                                        x: 0,
                                        y: Math.floor(normAddr / cachelineSize) + midHeight + 1,
                                        width: leftover,
                                        height: 1,
                                        start: obj.allocTs,
                                        end: obj.freeTs,
                                        colour: col,
                                        isStart: false,
                                        isEnd: true,
                                        isSubtype: obj.isSubtype
                                        });
                    }
                }
                else {
                    startBlock.isEnd = true;
                }
                pageBlocks.push(startBlock);
            }
        }
        return pageBlocks;
    }

    drawObjectLayout.toggleExpandType = function(tp) {
        toggleExpand(tp);
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
        if (!arguments) return actualHeight;
        actualHeight = val;
        return drawObjectLayout;
    }

    drawObjectLayout.stats = function(val) {
        if (!arguments) return statsTracker;
        statsTracker = val;
        return drawObjectLayout;
    }

    drawObjectLayout.fields = function(val) {
        if (!arguments) return fields;
        fields = val;
        return drawObjectLayout;
    }

    drawObjectLayout.perf = function(val) {
        if (!arguments) return perf;
        perf = val;
        return drawObjectLayout;
    }

    drawObjectLayout.expandedTypes = function(val) {
        if (!arguments) return expandedTypes;
        expandedTypes = val;
        return drawObjectLayout;
    }
    
    drawObjectLayout.cacheSetLayout = function(val) {
        if (!arguments) return cacheSetLayout;
        cacheSetLayout = val;
        return drawObjectLayout;
    }

    drawObjectLayout.perfVisible = function(on) {
        if (!arguments) return perfVis;
        perfVis = on;
        perfVisible();
        return drawObjectLayout;
    }

    return drawObjectLayout;
}

export default objectLayout;