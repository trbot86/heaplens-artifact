import * as d3 from 'd3';
import { colourOfType } from './vis.js';
import { mainVis } from './dbloader.js';

const LINE_SEP = 20;

function legendLayout() {
    let legendGroup = d3.select("#visPanels")
        .append("div")
        .attr("id", "legendLayout")
        .style('width', '85%')
        .style('height', '40%')
        .style("grid-column", 3)
        .style("grid-row", 2)
        .style("justify-self", "start")
        .style("position", "relative")
        .style("top", "40%")
        .style("overflow", "auto")
        .append('svg')
        .style('width', '90%')
        .style('height', `${(Object.keys(colourOfType).length+0.8)*LINE_SEP}px`)
        .style('position', 'absolute')
        .style('left', '20px');

    legendGroup.selectAll("rect")
        .data(Object.values(colourOfType))
        .enter()
        .append("rect")
        .attr("x", 0.5*LINE_SEP)
        .attr("y", (d, i) => i*LINE_SEP)
        .attr("width", 0.8*LINE_SEP)
        .attr("height", 0.8*LINE_SEP)
        .style("fill", d => d);

    legendGroup.selectAll("text")
        .data(Object.keys(colourOfType))
        .enter()
        .append("text")
        .attr("x", 1.7*LINE_SEP)
        .attr("y", (d, i) => (i+0.62)*LINE_SEP)
        .attr("font-family", "monospace")
        .text(d => d)
        .attr("text-anchor", "left")
        .style("alignment-baseline", "middle");

    d3.select('#legendLayout')
        .selectAll('input')
        .data(Object.keys(colourOfType))
        .enter()
        .append('input')
        .attr('type', 'checkbox')
        .attr('data-type', (d) => d)
        .style('position', 'absolute')
        .style('left', '0px')
        .style('top', (d, i) => `${(i-0.05)*LINE_SEP}px`)
        .property('checked', true)
        .on('change', function(event) {
            mainVis.changeVisOfType(d3.select(this).attr('data-type'));
        });
}

export default legendLayout;