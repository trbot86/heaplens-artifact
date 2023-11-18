import * as d3 from 'd3';
import { colour_of_type } from './vis.js';
import objectLayout from './objectFieldLayout.js';
import { getCurrTime } from './timeGraphLayout.js';
import { activate } from './objectFieldLayout.js';
import { addElementsByTimestamp } from './objectFieldLayout.js';

let pageSize = 4096;
let pageRectHeight = 32;
let pageRectWidth = 500;
let pageRectBorder = 2;

let data, pageScale = undefined;

export function updatePagesByTimestamp(ts) {
    d3.select("#pageLayout")
        .selectAll("svg")
        .data(Object.entries(data), d => d[0])
        .selectAll(".object")
        .data(d => d[1].filter(obj => obj.alloc_timestamp <= ts && obj.free_timestamp >= ts),
            d => (d.alloc_timestamp, d.alloc_addr))
        .join(enter => enter.insert("rect", ":first-child")
                .attr("class", "object")
                .attr("x", d => pageScale(d.alloc_addr % pageSize))
                .attr("y", 0)
                .attr("width", d => pageScale(d.alloc_size))
                .attr("height", pageRectHeight)
                .style("fill", d => colour_of_type[d.alloc_type]),
            update => undefined,
            exit => exit.remove()
        );
}

function pageLayout(pgsz, pages, initTs) {
    pageSize = pgsz;

    let layout = d3.select("#visPanels")
        .append("div")
        .attr("id", "pageLayout")
        // .style("display", "flex")
        // .style("flex-direction", "column")
        // .style("align-items", "flex-start")
        .style("width", "90%")
        .style("height", "85%")
        .style("grid-column", 1)
        .style("grid-row", 1)
        .style("justify-self", "end")
        .style("align-self", "center")
        .style("position", "relative")
        .style("overflow", "auto")
        .style("top", "40px")
        .style("left", "40px");

    pageScale = d3.scaleLinear().domain([0, pageSize]).range([0, pageRectWidth]);
    data = pages;

    layout.selectAll("svg")
        .data(Object.entries(pages), d => parseInt(d[0]))
        .enter()
        .append("svg")
        .attr("class", "pageGroup")
        .attr("data-pagenum", d => parseInt(d[0]))
        .style("width", `${pageRectWidth*1.1}px`)
        .style("height", `${pageRectHeight*1.2}px`)
        // .style("transform", (d, i) => `translate(70px, ${50 + 1.15*i*pageRectHeight}px)`)
        // .style("position", "relative")
        .append("rect")
        .attr("class", "pageBorder")
        // .attr("x", 0)
        // .attr("y", -pageRectBorder / 2)
        // .attr("y", (d, i) => 1.07*i*pageRectHeight)
        .style("width", `${pageRectWidth}px`)
        .style("height", `${pageRectHeight}px`)
        .style("min-height", `${pageRectHeight}px`)
        .style("stroke-width", pageRectBorder)
        .style("fill", "black")
        .style("fill-opacity", 0.0)
        .on("click", function() {
            let selPage = this.parentNode.getAttribute("data-pagenum");
            objectLayout(data[selPage], selPage, getCurrTime());
        })
        .on("mouseover", function() {
            d3.select(this)
                .transition()
                .style("fill-opacity", 0.3);
        })
        .on("mouseout", function() {
            d3.select(this)
                .transition()
                .style("fill-opacity", 0.0);
        });

    updatePagesByTimestamp(initTs);
    objectLayout(Object.values(data)[0], Object.keys(data)[0], initTs);
}

export default pageLayout;