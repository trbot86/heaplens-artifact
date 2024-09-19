'use client';
import { MutableRefObject, useEffect, useMemo, useRef, useState } from "react";
import * as d3 from 'd3';
import './componentStyles.scss';
import { TypeToColourMap } from "../vispanels/page";
import { Slider, styled, Tooltip } from "@mui/material";

interface SizePoint {
    ts: number,
    size: number
}

interface LineData {
    [tp: string]: SizePoint[]
};

const LINE_GRAPH_WIDTH = 640;
const LINE_GRAPH_HEIGHT = 330;
const LINE_GRAPH_Y_AXIS_WIDTH = 50;
const LINE_GRAPH_X_AXIS_HEIGHT = 30;
const LINE_GRAPH_LINE_STROKE_WIDTH = 2;
const LINE_GRAPH_RIGHT_PAD = 10;
const SLIDER_THUMB_WIDTH = 12;
const SLIDER_THUMB_HEIGHT = 15;
const SIZE_UNITS = [
    1,
    2**10,
    2**20,
    2**30
];
const SIZE_UNIT_SUFF = [
    'B',
    'KiB',
    'MiB',
    'GiB'
];

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

function getTsTickValues(minTs: number, maxTs: number, maxValues: number): number[] {
    const ret = [];
    for (let i = minTs + Math.max((maxTs - minTs) / maxValues, 1); i <= maxTs - Math.max((maxTs - minTs) / maxValues, 1); i += Math.max((maxTs - minTs) / maxValues, 1))
        ret.push(Math.floor(i));
    return ret;
}

function getUnitIndex(size: number): number {
    return Math.floor(Math.log2(size) / 10);
}

function getSizeTickValues(maxSize: number, maxValues: number): number[] {
    const unitIdx = getUnitIndex(maxSize);
    const mult = Math.max(Math.floor(Math.floor(maxSize / SIZE_UNITS[unitIdx]) / maxValues), 1);
    const ret = [];
    for (let i = mult*SIZE_UNITS[unitIdx]; i <= maxSize; i += mult*SIZE_UNITS[unitIdx]) {
        ret.push(i);
    }
    return ret;
}

const CustomSlider = styled(Slider)({
    '& .MuiSlider-thumb': {
        height: SLIDER_THUMB_HEIGHT,
        width: SLIDER_THUMB_WIDTH,
        borderRadius: '0',
        backgroundColor: '#e0e0e0',
        clipPath: 'polygon(50% 0%, 100% 25%, 100% 100%, 0% 100%, 0% 25%)',
    },
});

function TimeSlider({ xScale, currTs, setCurrTs } :
    {
        xScale: d3.ScaleLinear<number, number, never>,
        currTs: number,
        setCurrTs: (a: number) => void
    }) {
    // TODO change step below to bucket size
    return(
        <div id='sliderGroup' >
            <CustomSlider
                value={currTs}
                track={false}
                min={xScale.invert(0)}
                max={xScale.invert(LINE_GRAPH_WIDTH)}
                step={1}
                onChange={(e, val) => setCurrTs(val)} />
        </div>
        // <g
        //     id='sliderGroup'
        //     ref={ref} >
        //     <rect 
        //         id='sliderBar'
        //         x={0}
        //         y={0}
        //         width={LINE_GRAPH_WIDTH}
        //         height={3}
        //         rx='2px' />
        //     <rect
        //         id='sliderThumb'
        //         x={0}
        //         y={0}
        //         width={SLIDER_THUMB_WIDTH}
        //         height={SLIDER_THUMB_HEIGHT} />
        // </g>
    );
}

function LinePath({ lineData, colour, lineGenerator } :
    {
        lineData: SizePoint[],
        colour: d3.RGBColor | d3.HSLColor | null,
        lineGenerator: d3.Line<SizePoint> | null
    }) {
    const pathRef = useRef(null);

    useEffect(() => {
        d3.select(pathRef.current)
            .datum(lineData)
            .attr('d', lineGenerator);
    }, []);

    return (
        <path 
            className='timeGraphLine'
            stroke={colour ? colour.toString() : 'gray'}
            ref={pathRef} />
    );
}

function ZoomableLineGraph({ lines, colourOfType, currTs, setCurrTs } :
    {
        lines: LineData,
        colourOfType: TypeToColourMap,
        currTs: number,
        setCurrTs: (a: number) => void
    }) {
    const SVGref = useRef(null);
    // const xScale = useRef<d3.ScaleLinear<number, number, never> | null>(null);
    const lineGenerator = useRef<d3.Line<SizePoint> | null>(null);
    const [xScale, setXScale] = useState<d3.ScaleLinear<number, number, never> | null>(null);

    const minTs         = d3.min(Object.keys(lines), (tp: string) => lines[tp][0].ts);
    const maxTs         = d3.max(Object.keys(lines), (tp: string) => lines[tp][lines[tp].length - 1].ts);
    const xScaleOrig    = d3.scaleLinear().domain([minTs ? minTs : 0, maxTs ? maxTs : 1])
                                    .range([0, LINE_GRAPH_WIDTH]);
    
    // if (!xScale.current)
    //     xScale.current = xScaleOrig;
    const maxSize       = d3.max(Object.keys(lines), (tp: string) => {
                            return d3.max(lines[tp], (pt: SizePoint) => pt.size);
                        });
    const yScale        = d3.scaleLinear().domain([maxSize ? maxSize*1.05 : 1, 0])
                                    .range([0, LINE_GRAPH_HEIGHT]);

    let xAxis: d3.Axis<d3.NumberValue>;
    if (!xScale) {
        lineGenerator.current = d3.line((pt: SizePoint) => xScaleOrig(pt.ts), (pt: SizePoint) => yScale(pt.size));
        xAxis = d3.axisBottom(xScaleOrig).tickSize(9).tickValues(getTsTickValues(minTs ? minTs : 0, maxTs ? maxTs : 1, 10))
            .tickFormat((d) => `${(parseInt(d) / 100).toFixed(2)} s`);
    }
    else {
        lineGenerator.current = d3.line((pt: SizePoint) => xScale(pt.ts), (pt: SizePoint) => yScale(pt.size));
        xAxis = d3.axisBottom(xScale).tickSize(9).tickValues(getTsTickValues(minTs ? minTs : 0, maxTs ? maxTs : 1, 10))
            .tickFormat((d) => `${(parseInt(d) / 100).toFixed(2)} s`);
    }
    
    const yAxis = d3.axisLeft(yScale).tickSize(3).tickValues(getSizeTickValues(maxSize ? maxSize : 1, 6))
        .tickFormat((d) => `${d} ${SIZE_UNIT_SUFF[getUnitIndex(maxSize ? maxSize : 1)]}`);

    useEffect(() => {
        d3.select('#xAxisGroup').call(xAxis);
        d3.select('#yAxisGroup').call(yAxis);

        if (xScale) {
            d3.select('#xAxisGroup')
                .call(xAxis.scale(xScale));
                // .call(xAxis.scale(xScale.current));
            d3.selectAll('.timeGraphLine')
                .attr('d', lineGenerator.current);
                // .attr('d', d3.line((pt: SizePoint) => xScale.current(pt.ts), (pt: SizePoint) => yScale(pt.size)));
        }

        // d3.select(SVGref.current)
        //     .select('#linesGroup')
        //     .selectAll('.timeGraphLine')
        //     .data(Object.keys(lines))
        //     .enter()
        //     .append('path')
        //     .attr('class', 'timeGraphLine')
        //     .attr('stroke', (tp: string) => colourOfType[tp] ? colourOfType[tp].toString() : 'gray')
        //     .datum((tp: string) => lines[tp])
        //     .attr('d', lineGenerator);

        const zoom = d3.zoom()
            .scaleExtent([1, 10]) // TODO: get rid of constants
            .translateExtent([[0, 0], [LINE_GRAPH_WIDTH + LINE_GRAPH_RIGHT_PAD + LINE_GRAPH_Y_AXIS_WIDTH + (LINE_GRAPH_LINE_STROKE_WIDTH / 2), LINE_GRAPH_HEIGHT + 31]])
            .on('zoom', (event) => {
                setXScale(() => event.transform.rescaleX(xScaleOrig));
                // xScale.current = event.transform.rescaleX(xScaleOrig);
            });
        
        d3.select(SVGref.current)
            .call(zoom);
    }, [lines, xScale]);
    
    return (
        <div>
            <svg
                id='timeGraphSVG'
                ref={SVGref}
                width={LINE_GRAPH_WIDTH + LINE_GRAPH_Y_AXIS_WIDTH + (LINE_GRAPH_LINE_STROKE_WIDTH / 2) + LINE_GRAPH_RIGHT_PAD}
                height={LINE_GRAPH_HEIGHT + LINE_GRAPH_X_AXIS_HEIGHT + (LINE_GRAPH_LINE_STROKE_WIDTH / 2)} >
                <defs>
                    <clipPath id='timeGraphClip'>
                        <rect
                            id='timeGraphClipRect'
                            width={LINE_GRAPH_WIDTH}
                            height={LINE_GRAPH_HEIGHT} />
                    </clipPath>
                </defs>
                <g 
                    id='linesGroup'
                    clipPath={'url(#timeGraphClip)'} >
                    {
                        Object.keys(lines).map((tp) => <LinePath
                                                            key={tp}
                                                            lineData={lines[tp]}
                                                            colour={colourOfType[tp]}
                                                            lineGenerator={lineGenerator.current} />)
                    }
                </g>
                <g id='xAxisGroup' />
                <g id='yAxisGroup' />
                {/* <TimeSlider 
                    minTs={minTs ? minTs : 0}
                    maxTs={maxTs ? maxTs : 1}
                    xScale={xScale ? xScale : xScaleOrig}
                    currTs={currTs}
                    setCurrTs={setCurrTs} /> */}
            </svg>
            <TimeSlider 
                xScale={xScale ? xScale : xScaleOrig}
                currTs={currTs}
                setCurrTs={setCurrTs} />
        </div>
    );
}

export default function TimeGraph({ lines, maxPointsPerLine, colourOfType, currTs, setCurrTs } :
    {
        lines: LineData,
        maxPointsPerLine: number,
        colourOfType: TypeToColourMap,
        currTs: number,
        setCurrTs: (a: number) => void
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
                colourOfType={colourOfType}
                currTs={currTs}
                setCurrTs={setCurrTs} />
        </div>
    );
}