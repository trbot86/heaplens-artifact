'use client';
import { useEffect, useRef } from "react";
import * as d3 from 'd3';
import { TypeToColourMap } from "../vispanels/page";

interface SizePoint {
    ts: number,
    size: number
}

interface LineData {
    [tp: string]: SizePoint[]
};

const LINE_GRAPH_WIDTH = 520;
const LINE_GRAPH_HEIGHT = 350;

function getSampledAndSortedLine(line: SizePoint[], maxPointsPerLine: number): SizePoint[] {
    const sortedLine = line.toSorted((a, b) => a.ts - b.ts);
    const retLine: SizePoint[] = [];
    const minTs = line[0].ts;
    const maxTs = line[line.length - 1].ts;
    const quantum: number = (maxTs - minTs) / maxPointsPerLine;
    
    let prevDiv = 0,
        prevSize = 0;
    sortedLine.forEach((pt) => {
        const currDiv = Math.ceil(pt.ts / quantum);
        if (currDiv > prevDiv || line.length <= maxPointsPerLine) {
            retLine.push({ts: pt.ts, size: prevSize});
            retLine.push(pt);
            prevDiv = currDiv;
            prevSize = pt.size;
        }
    });

    return retLine;
}

function ZoomableLineGraph({ lines, colourOfType } :
    {
        lines: LineData,
        colourOfType: TypeToColourMap
    }) {
    const ref = useRef(null);
    const minTs = d3.min(Object.keys(lines), (tp: string) => lines[tp][0].ts);
    const maxTs = d3.max(Object.keys(lines), (tp: string) => lines[tp][lines[tp].length - 1].ts);
    const xScale = d3.scaleLinear().domain([minTs ? minTs : 0, maxTs ? maxTs : 1])
                                    .range([0, LINE_GRAPH_WIDTH]);
    const maxSize = d3.max(Object.keys(lines), (tp: string) => {
        return d3.max(lines[tp], (pt: SizePoint) => pt.size);
    });
    const yScale = d3.scaleLinear().domain([0, maxSize ? maxSize*1.05 : 1])
                                    .range([0, LINE_GRAPH_HEIGHT]);

    useEffect(() => {
        Object.keys(lines).forEach((tp: string) => {
            d3.select(ref.current)
                .select('#linesGroup')
                .append('path')
                .datum(lines[tp])
                .attr('class', 'timeGraphLine')
                .attr('stroke', colourOfType[tp])
                .attr('d', d3.line((pt: SizePoint) => xScale(pt.ts), (pt: SizePoint) => yScale(pt.size)));
        });

        const zoom = d3.zoom()
            .scaleExtent([1, 6]) // TODO: get rid of constants
            .translateExtent([[minTs ? minTs : 0, 0], [maxTs ? maxTs : 1, maxSize ? maxSize : 1]])
            .on('zoom', (event) => {
                const newXScale = event.rescaleX(xScale);
                d3.selectAll('.timeGraphLine')
                    .attr('d', d3.line((pt: SizePoint) => newXScale(pt.ts), (pt: SizePoint) => yScale(pt.size)));
            });
        
        d3.select(ref.current)
            .call(zoom);
    }, [lines]);
    
    return (
        <svg
            width={LINE_GRAPH_WIDTH}
            height={LINE_GRAPH_HEIGHT}
            ref={ref} >
            <g id='linesGroup' />
        </svg>
    );
}

export default function TimeGraph({ lines, maxPointsPerLine, colourOfType } :
    {
        lines: LineData,
        maxPointsPerLine: number,
        colourOfType: TypeToColourMap
    }) {

    const sampledAndSortedLines = Object.keys(lines).reduce((retLines: LineData, tp: string) => {
        retLines[tp] = getSampledAndSortedLine(lines[tp], maxPointsPerLine);
        return retLines;
    }, {});
    const minTs: number = Object.keys(sampledAndSortedLines)
            .reduce((min: number, tp: string) => Math.min(min, lines[tp][0].ts), Infinity);
    const maxTs: number = Object.keys(sampledAndSortedLines)
            .reduce((max: number, tp: string) => Math.max(max, lines[tp][lines[tp].length - 1].ts), 0);
    Object.keys(sampledAndSortedLines).forEach((tp) => {
        if (sampledAndSortedLines[tp][0].ts > minTs) {
            sampledAndSortedLines[tp].unshift({ts: minTs, size: 0});
        }
        if (sampledAndSortedLines[tp][sampledAndSortedLines[tp].length - 1].ts < maxTs) {
            sampledAndSortedLines[tp].push({ts: maxTs, size: sampledAndSortedLines[tp][sampledAndSortedLines[tp].length - 1].size});
        }
    });

    return (
        <div>
            <ZoomableLineGraph
                lines={sampledAndSortedLines}
                colourOfType={colourOfType} />
        </div>
    );
}