'use client';

import { Add, Remove } from "@mui/icons-material";
import { CircularProgress, IconButton, styled, Theme, ToggleButton, ToggleButtonGroup, Tooltip, tooltipClasses, TooltipProps, Typography } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import * as d3 from 'd3';
import { testCacheDataPerBucket, testMinAndMaxOccPerBucket } from "./testdata";
import { getData, getTypeName } from "../vispanels/page";
import React from "react";
import { theme } from "../page";

interface CacheInfo {
    size: number,
    assoc: number
}

export interface CacheInfoMap {
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

function isSubType(cacheData: CacheData, idx: number) {
    return cacheData.idxToTpAndSt[idx % cacheData.idxToTpAndSt.length].startsWith('>');
}

export const HtmlTooltip = styled(({ className, ...props } : TooltipProps) => (
    <Tooltip {...props} classes={{ popper: className }} />
    ))(({ theme } : { theme: Theme }) => ({
        [`& .${tooltipClasses.tooltip}`]: {
            maxWidth: 500,
            fontSize: theme.typography.pxToRem(12),
        },
}));

function CacheHeader({ allCacheInfo, selCacheName, setSelCacheName,
                       fname, pageSize, cacheLineSize, numBuckets,
                       setCacheData, loading, setLoading, setCacheWidth } : 
    {
        allCacheInfo: CacheInfoMap,
        selCacheName: string,
        setSelCacheName: (a: string) => void,
        fname: string | null,
        pageSize: number,
        cacheLineSize: number,
        numBuckets: number,
        setCacheData: (a: {occ: number[][], idxToTpAndSt: string[], numSets: number}) => void,
        loading: boolean,
        setLoading: (a: boolean) => void,
        setCacheWidth: (a: CacheWidthData) => void
    }) {
    return (
        <div id='cacheHeader' >
            <ToggleButtonGroup 
                id='cacheSetSelector'
                exclusive
                value={selCacheName}
                size='small'
                disabled={loading}
                onChange={(e, val) => {
                    setLoading(true);
                    setSelCacheName(val);
                    const newCacheInfo = allCacheInfo[val];
                    getData(`get-cache-data/${fname}-${pageSize}-${cacheLineSize}-${numBuckets}-${val == 'L2' ? 2**17 : val == 'L3' ? 2**18 : newCacheInfo.size}-${newCacheInfo.assoc}`, null)
                        .then((resp) => resp.json())
                        .then((cacheData) => {
                            setCacheData(cacheData);
                            setCacheWidth({
                                min: Math.floor(Math.sqrt(cacheData.numSets)),
                                max: cacheData.numSets,
                                curr: Math.floor(Math.sqrt(cacheData.numSets))
                            });
                            setLoading(false);
                        });
                }} >
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
    const colScale = d3.scalePow([minOcc / 2, maxOcc], ['#ffff91', '#e33a2b'])
                        .exponent(2);
    
    return (
        <rect
            x={x*size}
            y={y*size}
            width={size}
            height={size}
            data-total-max={`total: ${totalData}, max: ${maxOcc}`}
            fill={totalData > 0 ? colScale(totalData).toString() : theme.palette.primary.main}
            onMouseEnter={() => setHoverIdx(idx)}
            onMouseLeave={() => setHoverIdx(null)}
            stroke={theme.palette.background.default}
            strokeWidth={1} />
    );
}

function CacheBoxArray({ selCacheName, cacheData, bucketIdx, cacheWidth,
                         setCacheWidth, cacheVis, loading, expandedTypes } : 
    {
        selCacheName: string,
        cacheData: CacheData,
        bucketIdx: number,
        cacheWidth: CacheWidthData,
        setCacheWidth: (a: CacheWidthData) => void,
        cacheVis: {[tp: string]: boolean},
        loading: boolean,
        expandedTypes: {[a: string]: boolean}
    }) {
    const totalData: number[][] = useMemo(() => {
        return  cacheData.occ.map((bucket) => {
                    return  bucket.reduce((res, v, i) => {
                                    res[Math.floor(i / cacheData.idxToTpAndSt.length)] += v;
                                    return res;
                                }, new Array(cacheData.numSets).fill(0));
                });
    }, [cacheData]);
    const aggDataPerBucket: {min: number, max: number}[] = useMemo(() => {
        return totalData.map((bucket: number[]) => {
            return bucket.reduce((res: {min: number, max: number}, v: number) => {
                res.min = Math.min(res.min, v);
                res.max = Math.max(res.max, v);
                return res;
            }, {min: Infinity, max: 0});
        });
    }, [cacheData]);
    const [hoverIdx, setHoverIdx] = useState<number | null>(null);

    return (
        <>
        {
        loading ?
        <CircularProgress />
        :
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
                    <table className='cacheOccTable' >
                        <colgroup>
                            <col style={{'width': '330px'}} />
                            <col style={{'width': '70px'}} />
                        </colgroup>
                        <tbody>
                        {
                            cacheData.occ[bucketIdx].slice(hoverIdx*cacheData.idxToTpAndSt.length, (hoverIdx+1)*cacheData.idxToTpAndSt.length)
                                .map((v: number, tidx: number) => ({val: v, tidx: tidx}))
                                .filter((v) => v.val > 0)
                                .sort((a, b) => b.val - a.val)
                                .map((v: {val: number, tidx: number}) =>    <tr key={`cb-${v.tidx}`} >
                                                                                <td className='cacheTableTypeTextContainer' >
                                                                                    <Typography className='cacheTableTypeText' >
                                                                                        {cacheData.idxToTpAndSt[v.tidx]}
                                                                                    </Typography>
                                                                                </td>
                                                                                <td>{`${v.val} (${(v.val*100 / totalData[bucketIdx][hoverIdx]).toFixed(2)}%)`}</td>
                                                                            </tr>)
                        }
                        </tbody>
                    </table> :
                    <></>
                } >
                <svg 
                    id='cacheBoxesSVG'
                    viewBox={`0 0 ${MAX_CACHE_BOX_ARRAY_WIDTH} ${MAX_CACHE_BOX_ARRAY_WIDTH}`} >
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
        }
        </>
    );
}

export default function CacheSets({ cacheData, cacheInfo, bucketIdx, cacheVis,
                                    selCacheName, setSelCacheName, fname, pageSize,
                                    cacheLineSize, numBuckets, expandedTypes,
                                    setCacheData } : 
    {
        cacheData: {occ: number[][], idxToTpAndSt: string[], numSets: number}
        cacheInfo: CacheInfoMap,
        bucketIdx: number,
        cacheVis: {[tp: string]: boolean},
        selCacheName: string,
        setSelCacheName: (a: string) => void,
        fname: string | null,
        pageSize: number,
        cacheLineSize: number,
        numBuckets: number,
        expandedTypes: {[tp: string]: boolean},
        setCacheData: (a: {occ: number[][], idxToTpAndSt: string[], numSets: number}) => void
    }) {
    const [loading, setLoading] = useState<boolean>(false);
    const [cacheWidth, setCacheWidth] = useState<CacheWidthData>({
        min: Math.floor(Math.sqrt(cacheData.numSets)),
        max: cacheData.numSets,
        curr: Math.floor(Math.sqrt(cacheData.numSets))
    });

    let j = 0
    // console.log('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@');
    // cacheData.idxToTpAndSt.forEach((v, i) => {
    //     // console.log(v);
    //     if (v == '>block<Node<longlong,void*>>|block<class Node<long long, void *> > *') {
    //         console.log(`Here is index of block<class Node<long long, void *> > *: ${i}`);
    //         j = i;
    //     }
    // });
    // console.log(`Here is condition for ind ${j}:`);
    // console.log((isSubType(cacheData, j) && typeVisMatrix[cacheData.idxToTpAndSt[j % cacheData.idxToTpAndSt.length]].cacheVis && expandedTypes[getTypeName(cacheData.idxToTpAndSt[j % cacheData.idxToTpAndSt.length])]));
    
    const filteredCacheData: CacheData = useMemo(() => {
        // console.log(cacheData.occ.map((row) => row.map((v, i) => 
        //     (!isSubType(cacheData, i) && typeVisMatrix[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length]].cacheVis && !expandedTypes[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length].replace(/\s+/g, '')]) ||
        //     (isSubType(cacheData, i) && typeVisMatrix[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length]].cacheVis && expandedTypes[getTypeName(cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length])]) ?
        //     v : 0)));
        return {
            occ: cacheData.occ.map((row) => row.map((v, i) => 
                                                        (!isSubType(cacheData, i) && cacheVis[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length]] && !expandedTypes[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length].replace(/\s+/g, '')]) ||
                                                        (isSubType(cacheData, i) && cacheVis[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length]] && expandedTypes[getTypeName(cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length])]) ?
                                                        v : 0)),
            idxToTpAndSt: cacheData.idxToTpAndSt,
            numSets: cacheData.numSets
        }
    }, [cacheData, cacheVis, expandedTypes]);

    useEffect(() => {
        setCacheWidth({
            min: Math.floor(Math.sqrt(cacheData.numSets)),
            max: cacheData.numSets,
            curr: Math.floor(Math.sqrt(cacheData.numSets))
        });
    }, [cacheData]);

    return (
        <div id='cacheSetGroup' >
            <CacheHeader
                allCacheInfo={cacheInfo}
                selCacheName={selCacheName}
                setSelCacheName={setSelCacheName}
                fname={fname}
                numBuckets={numBuckets}
                pageSize={pageSize}
                cacheLineSize={cacheLineSize}
                setCacheData={setCacheData}
                loading={loading}
                setLoading={setLoading}
                setCacheWidth={setCacheWidth} />
            <CacheBoxArray
                selCacheName={selCacheName}
                cacheData={filteredCacheData}
                bucketIdx={bucketIdx}
                cacheWidth={cacheWidth}
                setCacheWidth={setCacheWidth}
                cacheVis={cacheVis}
                loading={loading}
                expandedTypes={expandedTypes} />
        </div>
    );
}