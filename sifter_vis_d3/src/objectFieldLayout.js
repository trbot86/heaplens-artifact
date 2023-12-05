import * as d3 from 'd3';
import { colourOfType } from './vis.js';

/* ISSUES 
        - Allocations without matching frees are not shown */

let memLayout, data, xScale, yScale, pageSize = undefined;

export function addElementsByTimestamp(ts) {
    memLayout.selectAll("rect")
        .data(data.filter((d) => d.start <= ts && d.end >= ts),
            (d) => d.id)
        .join(
            (enter) => enter.append("rect")
                    .attr("x", d => xScale(d.x))
                    .attr("y", d => yScale(d.y) - yScale(yScale.domain()[0]-1))
                    .attr("width", d => xScale(d.width))
                    .attr("height", d => yScale(yScale.domain()[0]-d.height))
                    .attr("transform", "translate(30, 40)")
                    .attr("fill", d => d.colour),
            (update) => undefined,
            (exit) => exit.remove()
        );
}

function splitBlocks(objects, startPage, pageSize, cachelineSize) {
    const pageBlocks = [];
    const startAddr = startPage * pageSize;
    // const startAddr = objects[0].alloc_addr - (objects[0].alloc_addr % cachelineSize);
    
    for (let i = 0; i < objects.length; i++) {
        let obj = objects[i];
        let col = colourOfType[obj.type];
        const normAddr = (obj.addr - startAddr);
        const begin = normAddr % cachelineSize;
        pageBlocks.push({id: i*3,
                        x: begin,
                        y: Math.floor(normAddr / cachelineSize),
                        width: Math.min(obj.size, cachelineSize - begin),
                        height: 1,
                        start: obj.allocTs,
                        end: obj.freeTs,
                        colour: col
                        });
        if (obj.size > cachelineSize - begin) {
            // let midHeight = Math.floor(Math.min(obj.alloc_size - cachelineSize + begin,
            //                                     pageSize - (obj.alloc_addr % pageSize) + cachelineSize - begin) / cachelineSize);
            let midHeight = Math.floor((obj.size - cachelineSize + begin) / cachelineSize);
            let pageRem = Math.floor((pageSize - (obj.addr % pageSize) + cachelineSize - begin) / cachelineSize) - 1;
            
            if (midHeight > pageRem) midHeight = pageRem;
            
            if (obj.size >= 2*cachelineSize - begin) {
                pageBlocks.push({id: i*3 + 1,
                                x: 0,
                                y: Math.floor(normAddr / cachelineSize) + midHeight,
                                width: cachelineSize,
                                height: midHeight,
                                start: obj.allocTs,
                                end: obj.freeTs,
                                colour: col
                                });
            }
            let leftover = (obj.size - cachelineSize + begin) % cachelineSize;
            if (midHeight != pageRem && leftover > 0) {
                pageBlocks.push({id: i*3 + 2,
                                x: 0,
                                y: Math.floor(normAddr / cachelineSize) + midHeight + 1,
                                width: leftover,
                                height: 1,
                                start: obj.allocTs,
                                end: obj.freeTs,
                                colour: col
                                });
            }
        }
    }
    return pageBlocks;
}

function objectLayout(objects, startAddr, initTs=0, pageSize=4096, cachelineSize=64) {
    d3.select("#memLayout").remove();

    memLayout = d3.select("#visPanels")
        .append("svg")
        .attr("id", "memLayout")
        .style("width", "80%")
        .style("height", "100%")
        .style("grid-column", 2)
        .style("grid-row", 1)
        .style("justify-self", "end");

    let memLayoutAxes = memLayout.append("g")
        .attr("id", "memLayoutAxes");
    memLayoutAxes.append("g")
        .attr("id", "memLayoutXAxis")
        .style("transform", "translate(30px, 330px)");
    memLayoutAxes.append("g")
        .attr("id", "memLayoutYAxis")
        .style("transform", "translate(30px, 40px)");

    xScale = d3.scaleLinear().domain([0, cachelineSize]).range([0, 290]);
    let xAxis = d3.axisBottom(xScale);
    xAxis.tickValues(d3.range(0, cachelineSize+1, 8)).tickFormat(d3.format("d"));

    yScale = d3.scaleLinear().domain([cachelineSize, 0]).range([0, 290]);
    let yAxis = d3.axisLeft(yScale);
    yAxis.tickValues(d3.range(0, cachelineSize+1, 8)).tickFormat(d3.format("d"));

    d3.select("#memLayoutXAxis").call(xAxis);
    d3.select("#memLayoutYAxis").call(yAxis);

    data = splitBlocks(objects, startAddr, pageSize, cachelineSize);
    addElementsByTimestamp(initTs);
}

export default objectLayout;