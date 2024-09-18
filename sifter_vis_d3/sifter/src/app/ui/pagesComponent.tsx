'use client';
import { useEffect, useRef, useState } from 'react';
import './componentStyles.scss';
import * as d3 from 'd3';
import { theme, TypeToColourMap } from '../vispanels/page';
import { Check, Dangerous, DangerousOutlined, LocalFireDepartment, LocalFireDepartmentOutlined, SentimentDissatisfied, SentimentDissatisfiedOutlined, SentimentDissatisfiedRounded, SentimentDissatisfiedSharp, SentimentDissatisfiedTwoTone, SentimentVeryDissatisfied, SentimentVeryDissatisfiedOutlined } from '@mui/icons-material';
import { Checkbox, ToggleButton, ToggleButtonGroup } from '@mui/material';

interface MemoryObject {
    file: string | null,
    line: number,
    size: number,
    address: number,
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

function ObjectLayout({ data, colourOfType, pageSize, cacheLineSize } :
    {
        data: PageContents,
        colourOfType: TypeToColourMap,
        pageSize: number,
        cacheLineSize: number
    }) {
    const objSVG = useRef(null);

    console.log(`Here is cls: ${cacheLineSize}, ps: ${pageSize}`);

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
            .call(yAxisGrid)
            .selectAll('.tick')
            .filter((d, i) => i % 2 === 1)
            .select('line')
            .style('stroke', theme.palette.background.default)
            .attr('opacity', 0.2);
        curObjSVG.select('#objectYAxisGridGroup')
            .select('path')
            .style('display', 'none');

        const objData = curObjSVG.select('#objectGroup')
            .selectAll('.dataObjectGroup')
            .data(data.events, (d: MemoryObject) => `${d.address}-${d.allocTs}`);
        const blockGroup = objData.enter()
            .append('g')
            .attr('class', 'dataObjectGroup');


        // Start chunk of data object
        blockGroup.append('rect')
            .attr('data-blockkind', 'start')
            .attr('x', (d) => xScale(d.address % cacheLineSize))
            .attr('y', (d) => yScale(Math.floor((d.address % pageSize) / cacheLineSize)))
            .attr('width', (d) => xScale(Math.min(d.size, cacheLineSize - (d.address % cacheLineSize))))
            .attr('height', (d) => yScale(1))
            .attr('fill', (d) => d.type ? colourOfType[d.type]?.toString() : 'gray');
        
        // Middle chunk of data object
        blockGroup.append('rect')
            .attr('x', (d) => xScale(0))
            .attr('y', (d) => yScale(Math.floor((d.address % pageSize) / cacheLineSize) + 1))
            .attr('width', xScale(cacheLineSize))
            .attr('height', (d) => yScale(Math.floor((d.size - cacheLineSize + (d.address % cacheLineSize)) / cacheLineSize)))
            .attr('fill', (d) => d.type ? colourOfType[d.type]?.toString() : 'gray')
            .style('visibility', (d) => Math.floor((d.size - cacheLineSize + (d.address % cacheLineSize)) / cacheLineSize) > 0 ? 'visible' : 'hidden');

        // Last chunk of data object
        blockGroup.append('rect')
            .attr('x', (d) => xScale(0))
            .attr('y', (d) => yScale(Math.floor((d.address % pageSize) / cacheLineSize) + 1 // y of middle chunk
                                    + Math.floor((d.size - cacheLineSize + (d.address % cacheLineSize)) / cacheLineSize))) // height of middle chunk
            .attr('width', (d) => xScale(Math.min(cacheLineSize, d.size
                                                - (cacheLineSize - (d.address % cacheLineSize)) // size of first chunk
                                                - Math.floor((d.size - cacheLineSize + (d.address % cacheLineSize)) / cacheLineSize)*cacheLineSize))) // size of middle chunk
            .attr('height', yScale(1))
            .attr('fill', (d) => d.type ? colourOfType[d.type]?.toString() : 'gray')
            .style('visibility', (d) => d.size
                - (cacheLineSize - (d.address % cacheLineSize)) // size of first chunk
                - Math.floor((d.size - cacheLineSize + (d.address % cacheLineSize)) / cacheLineSize)*cacheLineSize // size of middle chunk
                > 0 ? 'visible' : 'hidden');

        objData.exit()
            .remove();
    }, [data]);
    
    return (
        <svg
            id='objectSVG'
            width={OBJECT_LAYOUT_WIDTH + OBJECT_LAYOUT_MARGIN + 5}
            height={OBJECT_LAYOUT_HEIGHT + OBJECT_LAYOUT_MARGIN + 5}
            ref={objSVG} >
            <g id='objectGroup' />
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
            <Checkbox 
                id='hotSelectorCheck'
                icon={<LocalFireDepartmentOutlined />}
                checkedIcon={<LocalFireDepartment />} />
            <Checkbox 
                id='contentionCheck'
                icon={<DangerousOutlined />}
                checkedIcon={<Dangerous />} />
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
            .data(objectData.events, (d: MemoryObject) => `${d.address}-${d.allocTs}`);
        rectData.enter()
            .append('rect')
            .attr('class', 'pageCardObject')
            .attr('x', (d) => `${pageScale(d.address % pageSize)}px`)
            .attr('y', 0)
            .attr('width', (d) => pageScale(d.size))
            .attr('fill', (d) => d.type && colourOfType[d.type] ? colourOfType[d.type].toString() : 'black');
            // .attr('height', 50);
        rectData.exit()
            .remove();
    }, [objectData.events]);
    
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
        // if (addr == 0) {
        //     console.log(`Updated filtered of ${addr} with ts ${currTs}:`);
        //     console.log(filtered);
        // }
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