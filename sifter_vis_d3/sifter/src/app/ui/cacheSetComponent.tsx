'use client';

import { Add, Remove } from "@mui/icons-material";
import { Alert, Snackbar, CircularProgress, IconButton, styled, Theme, ToggleButton, ToggleButtonGroup, Tooltip, tooltipClasses, TooltipProps, Typography } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import * as d3 from 'd3';
import { testCacheDataPerBucket, testMinAndMaxOccPerBucket } from "./testdata";
import { getData, getTypeName, requestErrorMessage } from "../vispanels/page";
import React from "react";
import { theme } from "../page";
import { getCacheTotalsAtBucket } from './currentBucket';

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
                       setCacheData, loading, setLoading, setCacheWidth, busy, onBusyChange } :
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
        setCacheWidth: (a: CacheWidthData) => void,
        busy: boolean,
        onBusyChange: (a: boolean) => void
    }) {
    const [error, setError] = useState<string | null>(null);
    return (
        <div id='cacheHeader' >
            <Snackbar open={error !== null} anchorOrigin={{vertical: 'top', horizontal: 'center'}}>
                <Alert severity='error' onClose={() => setError(null)} sx={{maxWidth: 700}}>{error}</Alert>
            </Snackbar>
            <ToggleButtonGroup 
                id='cacheSetSelector'
                exclusive
                value={selCacheName}
                size='small'
                disabled={loading || busy}
                onChange={(e, val) => {
                    if (!val || val === selCacheName || loading || busy) return;
                    setError(null);
                    setLoading(true);
                    onBusyChange(true);
                    const newCacheInfo = allCacheInfo[val];
                    getData(`get-cache-data/${fname}-${pageSize}-${cacheLineSize}-${numBuckets}-${newCacheInfo.size}-${newCacheInfo.assoc}`, null)
                        .then((resp) => resp.json())
                        .then((cacheData) => {
                            setCacheData(cacheData);
                            setSelCacheName(val);
                            setCacheWidth({
                                min: Math.floor(Math.sqrt(cacheData.numSets)),
                                max: cacheData.numSets,
                                curr: Math.floor(Math.sqrt(cacheData.numSets))
                            });
                        })
                        .catch((error: unknown) => setError(requestErrorMessage(error)))
                        .finally(() => { setLoading(false); onBusyChange(false); });
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
    const visibleTypes: boolean[] = useMemo(() => {
        return cacheData.idxToTpAndSt.map((tp: string, i: number) => 
                    (!isSubType(cacheData, i) && cacheVis[tp] && !expandedTypes[tp.replace(/\s+/g, '')]) ||
                    (isSubType(cacheData, i) && cacheVis[tp] && expandedTypes[getTypeName(tp)]));
    }, [cacheData, cacheVis, expandedTypes]);
    const totalData = useMemo(() => getCacheTotalsAtBucket(cacheData.occ[bucketIdx],
        cacheData.numSets, cacheData.idxToTpAndSt.length, visibleTypes),
        [cacheData, visibleTypes, bucketIdx]);
    const aggData = useMemo(() => totalData.reduce((res, v) => ({
        min: Math.min(res.min, v), max: Math.max(res.max, v)
    }), {min: Infinity, max: 0}), [totalData]);
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
                        <caption>
                            {`Set ${hoverIdx}: ${totalData[hoverIdx]} visible object-line overlaps`}
                        </caption>
                        <colgroup>
                            <col style={{'width': '330px'}} />
                            <col style={{'width': '70px'}} />
                        </colgroup>
                        <thead>
                            <tr><th>Type</th><th>Count (share of this set)</th></tr>
                        </thead>
                        <tbody>
                        {
                            cacheData.occ[bucketIdx].slice(hoverIdx*cacheData.idxToTpAndSt.length, (hoverIdx+1)*cacheData.idxToTpAndSt.length)
                                .map((v: number, tidx: number) => ({val: v, tidx: tidx}))
                                .filter((v) => v.val > 0 && visibleTypes[v.tidx])
                                .sort((a, b) => b.val - a.val)
                                .map((v: {val: number, tidx: number}) =>    <tr key={`cb-${v.tidx}`} >
                                                                                <td className='cacheTableTypeTextContainer' >
                                                                                    <Typography className='cacheTableTypeText' >
                                                                                        {cacheData.idxToTpAndSt[v.tidx]}
                                                                                    </Typography>
                                                                                </td>
                                                                                <td>{`${v.val} (${(v.val*100 / totalData[hoverIdx]).toFixed(2)}%)`}</td>
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
                                                totalData={totalData[i]}
                                                minOcc={aggData.min}
                                                maxOcc={aggData.max}
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
                                    setCacheData, busy, onBusyChange } :
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
        setCacheData: (a: {occ: number[][], idxToTpAndSt: string[], numSets: number}) => void,
        busy: boolean,
        onBusyChange: (a: boolean) => void
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
    
    // const filteredCacheData: CacheData = useMemo(() => {
    //     // console.log(cacheData.occ.map((row) => row.map((v, i) => 
    //     //     (!isSubType(cacheData, i) && typeVisMatrix[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length]].cacheVis && !expandedTypes[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length].replace(/\s+/g, '')]) ||
    //     //     (isSubType(cacheData, i) && typeVisMatrix[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length]].cacheVis && expandedTypes[getTypeName(cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length])]) ?
    //     //     v : 0)));
    //     return {
    //         occ: cacheData.occ.map((row) => row.map((v, i) => 
                                                        // (!isSubType(cacheData, i) && cacheVis[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length]] && !expandedTypes[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length].replace(/\s+/g, '')]) ||
    //                                                     (isSubType(cacheData, i) && cacheVis[cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length]] && expandedTypes[getTypeName(cacheData.idxToTpAndSt[i % cacheData.idxToTpAndSt.length])]) ?
    //                                                     v : 0)),
    //         idxToTpAndSt: cacheData.idxToTpAndSt,
    //         numSets: cacheData.numSets
    //     }
    // }, [cacheData, cacheVis, expandedTypes]);

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
                busy={busy}
                onBusyChange={onBusyChange}
                setCacheWidth={setCacheWidth} />
            <CacheBoxArray
                selCacheName={selCacheName}
                cacheData={cacheData}
                bucketIdx={bucketIdx}
                cacheWidth={cacheWidth}
                setCacheWidth={setCacheWidth}
                cacheVis={cacheVis}
                loading={loading}
                expandedTypes={expandedTypes} />
        </div>
    );
}
