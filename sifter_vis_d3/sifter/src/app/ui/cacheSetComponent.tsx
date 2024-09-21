'use client';

import { Settings } from "@mui/icons-material";
import { IconButton, ToggleButton, ToggleButtonGroup, Tooltip } from "@mui/material";
import { useState } from "react";

interface CacheInfo {
    size: number,
    assoc: number
}

interface CacheInfoMap {
    [a: string]: CacheInfo
}

interface CacheContents {
    [type: string]: number
}

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
            <div id='cacheSettingsDiv' >
                <Tooltip
                    title='Cache settings' >
                    <IconButton 
                        id='cacheSettingsButton' >
                        <Settings />
                    </IconButton>
                </Tooltip>
            </div>
        </div>
    );
}

function CacheBoxes({ cacheInfo, selCacheName, cacheDataPerBucket } : 
    {
        cacheInfo: CacheInfoMap,
        selCacheName: string,
        cacheDataPerBucket: {[bucket: number]: CacheContents[]}
    }) {
    const [cacheBoxesWidth, setCacheBoxesWidth] = useState();

    return (
        <svg>
            <></>
        </svg>
    );
}

export default function CacheSets({ cacheInfo } : 
    {
        cacheInfo: CacheInfoMap
    }) {
    const [selCacheName, setSelCacheName] = useState(Object.keys(cacheInfo)[0]);

    return (
        <div id='cacheSetGroup' >
            <CacheHeader
                allCacheInfo={cacheInfo}
                selCacheName={selCacheName}
                setSelCacheName={setSelCacheName} />
            <CacheBoxes />
        </div>
    );
}