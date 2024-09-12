'use client';
import { useEffect, useState } from 'react';
import './componentStyles.scss';

interface MemoryObject {
    file: string,
    line: number,
    timestamp: number,
    size: number,
    address: number,
    allocTs: number,
    freeTs: number,
    type: string
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

function PageRow({ pageSize, addr, data, currTs, selAddr, onPageClicked, onFilterFocusData } : 
    {
        pageSize: number,
        addr: number,
        data: PageContents,
        currTs: number,
        selAddr: number,
        onPageClicked: (a: number) => void,
        onFilterFocusData: (a: MemoryObject[]) => void
    }) {
    const [currData, setCurrData] = useState(data);

    useEffect(() => {
        const filtered = {
            events: data.events.filter((obj) => obj.allocTs <= currTs && obj.freeTs >= currTs),
            cluster: data.cluster
        };
        setCurrData(filtered);
        if (selAddr == addr) {
            onFilterFocusData(filtered.events);
        }
    }, [currTs, selAddr, data]);

    return (
        <div id='pageRow'>
            <div>

            </div>
        </div>
    );
}

export default function Pages({ pageSize, pages, perf, currTs } :
    {
        pageSize: number,
        pages: PageMap,
        perf: PerfMap,
        currTs: number
    }) {
    const [selPageAddr, setSelPageAddr] = useState(parseInt(Object.keys(pages)[0]));
    const [focusData, setFocusData] = useState(pages[selPageAddr].events);

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
                                                                        onPageClicked={setSelPageAddr}
                                                                        onFilterFocusData={setFocusData} />)
                    }
                </div>
                <div id='objectContainer'></div>
            </div>
        </div>
    );
}