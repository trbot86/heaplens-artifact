import * as d3 from 'd3';
import { binarySearchSuccessor } from './vis.js';

export default class StatsTracker {
    #typeCount;
    #colocCount;

    constructor(types, records, cachelineSize=64) {
        this.#typeCount = types.reduce((acc, type) => {
            acc[type] = 0;
            return acc;
        }, {});
        this.#colocCount = types.reduce((acc, type) => {
            acc[type] = types.reduce((acc2, type2) => {
                acc2[type2] = 0;
                return acc2;
            }, {});
            return acc;
        }, {});

        // const allocs = records.filter((rec) => rec.is_alloc == 1);
        // const freesMap = records.filter((rec) => rec.is_alloc == 0).reduce((acc, curr) => {
        //     acc[curr.addr] ? acc[curr.addr].push(curr.ts) : acc[curr.addr] = [curr.ts];
        //     return acc;
        // }, {});
        // const objects = allocs.map((alloc) => {
        //                             let ft = binarySearchSuccessor(freesMap[alloc.addr], alloc.ts);
        //                             return {size: alloc.size,
        //                                 type: alloc.type,
        //                                 addr: alloc.addr,
        //                                 allocTs: alloc.ts,
        //                                 freeTs: ft ? ft[0] : 2*alloc.ts
        //                                 };
        //                         })
        //                     .sort((a, b) => a.freeTs != b.freeTs ? a.freeTs - b.freeTs : a.allocTs - b.allocTs);
        
        // const clMap = objects.reduce((acc, obj) => {
        //     acc[obj.addr - (obj.addr % cachelineSize)] ? acc[obj.addr - (obj.addr % cachelineSize)].push({type: obj.type, allocTs: obj.allocTs, freeTs: obj.freeTs}) :
        //                                                 acc[obj.addr - (obj.addr % cachelineSize)] = [{type: obj.type, allocTs: obj.allocTs, freeTs: obj.freeTs}];
        //     let end = (obj.addr + obj.size) % cachelineSize == 0 ? obj.addr + obj.size - 1 : obj.addr + obj.size;
        //     if (end - (end % cachelineSize) != obj.addr - (obj.addr % cachelineSize)) {
        //         acc[end - (end % cachelineSize)] ? acc[end - (end % cachelineSize)].push({type: obj.type, allocTs: obj.allocTs, freeTs: obj.freeTs}) :
        //                                             acc[end - (end % cachelineSize)] = [{type: obj.type, allocTs: obj.allocTs, freeTs: obj.freeTs}];
        //     }
        //     return acc;
        // }, {});
        
        // for (let obj of objects) {
        //     let endpts = [obj.addr - (obj.addr % cachelineSize)];
        //     let end = (obj.addr + obj.size) % cachelineSize == 0 ? obj.addr + obj.size - 1 : obj.addr + obj.size;
        //     if (end - (end % cachelineSize) != obj.addr - (obj.addr % cachelineSize)) {
        //         endpts.push(end - (end % cachelineSize));
        //     }

        //     this.#typeCount[obj.type] += 1;
        //     let seenTypes = new Set();
        //     for(let cl of endpts) {  
        //         let ind = binarySearchSuccessor(clMap[cl].map((d) => d.freeTs), obj.allocTs)[1];
                
        //         while (ind < clMap[cl].length && seenTypes.size < types.length) {
        //             if (clMap[cl][ind].allocTs < obj.freeTs && !seenTypes.has(clMap[cl][ind].type) && !(clMap[cl][ind].allocTs == obj.allocTs && clMap[cl][ind].freeTs == obj.freeTs)) {
        //                 this.#colocCount[obj.type][clMap[cl][ind].type] += 1;
        //                 seenTypes.add(clMap[cl][ind]);
        //             }
        //             ind++;
        //         }
        //     }
        // }
    }

    getColocRatios(type) {
        return Object.keys(this.#colocCount[type]).map((otherType) => [otherType, this.#colocCount[type][otherType]]); // / this.#typeCount[type]]);
    }
}

export function trimString(str, maxChars) {
    return str.length > maxChars ? str.substring(0, maxChars - 4) + '...' : str;
}

export function typeInfoPopup() {
    let x = '0px',
        y = '0px',
        width = 100,
        height = 150,
        lineSpace = 10,
        type = undefined,
        maxChars = 12,
        textLines = [];

    function drawPopup(selection) {
        let outText = [];
        for (let i = 0; i < textLines.length; i++) {
            outText.push(`${trimString(textLines[i][0], maxChars)}:`);
            outText.push(`${textLines[i][1].toFixed(3)}\n`);
        }

        let textGroup = selection.style('transform', `translate(${x}, ${y})`);

        textGroup.append('rect')
            .attr('x', 0)
            .attr('y', -15)
            .attr('width', width)
            .attr('height', (Math.floor(outText.length / 2) + 1)*lineSpace + 15)
            .style('fill', 'white');

        textGroup.append('text')
            .attr('font-family', 'monospace')
            .style('text-decoration', 'underline')
            .style('font-size', '10px')
            .text(`Cacheline colocation for ${trimString(type, maxChars)} \n`);

        textGroup.selectAll('.statText')
            .data(outText)
            .enter()
            .append('text')
            .attr('class', 'statText')
            .attr('font-family', 'monospace')
            .attr('x', (d, i) => i % 2 == 0 ? 5 : 130)
            .attr('y', (d, i) => (Math.floor(i / 2) + 1)*lineSpace)
            .style('font-size', '10px')
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

    drawPopup.textLines = function(val) {
        if (!arguments) return textLines;
        textLines = val;
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

    return drawPopup;
}