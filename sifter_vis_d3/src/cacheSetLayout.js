import * as d3 from 'd3';
import { getCurrTime } from './timeGraphLayout.js';

export let instantaneous = false;
let objects = [];
let cacheSize, associativity, cachelineSize = undefined;

function drawToggle() {
    d3.select("#toggleGroup").remove();

    let toggleGroup = d3.select("#cacheSetBox")
        .append("svg")
        .attr("id", "toggleGroup")
        .style("width", "100%")
        .style("height", "10%")
        .append("g")
        .style("transform", "translate(33%, 50%)");
    
    toggleGroup.append("rect")
        .style("width", "24px")
        .style("height", "5px")
        .style("fill", "#ddd");
    
    toggleGroup.append("circle")
        .attr("class", "toggle")
        .attr("cx", 0)
        .attr("cy", 2.5)
        .attr("r", 10)
        .style("fill", "#ccc")
        .on("click", function() {
            instantaneous = !instantaneous;
            if (instantaneous) {
                d3.select(this)
                    .transition()
                    .ease(d3.easeCubicOut)
                    .attr("cx", 21);
                drawLayout(getCurrTime());
            }
            else {
                d3.select(this)
                    .transition()
                    .ease(d3.easeCubicOut)
                    .attr("cx", 0);
                drawLayout();
            }
        });

    toggleGroup.append("text")
        .attr("x", -70)
        .attr("y", 5)
        .attr("font-family", "monospace")
        .text("Summary");

    toggleGroup.append("text")
        .attr("x", 40)
        .attr("y", 5)
        .attr("font-family", "monospace")
        .text("Instantaneous");
}

function getSquaresData(objs) {
    const width = 270;
    let numCacheSets = Math.ceil(cacheSize / (associativity*cachelineSize));
    let setsPerRow = Math.floor(Math.sqrt(numCacheSets));
    let squareSize = Math.floor(width / setsPerRow);

    let setMap = objs.map(obj => ({cacheline: Math.floor(obj.addr / cachelineSize) % numCacheSets,
        spread: 1 + Math.max(Math.ceil((obj.size - (cachelineSize - (obj.addr % cachelineSize))) / cachelineSize), 0)}));
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

export function drawLayout(ts=-1) {
    let squaresData = getSquaresData(instantaneous ? objects.filter(d => d.allocTs <= ts && d.freeTs >= ts) : objects,
        cacheSize, associativity, cachelineSize);
    const heatScale = d3.scaleLinear().domain([0, Math.max(1, Math.max(...squaresData.map(d => d.freq ? d.freq : 0)))]).range(["white", "red"]);

    let cacheLayout = d3.select("#cacheLayout");

    if (cacheLayout.empty()) {
        cacheLayout = d3.select("#cacheSetBox")
            .insert("svg", "#toggleGroup")
            .attr("id", "cacheLayout")
            .style("width", "100%")
            .style("height", "60%");
    }

    cacheLayout.selectAll("rect")
        .data(squaresData, d => (d.x, d.y))
        .join(enter => enter.append("rect")
            .attr("x", d => d.x)
            .attr("y", d => d.y)
            .attr("width", d => d.size)
            .attr("height", d => d.size)
            .style("stroke", "#ccc")
            .style("stroke-width", 0.5)
            .style("fill", function(d, i) {
                return heatScale(d.freq ? d.freq : 0);
            }),
            update => update.style("fill", function(d, i) {
                return heatScale(d.freq ? d.freq : 0);
            }),
            exit => exit.remove()
        );
        // .style("transform", "translate(50px, 85px)");
}

function refreshLayout(cs, assoc, cls) {
    cacheSize = cs;
    associativity = assoc;
    cachelineSize = cls;
    d3.select("#cacheLayout").remove();
    drawLayout(instantaneous ? getCurrTime() : -1);
    // drawToggle();
}

function cacheSetLayout(objs, cachelineSize=64, ...cacheInfo) {
    objects = objs;
    console.log(objects);

    let cacheSetTabs = d3.select("#visPanels")
        .append("div")
        .attr("id", "cacheSetBox")
        .style("display", "flex")
        .style("flex-direction", "column")
        .style("align-items", "flex-start")
        .style("position", "relative")
        .style("left", "30px")
        .style("top", "40px")
        .style("grid-column", 3)
        .style("grid-row", 1)
        .style("width", "300px")
        .style("height", "460px")
        .append("div")
        .attr("id", "cacheSetTabs")
        .style("display", "flex")
        .style("flex-direction", "row")
        .style("width", "100%")
        .style("height", "10%");
        // .style("align-items", "flex-start");

    cacheSetTabs.selectAll("svg")
        .data(cacheInfo)
        .enter()
        .append("svg")
        .attr("class", "cacheTab")
        .style("width", "45px")
        .style("height", "30px")
        // .style("width", "40px")
        // .style("height", "25px")
        .style("background-color", "white")
        .style("border", "1px solid #ccc")
        .style("border-top-left-radius", (d, i) => i == 0 ? "7px" : "0px")
        .style("border-bottom-left-radius", (d, i) => i == 0 ? "7px" : "0px")
        .style("border-top-right-radius", (d, i) => i == cacheInfo.length - 1 ? "7px" : "0px")
        .style("border-bottom-right-radius", (d, i) => i == cacheInfo.length - 1 ? "7px" : "0px")
        .on("click", function(e, d) {
            refreshLayout(d.size, d.associativity, cachelineSize); // TODO: make sure variables like "cachelineSize" are not overloaded
        })
        .on("mouseover", function() {
            d3.select(this)
                .transition()
                .style("background-color", "#ccc");
        })
        .on("mouseout", function() {
            d3.select(this)
                .transition()
                .style("background-color", "white");
        })
        .append("text")
        .attr("text-anchor", "middle")
        .attr("x", "50%")
        .attr("y", "62%")
        .attr("font-family", "monospace")
        .style("alignment-baseline", "middle")
        .text((d, i) => `L${i+1}`);

        drawToggle();
        refreshLayout(cacheInfo[0].size, cacheInfo[0].associativity, cachelineSize);
}

export default cacheSetLayout;