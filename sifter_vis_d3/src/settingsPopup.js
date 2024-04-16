import * as d3 from 'd3';

export class SettingsPopup {
    constructor(sampleInfo) {
        const TOP_BUFF = 50;
        const LEFT_BUFF = 40;
        const LINE_SEP = 50;
        const BUTTON_WIDTH = 90;
        const BUTTON_HEIGHT = 30;

        const algOptions = ['DBSCAN', 'Agglomerative Clustering', 'MeanShift'];
        const textFields = ['Page clustering algorithm:',
                            'Max run length:',
                            'Max runs from cluster:',
                            'Number of buckets:']

        const window = d3.select('body')
            .append('div')
            .attr('class', 'popup')
            .attr('id', 'settingsPopup');

        window.selectAll('text')
            .data(textFields)
            .enter()
            .append('text')
            .attr('font-family', 'monospace')
            .style('position', 'absolute')
            .style('top', (d, i) => `${TOP_BUFF + i*LINE_SEP}px`)
            .style('left', `${LEFT_BUFF}px`)
            .text((d) => d);

        let algSelector = window.append('select')
            .style('position', 'absolute')
            .style('top', `${TOP_BUFF}px`)
            .style('left', '230px');

        let sliderGroup = window.selectAll('.sliderGroup')
            .data([{min: 1, max: 10, id: 'runLength'},
                    {min: 1, max: 6, id: 'numRuns'}])
            .enter()
            .append('svg')
            .attr('class', 'sliderGroup')
            .style('width', '250px')
            .style('height', '100px')
            .style('position', 'absolute')
            .style('top', (d, i) => `${TOP_BUFF + 40 + (i * 50)}px`)
            .style('left', '230px')
            .call(numericalSlider()
                    .x(10)
                    .y(20)
                    .width(100));
        // sliderGroup.call(numericalSlider()      // max runs from cluster
        //                     .x(10)
        //                     .y(60)
        //                     .width(70)
        //                     .min(1)
        //                     .max(6));

        const saveButtonGroup = window.append('svg')
            .style('position', 'inherit')
            .style('top', '82%')
            .style('left', '78%');
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
                sampleInfo.runLength = parseInt(d3.select('#runLength').text());
                sampleInfo.numRuns = parseInt(d3.select('#numRuns').text());
                sampleInfo.buckets = parseInt(bucketSelector.property('value'));
                d3.select('#settingsPopup')
                    .transition()
                    .style('display', 'none');
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

        let bucketSelector = window.append('input')
            .attr('type', 'number')
            .attr('min', 1000)
            .attr('max', 100000)
            .attr('step', 100)
            .attr('value', 5000)
            .attr('size', 8)
            .style('position', 'absolute')
            .style('top', `${TOP_BUFF + 3*LINE_SEP}px`)
            .style('left', '230px');
    }

    static build(sampleInfo) {
        return new SettingsPopup(sampleInfo);
    }
}

function numericalSlider() {
    let x = 0,
        y = 0,
        width = 50,
        integer = true;

    function drawSlider(selection) {
        let currslot = 0;

        selection.each(function(d, i) {
            const selSlider = d3.select(this);
            selSlider.append('rect')
                .attr('x', x)
                .attr('y', y)
                .style('width', `${width}px`)
                .style('height', '5px')
                .style("fill", "#ddd");
            selSlider.append('circle')
                .attr('cx', x)
                .attr('cy', y + 2.5)
                .attr('r', 8)
                .style('fill', '#ccc')
                .call(d3.drag()
                    .on('drag', function(e) {
                        let prevCx = d3.select(this).attr('cx');
                        // absolutely no idea why the +300 is needed below, but it is
                        d3.select(this).attr('cx', Math.min(Math.max(e.x + 300, x), x + width));
                        let pos = (prevCx / (x + width))*(d.max - d.min) + d.min;
                        currslot = integer ? Math.round(pos) : pos;
                        selSlider.select(`#${d.id}`)
                            .text(currslot);
                    })
                    .on('end', function(e) {
                        if (integer) {
                            d3.select(this).attr('cx', ((currslot - d.min) / (d.max - d.min))*(width - x) + x);
                        }
                    }));
            selSlider.append('text')
                .attr('id', d.id)
                .attr('x', width + x + 10)
                .attr('y', y + 4)
                .attr('font-family', 'monospace')
                .text(d.min);
        });
    }

    drawSlider.x = function(val) {
        if (!arguments) return x;
        x = val;
        return drawSlider;
    }

    drawSlider.y = function(val) {
        if (!arguments) return y;
        y = val;
        return drawSlider;
    }

    drawSlider.width = function(val) {
        if (!arguments) return width;
        width = val;
        return drawSlider;
    }

    drawSlider.lineSep = function(val) {
        if (!arguments) return this.lineSep;
        lineSep = val;
        return drawSlider;
    }

    return drawSlider;
}