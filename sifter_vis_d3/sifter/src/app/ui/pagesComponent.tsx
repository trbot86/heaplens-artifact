'use client';
import { cache, forwardRef, Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './componentStyles.scss';
import * as d3 from 'd3';
import { getData, getSubtypeName, TypeToColourMap } from '../vispanels/page';
import { Check, Dangerous, DangerousOutlined, LocalFireDepartment, LocalFireDepartmentOutlined, PlaylistAdd, PlaylistPlay, RadioButtonChecked, SentimentDissatisfied, SentimentDissatisfiedOutlined, SentimentDissatisfiedRounded, SentimentDissatisfiedSharp, SentimentDissatisfiedTwoTone, SentimentVeryDissatisfied, SentimentVeryDissatisfiedOutlined, SportsMma, SportsMmaOutlined, ZoomInMap, ZoomOutMap } from '@mui/icons-material';
import { Box, Checkbox, Icon, IconButton, Stack, ToggleButton, ToggleButtonGroup, Tooltip } from '@mui/material';
import { SubtypeEntry } from './legendComponent';
import { HtmlTooltip } from './cacheSetComponent';
import Grid from '@mui/material/Grid2';
import { theme } from '../page';

interface MemoryObject {
    file: string | null,
    line: number,
    size: number,
    addr: number,
    actualAddr?: number,
    allocTs: number,
    freeTs: number | null,
    type: string | null
}

interface PageContents {
    events: MemoryObject[],
    cluster: number
}

interface PageMap {
    [ addr: number ]: PageContents
}

interface PerfEntry {
    hitm: number,
    stores: number,
    loads: number
}

interface ClustersInfo {
    [c: number]: {'pages': number[], 'size': number}
}

export interface PerfMap {
    addrs: {[ addr: number ]: PerfEntry},
    avgAccesses: number
}

const PAGE_CARD_SVG_WIDTH = 540;
const PAGE_CARD_SVG_HEIGHT = 50;
const PAGE_CARD_BORDER_WIDTH = PAGE_CARD_SVG_WIDTH - 10;
const OBJECT_LAYOUT_WIDTH = 300;
const OBJECT_LAYOUT_HEIGHT = 300;
const OBJECT_LAYOUT_MARGIN = 32;
const NUM_SLOTS_HUGEPAGE = 128;
const SEL_AND_ZOOM_GRANULARITY = 4096;
const MAX_HITM_ADDRS = 20;
const PERF_INDICATOR_SIZE = 4;

const SNAPSHOT_INTERVALS = 8; // number of intervals between earliest event and latest event
const SNAPSHOT_FILE_NAME = 'page_layout_snapshots.txt';

interface SnapshotObject {
    type: string,
    start_addr: number,
    size: number,
    alloc_ts: number,
    free_ts: number | null,
    actual_addr?: number
}

interface SnapshotPage {
    page_addr: number,
    cluster: number,
    objects: SnapshotObject[]
}

function getSnapshotTimes(pages: PageMap): number[] {
    const allEvents = Object.values(pages).flatMap((page) => page.events);
    if (allEvents.length === 0) {
        return [0];
    }
    const minTs = Math.min(...allEvents.map((e) => e.allocTs));
    const maxTs = Math.max(...allEvents.map((e) => e.allocTs));
    const step = (maxTs - minTs) / SNAPSHOT_INTERVALS;
    return Array.from({ length: SNAPSHOT_INTERVALS + 1 }, (_, i) => Number((minTs + step * i).toFixed(3)));
}

function serializeFieldsData(fieldsData: { [tp: string]: SubtypeEntry[] }): string {
    const lines: string[] = ['FIELDS_DATA:'];
    const types = Object.keys(fieldsData).sort();
    if (types.length === 0) {
        lines.push('  NONE');
        return lines.join('\n');
    }
    for (const type of types) {
        lines.push(`- type: ${type}`);
        const entries = fieldsData[type];
        if (!entries || entries.length === 0) {
            lines.push('  subtypes: []');
            continue;
        }
        lines.push('  subtypes:');
        for (const entry of entries) {
            lines.push(`    - name: ${entry.name}`);
            lines.push(`      subtype: ${entry.subtype}`);
            lines.push(`      offset: ${entry.offset}`);
            lines.push(`      size: ${entry.size}`);
        }
    }
    return lines.join('\n');
}

function serializeClusterData(clustersData: ClustersInfo): string {
    const lines: string[] = ['CLUSTERS:'];
    const clusterIds = Object.keys(clustersData).map((k) => parseInt(k)).sort((a, b) => a - b);
    if (clusterIds.length === 0) {
        lines.push('  NONE');
        return lines.join('\n');
    }
    for (const clusterId of clusterIds) {
        const cluster = clustersData[clusterId];
        const pageEntries = cluster.pages;
        let pageList: number[] = [];
        if (Array.isArray(pageEntries)) {
            pageList = pageEntries;
        } else if (pageEntries && typeof pageEntries[Symbol.iterator] === 'function') {
            pageList = Array.from(pageEntries as Iterable<number>);
        } else if (pageEntries && typeof pageEntries === 'object') {
            pageList = Object.values(pageEntries as Record<string, number>);
        }
        pageList = pageList.sort((a, b) => a - b);
        lines.push(`- cluster_id: ${clusterId}`);
        lines.push(`  size: ${cluster.size}`);
        lines.push(`  page_count: ${pageList.length}`);
        lines.push(`  pages: [${pageList.join(', ')}]`);
    }
    return lines.join('\n');
}

function buildPageSnapshotText(pages: PageMap, clustersData: ClustersInfo, fieldsData: { [tp: string]: SubtypeEntry[] }, pageSize: number): string {
    const pageAddrs = Object.keys(pages).map((addr) => parseInt(addr)).sort((a, b) => a - b);
    const snapshotTimes = getSnapshotTimes(pages);
    const lines: string[] = [];

    lines.push('MEMORY PAGE LAYOUT SNAPSHOTS');
    lines.push(`SNAPSHOT_INTERVALS: ${SNAPSHOT_INTERVALS}`);
    lines.push(`PAGE_SIZE: ${pageSize}`);
    lines.push(`TOTAL_PAGES: ${pageAddrs.length}`);
    lines.push(`GENERATED_AT: ${new Date().toISOString()}`);
    lines.push('');
    lines.push('');
    lines.push(serializeFieldsData(fieldsData));
    lines.push('');
    lines.push(serializeClusterData(clustersData));
    lines.push('');
    lines.push('SNAPSHOTS:');

    for (let i = 0; i < snapshotTimes.length; i++) {
        const ts = snapshotTimes[i];
        lines.push(`- snapshot_index: ${i}`);
        lines.push(`  time: ${ts}`);
        lines.push('  pages:');
        for (const pageAddr of pageAddrs) {
            const page = pages[pageAddr];
            const visibleObjects = page.events.filter((obj) => obj.allocTs <= ts && (obj.freeTs === null || obj.freeTs >= ts));
            lines.push(`  - page_addr: ${pageAddr}`);
            lines.push(`    cluster: ${page.cluster}`);
            lines.push(`    object_count: ${visibleObjects.length}`);
            if (visibleObjects.length === 0) {
                lines.push('    objects: []');
                continue;
            }
            lines.push('    objects:');
            for (const obj of visibleObjects) {
                lines.push('      -');
                lines.push(`        type: ${obj.type ?? 'UNKNOWN'}`);
                lines.push(`        size: ${obj.size}`);
                lines.push(`        actual_addr: ${obj.actualAddr ?? obj.addr}`);
            }
        }
    }

    return lines.join('\n');
}

function downloadTextFile(text: string, fileName: string): void {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

/*  TODO: Currently, this function just looks at the starting address of each
    event, without considering events crossing slot/page boundaries. This
    should be fine to give an approximate overview in most cases. */
function getSlotDataPerBucket(  events: MemoryObject[], pageAddr: number, pageSize: number, numSlots: number,
                                numBuckets: number, getBucketIdx: (ts: number) => number,
                                pageVis: {[tp: string]: boolean}) {
    const ret: number[][] = Array(numBuckets + 2).fill(undefined).map(() => Array(numSlots).fill(0));
    const slotSize = Math.floor(pageSize / numSlots);

    events.filter((event) => event.type && pageVis[event.type])
        .forEach((event) => {
        const eventAddr = event.actualAddr ? event.actualAddr : event.addr;
        if (Math.floor(eventAddr / pageSize) == Math.floor(pageAddr / pageSize)) {
            const eventSlot = Math.floor((eventAddr % pageSize) / slotSize);
            ret[getBucketIdx(event.allocTs)][eventSlot] += event.size;
            if (event.freeTs)
                ret[getBucketIdx(event.freeTs)][eventSlot] -= event.size;
        }
    });

    ret.forEach((bucket, i) => {
        bucket.forEach((slot, j) => {
            if (i != 0) {
                ret[i][j] = slot + ret[i-1][j];
            }
        });
    });
    return ret;
}

const SplitBlock = forwardRef(({ obj, colourOfType, viewStartAddr, cacheLineSize, xScale, yScale,
                                 expanded, viewSize, invisible, ...props } : 
    {
        obj: MemoryObject,
        colourOfType: TypeToColourMap,
        viewStartAddr: number,
        viewSize: number,
        cacheLineSize: number,
        xScale: d3.ScaleLinear<number, number, never>,
        yScale: d3.ScaleLinear<number, number, never>,
        expanded: boolean,
        invisible?: boolean
    }, ref) => {
    return (
        <g
            {...props}
            ref={ref}
            visibility={invisible ? 'hidden' : 'visible'} >
            {/* onMouseEnter={() => setHoveredType(obj.type)}
            onMouseLeave={() => setHoveredType(null)} > */}
            
            {/* Start chunk of data object */}
            <>
                <rect
                    // className={`objectBlock${obj.type == hoveredType ? ' objectBlockHovered' : ''}`}
                    x={xScale(obj.addr % cacheLineSize)}
                    y={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize))}
                    width={xScale(Math.min(obj.size, cacheLineSize - (obj.addr % cacheLineSize)))}
                    height={yScale(1) - yScale(0)}
                    fill={obj.type ? colourOfType[obj.type]?.toString() : 'gray'}
                    fillOpacity={expanded ? 0.2 : 1.0} />
                {
                obj.size
                - (cacheLineSize - (obj.addr % cacheLineSize)) // size of first chunk
                    <= 0 &&
                <line
                    className='objDelimLine'
                    x1={xScale((obj.addr % cacheLineSize) + obj.size)}
                    x2={xScale((obj.addr % cacheLineSize) + obj.size)}
                    y1={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize))}
                    y2={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize))
                        + yScale(1) - yScale(0) // height of one CL
                    } />
                }
            </>
            
            {/* Middle chunk of data object */}
            {
            Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize) > 0 &&
            <>
                <rect
                    // className={`objectBlock${obj.type == hoveredType ? ' objectBlockHovered' : ''}`}
                    x={xScale(0)}
                    y={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize) + 1)}
                    width={xScale(cacheLineSize)}
                    height={yScale(Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)) - yScale(0)}
                    fill={obj.type ? colourOfType[obj.type]?.toString() : 'gray'}
                    fillOpacity={expanded ? 0.2 : 1.0} />
                {
                obj.size
                - (cacheLineSize - (obj.addr % cacheLineSize)) // size of first chunk
                - Math.max(0, Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)*cacheLineSize) // size of middle chunk
                    <= 0 &&
                <line
                    className='objDelimLine'
                    x1={xScale(cacheLineSize)}
                    x2={xScale(cacheLineSize)}
                    y1={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize) + 1) // y of middle chunk
                        + yScale(Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)) - yScale(0) // height of middle chunk
                        - (yScale(1) - yScale(0)) // height of one CL
                    }
                    y2={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize) + 1) // y of middle chunk
                        + yScale(Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)) - yScale(0) // height of middle chunk
                    } />
                }
            </>
            }
            
            {/* Last chunk of data object */}
            {
            obj.size
            - (cacheLineSize - (obj.addr % cacheLineSize)) // size of first chunk
            - Math.max(0, Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)*cacheLineSize) // size of middle chunk
                > 0 &&
            <>
                <rect
                    // className={`objectBlock${obj.type == hoveredType ? ' objectBlockHovered' : ''}`}
                    x={xScale(0)}
                    y={
                        yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize) + 1 // y of middle chunk
                            + Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)) // height of middle chunk
                    }
                    width={
                        xScale(Math.min(cacheLineSize, obj.size
                            - (cacheLineSize - (obj.addr % cacheLineSize)) // size of first chunk
                            - Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)*cacheLineSize)) // size of middle chunk
                    }
                    height={yScale(1) - yScale(0)}
                    fill={obj.type ? colourOfType[obj.type]?.toString() : 'gray'}
                    fillOpacity={expanded ? 0.2 : 1.0} />
                {
                (obj.addr + obj.size <= viewStartAddr + viewSize) &&
                <line
                    className='objDelimLine'
                    x1={xScale(((obj.addr + obj.size - 1) % cacheLineSize) + 1)}
                    x2={xScale(((obj.addr + obj.size - 1) % cacheLineSize) + 1)}
                    y1={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize) + 1 // y of middle chunk
                        + Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)) // height of middle chunk
                    }
                    y2={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize) + 1 // y of middle chunk
                        + Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)) // height of middle chunk
                        + yScale(1) - yScale(0)
                    } />
                }
            </>
            }

            {/* Start line of object */}
            {
            (obj.actualAddr === undefined || obj.actualAddr >= viewStartAddr) &&
            <line
                className='objDelimLine'
                x1={xScale(obj.addr % cacheLineSize)}
                x2={xScale(obj.addr % cacheLineSize)}
                y1={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize))}
                y2={yScale(Math.floor((obj.addr - viewStartAddr) / cacheLineSize)) + yScale(1) - yScale(0)} />
            }
        </g>
    );
});

function HoverableSplitBlock({  event, colourOfType, viewStartAddr, viewSize,
                                cacheLineSize, xScale, yScale, expandedTypes,
                                fieldsData, pageVis, currTs } : 
    {
        event: MemoryObject,
        colourOfType: TypeToColourMap,
        viewSize: number,
        viewStartAddr: number,
        cacheLineSize: number,
        fieldsData: {[tp: string]: SubtypeEntry[]},
        expandedTypes: {[tp: string]: boolean},
        pageVis: {[tp: string]: boolean},
        xScale: d3.ScaleLinear<number, number, never>,
        yScale: d3.ScaleLinear<number, number, never>,
        currTs: number
    }) {
    return (
        <>
        {
        event.allocTs <= currTs && (event.freeTs == null || event.freeTs >= currTs) && (event.type && pageVis[event.type]) &&
        <>
            <HtmlTooltip
                title={
                <table>
                    <tbody>
                        <tr>
                            <td>type:</td>
                            <td>{event.type}</td>
                        </tr>
                        <tr>
                            <td>file:</td>
                            <td>{event.file}</td>
                        </tr>
                        <tr>
                            <td>line:</td>
                            <td>{event.line}</td>
                        </tr>
                    </tbody>
                </table>
                }
                placement='left' >
                <SplitBlock
                    obj={event}
                    colourOfType={colourOfType}
                    viewStartAddr={viewStartAddr}
                    viewSize={viewSize}
                    cacheLineSize={cacheLineSize}
                    xScale={xScale}
                    yScale={yScale}
                    expanded={event.type ? expandedTypes[event.type.replace(/\s+/g, '')] : false} />
            </HtmlTooltip>
            {
            (event.type && fieldsData[event.type.replace(/\s+/g, '')]) &&
            <>
            {
                fieldsData[event.type.replace(/\s+/g, '')].map((field) =>   
                                                        <HtmlTooltip 
                                                            title={
                                                            <table>
                                                                <tbody>
                                                                    <tr>
                                                                        <td>type:</td>
                                                                        <td>{field.subtype}</td>
                                                                    </tr>
                                                                    <tr>
                                                                        <td>name:</td>
                                                                        <td>{field.name}</td>
                                                                    </tr>
                                                                </tbody>
                                                            </table>
                                                            }
                                                            key={`${event.addr}-${event.allocTs}-${field.name}`}
                                                            placement='left' >
                                                            <SplitBlock
                                                                obj={{
                                                                    file: event.file,
                                                                    line: event.line,
                                                                    size: field.size,
                                                                    addr: (event.actualAddr ? event.actualAddr : event.addr) + field.offset,
                                                                    allocTs: event.allocTs,
                                                                    freeTs: event.freeTs,
                                                                    type: event.type ? getSubtypeName(event.type.replace(/\s+/g, ''), field.subtype) : field.subtype
                                                                }}
                                                                colourOfType={colourOfType}
                                                                viewStartAddr={viewStartAddr}
                                                                viewSize={viewSize}
                                                                cacheLineSize={cacheLineSize}
                                                                xScale={xScale}
                                                                yScale={yScale}
                                                                expanded={false}
                                                                invisible={!expandedTypes[event.type.replace(/\s+/g, '')]} />
                                                        </HtmlTooltip>)
            }
            </>
            }
        </>
        }
        </>
    );
}

function ObjectLayout({ data, colourOfType, viewSize, cacheLineSize, fieldsData, expandedTypes,
                        setExpandedTypes, viewStartAddr, showHot, showHitm, pageVis, perf, currTs,
                        hitmCutoff } :
    {
        data: MemoryObject[],
        colourOfType: TypeToColourMap,
        viewSize: number,
        cacheLineSize: number,
        fieldsData: {[tp: string]: SubtypeEntry[]},
        expandedTypes: {[tp: string]: boolean},
        setExpandedTypes: (a: {[tp: string]: boolean}) => void,
        viewStartAddr: number,
        showHot: boolean,
        showHitm: boolean,
        pageVis: {[tp: string]: boolean},
        perf: PerfMap,
        hitmCutoff: number,
        currTs: number
    }) {
    const objSVG = useRef(null);
    // const [hoveredType, setHoveredType] = useState<string | null>(null);

    // console.log(`Here is data in object layout:`);
    // console.log(data);
    // console.log('Here is perf in object layout:');
    // console.log(perf);

    const xScale = d3.scaleLinear().domain([0, cacheLineSize]).range([0, OBJECT_LAYOUT_WIDTH]);
    const yScaleOrig = d3.scaleLinear().domain([0, Math.floor(viewSize / cacheLineSize)]).range([0, (OBJECT_LAYOUT_HEIGHT / cacheLineSize)*(viewSize / cacheLineSize)]);
    const [yScale, setYScale] = useState<d3.ScaleLinear<number, number, never>>(() => yScaleOrig);
    const xAxis = d3.axisTop(xScale)
                    .tickValues(d3.range(0, cacheLineSize + 1, Math.floor(cacheLineSize / 8))).tickFormat(d3.format('d'));
    const yAxis = d3.axisLeft(yScale)
                    .tickValues(d3.range(0, Math.floor(viewSize / cacheLineSize) + 1, 8)).tickFormat(d3.format('d'));
    const yAxisGrid = d3.axisLeft(yScale).tickSize(-OBJECT_LAYOUT_WIDTH)
                        .tickValues(d3.range(0, Math.floor(viewSize / cacheLineSize) + 1, 1)).tickFormat('');

    useEffect(() => {
        const curObjSVG = d3.select(objSVG.current);
        
        curObjSVG.select('#objectXAxisGroup')
            .call(xAxis);
        curObjSVG.select('#objectYAxisGroup')
            .call(yAxis);
        curObjSVG.select('#objectYAxisGridGroup')
            .call(yAxisGrid);
    }, [cacheLineSize, viewSize, yAxis]);

    useEffect(() => {
        const zoom = d3.zoom()
            .scaleExtent([1, 6])
            .translateExtent([[0, -OBJECT_LAYOUT_MARGIN], [OBJECT_LAYOUT_WIDTH, (OBJECT_LAYOUT_HEIGHT / cacheLineSize)*(viewSize / cacheLineSize) + OBJECT_LAYOUT_MARGIN]]) // I think the +30 comes from the relative position of the object svg in the css, but not sure
            .on('zoom', (event) => {
                setYScale(() => event.transform.rescaleY(yScaleOrig));
            });
        d3.select(objSVG.current)
            .call(zoom);
    }, [viewSize]);
    
    return (
        <div id='objectLayoutDiv' >
            <svg
                id='objectSVG'
                viewBox={`${-OBJECT_LAYOUT_MARGIN} ${-OBJECT_LAYOUT_MARGIN} ${OBJECT_LAYOUT_WIDTH + 2*OBJECT_LAYOUT_MARGIN} ${OBJECT_LAYOUT_HEIGHT + 2*OBJECT_LAYOUT_MARGIN}`}
                ref={objSVG} >
                <defs>
                    <clipPath id='objectLayoutClip' >
                        <rect
                            id='objectLayoutClipRect'
                            x={0}
                            y={0}
                            width={OBJECT_LAYOUT_WIDTH}
                            height={OBJECT_LAYOUT_HEIGHT} />
                    </clipPath>
                    <clipPath id='objectLayoutYAxisClip' >
                        <rect
                            id='objectLayoutYAxisClip'
                            x={-OBJECT_LAYOUT_MARGIN}
                            y={-5}
                            width={OBJECT_LAYOUT_WIDTH}
                            height={OBJECT_LAYOUT_HEIGHT + 10} />
                    </clipPath>
                </defs>
                {
                viewSize > 0 ?
                <>
                    <g
                        id='objectGroup'
                        clipPath='url(#objectLayoutClip)' >
                        {
                            data.sort((a: MemoryObject, b: MemoryObject) => a.allocTs - b.allocTs)
                                .map((event: MemoryObject) =>   <HoverableSplitBlock
                                                                    key={`${event.addr}-${event.allocTs}`}
                                                                    event={event}
                                                                    colourOfType={colourOfType}
                                                                    viewStartAddr={viewStartAddr}
                                                                    viewSize={viewSize}
                                                                    cacheLineSize={cacheLineSize}
                                                                    xScale={xScale}
                                                                    yScale={yScale}
                                                                    expandedTypes={expandedTypes}
                                                                    fieldsData={fieldsData}
                                                                    pageVis={pageVis}
                                                                    currTs={currTs}
                                                                     />)
                        }
                        <g id='objectYAxisGridGroup' />
                    </g>
                    <g id='objectXAxisGroup' />
                    <g
                        id='objectYAxisGroup'
                        clipPath='url(#objectLayoutYAxisClip)' />
                    {
                    (showHitm || showHot) &&
                    <g 
                        className='objectPerfGroup' >
                        {
                            Object.keys(perf.addrs)
                                .map((perfAddr) => parseInt(perfAddr))
                                .filter((perfAddr) => perfAddr >= viewStartAddr && perfAddr <= viewStartAddr + viewSize &&
                                                        ((perf.addrs[perfAddr].hitm >= hitmCutoff && showHitm) || (perf.addrs[perfAddr].loads + perf.addrs[perfAddr].stores >= perf.avgAccesses && showHot)))
                                .map((perfAddr) =>  <g>
                                                        <circle
                                                            className='objectPerfIcon' 
                                                            cx={OBJECT_LAYOUT_WIDTH + 2*PERF_INDICATOR_SIZE}
                                                            cy={`${yScale(Math.floor((perfAddr - viewStartAddr) / cacheLineSize)) + ((yScale(1) - yScale(0)) / 2)}`}
                                                            r={`${PERF_INDICATOR_SIZE}`}
                                                            fill={theme.palette.primary.main} >
                                                            <title>{`HITM: ${perf.addrs[perfAddr].hitm.toFixed(2)}%\nloads: ${perf.addrs[perfAddr].loads}\nstores: ${perf.addrs[perfAddr].stores}`}</title>
                                                        </circle>
                                                        <rect 
                                                            className='perfHighlight'
                                                            x={0}
                                                            y={yScale(Math.floor((perfAddr - viewStartAddr) / cacheLineSize))}
                                                            width={xScale(cacheLineSize)}
                                                            height={yScale(1) - yScale(0)}
                                                            fill={theme.palette.primary.main} />
                                                    </g>)
                        }
                    </g>
                    }
                </>
                :
                <Tooltip
                    title={'Click and drag pages to select area'}
                    followCursor
                    placement='top' >
                    <PlaylistAdd sx={{opacity: 0.1}} />
                </Tooltip>
                }
            </svg>
        </div>
    );
}

function PageHeader({ sortMode, setSortMode, pageSize, selSize, setSelSize,
                      zoomedSize, setZoomedSize, showHot, setShowHot, showHitm,
                      setShowHitm, selAddr, setZoomedAddr } : 
    {
        sortMode: 'addr' | 'cluster',
        setSortMode: (a: 'addr' | 'cluster') => void,
        pageSize: number,
        selSize: number,
        setSelSize: (a: number) => void,
        zoomedSize: number,
        setZoomedSize: (a: number) => void,
        setZoomedAddr: (a: number) => void,
        showHot: boolean,
        setShowHot: (a: boolean) => void,
        showHitm: boolean,
        setShowHitm: (a: boolean) => void,
        selAddr: number
    }) {
    return (
        <div id='pageHeaderGroup' >
            <Tooltip 
                title={showHot ? 'Hide hot cache lines' : 'Show hot cache lines'}
                placement='bottom' >
                <Checkbox 
                    id='hotSelectorCheck'
                    icon={<LocalFireDepartmentOutlined />}
                    checkedIcon={<LocalFireDepartment />}
                    onChange={() => {
                        setShowHot(!showHot);
                    }} />
            </Tooltip>
            <Tooltip 
                title={showHitm ? 'Hide HITMs' : 'Show HITMs'}
                placement='bottom' >
                <Checkbox 
                    id='contentionCheck'
                    icon={<SportsMmaOutlined />}
                    checkedIcon={<SportsMma />}
                    onChange={() => {
                        setShowHitm(!showHitm);
                    }} />
            </Tooltip>
            {
            pageSize == 2 * 2**20 &&
            <>
                <Tooltip 
                    title='Zoom out'
                    placement='bottom' >
                    <IconButton
                        disabled={zoomedSize == 0}
                        onClick={() => {
                            setZoomedSize(0);
                            setSelSize(0);
                        }} >
                        <ZoomOutMap />
                    </IconButton>
                </Tooltip>
                <Tooltip 
                    title='Zoom in'
                    placement='bottom' >
                    <IconButton
                        disabled={selSize == 0}
                        onClick={() => {
                            setZoomedAddr(selAddr);
                            setZoomedSize(selSize);
                            setSelSize(0);
                        }} >
                        <ZoomInMap />
                    </IconButton>
                </Tooltip>
            </>
            }

            <ToggleButtonGroup 
                id='pageSortButtons'
                exclusive
                value={sortMode}
                size='small'
                onChange={(e, val) => setSortMode(val)} >
                <ToggleButton value='addr' >
                    Address
                </ToggleButton>
                <ToggleButton value='cluster' >
                    Cluster
                </ToggleButton>
            </ToggleButtonGroup>
        </div>
    );
}

const SizeIndicator = forwardRef(({ clusterSize, sumClusterSizes, maxClusterSize, ...props } :
    {
        clusterSize: number,
        sumClusterSizes: number,
        maxClusterSize: number
    }, ref) => {

    const   maxWidth = 36,
            minWidth = 6,
            colScale = d3.scaleLinear([1, sumClusterSizes], ['#abc9b3', '#c9b5b8']),
            widthScale = d3.scaleLinear([1, maxClusterSize], [minWidth, maxWidth]);

    return (
        <div
            className='sizeIndicatorDiv'
            ref={ref}
            {...props} >
            <svg className='sizeIndicatorSvg' >
                <rect
                    className='sizeIndicatorRect'
                    data-clustersize={clusterSize}
                    data-sumclustersizes={sumClusterSizes}
                    data-maxclustersize={maxClusterSize}
                    width={`${widthScale(clusterSize)}px`}
                    fill={colScale(clusterSize)} />
            </svg>
        </div>
    );
});

function PageObject({ x, y, width, fill, currTs, allocTs, freeTs, isVis } : 
    {
        x: number,
        y: number,
        width: number,
        fill: string,
        currTs: number,
        allocTs: number,
        freeTs: number | null,
        isVis: boolean
    }) {
    return (
        <>
        {
            allocTs <= currTs && (freeTs == null || freeTs >= currTs) && isVis &&
            <rect
                className='pageCardObject'
                x={x}
                y={y}
                width={width}
                fill={fill} />
        }
        </>
    );
}

function PageCard({ addr, selAddr, pageSize, objectData, setSelPageAddr, colourOfType,
                    showHot, pageVis, showHitm, perf, currTs, hitmCutoff } :
    {
        addr: number,
        selAddr: number,
        pageSize: number,
        objectData: PageContents,
        setSelPageAddr: (a: number) => void,
        colourOfType: TypeToColourMap,
        showHot: boolean,
        showHitm: boolean,
        perf: PerfMap,
        hitmCutoff: number,
        pageVis: {[tp: string]: boolean},
        currTs: number
    }) {
    // const ref = useRef(null);
    const pageScale = useMemo(() => d3.scaleLinear().domain([0, pageSize]).range([0, PAGE_CARD_BORDER_WIDTH]), [pageSize]);
    
    return (
        <div className='pageCardDiv' >
            <svg 
                className='pageCard'
                viewBox={`0 0 ${PAGE_CARD_SVG_WIDTH} ${PAGE_CARD_SVG_HEIGHT}`} >
                {/* // ref={ref} > */}
                <rect className='pageCardBorder pageCardShadow' />
                <rect
                    className={`pageCardBorder pageCardBack${selAddr == addr ? ' pageCardSelected' : ''}`}
                    onClick={() => setSelPageAddr(addr)} />
                <g
                    className='pageCardClipGroup' >
                    {
                        objectData.events.sort((a: MemoryObject, b: MemoryObject) => a.allocTs - b.allocTs)
                            .map((ev) =>   <PageObject
                                                key={`${ev.addr}-${ev.allocTs}`}
                                                // className='pageCardObject'
                                                x={pageScale(ev.addr % pageSize)}
                                                y={0}
                                                width={pageScale(ev.size)}
                                                fill={ev.type && colourOfType[ev.type] ? colourOfType[ev.type].toString() : 'black'}
                                                isVis={(ev.type && pageVis[ev.type]) == true}
                                                currTs={currTs}
                                                allocTs={ev.allocTs}
                                                freeTs={ev.freeTs} />)
                    }
                </g>
                {
                (showHitm || showHot) &&
                <g 
                    className='pagePerfIcons' >
                    {
                        Object.keys(perf.addrs)
                            .map((perfAddr) => parseInt(perfAddr))
                            .filter((perfAddr) => perfAddr >= addr && perfAddr < addr + pageSize &&
                                                    ((perf.addrs[perfAddr].hitm >= hitmCutoff && showHitm) || (perf.addrs[perfAddr].loads + perf.addrs[perfAddr].stores >= perf.avgAccesses && showHot)))
                            .map((perfAddr) => <circle 
                                                    cx={`${pageScale(perfAddr % pageSize) + 2*PERF_INDICATOR_SIZE + 1}`} // TODO: not sure why the extra shift is needed here
                                                    cy={`${PAGE_CARD_SVG_HEIGHT / 2}`}
                                                    r={`${PERF_INDICATOR_SIZE}`}
                                                    fill={theme.palette.primary.main} />)
                    }
                </g>
                }
            </svg>
        </div>
    );
}

function HugePageCard({ addr, selAddr, pageSize, slotSize, slotData, setSelPageAddr,
                        colourOfType, zoomedSize, setZoomedSize, selSize, setSelSize,
                        objData, zoomedAddr } :
    {
        addr: number,
        selAddr: number,
        pageSize: number,
        slotSize: number,
        objData: PageContents,
        slotData: number[],
        setSelPageAddr: (a: number) => void,
        colourOfType: TypeToColourMap,
        zoomedSize: number,
        setZoomedSize: (a: number) => void,
        selSize: number,
        setSelSize: (a: number) => void,
        zoomedAddr: number
    }) {
    const ref = useRef(null);
    const brushRef = useRef(null);
    const pageScale = zoomedSize == 0 ? d3.scaleLinear().domain([0, pageSize]).range([0, PAGE_CARD_BORDER_WIDTH])
                                        : d3.scaleLinear().domain([0, zoomedSize]).range([0, PAGE_CARD_BORDER_WIDTH]);
    // const pageBrush = d3.brushX()
    //                     .on('end', handleBrushEnd(pageScale));

    // const handleBrushEnd = useCallback(
    //     function(e: d3.D3BrushEvent<null> | null) {
    //         console.log(`Handle brush end page scale domain: ${pageScale.domain()[0]}, ${pageScale.domain()[1]}`);
    //         if (e && e.selection) {
    //             const startAddr = (zoomedSize > 0 ? zoomedAddr : addr) + pageScale.invert(Math.min(PAGE_CARD_BORDER_WIDTH, Math.max(0, e.selection[0])));
    //             const endAddr = (zoomedSize > 0 ? zoomedAddr : addr) + pageScale.invert(Math.min(PAGE_CARD_BORDER_WIDTH, Math.max(0, e.selection[1])));
    //             const startRounded = Math.round(startAddr / SEL_AND_ZOOM_GRANULARITY)*SEL_AND_ZOOM_GRANULARITY;
    //             const endRounded = Math.round(endAddr / SEL_AND_ZOOM_GRANULARITY)*SEL_AND_ZOOM_GRANULARITY;
    //             setSelPageAddr(startRounded);
    //             setSelSize(endRounded - startRounded);
    //             console.log(`startRounded=${startRounded}, endRounded=${endRounded}, selSize=${endRounded - startRounded}`);
    //         }
    //     }, [pageSize]);

    if (zoomedSize > 0) {
        console.log('HERE IS THE OBJ DATA IN ZOOMED HUGE PAGE:');
        console.log(objData);
        console.log(`Here is the domain of the page scale: ${pageScale.domain()[0]}, ${pageScale.domain()[1]}`);
    }

    const pageBrush = useMemo(() => d3.brushX()
        .on('end', 
            function(e: d3.D3BrushEvent<null> | null) {
                console.log(`Handle brush end page scale domain: ${pageScale.domain()[0]}, ${pageScale.domain()[1]}`);
                if (e && e.selection) {
                    console.log('Here is the selection:');
                    console.log(e.selection);
                    const startAddr = (zoomedSize > 0 ? zoomedAddr : addr) + pageScale.invert(Math.min(PAGE_CARD_BORDER_WIDTH, Math.max(0, e.selection[0])));
                    const endAddr = (zoomedSize > 0 ? zoomedAddr : addr) + pageScale.invert(Math.min(PAGE_CARD_BORDER_WIDTH, Math.max(0, e.selection[1])));
                    const startRounded = Math.round(startAddr / SEL_AND_ZOOM_GRANULARITY)*SEL_AND_ZOOM_GRANULARITY;
                    const endRounded = Math.round(endAddr / SEL_AND_ZOOM_GRANULARITY)*SEL_AND_ZOOM_GRANULARITY;
                    setSelPageAddr(startRounded);
                    setSelSize(endRounded - startRounded);
                    console.log(`startRounded=${startRounded}, endRounded=${endRounded}, selSize=${endRounded - startRounded}`);
                }
            }), [pageScale]);

    // console.log(`pageScale domain: ${pageScale.domain()[0]}, ${pageScale.domain()[1]}`);
    const colScale = useMemo(() => d3.scaleLinear().domain([0, slotSize]).range(['rgb(51, 51, 51)', '#e33a2b']), []);

    useEffect(() => {
        d3.select(brushRef.current)
            .call(pageBrush);
    }, [pageScale]);

    useEffect(() => {
        // console.log(`My addr: ${addr}, page num: ${Math.floor(addr / pageSize)}, selAddr page num: ${Math.floor(selAddr / pageSize)}, selAddr: ${selAddr}`);
        if (Math.floor(selAddr / pageSize) != Math.floor(addr / pageSize) && brushRef.current) {
            // console.log(`Bad useEffect, addr: ${addr}, selAddr: ${selAddr}, selSize: ${selSize}`);
            // console.log('Here is brushRef:');
            // console.log(brushRef);
            d3.select(brushRef.current)
                .call(pageBrush.clear);
        }
    }, [selAddr]);

    useEffect(() => {
        // console.log('Here is pageBrush.current.clear');
        // console.log(pageBrush.current.clear);
        // console.log(brushRef.current);
        d3.select(brushRef.current)
            .call(pageBrush.clear);
        d3.select(brushRef.current)
            .call(pageBrush);
    }, [zoomedSize]);

    return (
        <svg
            className={`pageCard hugePageCard${zoomedSize > 0 ? ' zoomedHugePageCard' : ''}`}
            viewBox={`0 0 ${PAGE_CARD_SVG_WIDTH} ${(zoomedSize > 0 ? 4 : 1)*PAGE_CARD_SVG_HEIGHT}`} >
            <rect className='hugePageCardBack' />
            <g
                className='pageCardClipGroup'
                ref={ref} >
                {
                zoomedSize == 0 ?
                <>
                    {
                    slotData.map((slot, i) =>   <rect
                                                    key={`hp-${addr}-${i}`}
                                                    className='pageCardObject slotObject'
                                                    x={pageScale(i*slotSize)}
                                                    y={0}
                                                    width={pageScale(slotSize)}
                                                    fill={colScale(slot).toString()} />)
                    }
                </>
                :
                <>
                    {
                    objData.events.map((ev) =>  <rect
                                                    key={`${ev.addr}-${ev.allocTs}`}
                                                    className='pageCardObject slotObject'
                                                    x={pageScale(ev.addr - zoomedAddr)}
                                                    y={0}
                                                    width={pageScale(ev.size)}
                                                    fill={ev.type && colourOfType[ev.type] ? colourOfType[ev.type].toString() : 'black'} />)
                    }
                </>
                }
                <g 
                    className='brushGroup'
                    ref={brushRef} />
            </g>
        </svg>
    );
}

function PageRow({  pageSize, addr, data, currTs, selAddr, colourOfType, 
                    setSelPageAddr, pageVis, showHot, showHitm, perf,
                    clusterSize, sumClusterSizes, maxClusterSize,
                    hitmCutoff } : 
    {
        clusterSize: number,
        sumClusterSizes: number,
        maxClusterSize: number,
        pageSize: number,
        addr: number,
        data: PageContents,
        currTs: number,
        selAddr: number,
        colourOfType: TypeToColourMap,
        setSelPageAddr: (a: number) => void,
        setFocusData: (a: PageContents) => void,
        pageVis: {[tp: string]: boolean},
        showHot: boolean,
        showHitm: boolean,
        perf: PerfMap,
        hitmCutoff: number
    }) {
    // const [currData, setCurrData] = useState(data);

    // useEffect(() => {
    //     const filtered = {
    //         events: data.events.filter((obj) => obj.allocTs <= currTs && 
    //                                             (obj.freeTs == null || obj.freeTs >= currTs)
    //                                             && obj.type
    //                                             && pageVis[obj.type]),
    //         cluster: data.cluster
    //     };
    //     setCurrData(filtered);
    //     if (selAddr == addr) {
    //         setFocusData(filtered);
    //     }
    // }, [currTs, selAddr, data, pageVis]);

    return (
        <div className='pageRow' >
            <PageCard 
                addr={addr}
                selAddr={selAddr}
                pageSize={pageSize}
                objectData={data}
                setSelPageAddr={setSelPageAddr}
                colourOfType={colourOfType}
                showHot={showHot}
                showHitm={showHitm}
                perf={perf}
                pageVis={pageVis}
                currTs={currTs}
                hitmCutoff={hitmCutoff} />
            <Grid
                container
                rowSpacing={0.3}
                columnSpacing={0.8}
                className='pageRowLabel' >
                <Grid size={12} >
                    <div className='pageLabelDiv' >{`0x${addr.toString(16)}`}</div>
                </Grid>
                
                <Grid size={5} >
                    <div className='clusterLabelDiv' >{`cluster: ${data.cluster}`}</div>
                </Grid>
                <Grid size={4} >
                    <Tooltip
                        placement='right'
                        title={`${clusterSize} of ${sumClusterSizes} pages`} >
                        <SizeIndicator
                            clusterSize={clusterSize}
                            sumClusterSizes={sumClusterSizes}
                            maxClusterSize={maxClusterSize} />
                    </Tooltip>
                </Grid>
            </Grid>
            {
            (addr == selAddr) &&
            <div id='selPageIcon' >
                <RadioButtonChecked fontSize='small' />
            </div>
            }
        </div>
    );
}

function HugePageRow({ pageSize, addr, data, currTs, selAddr, colourOfType, setSelPageAddr,
                       numBuckets, setFocusData, setZoomedSize, getBucketIdx, selSize,
                       setSelSize, pageVis, zoomedSize, zoomedAddr, setZoomedAddr,
                       clusterSize, sumClusterSizes, maxClusterSize } : 
    {
        clusterSize: number,
        sumClusterSizes: number,
        maxClusterSize: number,
        pageSize: number,
        addr: number,
        data: PageContents,
        currTs: number,
        numBuckets: number,
        selAddr: number,
        colourOfType: TypeToColourMap,
        setSelPageAddr: (a: number) => void,
        setFocusData: (a: PageContents) => void,
        zoomedSize: number,
        setZoomedSize: (a: number) => void,
        getBucketIdx: (a: number) => number,
        selSize: number,
        setSelSize: (a: number) => void,
        pageVis: {[tp: string]: boolean},
        zoomedAddr: number,
        setZoomedAddr: (a: number) => void
    }) {
    const [currData, setCurrData] = useState(data);
    const dataPerBucket = useMemo(() => {
        return getSlotDataPerBucket(data.events, addr, pageSize, NUM_SLOTS_HUGEPAGE, numBuckets, getBucketIdx, pageVis);
    }, [data, pageVis]);

    useEffect(() => {
        const filtered = {
            events: data.events.filter((obj) => obj.addr + obj.size > (zoomedSize > 0 ? zoomedAddr : selAddr) &&
                                                obj.addr < (zoomedSize > 0 ? zoomedAddr + zoomedSize : selAddr + selSize) &&
                                                obj.allocTs <= currTs && 
                                                (obj.freeTs == null || obj.freeTs >= currTs) &&
                                                obj.type &&
                                                pageVis[obj.type]),
            cluster: data.cluster
        };
        setCurrData(filtered);
        if (zoomedSize > 0) {
            console.log('Before filtering again:');
            console.log(filtered);
            console.log(`Here is zoomedAddr: ${zoomedAddr}, zoomedSize: ${zoomedSize}`);
        }
        // if (Math.floor(selAddr / pageSize) == Math.floor(addr / pageSize)) {

        //     setFocusData({
        //         events: filtered.events.filter((obj: MemoryObject) => obj.addr < selAddr + selSize && selAddr < obj.addr + obj.size),
        //         cluster: filtered.cluster
        //     });
        // }
    }, [currTs, selAddr, data, pageVis, zoomedSize]);

    return (
        <div className={`pageRow${zoomedSize > 0 ? ' pageRowZoomed' : ''}`} >
            <HugePageCard
                addr={addr}
                selAddr={selAddr}
                pageSize={pageSize}
                objData={currData}
                slotData={dataPerBucket[getBucketIdx(currTs)]}
                setSelPageAddr={setSelPageAddr}
                colourOfType={colourOfType}
                zoomedAddr={zoomedAddr}
                zoomedSize={zoomedSize}
                setZoomedSize={setZoomedSize}
                selSize={selSize}
                setSelSize={setSelSize}
                slotSize={Math.floor(pageSize / NUM_SLOTS_HUGEPAGE)} />
            <Grid
                container
                rowSpacing={0.3}
                columnSpacing={0.8}
                className='pageRowLabel' >
                <Grid size={12} >
                    <div className='pageLabelDiv' >{`0x${addr.toString(16)}`}</div>
                </Grid>
                
                <Grid size={5} >
                    <div className='clusterLabelDiv' >{`cluster: ${data.cluster}`}</div>
                </Grid>
                <Grid size={4} >
                    <Tooltip
                        placement='right'
                        title={`${clusterSize} of ${sumClusterSizes} pages`} >
                        <SizeIndicator
                            clusterSize={clusterSize}
                            sumClusterSizes={sumClusterSizes}
                            maxClusterSize={maxClusterSize} />
                    </Tooltip>
                </Grid>
            </Grid>
            {/* {
            (Math.floor(addr / pageSize) == Math.floor(selAddr / pageSize)) &&
            <div id='selPageIcon' >
                <RadioButtonChecked fontSize='small' />
            </div>
            } */}
        </div>
    );
}

export default function Pages({ pages, clustersData, sumClusterSizes, numClusters, features, pageSize,
                                cacheLineSize, perf, colourOfType, currTs, clusterAlg, maxRunLength,
                                maxRunsPerCluster, numBuckets, pageVis, fieldsData, expandedTypes,
                                setExpandedTypes, getBucketIdx, timeRange } :
    {
        pages: PageMap,
        clustersData: ClustersInfo,
        sumClusterSizes: number,
        numClusters: number,
        features: any,
        pageSize: number,
        cacheLineSize: number,
        perf: PerfMap,
        colourOfType: TypeToColourMap,
        currTs: number,
        clusterAlg: string,
        maxRunLength: number,
        maxRunsPerCluster: number,
        pageVis: {[tp: string]: boolean},
        fieldsData: {[tp: string]: SubtypeEntry[]},
        expandedTypes: {[tp: string]: boolean},
        setExpandedTypes: (a: {[tp: string]: boolean}) => void,
        getBucketIdx: (a: number) => number,
        timeRange: {min: number, max: number},
        numBuckets: number
    }) {
    // const [clusters, setClusters] = useState({});
    const [selPageAddr, setSelPageAddr] = useState(parseInt(Object.keys(pages)[0]));
    // const [focusData, setFocusData] = useState<PageContents>(Object.values(pages)[0]);
    const [sortMode, setSortMode] = useState<'addr' | 'cluster'>('addr');
    const [selSize, setSelSize] = useState<number>(0);
    const [zoomedAddr, setZoomedAddr] = useState<number>(0);
    const [zoomedSize, setZoomedSize] = useState<number>(0);
    const [showHot, setShowHot] = useState<boolean>(false);
    const [showHitm, setShowHitm] = useState<boolean>(false);
    const snapshotSavedRef = useRef(false);

    useEffect(() => {
        if (snapshotSavedRef.current) {
            return;
        }
        if (!pages || Object.keys(pages).length === 0) {
            return;
        }
        const snapshotText = buildPageSnapshotText(pages, clustersData, fieldsData, pageSize);
        downloadTextFile(snapshotText, SNAPSHOT_FILE_NAME);
        snapshotSavedRef.current = true;
    }, [pages, clustersData, fieldsData, pageSize]);

    const maxClusterSize = Object.values(clustersData).reduce((size: number, curr: {'pages': number[], 'size': number}) => Math.max(size, curr['size']), 0);
    const focusData = useMemo(() => {
        const currentPageAddr = Math.round(selPageAddr / pageSize) * pageSize;
        if (!pages[currentPageAddr]) {
            return { events: [], cluster: 0 } as PageContents;
        }
        return pages[currentPageAddr];
    }, [selPageAddr, pages, pageSize]);
    const hitmCutoff = useMemo(() => Object.keys(perf.addrs).length > 0 ? Object.values(perf.addrs)
                                            .toSorted((a, b) => b.hitm - a.hitm)[Math.min(Object.keys(perf.addrs).length, MAX_HITM_ADDRS) - 1].hitm : 0, [perf]);

    return (
        <div id='pageAndObjectVis'>
            <div id='pageVis'>
                <PageHeader
                    sortMode={sortMode}
                    setSortMode={setSortMode}
                    pageSize={pageSize}
                    selSize={selSize}
                    setSelSize={setSelSize}
                    zoomedSize={zoomedSize}
                    setZoomedSize={setZoomedSize}
                    setZoomedAddr={setZoomedAddr}
                    showHot={showHot}
                    setShowHot={setShowHot}
                    showHitm={showHitm}
                    setShowHitm={setShowHitm}
                    selAddr={selPageAddr} />
                <div id='pageRowContainer'>
                    {
                    pageSize == 4 * 2**10 ?
                    <>
                    {
                    Object.keys(pages)
                        .toSorted((ad1: string, ad2: string) => sortMode == 'addr' ? parseInt(ad1) - parseInt(ad2) : 
                                                sortMode == 'cluster' ? pages[parseInt(ad1)].cluster - pages[parseInt(ad2)].cluster : 0)
                        .map((addr: string) =>  <PageRow
                                                    key={addr}
                                                    clusterSize={clustersData[pages[parseInt(addr)].cluster]['size']}
                                                    sumClusterSizes={sumClusterSizes}
                                                    maxClusterSize={maxClusterSize}
                                                    pageSize={pageSize}
                                                    addr={parseInt(addr)}
                                                    data={pages[parseInt(addr)]}
                                                    currTs={currTs}
                                                    selAddr={selPageAddr}
                                                    colourOfType={colourOfType}
                                                    setSelPageAddr={setSelPageAddr}
                                                    // setFocusData={setFocusData}
                                                    pageVis={pageVis}
                                                    showHot={showHot}
                                                    showHitm={showHitm}
                                                    perf={perf}
                                                    hitmCutoff={hitmCutoff} />)
                    }
                    </>
                    :
                    <>
                    {
                    Object.keys(pages)
                        .toSorted((ad1: string, ad2: string) => sortMode == 'addr' ? parseInt(ad1) - parseInt(ad2) : 
                                                sortMode == 'cluster' ? pages[parseInt(ad1)].cluster - pages[parseInt(ad2)].cluster : 0)
                        .filter((addr: string) => zoomedSize == 0 || Math.floor(parseInt(addr) / pageSize) == Math.floor(selPageAddr / pageSize))
                        .map((addr: string) =>  <HugePageRow
                                                    key={addr}
                                                    clusterSize={clustersData[pages[parseInt(addr)].cluster]['size']}
                                                    sumClusterSizes={sumClusterSizes}
                                                    maxClusterSize={maxClusterSize}
                                                    pageSize={pageSize}
                                                    addr={parseInt(addr)}
                                                    data={pages[parseInt(addr)]}
                                                    selAddr={selPageAddr}
                                                    colourOfType={colourOfType}
                                                    setSelPageAddr={setSelPageAddr}
                                                    // setFocusData={setFocusData}
                                                    zoomedAddr={zoomedAddr}
                                                    setZoomedAddr={setZoomedAddr}
                                                    zoomedSize={zoomedSize}
                                                    setZoomedSize={setZoomedSize}
                                                    getBucketIdx={getBucketIdx}
                                                    currTs={currTs}
                                                    numBuckets={numBuckets}
                                                    selSize={selSize}
                                                    setSelSize={setSelSize}
                                                    pageVis={pageVis} />)
                    }
                    </>
                    }
                </div>
            </div>
            <div id='objectVis' >
                <ObjectLayout
                    data={focusData.events}
                    colourOfType={colourOfType}
                    viewSize={pageSize == 4 * 2**10 ? pageSize : selSize}
                    cacheLineSize={cacheLineSize}
                    fieldsData={fieldsData}
                    expandedTypes={expandedTypes}
                    setExpandedTypes={setExpandedTypes}
                    viewStartAddr={selPageAddr}
                    showHot={showHot}
                    showHitm={showHitm}
                    perf={perf}
                    hitmCutoff={hitmCutoff}
                    pageVis={pageVis}
                    currTs={currTs} />
            </div>
        </div>
    );
}