import * as d3 from 'd3';
import { mainVis } from './dbloader.js';
import timegraphSvg from './assets/timegraph_icon.svg';
import memlayoutSvg from './assets/memlayout_icon.svg';

const TIMEBOX_INDENT = 0;
const SAMPLEBOX_INDENT = 25;
const LINE_SEP = 20;
const COL_INDENT = SAMPLEBOX_INDENT + LINE_SEP + 22;
const ICON_SIZE = 1.4*LINE_SEP;


function legendLayout() {
    let legendGroup = undefined,
        types = [];

    function drawLayout(selection) {
        types = Object.entries(selection.datum()).map((elem) => ({type: elem[0], col: elem[1]}));

        const headerBar = selection.append('div')
            .style('overflow', 'hidden')
            .style('position', 'absolute')
            .style('width', '100%')
            .style('height', `${1.2*LINE_SEP}px`);

        headerBar.append('div')
            .style('position', 'absolute')
            .style('left', `${TIMEBOX_INDENT}px`)
            .style('width', `${ICON_SIZE}px`)
            .style('height', `${ICON_SIZE}px`)
            .html(timegraphSvg);

        headerBar.append('div')
            .style('position', 'absolute')
            .style('left', `${SAMPLEBOX_INDENT}px`)
            .style('width', `${ICON_SIZE}px`)
            .style('height', `${ICON_SIZE}px`)
            .html(memlayoutSvg);

        headerBar.append('input')
            .attr('type', 'text')
            .attr('placeholder', 'Filter types')
            .style('position', 'absolute')
            .style('top', `0px`)
            .style('left', `${COL_INDENT}px`)
            .on('input', function() {
                drawTypes(d3.select(this).property('value'));
            });

        legendGroup = selection.append('div')
            .attr('id', 'typesBox')
            .style('width', '450px')
            .style('height', '250px')
            .style('overflow', 'scroll')
            .style('position', 'absolute')
            .style('top', `${1.5*LINE_SEP}px`)
            .append('svg')
            .style('width', '90%')
            .style('height', `${(types.length+0.8)*LINE_SEP}px`);

        drawTypes('');
    }

    function drawTypes(substr) {
        let filteredTypes = types.filter((elem) => elem.type.includes(substr));
        
        legendGroup.selectAll('.legendGroup')
            .data(filteredTypes, (d) => d.type)
            .join(
                (enter) => {
                    let group = enter.append('g')
                        .attr('class', 'legendGroup');
                        // .style('transform', 'translate(17px, 0px)');
                    
                    group.append('rect')
                        .attr('x', COL_INDENT)
                        .attr('y', (d, i) => i*(LINE_SEP))
                        .attr('width', 0.8*LINE_SEP)
                        .attr('height', 0.8*LINE_SEP)
                        .style('fill', (d) => d.col);

                    group.append('text')
                        .attr('x', COL_INDENT + 1.1*LINE_SEP)
                        .attr('y', (d, i) => (i+0.62)*(LINE_SEP))
                        .attr('font-family', 'monospace')
                        .text((d) => d.type)
                        .attr('text-anchor', 'left')
                        .style('alignment-baseline', 'middle');
                },
                (update) => {
                    update.select('rect')
                        .transition()
                        .attr('y', (d, i) => i*(LINE_SEP));
                    update.select('text')
                        .transition()
                        .attr('y', (d, i) => (i+0.62)*(LINE_SEP));
                },
                (exit) => {
                    exit.remove();
                }
            );

        // rectData.enter()
        //     .append('rect')
        //     .attr('x', 1.4*LINE_SEP)
        //     .attr('y', (d, i) => i*(LINE_SEP))
        //     .attr('width', 0.8*LINE_SEP)
        //     .attr('height', 0.8*LINE_SEP)
        //     .style('fill', (d) => d.col);
        // rectData.exit().remove();

        // let textData = legendGroup.selectAll('text')
        //     .data(filteredTypes, (d) => d.type);
        // textData.enter()
        //     .append('text')
        //     .attr('x', 2.6*LINE_SEP)
        //     .attr('y', (d, i) => (i+0.62)*(LINE_SEP))
        //     .attr('font-family', 'monospace')
        //     .text((d) => d.type)
        //     .attr('text-anchor', 'left')
        //     .style('alignment-baseline', 'middle');
        // textData.exit().remove();

        let timeCheckData = d3.select('#typesBox')
            .selectAll('.timeCheckbox')
            .data(filteredTypes, (d) => d.type)
            .join(
                (enter) => {
                    enter.append('input')
                        .attr('class', 'timeCheckbox')
                        .attr('type', 'checkbox')
                        .attr('data-type', (d) => d.type)
                        .style('position', 'absolute')
                        .style('left', `${TIMEBOX_INDENT + (ICON_SIZE / 7)}px`)
                        .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`)
                        .property('checked', (d) => mainVis ? mainVis.getVisOfType(d.type) : true)
                        .on('change', function(event) {
                            mainVis.changeVisOfType(d3.select(this).attr('data-type'));
                        });
                },
                (update) => {
                    update.transition()
                        .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`);
                },
                (exit) => {
                    exit.remove();
                }
            );

        let sampleCheckData = d3.select('#typesBox')
                .selectAll('.sampleCheckbox')
                .data(filteredTypes, (d) => d.type)
                .join(
                    (enter) => {
                        enter.append('input')
                            .attr('class', 'sampleCheckbox')
                            .attr('type', 'checkbox')
                            .attr('data-type', (d) => d.type)
                            .style('position', 'absolute')
                            .style('left', `${SAMPLEBOX_INDENT + (ICON_SIZE / 7)}px`)
                            .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`)
                            .property('checked', (d) => mainVis ? mainVis.isTypeSampled(d.type) : true)
                            .on('change', function(event) {
                                mainVis.changeTypeSampled(d3.select(this).attr('data-type'));
                            });
                    },
                    (update) => {
                        update.transition()
                            .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`);
                    },
                    (exit) => {
                        exit.remove();
                    }
                );

        //     .append('input')
        //     .attr('class', 'timeCheckbox')
        //     .attr('type', 'checkbox')
        //     .attr('data-type', (d) => d)
        //     .style('position', 'absolute')
        //     .style('left', '0px')
        //     .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`)
        //     .property('checked', true)
        //     .on('change', function(event) {
        //         mainVis.changeVisOfType(d3.select(this).attr('data-type'));
        //     });
        // timeCheckData.exit().remove();
    }

    return drawLayout;
}

export default legendLayout;