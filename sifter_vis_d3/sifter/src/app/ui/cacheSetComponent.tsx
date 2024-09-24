'use client';

import { Add, Remove, Settings } from "@mui/icons-material";
import { IconButton, styled, Theme, ToggleButton, ToggleButtonGroup, Tooltip, tooltipClasses, TooltipProps } from "@mui/material";
import { useMemo, useState } from "react";
import * as d3 from 'd3';
import { testCacheDataPerBucket, testMinAndMaxOccPerBucket } from "./testdata";

interface CacheInfo {
    size: number,
    assoc: number
}

interface CacheInfoMap {
    [a: string]: CacheInfo
}

interface CacheContents {
    type: {[type: string]: number},
    total: number
}

const MAX_CACHE_BOX_SIZE = 60;
const MAX_CACHE_BOX_ARRAY_WIDTH = 300;

const HtmlTooltip = styled(({ className, ...props } : TooltipProps) => (
    <Tooltip {...props} classes={{ popper: className }} />
    ))(({ theme } : { theme: Theme }) => ({
        [`& .${tooltipClasses.tooltip}`]: {
            backgroundColor: '#f5f5f9',
            color: 'rgba(0, 0, 0, 0.87)',
            maxWidth: 220,
            fontSize: theme.typography.pxToRem(12),
            border: '1px solid #dadde9',
        },
}));

function CacheHeader({ allCacheInfo, selCacheName, setSelCacheName } : 
    {
        allCacheInfo: CacheInfoMap,
        selCacheName: string,
        setSelCacheName: (a: string) => void
    }) {
    return (
        <div id='cacheHeader' >
            <ToggleButtonGroup 
                id='cacheSetSelector'
                exclusive
                value={selCacheName}
                size='small'
                onChange={(e, val) => setSelCacheName(val)} >
                {
                    Object.keys(allCacheInfo).map((name) => <ToggleButton 
                                                                key={name}
                                                                value={name} >
                                                                {name}
                                                            </ToggleButton>)
                }
            </ToggleButtonGroup>
            {/* <div id='cacheSettingsDiv' >
                <Tooltip
                    title='Cache settings' >
                    <IconButton 
                        id='cacheSettingsButton' >
                        <Settings />
                    </IconButton>
                </Tooltip>
            </div> */}
        </div>
    );
}

function CacheBox({ occData, minOcc, maxOcc, bucketIdx, idx, x, y, size, setHoverIdx } : 
    {
        occData: CacheContents[],
        minOcc: number,
        maxOcc: number,
        bucketIdx: number,
        idx: number,
        x: number,
        y: number,
        size: number,
        setHoverIdx: (a: number | null) => void
    }) {
    const colScale = d3.scaleLinear().domain([minOcc / 2, (maxOcc + minOcc) / 2, maxOcc]).range(['#ffff91', '#faca1e', '#cf3325']);
    
    return (
        // <Tooltip 
        //     title={
        //         <table>
        //             <tbody>
        //             {
        //                 Object.keys(occData[bucketIdx].type).map((tp: string) =>    <tr key={`cb-${x}-${y}-${tp}`} >
        //                                                                                 <td>{tp}</td>
        //                                                                                 <td>{`${occData[bucketIdx].type[tp]} (${(occData[bucketIdx].type[tp] / occData[bucketIdx].total).toFixed(2)}%)`}</td>
        //                                                                             </tr>)
        //             }
        //             </tbody>
        //         </table>
        //     } >
        <rect
            x={x*size}
            y={y*size}
            width={size}
            height={size}
            fill={colScale(occData[bucketIdx].total).toString()}
            onMouseEnter={() => setHoverIdx(idx)}
            onMouseLeave={() => setHoverIdx(null)} />
        // </Tooltip>
    );
}

function CacheBoxArray({ selCacheName, cacheDataPerBucket, minAndMaxOccPerBucket, bucketIdx } : 
    {
        selCacheName: string,
        cacheDataPerBucket: CacheContents[][],
        minAndMaxOccPerBucket: {min: number, max: number}[],
        bucketIdx: number
    }) {
    const minWidth = useMemo(() => Math.floor(Math.sqrt(cacheDataPerBucket.length)), [selCacheName]);
    const maxWidth = useMemo(() => cacheDataPerBucket.length, [selCacheName]);
    const [cacheBoxesWidth, setCacheBoxesWidth] = useState(minWidth);
    const [hoverIdx, setHoverIdx] = useState<number | null>(null);

    return (
        <div id='cacheBoxesContainer' >
            <Tooltip 
                title='Decrease width'
                placement='bottom' >
                <IconButton 
                    aria-label='decrease-width'
                    onClick={() => {
                        if (cacheBoxesWidth > minWidth) {
                            setCacheBoxesWidth(cacheBoxesWidth - 1);
                        }}} >
                    <Remove />
                </IconButton>
            </Tooltip>
            {/* TODO: need to hide tooltip completely if mouse over svg but not cache box */}
            <Tooltip 
                placement='left'
                title={
                    hoverIdx != null ?
                    <table>
                        <tbody>
                        {
                            Object.keys(cacheDataPerBucket[hoverIdx][bucketIdx].type).map((tp: string) =>    <tr key={`cb-${tp}`} >
                                                                                            <td>{tp}</td>
                                                                                            <td>{`${cacheDataPerBucket[hoverIdx][bucketIdx].type[tp]} (${(cacheDataPerBucket[hoverIdx][bucketIdx].type[tp]*100 / cacheDataPerBucket[hoverIdx][bucketIdx].total).toFixed(2)}%)`}</td>
                                                                                        </tr>)
                        }
                        </tbody>
                    </table> :
                    <></>
                } >
                <svg 
                    id='cacheBoxesSVG'
                    width={MAX_CACHE_BOX_ARRAY_WIDTH}
                    height={MAX_CACHE_BOX_ARRAY_WIDTH} >
                    {
                        cacheDataPerBucket.map((cacheBucketData, i) =>  <CacheBox
                                                                            key={i}
                                                                            occData={cacheDataPerBucket[i]}
                                                                            minOcc={minAndMaxOccPerBucket[bucketIdx].min}
                                                                            maxOcc={minAndMaxOccPerBucket[bucketIdx].max}
                                                                            bucketIdx={bucketIdx}
                                                                            idx={i}
                                                                            x={i % cacheBoxesWidth}
                                                                            y={Math.floor(i / cacheBoxesWidth)}
                                                                            size={Math.min(MAX_CACHE_BOX_SIZE, MAX_CACHE_BOX_ARRAY_WIDTH / cacheBoxesWidth)}
                                                                            setHoverIdx={setHoverIdx} />)
                    }
                </svg>
            </Tooltip>
            <Tooltip 
                title='Increase width'
                placement='bottom' >
                <IconButton 
                    aria-label='increase-width'
                    onClick={() => {
                        if (cacheBoxesWidth < maxWidth) {
                            setCacheBoxesWidth(cacheBoxesWidth + 1);
                        }}} >
                    <Add />
                </IconButton>
            </Tooltip>
        </div>
    );
}

export default function CacheSets({ cacheInfo, bucketIdx } : 
    {
        cacheInfo: CacheInfoMap,
        bucketIdx: number
    }) {
    const [selCacheName, setSelCacheName] = useState(Object.keys(cacheInfo)[0]);

    return (
        <div id='cacheSetGroup' >
            <CacheHeader
                allCacheInfo={cacheInfo}
                selCacheName={selCacheName}
                setSelCacheName={setSelCacheName} />
            <CacheBoxArray
                selCacheName={selCacheName}
                cacheDataPerBucket={testCacheDataPerBucket}
                minAndMaxOccPerBucket={testMinAndMaxOccPerBucket}
                bucketIdx={bucketIdx} />
        </div>
    );
}