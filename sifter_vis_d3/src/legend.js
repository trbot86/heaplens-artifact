import * as d3 from 'd3';
import { mainVis } from './dbloader.js';
import timegraphSvg from './assets/timegraph_icon.svg';
import memlayoutSvg from './assets/memlayout_icon.svg';
import invertSvg from './assets/invert_icon.svg';
import { colourOfType } from './vis.js';

const TIMEBOX_INDENT = 0;
const SAMPLEBOX_INDENT = 25;
const LINE_SEP = 20;
const COL_INDENT = SAMPLEBOX_INDENT + LINE_SEP + 22;
const ICON_SIZE = 1.4*LINE_SEP;
const LEGEND_HEIGHT = 250;

export function noSpaces(string) {
    return string.replaceAll(' ', '');
}

export function trimLongTypeName(tp, len=28) {
    return tp.length > len ? '...' + tp.substring(tp.length - (len - 3), tp.length) : tp;
}


function legendLayout() {
    let legendGroup = undefined,
        types = [],
        fields = {},
        currFilter = '',
        expandedTypes = undefined,
        typeCounts = undefined,
        sorters = {
            'alph': (a, b) => b.type.localeCompare(a.type),
            'allocs': (a, b) => a.numAllocs - b.numAllocs,
            'pages': (a, b) => a.numPages - b.numPages
        },
        currSorter = {
            mode: 'alph',
            rev: false
        },
        arrow = d3.symbol()
                .type(d3.symbolTriangle)
                .size(40),
        canvas;

    function drawLegendLayout(selection) {
        types = selection.datum().map((elem) => ({  type: elem,
                                                    col: colourOfType[elem],
                                                    numAllocs: typeCounts[elem] ? typeCounts[elem].numAllocs : undefined,
                                                    numPages: typeCounts[elem] ? typeCounts[elem].numPages : undefined
                                                }));

        // console.log('In legend layout, here are the typeCounts:');
        // console.log(typeCounts);

        canvas = document.createElement('canvas');

        const headerBar = selection.append('thead')
            .style('overflow', 'hidden')
            .style('position', 'sticky')
            .style('width', '100%')
            .style('height', `${1.2*LINE_SEP}px`)
            .style('top', '0px')
            .style('background-color', 'white')
            .style('z-index', 2);
            // .style('display', 'table-row');

        headerBar.append('td')
            .append('div')
            .style('position', 'relative')
            // .style('float', 'left')
            .style('vertical-align', 'middle')
            // .style('left', `${TIMEBOX_INDENT}px`)
            .style('width', `${ICON_SIZE}px`)
            .style('height', `${ICON_SIZE}px`)
            // .style('display', 'table-cell')
            .html(timegraphSvg);

        headerBar.append('td')
            .append('div')
            .style('position', 'relative')
            // .style('float', 'left')
            .style('vertical-align', 'middle')
            // .style('left', `${SAMPLEBOX_INDENT}px`)
            .style('width', `${ICON_SIZE}px`)
            .style('height', `${ICON_SIZE}px`)
            // .style('display', 'table-cell')
            .html(memlayoutSvg);

        headerBar.append('td');
        headerBar.append('td');

        headerBar.append('td')
            .append('input')
            .attr('type', 'text')
            .attr('placeholder', 'Filter types')
            .style('position', 'relative')
            // .style('float', 'left')
            .style('left', '10px')
            .style('vertical-align', 'middle')
            // .style('display', 'table-cell')
            // .style('top', `0px`)
            // .style('left', `${COL_INDENT}px`)
            .on('input', function() {
                currFilter = d3.select(this).property('value');
                drawTypes();
            });

        const allocHeader = headerBar.append('td')
            .attr('class', 'allocCol')
            .append('div')
            // .style('outline', '1px dashed black')
            .style('display', 'inline-block')
            .style('width', '73px')
            .style('height', `${LINE_SEP}px`)
            .style('cursor', 'pointer')
            .style('pointer-events', 'visible')
            .style('vertical-align', 'middle')
            .on('click', function() {
                if (currSorter.mode == 'allocs' && currSorter.rev) {
                    currSorter.mode = 'alph';
                    currSorter.rev = false;
                    d3.select(this)
                        .select('.sortArrow')
                        .style('visibility', 'hidden');
                }
                else if (currSorter.mode == 'allocs') {
                    currSorter.rev = true;
                    d3.select(this)
                        .select('.sortArrow')
                        .style('transform', 'translate(50%, 50%)');
                }
                else {
                    currSorter.mode = 'allocs';
                    currSorter.rev = false;
                    d3.select('#pagesColSVG')
                        .select('.sortArrow')
                        .style('visibility', 'hidden');
                    d3.select(this)
                        .select('.sortArrow')
                        .style('transform', 'translate(50%, 50%) rotate(0.5turn)')
                        .style('visibility', 'visible');
                }
                drawTypes();
            });
        allocHeader.append('div')
            .style('font-family', 'monospace')
            .style('font-size', '12px')
            .style('float', 'left')
            // .style('left', '10px')
            .style('vertical-align', 'middle')
            .style('transform', 'translateY(20%)')
            .style('user-select', 'none')
            // .style('display', 'table-cell')
            .text('# allocs');
        allocHeader.append('svg')
            .attr('id', 'allocColSVG')
            .style('width', `${LINE_SEP}px`)
            .style('height', `${LINE_SEP}px`)
            .style('vertical-align', 'middle')
            .style('float', 'left')
            .append('path')
            .attr('class', 'sortArrow')
            .attr('d', arrow)
            .attr('fill', 'black')
            .style('visibility', currSorter.mode == 'allocs' ? 'visible' : 'hidden')
            .style('transform', 'translate(50%, 30%) rotate(0.5turn)');

        const pageHeader = headerBar.append('td')
            .attr('class', 'pageCol')
            .append('div')
            .style('width', '73px')
            .style('height', `${LINE_SEP}px`)
            .style('cursor', 'pointer')
            .style('pointer-events', 'visible')
            .style('vertical-align', 'middle')
            .on('click', function() {
                if (currSorter.mode == 'pages' && currSorter.rev) {
                    currSorter.mode = 'alph';
                    currSorter.rev = false;
                    d3.select(this)
                        .select('.sortArrow')
                        .style('visibility', 'hidden');
                }
                else if (currSorter.mode == 'pages') {
                    currSorter.rev = true;
                    d3.select(this)
                        .select('.sortArrow')
                        .style('transform', 'translate(50%, 50%)');
                }
                else {
                    currSorter.mode = 'pages';
                    currSorter.rev = false;
                    d3.select('#allocColSVG')
                        .select('.sortArrow')
                        .style('visibility', 'hidden');
                    d3.select(this)
                        .select('.sortArrow')
                        .style('transform', 'translate(50%, 50%) rotate(0.5turn)')
                        .style('visibility', 'visible');
                }
                drawTypes();
            });
        pageHeader.append('div')
            .style('font-family', 'monospace')
            .style('font-size', '12px')
            .style('float', 'left')
            // .style('left', '10px')
            .style('vertical-align', 'middle')
            .style('transform', 'translateY(20%)')
            .style('user-select', 'none')
            // .style('display', 'table-cell')
            .text('# pages');
        pageHeader.append('svg')
            .attr('id', 'pagesColSVG')
            .style('width', `${LINE_SEP}px`)
            .style('height', `${LINE_SEP}px`)
            .style('vertical-align', 'middle')
            .style('float', 'left')
            .append('path')
            .attr('class', 'sortArrow')
            .attr('d', arrow)
            .attr('fill', 'black')
            .style('visibility', currSorter.mode == 'allocs' ? 'visible' : 'hidden')
            .style('transform', 'translate(50%, 30%) rotate(0.5turn)');

        legendGroup = selection.append('tbody')
            .attr('id', 'typesBox')
            .style('width', '450px')
            .style('height', `${Math.min((types.length+0.8)*LINE_SEP, LEGEND_HEIGHT)}px`)
            .style('overflow', 'scroll')
            .style('position', 'relative')
            .style('top', '5px')
            .style('z-index', 1);
            // .style('display', 'table-row-group');
            // .style('top', `${1.5*LINE_SEP}px`);
            // .append('svg')
            // .style('width', '90%')
            // .style('height', `${(types.length+0.8)*LINE_SEP}px`);

        const footerBar = selection.append('tfoot')
            .style('overflow', 'visible')
            .style('position', 'sticky')
            .style('bottom', '0px')
            .style('width', '100%')
            .style('height', `${1.2*LINE_SEP}px`)
            .style('background-color', 'white')
            .style('z-index', 2);
            // .style('display', 'table-row');
            // .style('top', `${legendGroup.attr('height') + 2*LINE_SEP}px`);

        let timeInvertBox = footerBar.append('td')
            .append('div')
            .attr('class', 'invertIcon')
            .style('position', 'relative')
            // .style('float', 'left')
            // .style('left', `${TIMEBOX_INDENT}px`)
            .style('width', `${ICON_SIZE}px`)
            .style('height', `${ICON_SIZE}px`)
            // .style('display', 'table-cell')
            .html(invertSvg)
            .on('click', function() {
                timeInvertBox.style('pointer-events', 'none');
                const timeInvertAnim = footerBar.append('div')
                    .attr('id', 'sampleLoadingAnim')
                    .attr('class', 'loadingAnim')
                    .style('width', '10px')
                    .style('height', '10px')
                    .style('left', `${TIMEBOX_INDENT + 14}px`);
                const timeBoxes = document.querySelectorAll('.timeCheckbox');
                timeBoxes.forEach((checkBox) => checkBox.click()); // TODO turn this to async call to have loading anim
                timeInvertAnim.remove();
                timeInvertBox.style('pointer-events', 'visible');
            });

        footerBar.append('td')
            .append('div')
            .attr('class', 'invertIcon')
            .style('position', 'relative')
            // .style('float', 'left')
            .style('left', '1px')
            // .style('left', `${SAMPLEBOX_INDENT}px`)
            .style('width', `${ICON_SIZE}px`)
            .style('height', `${ICON_SIZE}px`)
            // .style('display', 'table-cell')
            .html(invertSvg)
            .on('click', function() {
                const sampleBoxes = document.querySelectorAll('.sampleCheckbox');
                sampleBoxes.forEach((checkBox) => checkBox.click());
            });

        drawTypes();
    }

    function drawTypes() {
        const filteredTypes = [];
        let filteredTypesPre = [];
        types.filter((elem) => elem.type.includes(currFilter))
            .forEach((d) => {
                filteredTypesPre.push({type: d.type, col: d.col, hasFields: fields[noSpaces(d.type)] ? true : false, numAllocs: d.numAllocs, numPages: d.numPages});
            });
        filteredTypesPre = filteredTypesPre.sort((a, b) => sorters[currSorter.mode](a, b)*(currSorter.rev ? 1 : -1));
        filteredTypesPre.forEach((d) => {
            filteredTypes.push(d);
            if (fields[noSpaces(d.type)] && expandedTypes.has(d.type)) {
                fields[noSpaces(d.type)].forEach((st) => filteredTypes.push({type: st, col: colourOfType[st], parent: d.type}));
            }
        });

        d3.select('#typesBox')
            .style('height', `${Math.min((Math.max(filteredTypes.length, types.length)+0.8)*LINE_SEP, LEGEND_HEIGHT)}px`)

        // let filteredSubtypes = filteredTypes.map((d) => d.expanded ? fields[d.type.replaceAll(' ', '')].map((st) => ({type: st.type, col: st.col, parent: d.type})) : [])
        //     .reduce((acc, curr) => acc.concat(curr), []);

        // filteredTypes = filteredTypes.concat(filteredSubtypes);
        
        const buffer = 3;
        legendGroup.selectAll('.legendGroup')
            .data(filteredTypes, (d) => d.type)
            .order()
            .join(
                (enter) => {
                    let group = enter.append('tr')
                            .attr('class', 'legendGroup')
                            // .style('display', 'table-row')
                            .style('transform', 'translateX(3px)')
                            .style('width', '100%')
                            .style('height', `${LINE_SEP}px`);
                        // .style('transform', 'translate(17px, 0px)');

                    group.append('td')
                        .style('vertical-align', 'middle')
                        .style('justify-content', 'center')
                        .style('align-items', 'center')
                        .style('position', 'relative')
                        // .style('display', 'table-cell')
                        .append('input')
                        .attr('class', 'timeCheckbox')
                        .attr('type', 'checkbox')
                        .attr('data-type', (d) => d.type)
                        // .style('float', 'left')
                        // .style('left', '3px')
                        // .style('top', '-2px')
                        .style('pointer-events', 'visible')
                        .style('visibility', (d) => d.parent ? 'hidden' : 'visible')
                        // .style('left', `${TIMEBOX_INDENT + (ICON_SIZE / 7)}px`)
                        // .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`)
                        .property('checked', (d) => mainVis ? mainVis.getVisOfType(d.type) : true)
                        .on('change', function(event) {
                            mainVis.changeVisOfType(d3.select(this).attr('data-type'));
                        });

                    group.append('td')
                        .style('vertical-align', 'middle')
                        .style('justify-content', 'center')
                        .style('align-items', 'center')
                        // .style('display', 'table-cell')
                        .style('position', 'relative')
                        .style('left', '1px')
                        .append('input')
                        .attr('class', 'sampleCheckbox')
                        .attr('type', 'checkbox')
                        .attr('data-type', (d) => d.type)
                        // .style('float', 'left')
                        // .style('top', '-2px')
                        .style('pointer-events', 'visible')
                        .style('visibility', 'visible')
                        // .style('left', `${SAMPLEBOX_INDENT + (ICON_SIZE / 7)}px`)
                        // .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`)
                        .property('checked', (d) => mainVis ? (d.parent ? mainVis.isSubtypeSampled(d.type) : mainVis.isTypeSampled(d.type)) : true)
                        .on('change', function(event, d) {
                            mainVis.changeTypeSampled(d3.select(this).attr('data-type'), d.parent ? true : false);
                        });

                    group.append('td')
                        .style('justify-content', 'center')
                        .style('align-items', 'center')
                        // .style('display', 'table-cell')
                        .append('svg')
                        .style('vertical-align', 'middle')
                        .style('width', `${LINE_SEP}px`)
                        .style('height', `${LINE_SEP}px`)
                        .style('position', 'relative')
                        // .style('float', 'left')
                        // .style('left', '10px')
                        // .style('top', '-2px')
                        .style('pointer-events', 'visible')
                        .style('cursor', 'pointer')
                        .style('visibility', (d) => d.hasFields ? 'visible' : 'hidden')
                        .on('click', function(e, d) {
                            mainVis.toggleExpandType(d.type);
                            // if (expandedTypes.has(d.type)) {
                            //     expandedTypes.delete(d.type);
                            // }
                            // else {
                            //     expandedTypes.add(d.type);
                            // }
                            // if (d.expanded) {
                            //     group.append('div')
                            //         .attr('class', 'legendSubtypeGroup')
                            //         .style('position', 'relative')
                            //         .style('width', '450px')
                            //         .style('height', `${(types.length+0.8)*LINE_SEP}px`);
                            // }
                            // else {
                            //     group.select('.legendSubtypeGroup')
                            //         .remove();
                            // }
                            drawTypes();
                        })
                        .append('path')
                        .attr('class', 'typeExpandArrow')
                        .attr('d', arrow)
                        .attr('fill', '#ccc')
                        // .style('position', 'relative')
                        // .style('pointer-events', 'none')
                        .style('transform', 'translate(50%, 50%) rotate(0.25turn)');
                    
                    group.append('td')
                        .append('div')
                        // .attr('x', COL_INDENT)
                        // .attr('y', (d, i) => i*(LINE_SEP))
                        .style('position', 'relative')
                        // .style('float', 'left')
                        .style('vertical-align', 'middle')
                        .style('justify-content', 'center')
                        .style('align-items', 'center')
                        .style('width', `${0.8*LINE_SEP}px`)
                        .style('height', `${0.8*LINE_SEP}px`)
                        .style('max-width', `${0.8*LINE_SEP}px`)
                        .style('max-height', `${0.8*LINE_SEP}px`)
                        .style('left', (d) => d.parent ? '20px' : '0px')
                        .style('background', (d) => d.col);
                        // .style('display', 'table-cell');

                    // TODO this will probably overflow to next line if text is sufficiently long
                    group.append('th')
                        .attr('scope', 'row')
                        // .attr('x', COL_INDENT + 1.1*LINE_SEP)
                        // .attr('y', (d, i) => (i+0.62)*(LINE_SEP))
                        .style('font-family', 'monospace')
                        .style('position', 'relative')
                        .style('left', (d) => d.parent ? '20px' : '7px')
                        // .style('float', 'left')
                        .style('vertical-align', 'middle')
                        .style('text-align', 'left')
                        // .style('display', 'table-cell')
                        .text((d) => trimLongTypeName(d.type))
                        .on('mouseover', function(e, d) {
                            d3.select('#legendTypeHint')
                                .remove();
                            if (d.type.length > 28) {
                                let [text, width, height] = getTextBlockForType(d.type, '10pt monospace', 45);
                                const legendDiv = d3.select('#legendDiv');
                                const body = d3.select('body').node();
                                let typeGroup = legendDiv.append('svg')
                                    .attr('id', 'legendTypeHint')
                                    // .style('transform', `translate(${e.pageX}px, ${e.pageY - (height*text.length) - buffer}px)`)
                                    // .style('transform', `translate(${d3.pointer(e)[0]}px, ${d3.pointer(e)[1] - (height*text.length) - buffer}px)`)
                                    .style('position', 'fixed')
                                    .style('width', `${width}px`)
                                    .style('height', `${text.length*height + 3}px`)
                                    .style('left', `${e.clientX}px`)
                                    .style('top', `${e.clientY - height*(text.length+1) - buffer}px`)
                                    .style('pointer-events', 'none')
                                    .style('background-color', 'white')
                                    .style('z-index', 3);
                                    
                                typeGroup.selectAll('.cacheSetHintText')
                                    .data(text)
                                    .enter()
                                    .append('text')
                                    .attr('font-family', 'monospace')
                                    .style('font-size', '10px')
                                    .style('position', 'fixed')
                                    .style('top', '0px')
                                    .style('left', '0px')
                                    .style('transform', (d, i) => `translateY(${(i+1)*height}px)`)
                                    .style('pointer-events', 'none')
                                    .text((tx) => tx);
                            }
                        })
                        .on('mousemove', function(e, d) {
                            const body = d3.select('body').node();
                            let [text, width, height] = getTextBlockForType(d.type, '10pt monospace', 45);
                            d3.select('#legendTypeHint')
                                .style('left', `${e.clientX}px`)
                                .style('top', `${e.clientY - height*(text.length+1) - buffer}px`);
                                // .style('transform', `translate(${e.pageX}px, ${e.pageY - (height*text.length) - buffer}px)`)
                                // .style('transform', `translate(${d3.pointer(e)[0]}px, ${d3.pointer(e)[1] - (height*text.length) - buffer}px)`);
                        })
                        .on('mouseout', function() {
                            d3.select('#legendTypeHint')
                                .remove();
                        });

                    group.append('td')
                        .attr('class', 'allocCol')
                        .style('font-family', 'monospace')
                        .style('position', 'relative')
                        .style('vertical-align', 'middle')
                        .style('justify-content', 'left')
                        // .style('display', 'table-cell')
                        .text((d) => d.numAllocs ? d.numAllocs : '');
                    
                    group.append('td')
                        .attr('class', 'pageCol')
                        .style('font-family', 'monospace')
                        .style('position', 'relative')
                        .style('vertical-align', 'middle')
                        .style('justify-content', 'left')
                        // .style('display', 'table-cell')
                        .text((d) => d.numPages ? d.numPages : '');
                },
                (update) => {
                    update.select('.typeExpandArrow')
                        // .transition()
                        // .ease(d3.easeCubicOut)
                        .style('transform', (d) => expandedTypes.has(d.type) ? 'translate(50%, 50%) rotate(0.5turn)' : 'translate(50%, 50%) rotate(0.25turn)');
                    // update.select('rect')
                    //     .transition()
                    //     .attr('y', (d, i) => i*(LINE_SEP));
                    // update.select('text')
                    //     .transition()
                    //     .attr('y', (d, i) => (i+0.62)*(LINE_SEP));
                },
                (exit) => {
                    exit.transition()
                        .remove();
                }
            );

        // let timeCheckData = d3.select('#typesBox')
        //     .selectAll('.timeCheckbox')
        //     .data(filteredTypes, (d) => d.type)
        //     .join(
        //         (enter) => {
        //             enter.append('input')
        //                 .attr('class', 'timeCheckbox')
        //                 .attr('type', 'checkbox')
        //                 .attr('data-type', (d) => d.type)
        //                 .style('position', 'absolute')
        //                 .style('left', `${TIMEBOX_INDENT + (ICON_SIZE / 7)}px`)
        //                 .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`)
        //                 .property('checked', (d) => mainVis ? mainVis.getVisOfType(d.type) : true)
        //                 .on('change', function(event) {
        //                     mainVis.changeVisOfType(d3.select(this).attr('data-type'));
        //                 });
        //         },
        //         (update) => {
        //             update.transition()
        //                 .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`);
        //         },
        //         (exit) => {
        //             exit.remove();
        //         }
        //     );

        // let sampleCheckData = d3.select('#typesBox')
        //         .selectAll('.sampleCheckbox')
        //         .data(filteredTypes, (d) => d.type)
        //         .join(
        //             (enter) => {
        //                 enter.append('input')
        //                     .attr('class', 'sampleCheckbox')
        //                     .attr('type', 'checkbox')
        //                     .attr('data-type', (d) => d.type)
        //                     .style('position', 'absolute')
        //                     .style('left', `${SAMPLEBOX_INDENT + (ICON_SIZE / 7)}px`)
        //                     .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`)
        //                     .property('checked', (d) => mainVis ? mainVis.isTypeSampled(d.type) : true)
        //                     .on('change', function(event) {
        //                         mainVis.changeTypeSampled(d3.select(this).attr('data-type'));
        //                     });
        //             },
        //             (update) => {
        //                 update.transition()
        //                     .style('top', (d, i) => `${(i-0.07)*LINE_SEP}px`);
        //             },
        //             (exit) => {
        //                 exit.remove();
        //             }
        //         );
    }

    function getTextBlockForType(tp, font, len=28) {
        const context = canvas.getContext('2d');
        context.font = font;
        const textHeight = 12;
        const lines = [];
        for (let i = 0; i < tp.length; i += len) {
            lines.push(tp.substring(i, Math.min(i + len, tp.length)));
        }
        return [lines, context.measureText(lines[0]).width, textHeight];
    }

    drawLegendLayout.redraw = function() {
        drawTypes();
    }

    drawLegendLayout.fields = function(val) {
        if (!arguments) return fields;
        fields = val;
        // console.log('Here are fields in legend:');
        // console.log(fields);
        return drawLegendLayout;
    }

    drawLegendLayout.expandedTypes = function(val) {
        if (!arguments) return expandedTypes;
        expandedTypes = val;
        return drawLegendLayout;
    }

    drawLegendLayout.typeCounts = function(val) {
        if (!arguments) return typeCounts;
        typeCounts = val;
        return drawLegendLayout;
    }

    drawLegendLayout.toggleExpand = function(tp) {
        for (let i = 0; i < types.length; i++) {
            if (tp == types[i].type) {
                types[i].expanded = !types[i].expanded;
                break;
            }
        }
    }

    return drawLegendLayout;
}

export default legendLayout;