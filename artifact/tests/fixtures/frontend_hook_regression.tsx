'use client';
// Copy only into a temporary test frontend's src/app/hook-regression/page.tsx.
// This route is not part of the shipped application.
import { useState } from 'react';
import * as d3 from 'd3';
import TimeGraph from '../ui/timeGraphComponent';
import { AlignAndSize } from '../ui/legendComponent';
import { ObjectLayout } from '../ui/pagesComponent';

const firstLines = {node: [{bucket: 0, size: 10}, {bucket: 1, size: 20}, {bucket: 2, size: 10}]};
const nextLines = {node: [{bucket: 0, size: 400}, {bucket: 1, size: 200}, {bucket: 2, size: 100}]};
const visibility = {node: true};
const firstAlign = [{align: 0, size: 16, count: 1}, {align: 8, size: 16, count: 2}, {align: 16, size: 16, count: 3}];
const nextAlign = [{align: 0, size: 32, count: 5}, {align: 32, size: 32, count: 1}];
const emptyFields = {};
const noPerf = {addrs: {}, avgAccesses: 0};
const noAction = () => {};

export default function HookRegression() {
    const [time, setTime] = useState(25);
    const [next, setNext] = useState(false);
    const [empty, setEmpty] = useState(false);
    const [blue, setBlue] = useState(false);
    const [alignment, setAlignment] = useState(false);
    const [lineSize, setLineSize] = useState(64);
    const [detailStart, setDetailStart] = useState(4096);
    const colour = d3.rgb(blue ? 'blue' : 'red');
    return <main style={{padding: 20, color: 'white', background: '#282828'}}>
        <h1>State-change regression fixture</h1>
        <button onClick={() => setTime(next ? 500 : 75)}>Set time to 75%</button>
        <button onClick={() => {setNext(value => !value); setEmpty(false); setTime(next ? 25 : 300);}}>Replace trace</button>
        <button onClick={() => setEmpty(value => !value)}>Toggle empty lines</button>
        <button onClick={() => setBlue(value => !value)}>Change colour</button>
        <button onClick={() => setAlignment(value => !value)}>Replace alignment data</button>
        <button onClick={() => setLineSize(value => value === 64 ? 128 : 64)}>Change detail geometry</button>
        <button onClick={() => setDetailStart(value => value === 4096 ? 8192 : 4096)}>Change selected region</button>
        <p>Time: <output id='fixture-time'>{time}</output>; cache line: <output id='fixture-line-size'>{lineSize}</output>; region: <output id='fixture-region'>{detailStart}</output></p>
        <div style={{width: 760, height: 350, marginBottom: 130}}>
            <TimeGraph lines={empty ? {} : next ? nextLines : firstLines} colourOfType={{node: colour}}
                currTs={time} setCurrTs={setTime} timeRange={next ? {min: 200, max: 600} : {min: 0, max: 100}}
                numBuckets={2} lineVis={visibility} timestampHz={next ? 100 : null} />
        </div>
        <div style={{display: 'flex', gap: 20}}>
            <div style={{width: 450, height: 350}}>
                <AlignAndSize data={alignment ? nextAlign : firstAlign} colour={colour} setAlignTypeDisplay={noAction} />
            </div>
            <div style={{width: 450, height: 350}}>
                <ObjectLayout data={[]} colourOfType={{node: colour}} viewSize={4096} viewStartAddr={detailStart}
                    cacheLineSize={lineSize} fieldsData={emptyFields} expandedTypes={emptyFields} setExpandedTypes={noAction}
                    showHot={false} showHitm={false} pageVis={visibility} perf={noPerf} hitmCutoff={1} currTs={time} />
            </div>
        </div>
    </main>;
}
