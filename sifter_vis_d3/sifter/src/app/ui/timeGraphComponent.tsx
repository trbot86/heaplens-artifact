'use client';
import { forwardRef, MutableRefObject, useEffect, useMemo, useRef, useState } from "react";
import * as d3 from 'd3';
import './componentStyles.scss';
import { TypeToColourMap } from "../vispanels/page";
import { Slider, styled, Tooltip } from "@mui/material";

export interface SizePoint {
    bucket: number,
    size: number
}

interface LineData {
    [tp: string]: SizePoint[]
};

const LINE_GRAPH_WIDTH = 700;
const LINE_GRAPH_HEIGHT = 300;
const LINE_GRAPH_Y_AXIS_WIDTH = 50;
const LINE_GRAPH_X_AXIS_HEIGHT = 30;
const LINE_GRAPH_LINE_STROKE_WIDTH = 2;
const LINE_GRAPH_RIGHT_PAD = 10;
const SLIDER_THUMB_WIDTH = 12;
const SLIDER_THUMB_HEIGHT = 15;
export const SIZE_UNITS = [
    1,
    2**10,
    2**20,
    2**30
];
export const SIZE_UNIT_SUFF = [
    'B',
    'KiB',
    'MiB',
    'GiB'
];

// function getSampledLine(sortedLine: SizePoint[], maxPointsPerLine: number): SizePoint[] {
//     // const sortedLine = line.toSorted((a, b) => a.ts - b.ts);
//     const retLine: SizePoint[] = [];
//     const minTs = sortedLine[0].ts;
//     const maxTs = sortedLine[sortedLine.length - 1].ts;
//     const quantum: number = (maxTs - minTs) / maxPointsPerLine;
    
//     let prevDiv = 0,
//         prevSize = 0;
//     sortedLine.forEach((pt) => {
//         const currDiv = Math.ceil(pt.ts / quantum);
//         if (currDiv > prevDiv || sortedLine.length <= maxPointsPerLine) {
//             retLine.push({ts: pt.ts, size: prevSize});
//             retLine.push(pt);
//             prevDiv = currDiv;
//             prevSize = pt.size;
//         }
//     });

//     return retLine;
// }

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

function convertLinePtXToTs(linePtX: number, minTs: number, maxTs: number, numLinePtsX: number) {
    const sizeOfLinePtX = Math.max((maxTs - minTs) / numLinePtsX, 1);
    return (linePtX * sizeOfLinePtX) + minTs;
}

function convertTsToLinePtX(currTs: number, ) {

}

const CustomSlider = styled(Slider)({
    '& .MuiSlider-thumb': {
        height: SLIDER_THUMB_HEIGHT,
        width: SLIDER_THUMB_WIDTH,
        transition: 'none',
        borderRadius: '0',
        backgroundColor: '#e0e0e0',
        clipPath: 'polygon(50% 0%, 100% 25%, 100% 100%, 0% 100%, 0% 25%)',
    },
});

function TimeSlider({ xScale, currTs, numLinePtsX, setCurrTs, timeRange, numBuckets } :
    {
        xScale: d3.ScaleLinear<number, number, never>,
        currTs: number,
        numLinePtsX: number,
        setCurrTs: (a: number) => void,
        timeRange: {min: number, max: number},
        numBuckets: number
    }) {
    return(
        <div id='sliderGroup' >
            <CustomSlider
                value={currTs}
                track={false}
                min={convertLinePtXToTs(xScale.invert(0), timeRange.min, timeRange.max, numLinePtsX)}
                max={convertLinePtXToTs(xScale.invert(LINE_GRAPH_WIDTH), timeRange.min, timeRange.max, numLinePtsX)}
                step={Math.max(Math.floor(timeRange.max - timeRange.min) / numBuckets, 1)}
                onChange={(e, val) => {
                    console.log(`Timestamp: ${val}`);
                    setCurrTs(val);
                }} />
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

const LinePath = forwardRef(({ lineData, colour, lineGenerator, ...props } :
    {
        lineData: SizePoint[],
        colour: d3.RGBColor | d3.HSLColor | null,
        lineGenerator: d3.Line<SizePoint> | null
    }, ref) => {
    const pathRef = useRef(null);

    useEffect(() => {
        d3.select(pathRef.current)
            .datum(lineData)
            .attr('d', lineGenerator);
    }, []);

    return (
        <g 
            {...props}
            ref={ref} >
            <path
                className='timeGraphLine'
                stroke={colour ? colour.toString() : 'gray'}
                ref={pathRef} />
        </g>
    );
});

function ZoomableLineGraph({ lines, colourOfType, currTs, setCurrTs, timeRange,
                             numBuckets, lineVis } :
    {
        lines: LineData,
        colourOfType: TypeToColourMap,
        currTs: number,
        setCurrTs: (a: number) => void,
        timeRange: {min: number, max: number},
        numBuckets: number,
        lineVis: {[tp: string]: boolean},
    }) {
    const SVGref = useRef(null);
    const [thumbX, setThumbX] = useState<number>(LINE_GRAPH_Y_AXIS_WIDTH);
    // const xScale = useRef<d3.ScaleLinear<number, number, never> | null>(null);
    const lineGenerator = useRef<d3.Line<SizePoint> | null>(null);
    const [xScale, setXScale] = useState<d3.ScaleLinear<number, number, never> | null>(null);

    // const xScaleOrig = d3.scaleLinear().domain([timeRange.min, timeRange.max])
    //                                 .range([0, LINE_GRAPH_WIDTH]);
    const numLinePtsX = Object.values(lines)[0].length
    const xScaleOrig = d3.scaleLinear().domain([0, numLinePtsX])
                                    .range([0, LINE_GRAPH_WIDTH]);

    const xPtToTsScale = d3.scaleLinear().domain([0, numLinePtsX])
                                    .range([timeRange.min, timeRange.max]);
    
    // if (!xScale.current)
    //     xScale.current = xScaleOrig;
    const maxSize = useMemo(() => d3.max(Object.keys(lines).filter((tp) => lineVis[tp]), (tp: string) => {
                                    return d3.max(lines[tp], (pt: SizePoint) => pt.size);
                                    }), [lineVis]);
    const yScale = useMemo(() => d3.scaleLinear().domain([maxSize ? maxSize*1.05 : 1, 0])
                                    .range([0, LINE_GRAPH_HEIGHT-5]), [maxSize]);

    let xAxis: d3.Axis<d3.NumberValue>;
    if (!xScale) {
        lineGenerator.current = d3.line((pt: SizePoint) => xScaleOrig(pt.bucket), (pt: SizePoint) => yScale(pt.size));
        xAxis = d3.axisBottom(xScaleOrig).tickSize(9).tickValues(new Array(10).fill(0).map((d, i) => i*Math.floor(numLinePtsX / 10)))
            .tickFormat((d) => `${((xPtToTsScale(d) - timeRange.min) / 1000000000).toFixed(2)} s`);
    }
    else {
        lineGenerator.current = d3.line((pt: SizePoint) => xScale(pt.bucket), (pt: SizePoint) => yScale(pt.size));
        xAxis = d3.axisBottom(xScale).tickSize(9).tickValues(new Array(10).fill(0).map((d, i) => i*Math.floor(numLinePtsX / 10)))
            .tickFormat((d) => `${((xPtToTsScale(d) - timeRange.min) / 1000000000).toFixed(2)} s`);
    }
    
    const yAxis = useMemo(() => d3.axisLeft(yScale).tickSize(3).tickValues(getSizeTickValues(maxSize ? maxSize : 1, 6))
        .tickFormat((d: number) => `${d / SIZE_UNITS[getUnitIndex(maxSize ? maxSize : 1)]} ${SIZE_UNIT_SUFF[getUnitIndex(maxSize ? maxSize : 1)]}`)
    , [yScale]);

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

        const zoom = d3.zoom()
            .scaleExtent([1, 10]) // TODO: get rid of constants
            .translateExtent([[0, 0], [LINE_GRAPH_WIDTH + LINE_GRAPH_RIGHT_PAD + LINE_GRAPH_Y_AXIS_WIDTH + (LINE_GRAPH_LINE_STROKE_WIDTH / 2), LINE_GRAPH_HEIGHT + 31]])
            .on('zoom', (event) => {
                const newXScale = event.transform.rescaleX(xScaleOrig);
                setXScale(() => newXScale);
                setThumbX(Math.max(LINE_GRAPH_Y_AXIS_WIDTH, Math.min(newXScale(xPtToTsScale.invert(currTs)), LINE_GRAPH_WIDTH + LINE_GRAPH_Y_AXIS_WIDTH)));
                // xScale.current = event.transform.rescaleX(xScaleOrig);
            });
        
        d3.select(SVGref.current)
            .call(zoom);

        const thumbDrag = d3.drag()
            .on("start", (event) => event.sourceEvent.stopPropagation()) // Prevent zooming when dragging
            .on("drag", (event) => {
                const newX = Math.max(LINE_GRAPH_Y_AXIS_WIDTH, Math.min(event.x, LINE_GRAPH_WIDTH + LINE_GRAPH_Y_AXIS_WIDTH));
                let newTs = 0;
                if (xScale) {
                    newTs = xPtToTsScale(xScale.invert(newX - LINE_GRAPH_Y_AXIS_WIDTH));
                }
                else {
                    newTs = xPtToTsScale(xScaleOrig.invert(newX - LINE_GRAPH_Y_AXIS_WIDTH));
                }
                setCurrTs(newTs);
                setThumbX(newX);
            });

        d3.select('#timeThumb')
            .call(thumbDrag);
    }, [lines, xScale, yAxis]);
    
    return (
        <div
            id='timeGraphContainer' >
            <svg
                id='timeGraphSVG'
                ref={SVGref}
                viewBox={`0 0 ${LINE_GRAPH_WIDTH + LINE_GRAPH_Y_AXIS_WIDTH + (LINE_GRAPH_LINE_STROKE_WIDTH / 2) + LINE_GRAPH_RIGHT_PAD} ${LINE_GRAPH_HEIGHT + LINE_GRAPH_X_AXIS_HEIGHT + (LINE_GRAPH_LINE_STROKE_WIDTH / 2)}`} >
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
                    clipPath='url(#timeGraphClip)' >
                    {
                        Object.keys(lines).filter((tp) => lineVis[tp])
                                        .map((tp) =>   <Tooltip 
                                                            key={tp}
                                                            title={tp}
                                                            followCursor
                                                            placement='top' >
                                                            <LinePath
                                                                lineData={lines[tp]}
                                                                colour={colourOfType[tp]}
                                                                lineGenerator={lineGenerator.current} />
                                                        </Tooltip>)
                    }
                </g>
                <g id='xAxisGroup' />
                <g id='yAxisGroup' />
                <circle
                    id='timeThumb'
                    cx={thumbX}
                    cy='0'
                    r='8'
                    fill='white' />
            </svg>
        </div>
    );
}

export default function TimeGraph({ lines, colourOfType, currTs, setCurrTs, timeRange,
                                    numBuckets, lineVis } :
    {
        lines: LineData,
        colourOfType: TypeToColourMap,
        currTs: number,
        setCurrTs: (a: number) => void,
        timeRange: {min: number, max: number},
        numBuckets: number,
        lineVis: {[tp: string]: boolean}
    }) {
    // const sampledAndSortedLines = Object.keys(lines).reduce((retLines: LineData, tp: string) => {
    //     retLines[tp] = getSampledLine(lines[tp], maxPointsPerLine);
    //     return retLines;
    // }, {});

    // Object.keys(sampledAndSortedLines).forEach((tp) => {
    //     if (sampledAndSortedLines[tp][0].ts > timeRange.min) {
    //         sampledAndSortedLines[tp].unshift({ts: timeRange.min, size: 0});
    //     }
    //     if (sampledAndSortedLines[tp][sampledAndSortedLines[tp].length - 1].ts < timeRange.max) {
    //         sampledAndSortedLines[tp].push({ts: timeRange.max, size: sampledAndSortedLines[tp][sampledAndSortedLines[tp].length - 1].size});
    //     }
    // });

    return (
        <ZoomableLineGraph
            lines={lines}
            colourOfType={colourOfType}
            currTs={currTs}
            setCurrTs={setCurrTs}
            timeRange={timeRange}
            numBuckets={numBuckets}
            lineVis={lineVis} />
    );
}