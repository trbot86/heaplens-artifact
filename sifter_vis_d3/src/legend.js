import * as d3 from 'd3';
import { colour_of_type } from './vis.js';

const LINE_SEP = 20;

function legendLayout() {
    let legendGroup = d3.select("#visPanels")
        .append("div")
        .attr("id", "legendLayout")
        .style('width', '80%')
        .style('height', '40%')
        .style("grid-column", 3)
        .style("grid-row", 2)
        .style("justify-self", "start")
        .style("position", "relative")
        .style("top", "40%")
        .style("overflow", "auto")
        .append('svg')
        .style('width', '100%')
        .style('height', `${(Object.keys(colour_of_type).length+0.8)*LINE_SEP}px`);

    legendGroup.selectAll("rect")
        .data(Object.values(colour_of_type))
        .enter()
        .append("rect")
        .attr("x", 0)
        .attr("y", (d, i) => i*LINE_SEP)
        .attr("width", 0.8*LINE_SEP)
        .attr("height", 0.8*LINE_SEP)
        .style("fill", d => d);

    legendGroup.selectAll("text")
        .data(Object.keys(colour_of_type))
        .enter()
        .append("text")
        .attr("x", 1.5*LINE_SEP)
        .attr("y", (d, i) => (i+0.67)*LINE_SEP)
        .attr("font-family", "monospace")
        .text(d => d)
        .attr("text-anchor", "left")
        .style("alignment-baseline", "middle");
}

export default legendLayout;