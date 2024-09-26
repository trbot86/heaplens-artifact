'use client';
import { forwardRef, useEffect, useRef, useState } from 'react';
import './componentStyles.scss';
import * as d3 from 'd3';
import { TypeToColourMap } from '../vispanels/page';
import { Check, Dangerous, DangerousOutlined, LocalFireDepartment, LocalFireDepartmentOutlined, SentimentDissatisfied, SentimentDissatisfiedOutlined, SentimentDissatisfiedRounded, SentimentDissatisfiedSharp, SentimentDissatisfiedTwoTone, SentimentVeryDissatisfied, SentimentVeryDissatisfiedOutlined } from '@mui/icons-material';
import { Checkbox, ToggleButton, ToggleButtonGroup, Tooltip } from '@mui/material';

interface MemoryObject {
    file: string | null,
    line: number,
    size: number,
    addr: number,
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

interface PerfMap {
    [ addr: number ]: {
        hitm: number,
        accesses: number
    }
}

const PAGE_CARD_SVG_WIDTH = 530;
const PAGE_CARD_BORDER_WIDTH = PAGE_CARD_SVG_WIDTH - 10;
const OBJECT_LAYOUT_WIDTH = 300;
const OBJECT_LAYOUT_HEIGHT = 300;
const OBJECT_LAYOUT_MARGIN = 25;

const SplitBlock = forwardRef(({ obj, colourOfType, pageSize, cacheLineSize, xScale, yScale,
                                 /*hoveredType, setHoveredType,*/ ...props } : 
    {
        obj: MemoryObject,
        colourOfType: TypeToColourMap,
        pageSize: number,
        cacheLineSize: number,
        xScale: d3.ScaleLinear<number, number, never>,
        yScale: d3.ScaleLinear<number, number, never>,
        /*hoveredType: string | null,
        setHoveredType: (a: string | null) => void*/
    }, ref) => {
    return (
        <g
            {...props}
            ref={ref} >
            {/* onMouseEnter={() => setHoveredType(obj.type)}
            onMouseLeave={() => setHoveredType(null)} > */}
            {/* Start chunk of data object */}
            <rect
                // className={`objectBlock${obj.type == hoveredType ? ' objectBlockHovered' : ''}`}
                x={xScale(obj.addr % cacheLineSize)}
                y={yScale(Math.floor((obj.addr % pageSize) / cacheLineSize))}
                width={xScale(Math.min(obj.size, cacheLineSize - (obj.addr % cacheLineSize)))}
                height={yScale(1)}
                fill={obj.type ? colourOfType[obj.type]?.toString() : 'gray'} />
            {/* Middle chunk of data object */}
            <rect
                // className={`objectBlock${obj.type == hoveredType ? ' objectBlockHovered' : ''}`}
                x={xScale(0)}
                y={yScale(Math.floor((obj.addr % pageSize) / cacheLineSize) + 1)}
                width={xScale(cacheLineSize)}
                height={yScale(Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize))}
                fill={obj.type ? colourOfType[obj.type]?.toString() : 'gray'}
                style={{
                    'visibility': Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize) > 0 ? 'visible' : 'hidden'
                }} />
            {/* Last chunk of data object */}
            <rect
                // className={`objectBlock${obj.type == hoveredType ? ' objectBlockHovered' : ''}`}
                x={xScale(0)}
                y={
                    yScale(Math.floor((obj.addr % pageSize) / cacheLineSize) + 1 // y of middle chunk
                        + Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)) // height of middle chunk
                }
                width={
                    xScale(Math.min(cacheLineSize, obj.size
                        - (cacheLineSize - (obj.addr % cacheLineSize)) // size of first chunk
                        - Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)*cacheLineSize)) // size of middle chunk
                }
                height={yScale(1)}
                fill={obj.type ? colourOfType[obj.type]?.toString() : 'gray'}
                style={{
                    'visibility': obj.size
                        - (cacheLineSize - (obj.addr % cacheLineSize)) // size of first chunk
                        - Math.floor((obj.size - cacheLineSize + (obj.addr % cacheLineSize)) / cacheLineSize)*cacheLineSize // size of middle chunk
                        > 0 ? 'visible' : 'hidden'
                }} />
        </g>
    );
});

function ObjectLayout({ data, colourOfType, pageSize, cacheLineSize } :
    {
        data: PageContents,
        colourOfType: TypeToColourMap,
        pageSize: number,
        cacheLineSize: number
    }) {
    const objSVG = useRef(null);
    const [hoveredType, setHoveredType] = useState<string | null>(null);

    const xScale = d3.scaleLinear().domain([0, cacheLineSize]).range([0, OBJECT_LAYOUT_WIDTH]);
    const yScale = d3.scaleLinear().domain([0, Math.floor(pageSize / cacheLineSize)]).range([0, OBJECT_LAYOUT_HEIGHT]);
    const xAxis = d3.axisTop(xScale)
                    .tickValues(d3.range(0, cacheLineSize + 1, Math.floor(cacheLineSize / 8))).tickFormat(d3.format('d'));
    const yAxis = d3.axisLeft(yScale)
                    .tickValues(d3.range(0, Math.floor(pageSize / cacheLineSize) + 1, 8)).tickFormat(d3.format('d'));
    const yAxisGrid = d3.axisLeft(yScale).tickSize(-OBJECT_LAYOUT_WIDTH)
                        .tickValues(d3.range(0, Math.floor(pageSize / cacheLineSize) + 1, 1)).tickFormat('');

    useEffect(() => {
        const curObjSVG = d3.select(objSVG.current);
        
        curObjSVG.select('#objectXAxisGroup')
            .call(xAxis);
        curObjSVG.select('#objectYAxisGroup')
            .call(yAxis);
        curObjSVG.select('#objectYAxisGridGroup')
            .call(yAxisGrid);
    }, [cacheLineSize]);
    
    return (
        <svg
            id='objectSVG'
            width={OBJECT_LAYOUT_WIDTH + OBJECT_LAYOUT_MARGIN + 5}
            height={OBJECT_LAYOUT_HEIGHT + OBJECT_LAYOUT_MARGIN + 5}
            ref={objSVG} >
            <defs>
                <pattern
                    id='diagHatch'
                    width={3}
                    height={3}
                    patternTransform='rotate(45, 0, 0)'
                    patternUnits='userSpaceOnUse' >
                    <line 
                        x1={0}
                        y1={0}
                        x2={0}
                        y2={3}
                        style={{
                            stroke: 'black',
                            strokeWidth: '1px'
                        }} />
                </pattern>
                <mask id='hatchMask' >
                    <rect
                        x={0}
                        y={0}
                        width={xScale(cacheLineSize)}
                        height={yScale(cacheLineSize)}
                        fill='url(#diagHatch)' />
                </mask>
            </defs>
            <g id='objectGroup' >
                {
                    data.events.map((event: MemoryObject) => <Tooltip title={event.type} 
                                                                key={`${event.addr}-${event.allocTs}`} >
                                                                <SplitBlock
                                                                    obj={event}
                                                                    colourOfType={colourOfType}
                                                                    pageSize={pageSize}
                                                                    cacheLineSize={cacheLineSize}
                                                                    xScale={xScale}
                                                                    yScale={yScale} />
                                                                    {/* hoveredType={hoveredType}
                                                                    setHoveredType={setHoveredType} /> */}
                                                             </Tooltip>)
                }
            </g>
            <g id='objectXAxisGroup' />
            <g id='objectYAxisGridGroup' />
            <g id='objectYAxisGroup' />
        </svg>
    );
}

function PageHeader({ sortMode, setSortMode } : 
    {
        sortMode: 'addr' | 'cluster',
        setSortMode: (a: 'addr' | 'cluster') => void
    }) {
    return (
        <div id='pageHeaderGroup' >
            <Tooltip 
                title='Show hot cache lines'
                placement='top' >
                <Checkbox 
                    id='hotSelectorCheck'
                    icon={<LocalFireDepartmentOutlined />}
                    checkedIcon={<LocalFireDepartment />} />
            </Tooltip>
            <Tooltip 
                title='Show HITMs'
                placement='top' >
                <Checkbox 
                    id='contentionCheck'
                    icon={<DangerousOutlined />}
                    checkedIcon={<Dangerous />} />
            </Tooltip>
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

function PageCard({ addr, selAddr, pageSize, objectData, setSelPageAddr, colourOfType } :
    {
        addr: number,
        selAddr: number,
        pageSize: number,
        objectData: PageContents,
        setSelPageAddr: (a: number) => void,
        colourOfType: TypeToColourMap,
    }) {
    const ref = useRef(null);
    const pageScale = d3.scaleLinear().domain([0, pageSize]).range([0, 520]); //TODO get rid of this 520 constant

    useEffect(() => {
        const rectData = d3.select(ref.current)
            .select('.pageCardClipGroup')
            .selectAll('.pageCardObject')
            .data(objectData.events, (d: MemoryObject) => `${d.addr}-${d.allocTs}`);
        rectData.enter()
            .append('rect')
            .attr('class', 'pageCardObject')
            .attr('x', (d) => pageScale(d.addr % pageSize))
            .attr('y', 0)
            .attr('width', (d) => pageScale(d.size))
            .attr('fill', (d) => d.type && colourOfType[d.type] ? colourOfType[d.type].toString() : 'black');
            // .attr('height', 50);
        rectData.exit()
            .remove();
    }, [objectData.events, colourOfType]);
    
    return (
        <svg 
            className='pageCard'
            ref={ref} >
            {/* <defs>
                <clipPath id={`pageCardClip${addr}`}>
                    <rect
                        className='pageCardBorder'
                        clipPathUnits='objectBoundingBox' />
                </clipPath>
            </defs> */}
            <rect className='pageCardBorder pageCardShadow' />
            <rect
                className={`pageCardBorder pageCardBack${selAddr == addr ? ' pageCardSelected' : ''}`}
                onClick={() => setSelPageAddr(addr)} />
            <g
                className='pageCardClipGroup' >
            </g>
        </svg>
    );
}

function PageRow({  pageSize, addr, data, currTs, selAddr,
                    colourOfType, setSelPageAddr, setFocusData } : 
    {
        pageSize: number,
        addr: number,
        data: PageContents,
        currTs: number,
        selAddr: number,
        colourOfType: TypeToColourMap,
        setSelPageAddr: (a: number) => void,
        setFocusData: (a: PageContents) => void
    }) {
    const [currData, setCurrData] = useState(data);

    useEffect(() => {
        const filtered = {
            events: data.events.filter((obj) => obj.allocTs <= currTs && 
                                                (obj.freeTs == null || obj.freeTs >= currTs)),
            cluster: data.cluster
        };
        setCurrData(filtered);
        if (selAddr == addr) {
            setFocusData(filtered);
        }
    }, [currTs, selAddr, data]);

    return (
        <div className='pageRow'>
            <PageCard 
                addr={addr}
                selAddr={selAddr}
                pageSize={pageSize}
                objectData={currData}
                setSelPageAddr={setSelPageAddr}
                colourOfType={colourOfType} />
            <div className='pageRowLabel'>
                <div>{`0x${addr.toString(16)}`}</div>
                <div>{`cluster: ${currData.cluster}`}</div>
            </div>
        </div>
    );
}

export default function Pages({ pageSize, cacheLineSize, pages, perf, colourOfType, currTs } :
    {
        pageSize: number,
        cacheLineSize: number,
        pages: PageMap,
        perf: PerfMap,
        colourOfType: TypeToColourMap,
        currTs: number
    }) {
    const [selPageAddr, setSelPageAddr] = useState(parseInt(Object.keys(pages)[0]));
    const [focusData, setFocusData] = useState({
        events: Object.values(pages)[0].events.filter((obj: MemoryObject) => obj.allocTs <= currTs && (!obj.freeTs || obj.freeTs >= currTs)),
        cluster: Object.values(pages)[0].cluster
    });
    const [sortMode, setSortMode] = useState<'addr' | 'cluster'>('addr');

    return (
        <div id='pageAndObjectVis'>
            <div id='pageVis'>
                <PageHeader
                    sortMode={sortMode}
                    setSortMode={setSortMode} />
                <div id='pageRowContainer'>
                    {
                        Object.keys(pages)
                            .toSorted((ad1, ad2) => sortMode == 'addr' ? parseInt(ad1) - parseInt(ad2) : 
                                                    sortMode == 'cluster' ? pages[parseInt(ad1)].cluster - pages[parseInt(ad2)].cluster : 0)
                            .map((addr: string) =>    <PageRow
                                                                        key={addr}
                                                                        pageSize={pageSize}
                                                                        addr={parseInt(addr)}
                                                                        data={pages[parseInt(addr)]}
                                                                        currTs={currTs}
                                                                        selAddr={selPageAddr}
                                                                        colourOfType={colourOfType}
                                                                        setSelPageAddr={setSelPageAddr}
                                                                        setFocusData={setFocusData} />)
                    }
                </div>
            </div>
            <div id='objectVis' >
                <ObjectLayout
                    data={focusData}
                    colourOfType={colourOfType}
                    pageSize={pageSize}
                    cacheLineSize={cacheLineSize} />
            </div>
        </div>
    );
}