import * as d3 from 'd3';
import { mainVis } from './dbloader.js';

const LINE_SEP = 20;

function legendLayout() {
    let legendGroup = undefined,
        types = [];

    function drawLayout(selection) {
        types = Object.entries(selection.datum()).map((elem) => ({type: elem[0], col: elem[1]}));

        selection.append('div')
            .style('overflow', 'hidden')
            .append('input')
            .attr('type', 'text')
            .attr('placeholder', 'Filter types')
            .attr('x', LINE_SEP)
            .attr('y', 0)
            .on('input', function() {
                console.log('test');
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
                    
                    group.append('rect')
                        .attr('x', 1.4*LINE_SEP)
                        .attr('y', (d, i) => i*(LINE_SEP))
                        .attr('width', 0.8*LINE_SEP)
                        .attr('height', 0.8*LINE_SEP)
                        .style('fill', (d) => d.col);

                    group.append('text')
                        .attr('x', 2.6*LINE_SEP)
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
                        .attr('data-type', (d) => d)
                        .style('position', 'absolute')
                        .style('left', '0px')
                        .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`)
                        .property('checked', true)
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