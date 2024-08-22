import * as d3 from 'd3';

export class SettingsPopup {
    constructor(sampleInfo) {
        const TOP_BUFF = 50;
        const LEFT_BUFF = 40;
        const LINE_SEP = 50;
        const BUTTON_WIDTH = 96;
        const BUTTON_HEIGHT = 30;

        const algOptions = ['DBSCAN', 'Agglomerative Clustering', 'MeanShift'];
        const textFields = ['Page clustering algorithm:',
                            'Max run length:',
                            'Max runs from cluster:',
                            'Number of buckets:']

        const window = d3.select('body')
            .append('div')
            .attr('class', 'popup')
            .attr('id', 'settingsPopup')
            .style('display', 'grid')
            .style('grid-template-columns', '5fr 5fr 3fr')
            .style('grid-template-rows', '2fr 2fr 2fr 2fr 1fr')
            .style('align-items', 'center')
            .style('column-gap', '10px');

        window.selectAll('.settingsPopupText')
            .data(textFields)
            .enter()
            .append('div')
            .style('font-family', 'monospace')
            .style('justify-self', 'right')
            .style('grid-column', 1)
            .style('grid-row', (d, i) => i+1)
            .text((d) => d);

        let algSelector = window.append('div')
            .style('grid-column', 2)
            .style('grid-row', 1)
            .style('vertical-align', 'middle')
            .append('select')
            .style('position', 'relative');
        algSelector.selectAll('option')
            .data(algOptions)
            .enter()
            .append('option')
            .text((d) => d)
            .attr('value', (d) => d);
        algSelector.on('change', function() {
            const sel = d3.select(this).property('value');
            console.log("Selected algorithm: ", sel);
        });

        let sliderGroup = window.selectAll('.sliderGroup')
            .data([{init: 5, min: 1, max: 20, id: 'runLength'},
                    {init: 3, min: 1, max: 10, id: 'numRuns'}])
            .enter()
            .append('div')
            .attr('class', 'sliderGroup')
            .style('grid-column', 2)
            .style('grid-row', (d, i) => i+2)
            .style('display', 'inline-block');
        sliderGroup.append('input')
            .attr('id', (d) => d.id)
            .attr('type', 'range')
            .attr('value', (d) => d.init)
            .attr('min', (d) => d.min)
            .attr('max', (d) => d.max)
            .attr('step', 1)
            // .style('width', '250px')
            // .style('height', '100px')
            .style('position', 'relative')
            .style('float', 'left')
            .on('input', function(e, d) {
                d3.select(`#${d.id}Text`)
                    .text(d3.select(this).property('value'));
            });
        sliderGroup.append('div')
            .attr('id', (d) => `${d.id}Text`)
            .style('font-family', 'monospace')
            .style('float', 'left')
            .style('transform', 'translateX(6px)')
            .text((d) => d.init);
            

        window.append('div')
            .style('grid-column', 2)
            .style('grid-row', 4)
            .append('input')
            .attr('id', 'numBuckets')
            .attr('type', 'number')
            .attr('min', 1000)
            .attr('max', 100000)
            .attr('step', 100)
            .attr('value', 1000)
            .attr('size', 8);

        window.append('div')
            .style('grid-column', 3)
            .style('grid-row', 1)
            .style('justify-self', 'center')
            .append('i')
            .attr('class', 'fa fa-close')
            .style('font-size', '24px')
            .style('color', '#ccc')
            .style('cursor', 'pointer')
            .on('click', function() {
                algSelector.property('value', sampleInfo.algorithm == 'dbscan' ? 'DBSCAN' :
                    sampleInfo.algorithm == 'agglomerative' ? 'Agglomerative Clustering' :
                    'MeanShift')
                d3.select('#runLength')
                    .property('value', parseInt(sampleInfo.runLength));
                d3.select('#numRuns')
                    .property('value', parseInt(sampleInfo.numRuns));
                d3.select('#numBuckets')
                    .property('value', parseInt(sampleInfo.buckets));
                d3.select('#settingsPopup')
                    .style('visibility', 'hidden');
                d3.select('#runLengthText')
                    .text(sampleInfo.runLength);
                d3.select('#numRunsText')
                    .text(sampleInfo.numRuns);
            });

        const saveButtonGroup = window.append('svg')
            .style('grid-column', 3)
            .style('grid-row', 5)
            .style('width', '100%')
            .style('height', '100%');
        saveButtonGroup.append('rect')
            .attr('width', BUTTON_WIDTH)
            .attr('height', BUTTON_HEIGHT)
            .attr('rx', 7)
            .attr('ry', 7)
            .style('fill', 'white')
            .style('stroke', '#ccc')
            .style('stroke-width', '1px')
            .style('cursor', 'pointer')
            .style('pointer-events', 'visible')
            .on('click', function() {
                sampleInfo.algorithm =  algSelector.node().value == 'DBSCAN' ? 'dbscan' :
                                        algSelector.node().value == 'Agglomerative Clustering' ? 'agglomerative' :
                                        'meanshift';
                sampleInfo.runLength = parseInt(d3.select('#runLength').property('value'));
                sampleInfo.numRuns = parseInt(d3.select('#numRuns').property('value'));
                sampleInfo.buckets = parseInt(d3.select('#numBuckets').property('value'));
                d3.select('#settingsPopup')
                    .transition()
                    .style('visibility', 'hidden');
            })
            .on('mouseover', function() {
                d3.select(this)
                    .transition()
                    .style('fill', '#ccc');
            })
            .on('mouseout', function() {
                d3.select(this)
                    .transition()
                    .style('fill', 'white');
            });
        saveButtonGroup.append('text')
            .attr('x', BUTTON_WIDTH / 2)
            .attr('y', (BUTTON_HEIGHT / 2) + 4)
            .attr('text-anchor', 'middle')
            .attr('font-family', 'monospace')
            .style('alignment-baseline', 'middle')
            .style('pointer-events', 'none')
            .text('Save & close');
    }

    static build(sampleInfo) {
        return new SettingsPopup(sampleInfo);
    }
}

// function numericalSlider() {
//     let x = 0,
//         y = 0,
//         width = 50,
//         integer = true;

//     function drawSlider(selection) {
//         let currslot = 0;

//         selection.each(function(d, i) {
//             const selSlider = d3.select(this);
//             selSlider.append('rect')
//                 .attr('x', x)
//                 .attr('y', y)
//                 .style('width', `${width}px`)
//                 .style('height', '5px')
//                 .style("fill", "#ddd");
//             selSlider.append('circle')
//                 .attr('cx', x)
//                 .attr('cy', y + 2.5)
//                 .attr('r', 8)
//                 .style('fill', '#ccc')
//                 .call(d3.drag()
//                     .on('drag', function(e) {
//                         let prevCx = d3.select(this).attr('cx');
//                         // absolutely no idea why the +300 is needed below, but it is
//                         d3.select(this).attr('cx', Math.min(Math.max(e.x + 300, x), x + width));
//                         let pos = (prevCx / (x + width))*(d.max - d.min) + d.min;
//                         currslot = integer ? Math.round(pos) : pos;
//                         selSlider.select(`#${d.id}`)
//                             .text(currslot);
//                     })
//                     .on('end', function(e) {
//                         if (integer) {
//                             d3.select(this).attr('cx', ((currslot - d.min) / (d.max - d.min))*(width - x) + x);
//                         }
//                     }));
//             selSlider.append('text')
//                 .attr('id', d.id)
//                 .attr('x', width + x + 10)
//                 .attr('y', y + 4)
//                 .attr('font-family', 'monospace')
//                 .text(d.min);
//         });
//     }

//     drawSlider.x = function(val) {
//         if (!arguments) return x;
//         x = val;
//         return drawSlider;
//     }

//     drawSlider.y = function(val) {
//         if (!arguments) return y;
//         y = val;
//         return drawSlider;
//     }

//     drawSlider.width = function(val) {
//         if (!arguments) return width;
//         width = val;
//         return drawSlider;
//     }

//     drawSlider.lineSep = function(val) {
//         if (!arguments) return this.lineSep;
//         lineSep = val;
//         return drawSlider;
//     }

//     return drawSlider;
// }