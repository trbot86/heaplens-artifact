'use client';

import { Add, Remove, Settings } from "@mui/icons-material";
import { IconButton, styled, Theme, ToggleButton, ToggleButtonGroup, Tooltip, tooltipClasses, TooltipProps } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import * as d3 from 'd3';
import { testCacheDataPerBucket, testMinAndMaxOccPerBucket } from "./testdata";
import { getData } from "../vispanels/page";
import React from "react";
import { theme } from "../page";

interface CacheInfo {
    size: number,
    assoc: number
}

interface CacheInfoMap {
    [a: string]: CacheInfo
}

interface CacheWidthData {
    min: number,
    max: number,
    curr: number
}

interface CacheData {
    occ: number[][],
    idxToTpAndSt: string[],
    numSets: number
}

const MAX_CACHE_BOX_SIZE = 60;
const MAX_CACHE_BOX_ARRAY_WIDTH = 300;

async function getCacheData(cacheInfo: CacheInfo) {
    return getData(`get-cache-data/${cacheInfo.size}-${cacheInfo.assoc}`, null)
        .then((resp) => resp.json());
}

function isSubType(cacheData: CacheData, idx: number) {
    return cacheData.idxToTpAndSt[idx % cacheData.idxToTpAndSt.length].startsWith('>');
}

const HtmlTooltip = styled(({ className, ...props } : TooltipProps) => (
    <Tooltip {...props} classes={{ popper: className }} />
    ))(({ theme } : { theme: Theme }) => ({
        [`& .${tooltipClasses.tooltip}`]: {
            maxWidth: 500,
            fontSize: theme.typography.pxToRem(12),
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

function CacheBox({ totalData, minOcc, maxOcc, idx, x, y, size, setHoverIdx } : 
    {
        totalData: number,
        minOcc: number,
        maxOcc: number,
        idx: number,
        x: number,
        y: number,
        size: number,
        setHoverIdx: (a: number | null) => void
    }) {
    const colScale = d3.scaleLinear().domain([minOcc / 2, (maxOcc + minOcc) / 2, maxOcc]).range(['#ffff91', '#faca1e', '#cf3325']);
    
    return (
        <rect
            x={x*size}
            y={y*size}
            width={size}
            height={size}
            fill={totalData > 0 ? colScale(totalData).toString() : theme.palette.primary.main}
            onMouseEnter={() => setHoverIdx(idx)}
            onMouseLeave={() => setHoverIdx(null)}
            stroke={theme.palette.background.default}
            strokeWidth={1} />
    );
}

function CacheBoxArray({ selCacheName, cacheData, bucketIdx, cacheWidth, setCacheWidth } : 
    {
        selCacheName: string,
        cacheData: CacheData,
        bucketIdx: number,
        cacheWidth: CacheWidthData,
        setCacheWidth: (a: CacheWidthData) => void
    }) {
    const aggDataPerBucket: {min: number, max: number}[] = useMemo(() => {
        return  cacheData.occ.map((bucket) => {
                    return  bucket.filter((v, i) => !isSubType(cacheData, i))
                                .reduce((res: {min: number, max: number}, v: number) => {
                                    res.min = Math.min(res.min, v);
                                    res.max = Math.max(res.max, v);
                                    return res;
                                }, {min: Infinity, max: 0});
                });
    }, [cacheData]);
    const totalData: number[][] = useMemo(() => {
        return  cacheData.occ.map((bucket) => {
                    return  bucket.reduce((res, v, i) => {
                                    if (!isSubType(cacheData, i))
                                        res[Math.floor(i / cacheData.idxToTpAndSt.length)] += v;
                                    return res;
                                }, new Array(cacheData.numSets).fill(0));
                });
    }, [cacheData]);
    const [hoverIdx, setHoverIdx] = useState<number | null>(null);

    return (
        <div id='cacheBoxesContainer' >
            <Tooltip 
                title='Decrease width'
                placement='bottom' >
                <IconButton 
                    aria-label='decrease-width'
                    onClick={() => {
                        if (cacheWidth.curr > cacheWidth.min) {
                            setCacheWidth({
                                min: cacheWidth.min,
                                max: cacheWidth.max,
                                curr: cacheWidth.curr - 1
                            });
                        }}} >
                    <Remove />
                </IconButton>
            </Tooltip>
            {/* TODO: need to hide tooltip completely if mouse over svg but not cache box */}
            <HtmlTooltip 
                placement='left'
                title={
                    hoverIdx != null ?
                    <table>
                        <tbody>
                        {
                            cacheData.occ[bucketIdx].slice(hoverIdx*cacheData.idxToTpAndSt.length, (hoverIdx+1)*cacheData.idxToTpAndSt.length)
                                .map((v: number, tidx: number) => ({val: v, tidx: tidx}))
                                .filter((v) => !isSubType(cacheData, v.tidx) && v.val > 0)
                                .sort((a, b) => b.val - a.val)
                                .map((v: {val: number, tidx: number}) =>    <tr key={`cb-${v.tidx}`} >
                                                                                <td>{cacheData.idxToTpAndSt[v.tidx]}</td>
                                                                                <td>{`${v.val} (${(v.val*100 / totalData[bucketIdx][hoverIdx]).toFixed(2)}%)`}</td>
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
                        new Array(cacheData.numSets)
                            .fill(undefined)
                            .map((e, i) =>  <CacheBox
                                                key={i}
                                                totalData={totalData[bucketIdx][i]}
                                                minOcc={aggDataPerBucket[bucketIdx].min}
                                                maxOcc={aggDataPerBucket[bucketIdx].max}
                                                idx={i}
                                                x={i % cacheWidth.curr}
                                                y={Math.floor(i / cacheWidth.curr)}
                                                size={Math.min(MAX_CACHE_BOX_SIZE, MAX_CACHE_BOX_ARRAY_WIDTH / cacheWidth.curr)}
                                                setHoverIdx={setHoverIdx} />)
                    }
                </svg>
            </HtmlTooltip>
            <Tooltip 
                title='Increase width'
                placement='bottom' >
                <IconButton 
                    aria-label='increase-width'
                    onClick={() => {
                        if (cacheWidth.curr < cacheWidth.max) {
                            setCacheWidth({
                                min: cacheWidth.min,
                                max: cacheWidth.max,
                                curr: cacheWidth.curr + 1
                            });
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
    const [cacheData, setCacheData] = useState({occ: [[]], idxToTpAndSt: [''], numSets: 1});
    const [selCacheName, setSelCacheName] = useState<string>(Object.keys(cacheInfo)[0]);
    const [cacheWidth, setCacheWidth] = useState<CacheWidthData>({min: 1, max: 1, curr: 1});

    useEffect(() => {
        getCacheData(cacheInfo[selCacheName])
            .then((data) => {
                setCacheData(data)
                setCacheWidth({
                    min: Math.floor(Math.sqrt(data['numSets'])),
                    max: data['numSets'],
                    curr: Math.floor(Math.sqrt(data['numSets']))
                });
        });
    }, []);

    return (
        <div id='cacheSetGroup' >
            <CacheHeader
                allCacheInfo={cacheInfo}
                selCacheName={selCacheName}
                setSelCacheName={setSelCacheName} />
            <CacheBoxArray
                selCacheName={selCacheName}
                cacheData={cacheData}
                bucketIdx={bucketIdx}
                cacheWidth={cacheWidth}
                setCacheWidth={setCacheWidth} />
        </div>
    );
}