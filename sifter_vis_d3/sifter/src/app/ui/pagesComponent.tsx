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

function PageHeader() {
    return (
        <></>
    );
}

function PageCard({ addr, selAddr, pageSize, objectData, setSelPageAddr } :
    {
        addr: number,
        selAddr: number,
        pageSize: number,
        objectData: MemoryObject[],
        setSelPageAddr: (a: number) => void
    }) {
    const ref = useRef(null);
    const pageScale = d3.scaleLinear().domain([0, pageSize]).range([0, 520]); //TODO get rid of this 520 constant

    useEffect(() => {
        const rectData = d3.select(ref.current)
            .select('.pageCardClipGroup')
            .selectAll('.pageCardObject')
            .data(objectData);
        rectData.enter()
            .append('rect')
            .attr('class', 'pageCardObject')
            .style('left', (d) => `${pageScale(d.address % pageSize)}px`)
            .style('width', (d) => `${pageScale(d.size)}px`);
        rectData.exit()
            .remove();
    }, []); // MIGHT need currData in dependencies? Not sure...
    
    return (
        <svg 
            className='pageCard'
            ref={ref} >
            <defs>
                <clipPath id={`pageCardClip${addr}`}>
                    <rect className='pageCardBorder' />
                </clipPath>
            </defs>
            <rect className='pageCardBorder pageCardShadow' />
            <rect
                className={`pageCardBorder pageCardBack${selAddr == addr ? ' pageCardSelected' : ''}`}
                onClick={() => setSelPageAddr(addr)} />
            <g
                className='pageCardClipGroup'
                clipPath={`url(#pageCardClip${addr})`} >
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
                objectData={currData.events}
                setSelPageAddr={setSelPageAddr} />
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
    const [selPageAddr, setSelPageAddr] = useState(null);
    const [focusData, setFocusData] = useState(null);

    return (
        <div>
            <PageHeader />
            <div id='pageAndObjectVis'>
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
                <div id='objectContainer'></div>
            </div>
        </div>
    );
}