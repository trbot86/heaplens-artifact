'use client';
import { useEffect, useRef, useState } from 'react';
import './componentStyles.scss';
import * as d3 from 'd3';
import { TypeToColourMap } from '../vispanels/page';

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

function ObjectLayout({ data, colourOfType } :
    {
        data: PageContents,
        colourOfType: TypeToColourMap
    }) {
    const objGroup = useRef(null);
    const xScale = useRef();
    const yScale = useRef();
    const xAxis = useRef();
    const yAxis = useRef();

    useEffect(() => {
        const objData = d3.select(objGroup.current)
            .selectAll('.dataObjectGroup')
            .data(data.events, (d: MemoryObject) => `${d.address}-${d.allocTs}`);
        const blockGroup = objData.enter()
            .append('g')
            .attr('class', 'dataObjectGroup');

        // Start chunk of data object
        blockGroup.append('rect')
            .attr('x', )

        blockGroup.exit()
            .remove();
    }, [data]);
    
    return (
        <svg
            id='objectSVG'
            ref={objGroup} >
            <g id='objectGroup' />
            <g id='objectXAxisGroup' />
            <g id='objectYAxisGroup' />
        </svg>
    );
}

function PageHeader() {
    return (
        <></>
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
        setFocusData: (a: MemoryObject[]) => void
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
            setFocusData(filtered.events);
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

export default function Pages({ pageSize, pages, perf, colourOfType, currTs } :
    {
        pageSize: number,
        pages: PageMap,
        perf: PerfMap,
        colourOfType: TypeToColourMap,
        currTs: number
    }) {
    const [selPageAddr, setSelPageAddr] = useState(parseInt(Object.keys(pages)[0]));
    const [focusData, setFocusData] = useState(Object.values(pages)[0]);

    return (
        <div id='pageAndObjectVis'>
            <div id='pageVis'>
                <PageHeader />
                <div id='pageRowContainer'>
                    {
                        Object.keys(pages).map((addr: string) =>    <PageRow
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
                    data={focusData} />
            </div>
        </div>
    );
}