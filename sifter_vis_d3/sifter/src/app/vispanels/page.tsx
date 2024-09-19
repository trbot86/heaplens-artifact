'use client';
import { useState } from 'react';
import * as d3 from 'd3';
import Legend from '../ui/legendComponent';
import { createTheme, Theme, ThemeProvider } from '@mui/material/styles';
import { Grid } from '@mui/system';
import Pages from '../ui/pagesComponent';
import { testCacheInfo, testColourOfType, testLineData, testMaxPointsPerLine, testPageData, testPerfData, testTypeStats } from '../ui/testdata';
import TimeGraph from '../ui/timeGraphComponent';
import CssBaseline from '@mui/material/CssBaseline';
import CacheSets from '../ui/cacheSetComponent';

export interface TypeToColourMap {
    [ tp: string ]: d3.RGBColor | d3.HSLColor | null
};

export const theme: Theme = createTheme({
    palette: {
        mode: 'dark',
        primary: {
            main: '#e0e0e0',
            contrastText: '#e9e7e5',
        },
        secondary: {
            main: '#bea7da',
        },
        background: {
            default: '#282828',
            paper: '#212121',
        },
        success: {
            main: '#42c947',
        },
    },
});

const INIT_PAGE_SIZE = 4096;
const INIT_CACHELINE_SIZE = 64;

function getRand(min: number, max: number): number {
    return min + Math.floor(Math.random() * (max - min + 1));
}

export function generateColours(types: string[]): TypeToColourMap {
    return types.reduce((map: TypeToColourMap, tp: string) => {
        const r = getRand(0, 255);
        const g = r > 127 ? getRand(0, 127) : getRand(128, 255);
        const b = getRand(0, 255);
        map[tp] = d3.hsl(d3.color(`rgb(${r}, ${g}, ${b})`));
        map[tp].s *= 0.8;
        map[tp].l *= 1.4;
        return map;
    }, {});
}

export default function VisPanels() {
    const [pageSize, setPageSize] = useState(INIT_PAGE_SIZE);
    const [currTs, setCurrTs] = useState(0); //TODO: CHANGE TO INIT TS
    const [cacheLineSize, setCacheLineSize] = useState(INIT_CACHELINE_SIZE);
    const [colourOfType, setColourOfType] = useState(generateColours(Object.keys(testLineData)));
    const [highlightType, setHighlightType] = useState<string | null>(null);

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Grid container 
                id='visPanelGrid'
                rowSpacing={2}
                columnSpacing={2} >
                <Grid 
                    className='visPanel'
                    size={8} >
                    <Pages
                        pageSize={pageSize}
                        pages={testPageData}
                        perf={testPerfData}
                        colourOfType={colourOfType}
                        currTs={currTs}
                        cacheLineSize={cacheLineSize} />
                </Grid>
                <Grid
                    className='visPanel'
                    size={4} >
                    <CacheSets
                        cacheInfo={testCacheInfo} />
                </Grid>

                <Grid
                    className='visPanel' 
                    size={6} >
                    <TimeGraph
                        lines={testLineData}
                        maxPointsPerLine={testMaxPointsPerLine}
                        colourOfType={colourOfType}
                        currTs={currTs}
                        setCurrTs={setCurrTs} />
                </Grid>
                <Grid 
                    className='visPanel'
                    size={6} >
                    <Legend 
                        colourOfType={colourOfType}
                        setColourOfType={setColourOfType}
                        typeStats={testTypeStats} />
                </Grid>
            </Grid>
        </ThemeProvider>
    );
}