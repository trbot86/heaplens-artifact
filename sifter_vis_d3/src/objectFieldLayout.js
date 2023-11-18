import * as d3 from 'd3';
import { CACHELINE_SIZE, colour_of_type } from './vis.js';

/* ISSUES 
        - Allocations without matching frees are not shown */

let memLayout, data, xScale, yScale = undefined;

export function addElementsByTimestamp(ts) {
    memLayout.selectAll("rect")
        .data(data.filter(d => d.start <= ts && d.end >= ts),
            d => (d.x, d.y))
        .join(
            enter => enter.append("rect")
                    .attr("x", d => xScale(d.x))
                    .attr("y", d => yScale(d.y) - yScale(yScale.domain()[0]-1))
                    .attr("width", d => xScale(d.width))
                    .attr("height", d => yScale(yScale.domain()[0]-d.height))
                    .attr("transform", "translate(30, 40)")
                    .attr("fill", d => d.colour),
            update => undefined,
            exit => exit.remove()
        );
}

function splitBlocks(objects, startAddr) {
    const pageBlocks = [];
    // const startAddr = objects[0].alloc_addr - (objects[0].alloc_addr % CACHELINE_SIZE);
    
    for (let i = 0; i < objects.length; i++) {
        let obj = objects[i];
        let col = colour_of_type[obj.alloc_type];
        const normAddr = (obj.alloc_addr - startAddr);
        const begin = normAddr % CACHELINE_SIZE;
        pageBlocks.push({x: begin,
                        y: Math.floor(normAddr / CACHELINE_SIZE),
                        width: Math.min(obj.alloc_size, CACHELINE_SIZE - begin),
                        height: 1,
                        start: obj.alloc_timestamp,
                        end: obj.free_timestamp,
                        colour: col
                        });
        if (obj.alloc_size > CACHELINE_SIZE - begin) {
            let midHeight = Math.floor((obj.alloc_size - CACHELINE_SIZE + begin) / CACHELINE_SIZE);
            if (obj.alloc_size >= 2*CACHELINE_SIZE - begin) {
                pageBlocks.push({x: 0,
                                y: Math.floor(normAddr / CACHELINE_SIZE) + midHeight,
                                width: CACHELINE_SIZE,
                                height: midHeight,
                                start: obj.alloc_timestamp,
                                end: obj.free_timestamp,
                                colour: col
                                });
            }
            let leftover = (obj.alloc_size - CACHELINE_SIZE + begin) % CACHELINE_SIZE;
            if (leftover > 0) {
                pageBlocks.push({x: 0,
                                y: Math.floor(normAddr / CACHELINE_SIZE) + midHeight + 1,
                                width: leftover,
                                height: 1,
                                start: obj.alloc_timestamp,
                                end: obj.free_timestamp,
                                colour: col
                                });
            }
        }
    }
    return pageBlocks;
}

function objectLayout(objects, startAddr, initTs = 0) {
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

    xScale = d3.scaleLinear().domain([0, CACHELINE_SIZE]).range([0, 290]);
    let xAxis = d3.axisBottom(xScale);
    xAxis.tickValues(d3.range(0, CACHELINE_SIZE+1, 8)).tickFormat(d3.format("d"));

    yScale = d3.scaleLinear().domain([CACHELINE_SIZE, 0]).range([0, 290]);
    let yAxis = d3.axisLeft(yScale);
    yAxis.tickValues(d3.range(0, CACHELINE_SIZE+1, 8)).tickFormat(d3.format("d"));

    d3.select("#memLayoutXAxis").call(xAxis);
    d3.select("#memLayoutYAxis").call(yAxis);

    data = splitBlocks(objects, startAddr);
    addElementsByTimestamp(initTs);
}

export default objectLayout;