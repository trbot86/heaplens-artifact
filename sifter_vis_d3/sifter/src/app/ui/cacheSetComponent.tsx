'use client';

import { Settings } from "@mui/icons-material";
import { IconButton, ToggleButton, ToggleButtonGroup, Tooltip } from "@mui/material";
import { useState } from "react";

interface CacheInfo {
    name: string,
    size: number,
    assoc: number
}

function CacheHeader({ allCacheInfo, selCache, setSelCache } : 
    {
        allCacheInfo: CacheInfo[],
        selCache: CacheInfo,
        setSelCache: (a: CacheInfo) => void
    }) {
    return (
        <div id='cacheHeader' >
            <ToggleButtonGroup 
                id='cacheSetSelector'
                exclusive
                value={selCache.name}
                size='small'
                onChange={(e, val) => setSelCache(val)} >
                {
                    allCacheInfo.map((cache) => <ToggleButton value={cache.name} >
                                                    {cache.name}
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

function CacheBoxes() {
    return (
        <></>
    );
}

export default function CacheSets({ cacheInfo } : 
    {
        cacheInfo: CacheInfo[]
    }) {
    const [selCache, setSelCache] = useState(cacheInfo[0]);

    return (
        <div id='cacheSetGroup' >
            <CacheHeader
                allCacheInfo={cacheInfo}
                selCache={selCache}
                setSelCache={setSelCache} />
            <CacheBoxes />
        </div>
    );
}