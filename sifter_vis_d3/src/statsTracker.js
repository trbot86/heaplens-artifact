import * as d3 from 'd3';
import { binarySearchSuccessor } from './vis.js';

export default class StatsTracker {
    #colocCount;

    constructor(types, stats) {
        this.#colocCount = stats;
    }

    getColocRatios(clKind='single', type) {
        return Object.keys(this.#colocCount[clKind]['coloc'][type]).map((otherType) => [otherType, this.#colocCount[clKind]['coloc'][type][otherType] / this.#colocCount[clKind]['total'][type]]);
    }

    getTypes() {
        return Object.keys(this.#colocCount['single']['coloc']);
    }
}

export function trimString(str, maxChars) {
    return str.length > maxChars ? str.substring(0, maxChars - 4) + '...' : str;
}

export function typeInfoPopup() {
    let x = '0px',
        y = '0px',
        width = '50%',
        height = '100%',
        lineSpace = 10,
        type = undefined,
        maxChars = 12,
        clKind = 'single',
        stats = undefined;

    function drawPopup(selection) {
        let ratios = stats.getColocRatios(clKind.toLowerCase(), type);
        let vals = ratios.map((d) => d[1]);

        let colScale = d3.scaleLinear()
                        .domain([Math.min(...vals), Math.max(...vals)])
                        .range(['green', 'red']);

        let outText = [];
        for (let i = 0; i < ratios.length; i++) {
            outText.push(`${trimString(ratios[i][0], maxChars)}:`);
            outText.push(ratios[i][1].toFixed(3));
        }
        let textGroup = selection.append('div')
            .style('position', 'relative')
            .style('x', x)
            .style('y', y)
            .style('width', width)
            .style('height', height)
            .style('display', 'inline-block');

        textGroup.append('p')
            .attr('font-family', 'monospace')
            .style('text-decoration', 'underline')
            .style('font-size', '10px')
            .text(`${clKind} cacheline colocation for ${trimString(type, maxChars)} \n`);

        textGroup.selectAll('.statText')
            .data(outText)
            .enter()
            .append('p')
            .attr('class', 'statText')
            .attr('font-family', 'monospace')
            .style('position', 'absolute')
            .style('left', (d, i) => `${i % 2 == 0 ? 20 : 170}px`)
            .style('top', (d, i) => `${(Math.floor(i / 2) + 1)*lineSpace}px`)
            .style('font-size', '10px')
            .style('color', (d, i) => i % 2 == 0 ? 'black' : colScale(parseFloat(d)))
            .text((d) => d);
    }

    drawPopup.x = function(val) {
        if (!arguments) return x;
        x = val;
        return drawPopup;
    }

    drawPopup.y = function(val) {
        if (!arguments) return y;
        y = val;
        return drawPopup;
    }

    drawPopup.width = function(val) {
        if (!arguments) return width;
        width = val;
        return drawPopup;
    }

    drawPopup.height = function(val) {
        if (!arguments) return height;
        height = val;
        return drawPopup;
    }

    drawPopup.type = function(val) {
        if (!arguments) return type;
        type = val;
        return drawPopup;
    }

    drawPopup.stats = function(val) {
        if (!arguments) return stats;
        stats = val;
        return drawPopup;
    }

    drawPopup.lineSpace = function(val) {
        if (!arguments) return lineSpace;
        lineSpace = val;
        return drawPopup;
    }

    drawPopup.maxChars = function(val) {
        if (!arguments) return maxChars;
        maxChars = val;
        return drawPopup;
    }

    drawPopup.clKind = function(val) {
        if (!arguments) return clKind;
        clKind = val;
        return drawPopup;
    }

    return drawPopup;
}