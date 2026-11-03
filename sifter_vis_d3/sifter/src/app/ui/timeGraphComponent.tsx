'use client';
import { forwardRef, useEffect, useMemo, useRef, useState } from "react";
import * as d3 from 'd3';
import './componentStyles.scss';
import { TypeToColourMap } from "./appShared";
import { Tooltip } from "@mui/material";
import { formatElapsedTimestamp } from './timestampClock';

export interface SizePoint { bucket: number; size: number }
interface LineData { [tp: string]: SizePoint[] }
const LINE_GRAPH_WIDTH = 700;
const LINE_GRAPH_HEIGHT = 300;
const LINE_GRAPH_Y_AXIS_WIDTH = 50;
const LINE_GRAPH_X_AXIS_HEIGHT = 30;
const LINE_GRAPH_LINE_STROKE_WIDTH = 2;
const LINE_GRAPH_RIGHT_PAD = 10;
export const SIZE_UNITS = [1, 2**10, 2**20, 2**30];
export const SIZE_UNIT_SUFF = ['B', 'KiB', 'MiB', 'GiB'];

function getUnitIndex(size: number): number {
    return Math.min(SIZE_UNITS.length - 1, Math.max(0, Math.floor(Math.log2(Math.max(1, size)) / 10)));
}
function getSizeTickValues(maxSize: number, maxValues: number): number[] {
    const unit = SIZE_UNITS[getUnitIndex(maxSize)];
    const step = Math.max(Math.floor(maxSize / unit / maxValues), 1) * unit;
    return d3.range(step, maxSize + 1, step);
}

// React owns the path: new data redraws even if the type's key is unchanged.
const LinePath = forwardRef(function LinePath({ lineData, colour, lineGenerator, ...props }: {
    lineData: SizePoint[];
    colour: d3.RGBColor | d3.HSLColor | null;
    lineGenerator: d3.Line<SizePoint>;
}, ref: React.ForwardedRef<SVGGElement>) {
    return <g {...props} ref={ref}><path className='timeGraphLine'
        stroke={colour?.toString() ?? 'gray'} d={lineGenerator(lineData) ?? undefined} /></g>;
});

export default function TimeGraph({ lines, colourOfType, currTs, setCurrTs, timeRange,
                                   lineVis, timestampHz }: {
    lines: LineData;
    colourOfType: TypeToColourMap;
    currTs: number;
    setCurrTs: (a: number) => void;
    timeRange: {min: number; max: number};
    numBuckets: number;
    lineVis: {[tp: string]: boolean};
    timestampHz: number | null;
}) {
    const svgRef = useRef<SVGSVGElement>(null);
    const thumbRef = useRef<SVGCircleElement>(null);
    const [zoomTransform, setZoomTransform] = useState(d3.zoomIdentity);
    // LINES includes both endpoint buckets, so its length is one more than
    // the final bucket index. Use the index to align the graph and time cursor.
    const lastBucket = useMemo(() => Math.max(1,
        d3.max(Object.values(lines), points => d3.max(points, point => point.bucket)) ?? 1), [lines]);
    const baseX = useMemo(() => d3.scaleLinear().domain([0, lastBucket])
        .range([0, LINE_GRAPH_WIDTH]), [lastBucket]);
    const bucketToTs = useMemo(() => d3.scaleLinear().domain([0, lastBucket])
        .range([timeRange.min, timeRange.max]), [lastBucket, timeRange.min, timeRange.max]);
    const xScale = useMemo(() => zoomTransform.rescaleX(baseX), [zoomTransform, baseX]);
    const maxSize = useMemo(() => d3.max(Object.keys(lines).filter(tp => lineVis[tp]),
        tp => d3.max(lines[tp], point => point.size)) ?? 0, [lines, lineVis]);
    const yScale = useMemo(() => d3.scaleLinear().domain([maxSize ? maxSize * 1.05 : 1, 0])
        .range([0, LINE_GRAPH_HEIGHT - 5]), [maxSize]);
    const lineGenerator = useMemo(() => d3.line<SizePoint>()
        .x(point => xScale(point.bucket)).y(point => yScale(point.size)), [xScale, yScale]);
    const xAxis = useMemo(() => d3.axisBottom(xScale).tickSize(9).ticks(5)
        .tickFormat(value => formatElapsedTimestamp(bucketToTs(Number(value)) - timeRange.min, timestampHz)),
        [xScale, bucketToTs, timeRange.min, timestampHz]);
    const yAxis = useMemo(() => {
        const unit = getUnitIndex(maxSize);
        return d3.axisLeft(yScale).tickSize(3).tickValues(getSizeTickValues(maxSize || 1, 6))
            .tickFormat(value => `${Number(value) / SIZE_UNITS[unit]} ${SIZE_UNIT_SUFF[unit]}`);
    }, [yScale, maxSize]);
    const thumbX = LINE_GRAPH_Y_AXIS_WIDTH + Math.max(0, Math.min(LINE_GRAPH_WIDTH,
        xScale(bucketToTs.invert(currTs))));

    useEffect(() => {
        const svg = d3.select(svgRef.current!);
        svg.select<SVGGElement>('#xAxisGroup').call(xAxis);
        svg.select<SVGGElement>('#yAxisGroup').call(yAxis);
    }, [xAxis, yAxis]);

    useEffect(() => {
        const svg = d3.select(svgRef.current!);
        const zoom = d3.zoom<SVGSVGElement, unknown>().scaleExtent([1, 10])
            .extent([[LINE_GRAPH_Y_AXIS_WIDTH, 0], [LINE_GRAPH_Y_AXIS_WIDTH + LINE_GRAPH_WIDTH, LINE_GRAPH_HEIGHT]])
            .translateExtent([[LINE_GRAPH_Y_AXIS_WIDTH, 0], [LINE_GRAPH_Y_AXIS_WIDTH + LINE_GRAPH_WIDTH, LINE_GRAPH_HEIGHT]])
            .on('zoom', event => {
                // Zoom coordinates are in the SVG; the lines start after the y axis.
                setZoomTransform(d3.zoomIdentity.translate(
                    event.transform.x + (event.transform.k - 1) * LINE_GRAPH_Y_AXIS_WIDTH, 0)
                    .scale(event.transform.k));
            });
        svg.call(zoom).call(zoom.transform, d3.zoomIdentity);
        return () => { svg.on('.zoom', null); };
    }, [lastBucket, timeRange.min, timeRange.max]);

    useEffect(() => {
        const thumb = d3.select(thumbRef.current!);
        const drag = d3.drag<SVGCircleElement, unknown>()
            .on('start', event => event.sourceEvent.stopPropagation())
            .on('drag', event => {
                const x = Math.max(0, Math.min(LINE_GRAPH_WIDTH, event.x - LINE_GRAPH_Y_AXIS_WIDTH));
                setCurrTs(Math.max(timeRange.min, Math.min(timeRange.max, bucketToTs(xScale.invert(x)))));
            });
        thumb.call(drag);
        return () => { thumb.on('.drag', null); };
    }, [xScale, bucketToTs, setCurrTs, timeRange.min, timeRange.max]);

    return <div id='timeGraphContainer'><svg id='timeGraphSVG' ref={svgRef}
        viewBox={`0 0 ${LINE_GRAPH_WIDTH + LINE_GRAPH_Y_AXIS_WIDTH + LINE_GRAPH_LINE_STROKE_WIDTH / 2 + LINE_GRAPH_RIGHT_PAD} ${LINE_GRAPH_HEIGHT + LINE_GRAPH_X_AXIS_HEIGHT + LINE_GRAPH_LINE_STROKE_WIDTH / 2}`}>
        <defs><clipPath id='timeGraphClip'><rect width={LINE_GRAPH_WIDTH} height={LINE_GRAPH_HEIGHT} /></clipPath></defs>
        <g id='linesGroup' clipPath='url(#timeGraphClip)'>
            {Object.keys(lines).filter(tp => lineVis[tp]).map(tp =>
                <Tooltip key={tp} title={tp} followCursor placement='top'>
                    <LinePath lineData={lines[tp]} colour={colourOfType[tp]} lineGenerator={lineGenerator} />
                </Tooltip>)}
        </g>
        <g id='xAxisGroup' /><g id='yAxisGroup' />
        <circle id='timeThumb' ref={thumbRef} cx={thumbX} cy='0' r='8' fill='white' />
    </svg></div>;
}
