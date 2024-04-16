import * as d3 from 'd3';
import { colourOfType } from './vis.js';
import objectLayout from './objectFieldLayout.js';
import { getCurrTime } from './dbloader.js';
import { trimString } from './statsTracker.js';

let pageSize = 4096;
let pageRectHeight = 32;
let pageRectWidth = 500;
let pageRectBorder = 2;

let data, pageScale, objLayout, statsTracker = undefined;
let expandedTypes = [];

const   SORT_PAGE_NUM = 0,
        SORT_CLUSTER = 1;
let sorting = 0;

export function updatePagesByTimestamp(ts) {
    objLayout.addElementsByTimestamp(ts);
    const elements = d3.select('#pageLayout')
        .selectAll('.pageGroup')
        .data(Object.entries(data), (d) => parseInt(d[0]))
        .selectAll('.dataObject')
        .data((d) => d[1].events.filter((obj) => obj.allocTs <= ts && (obj.freeTs == null || obj.freeTs >= ts)),
            (d) => d.ID);
    
    const enterElements = elements.enter()
        .insert('g', ':first-child')
        .attr('class', 'dataObject');
    enterElements.append('rect')
        .attr('x', (d) => pageScale(d.addr % pageSize))
        .attr('y', 0)
        .attr('width', (d) => pageScale(Math.min(d.size, pageSize - (d.addr % pageSize))))
        .attr('height', pageRectHeight)
        // .style('stroke', 'black')
        // .style('stroke-width', '1px')
        .style('fill', (d) => colourOfType[d.type]);
    enterElements.append('line')
        .attr('x1', (d) => pageScale(d.addr % pageSize))
        .attr('y1', 0)
        .attr('x2', (d) => pageScale(d.addr % pageSize))
        .attr('y2', pageRectHeight)
        .style('stroke', 'black');
    enterElements.append('line')
        .attr('x1', (d) => pageScale((d.addr % pageSize) + Math.min(d.size, pageSize - (d.addr % pageSize))))
        .attr('y1', 0)
        .attr('x2', (d) => pageScale((d.addr % pageSize) + Math.min(d.size, pageSize - (d.addr % pageSize))))
        .attr('y2', pageRectHeight)
        .style('stroke', 'black');

    elements.exit().remove();
}

function refreshObjectLayout(objects, startAddr, initTs, fields, pageSize=4096, cachelineSize=64,
                            x=30, y=40, width=290, height=290) {
    d3.select('#memLayout').remove();
    let memLayout = d3.select('#visPanels')
        .append('svg')
        .attr('id', 'memLayout')
        .style('width', '100%')
        .style('height', '100%')
        .style('grid-column', 2)
        .style('grid-row', 1)
        .style('overflow', 'visible');

    objLayout = objectLayout()
                    .x(x)
                    .y(y)
                    .width(width)
                    .height(height)
                    .stats(statsTracker)
                    .fields(fields);
    memLayout.datum({objects: objects,
                    startAddr: startAddr,
                    initTs: initTs,
                    pageSize: pageSize,
                    cachelineSize: cachelineSize})
        .call(objLayout);
}

function pageLayout(pages, clusters, features, initTs, st, fields, pgsz=4096, cachelineSize=64) {
    pageSize = pgsz;
    statsTracker = st;

    let subtypes = Array.from(new Set(Object.values(fields).reduce((acc, curr) => acc.concat(curr), []).map((obj) => obj.subtype)))
    const colScale = d3.scaleSequential()
                        .domain([0, subtypes.length])
                        .interpolator(d3.interpolateTurbo);
    let col = 0;
    for (let type of subtypes) {
        if (!colourOfType[type])
            colourOfType[type] = colScale(col);
        col++;
    }

    let layout = d3.select('#visPanels')
        .append('div')
        .attr('id', 'pageLayout')
        .style('width', '100%')
        .style('height', '85%')
        .style('grid-column', 1)
        .style('grid-row', 1)
        .style('justify-self', 'end')
        .style('align-self', 'center')
        .style('position', 'relative')
        .style('overflow-x', 'hidden')
        .style('overflow-y', 'auto')
        .style('top', '40px')
        .style('left', '40px');

    pageScale = d3.scaleLinear().domain([0, pageSize]).range([0, pageRectWidth]);
    data = pages;

    let pageGroups = layout.selectAll('svg')
        .data(Object.entries(pages), d => parseInt(d[0]))
        .enter()
        .append('svg')
        .attr('class', 'pageGroup')
        .attr('data-pagenum', d => parseInt(d[0]))
        .style('width', `${pageRectWidth*1.17}px`)
        .style('height', `${pageRectHeight*1.2}px`);
    
    pageGroups.append('rect')
        .attr('class', 'pageBorder')
        .style('width', `${pageRectWidth}px`)
        .style('height', `${pageRectHeight}px`)
        .style('min-height', `${pageRectHeight}px`)
        .style('stroke-width', pageRectBorder)
        .style('fill', 'black')
        .style('fill-opacity', 0.0)
        .on('click', function() {
            let selPage = this.parentNode.getAttribute('data-pagenum');
            refreshObjectLayout(data[selPage].events, selPage, getCurrTime(), fields, 4096, cachelineSize, '16%', '14%');
        })
        .on('mouseover', function() {
            d3.select(this)
                .transition()
                .style('fill-opacity', 0.3);
        })
        .on('mouseout', function() {
            d3.select(this)
                .transition()
                .style('fill-opacity', 0.0);
        });

    pageGroups.append('text')
        .attr('font-family', 'monospace')
        .attr('x', '87%')
        .attr('y', '37%')
        .style('font-size', '10px')
        .text((d) => `${parseInt(d[0]).toString(16)}`);

    pageGroups.append('text')
        .attr('font-family', 'monospace')
        .attr('x', '87%')
        .attr('y', '63%')
        .style('font-size', '10px')
        .text((d) => `cluster: ${d[1].cluster}`)
        .style('cursor', 'pointer')
        .on('click', function(e, d, i) {
            const featWindow = d3.select('body')
                .append('div')
                .attr('class', 'popup')
                .attr('id', 'featurePopup')
                .style('display', 'block')
                .style('overflow', 'scroll');

            featWindow.append('i')
                .attr('class', 'fa fa-close')
                .style('position', 'absolute')
                .style('top', '3%')
                .style('right', '1%')
                .style('font-size', '24px')
                .style('color', '#ccc')
                .style('cursor', 'pointer')
                .on('click', function() {
                    d3.select('#featurePopup').remove();
                });

            featWindow.selectAll('.featureVector')
                .data(clusters[d[1].cluster].page_num)
                .enter()
                .append('p')
                .attr('class', 'featureVector')
                .style('position', 'absolute')
                .style('left', '10px')
                .style('top', (d2, i) => `calc(3% + ${5 + i*20}px)`)
                .text((d2) => `${trimString(d2, 20)}: ${Object.entries(features[d2])}`);
        });

    const pageNumSet = new Set(Object.keys(pages).map((page) => parseInt(page)));
    const minPage = Math.min(...Object.keys(pages).map((page) => parseInt(page)));
    for (let page of Object.keys(pages)) {
        if (!(pageNumSet.has(parseInt(page) - 1) || parseInt(page) == minPage)) {
            layout.insert('svg', `svg[data-pagenum='${page}']`)
                .style('width', `${pageRectWidth}px`)
                .style('height', `${pageRectHeight / 2}px`)
                .append('text')
                .attr('text-anchor', 'middle')
                .attr('font-family', 'monospace')
                .attr('x', '50%')
                .attr('y', '50%')
                .style('alignment-baseline', 'middle')
                .text('......');
        }
    }

    refreshObjectLayout(Object.values(data)[0].events, Object.keys(data)[0],
                                    initTs, fields, pageSize, cachelineSize, '16%', '14%');
    updatePagesByTimestamp(initTs);
}

export default pageLayout;