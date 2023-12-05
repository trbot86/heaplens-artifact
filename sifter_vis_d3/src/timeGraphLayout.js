import * as d3 from 'd3';
import { colourOfType } from "./vis.js";
import { addElementsByTimestamp } from './objectFieldLayout.js';
import { updatePagesByTimestamp } from './pageLayout.js';
import { instantaneous, drawLayout } from './cacheSetLayout.js';

const LAYOUT_TRANSLATE_X = 70;
const LAYOUT_TRANSLATE_Y = 20;
const tabPosition = {x: 70, y: 310};
let xScale, xAxis = undefined;

export function getCurrTime() {
    return xScale.invert(tabPosition.x - LAYOUT_TRANSLATE_X);
}

function updateTab() {
    let newX = Math.max(Math.min(tabPosition.x,
        xScale.range()[1]+LAYOUT_TRANSLATE_X), LAYOUT_TRANSLATE_X);
    // TODO: Should be able to group these selections somehow
    d3.select("#bottomTab")
        .style("transform", d => `translate(${newX}px, ${d.y}px)`);
    d3.select("#topTab")
        .style("transform", d => `translate(${newX}px, ${d.y-300}px)  rotate(0.5turn)`);
    d3.select("#tabLine")
        .style("transform", d => `translate(${newX}px, 10px)`);
}

function handleDrag(e) {
    // console.log(e);
    // tabPosition.x += e.dx;
    e.subject.x = e.x;
    updateTab();
    let ts = getCurrTime();
    addElementsByTimestamp(ts);
    updatePagesByTimestamp(ts);
    if (instantaneous) drawLayout(ts);
}

function slider() {
    const colour = "rgb(148, 148, 148)";
    let tab = d3.symbol()
        .type(d3.symbolTriangle)
        .size(60);

    let tabGroup = d3.select("#graphLayout")
        .append("g")
        // .datum(tabPosition)
        .attr("id", "dragTab");
        // .attr("transform", d => `translate(${d.x}, ${d.y})`);

    tabGroup.append("line")
        .datum(tabPosition)
        .attr("id", "tabLine")
        .style("stroke", colour)
        .style("stroke-width", 2)
        .attr("x1", 0)
        .attr("y1", 0)
        .attr("x2", 0)
        .attr("y2", 300)
        .style("transform", d => `translate(${d.x}px, 10px)`);

    tabGroup.append("path")
        .datum(tabPosition)
        .attr("id", "bottomTab")
        .attr("d", tab)
        .attr("stroke", colour)
        .attr("fill", colour)
        .style("transform", d => `translate(${d.x}px, ${d.y}px)`)
        .call(d3.drag()
            .on("drag", handleDrag));

    tabGroup.append("path")
        .datum(tabPosition)
        .attr("id", "topTab")
        .attr("d", tab)
        .attr("stroke", colour)
        .attr("fill", colour)
        .style("transform", d => `translate(${d.x}px, ${d.y-300}px) rotate(0.5turn)`)
        .call(d3.drag()
            .on("drag", handleDrag));
}

function allocsOverTimeLayout(objects) {
    const allocTimes = objects.map(obj => obj.allocTs);
    const freeTimes = objects.map(obj => obj.freeTs == null ? 0 : obj.freeTs);
    const minTime = Math.min(...allocTimes);
    const maxTime = Math.max(Math.max(...allocTimes), Math.max(...freeTimes));
    const endBuff = Math.floor((maxTime - minTime)*0.03);
    const sizes = objects.map(obj => obj.size);

    let graphLayout = d3.select("#visPanels")
        .append("svg")
        .attr("id", "graphLayout")
        .style("width", "100%")
        .style("height", "100%")
        .style("grid-column", "1 / 3")
        .style("grid-row", 2)
        .style("justify-self", "end");

    let graphLayoutAxes = graphLayout.append("g")
        .attr("id", "graphLayoutAxes");
    graphLayoutAxes.append("g")
        .attr("id", "graphLayoutXAxis")
        .style("transform", `translate(${LAYOUT_TRANSLATE_X}px, 300px)`);
    graphLayoutAxes.append("g")
        .attr("id", "graphLayoutYAxis")
        .style("transform", `translate(${LAYOUT_TRANSLATE_X}px, ${LAYOUT_TRANSLATE_Y}px)`);

    // console.log(Math.max);
    
    xScale = d3.scaleLinear().domain([minTime-endBuff, maxTime+endBuff]).range([0, 800]);
    xAxis = d3.axisBottom(xScale).tickSize(0).tickValues([]);

    const maxY = Math.ceil(1.1*Math.max(...sizes));
    let yScale = d3.scaleLinear().domain([maxY, 0]).range([0, 280]);
    let yAxis = d3.axisLeft(yScale);
    yAxis.tickValues(d3.range(0, maxY+1, 
        Math.pow(2, Math.floor(Math.log2(0.1*maxY)))
        )).tickFormat(d3.format("d"));

    d3.select("#graphLayoutXAxis").call(xAxis);
    d3.select("#graphLayoutYAxis").call(yAxis);

    slider();
    
    const events = {};
    const lines = {};

    let objects_by_type = objects.reduce((acc, curr) => {
        acc[curr.type] ? acc[curr.type].push(curr) : acc[curr.type] = [curr];
        return acc;
    }, {});

    for (let type of Object.keys(objects_by_type)) {
        events[type] = [];
        for (let obj of objects_by_type[type]) {
            events[type].push([obj.allocTs, obj.size, true]);
            if (obj.freeTs != null) {
                events[type].push([obj.freeTs, obj.size, false]);
            }
        }
        events[type].sort((a, b) => a[0] - b[0]);

        lines[type] = [[minTime-endBuff, 0]];
        let sizeSum = 0;
        for (let event of events[type]) {
            if (event[2]) {
                lines[type].push([event[0], sizeSum]);
                sizeSum += event[1];
                lines[type].push([event[0], sizeSum]);
            }
            else {
                lines[type].push([event[0], sizeSum]);
                sizeSum -= event[1];
                lines[type].push([event[0], sizeSum]);
            }
        }
        lines[type].push([maxTime+endBuff, sizeSum]);

        d3.select("#graphLayout")
            .append("path")
            .datum(lines[type])
            .attr("class", "line")
            .attr("fill", "none")
            .attr("stroke", colourOfType[type])
            .attr("stroke-width", 2)
            .attr("transform", `translate(${LAYOUT_TRANSLATE_X}, ${LAYOUT_TRANSLATE_Y})`)
            .attr("d", d3.line()
                        .x(d => xScale(d[0]))
                        .y(d => yScale(d[1]))
            );
    }

    // Return timestamp corresponding to initial tab position
    return getCurrTime();
}

export default allocsOverTimeLayout;