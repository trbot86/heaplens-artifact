'use client';
import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import Legend from '../ui/legendComponent';
import { createTheme, Theme, ThemeProvider } from '@mui/material/styles';
import { Box, Grid } from '@mui/system';
import Pages from '../ui/pagesComponent';
import { testCacheInfo, testColourOfType, testLineData, testMaxPointsPerLine, testMaxTs, testMinTs, testNumBuckets, testPageData, testPerfData, testTypeStats } from '../ui/testdata';
import TimeGraph, { SizePoint } from '../ui/timeGraphComponent';
import CssBaseline from '@mui/material/CssBaseline';
import CacheSets from '../ui/cacheSetComponent';
import { theme } from '../page';
import { useSearchParams } from 'next/navigation';
import { LinearProgress } from '@mui/material';
import { flushSync } from 'react-dom';

export interface TypeToColourMap {
    [ tp: string ]: d3.RGBColor | d3.HSLColor | null
};

const INIT_PAGE_SIZE = 4096;
const INIT_CACHELINE_SIZE = 64;
const INIT_NUM_BUCKETS = 2000;
const INIT_MAX_RUN_LENGTH = 5;
const INIT_MAX_RUNS_PER_CLUSTER = 3;
const INIT_CLUSTER_ALG = 'agglomerative';
const INIT_CACHE_SIZE = 32768;
const INIT_CACHE_ASSOC = 8;
const INIT_TIME_RANGE = {min: 0, max: 1};
const INIT_CACHE_INFO = {
    'L1': {size: 32768, assoc: 8},
    'L2': {size: 2097152, assoc: 8},
    'L3': {size: 4194304, assoc: 8}
};
const INIT_CACHE_DATA = {occ: [[]], idxToTpAndSt: [''], numSets: 1};
const MAX_POINTS_PER_LINE = 3000;

function getRand(min: number, max: number): number {
    return min + Math.floor(Math.random() * (max - min + 1));
}

export function generateColours(types: string[]): TypeToColourMap {
    return types.reduce((map: TypeToColourMap, tp: string) => {
        map[tp] = d3.color(`hsl(${getRand(0, 360)}, ${getRand(20, 60)}%, ${getRand(35, 55)}%)`);
        return map;
    }, {});
}

export async function getData(url: string, postBody: {[tp: string]: boolean} | null) {
    const data = await fetch(`http://localhost:5000/${url}`, {
        method: postBody ? 'POST' : 'GET',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: postBody ? JSON.stringify(postBody) : null
    });
    return data;
}

export default function VisPanels() {
    const shouldFetch = useRef(true);
    const searchParams = useSearchParams();
    const [loading, setLoading] = useState(true);
    const [pageSize, setPageSize] = useState(INIT_PAGE_SIZE);
    const [currTs, setCurrTs] = useState(0);
    const [cacheLineSize, setCacheLineSize] = useState(INIT_CACHELINE_SIZE);
    const [colourOfType, setColourOfType] = useState({});
    const [maxRunLength, setMaxRunLength] = useState(INIT_MAX_RUN_LENGTH);
    const [maxRunsPerCluster, setMaxRunsPerCluster] = useState(INIT_MAX_RUNS_PER_CLUSTER);
    const [clusterAlg, setClusterAlg] = useState(INIT_CLUSTER_ALG);
    const [lineData, setLineData] = useState<{[tp: string]: SizePoint[]}>({});
    const [statsData, setStatsData] = useState({});
    const [fieldsData, setFieldsData] = useState({});
    const [countsData, setCountsData] = useState({});
    const [pageData, setPageData] = useState({});
    const [clustersData, setClustersData] = useState({});
    const [featuresData, setFeaturesData] = useState({});
    const [perfData, setPerfData] = useState({});
    const [cacheInfo, setCacheInfo] = useState(INIT_CACHE_INFO);
    const [cacheData, setCacheData] = useState(INIT_CACHE_DATA);
    const [numBuckets, setNumBuckets] = useState(INIT_NUM_BUCKETS);
    const [timeRange, setTimeRange] = useState(INIT_TIME_RANGE);
    const [getBucketIdx, setGetBucketTs] = useState(() => (ts: number) => 0);
    const [typesToSample, setTypesToSample] = useState({});

    useEffect(() => {
        if (shouldFetch.current) {
            shouldFetch.current = false;
            const fname = searchParams.get('fname');
            getData(`init-app/${fname}-${pageSize}-${cacheLineSize}-${numBuckets}-${clusterAlg}-${maxRunLength}-${maxRunsPerCluster}-${Object.values(INIT_CACHE_INFO)[0].size}-${Object.values(INIT_CACHE_INFO)[0].assoc}`, null)
                    .then((resp) => resp.json())
                    .then((allData) => {
                        console.log('Here is allData:');
                        console.log(allData);
                        setTypesToSample(allData['types'].reduce((map: {[a: string]: boolean}, tp: string) => {
                            map[tp] = true;
                            return map;
                        }, {}));
                        setColourOfType(generateColours(allData['types']));

                        const sortedLineData = Object.keys(allData['linesAndStats']['pts']).reduce((map: {[tp: string]: SizePoint[]}, tp: string) => {
                            map[tp] = allData['linesAndStats']['pts'][tp].toSorted((a: SizePoint, b: SizePoint) => a.ts - b.ts);
                            return map;
                        }, {});
                        const minTs: number = allData['linesAndStats']['minTs'];
                        const maxTs: number = allData['linesAndStats']['maxTs'];
                        setTimeRange({min: minTs, max: maxTs});
                        setGetBucketTs(() => {
                            return (ts: number) => {
                                const sizeOfBucket = Math.max(Math.floor((maxTs - minTs) / numBuckets), 1);
                                return Math.ceil((ts - minTs) / sizeOfBucket);
                            }
                        });
                        setCurrTs(minTs);
                        setLineData(sortedLineData);
                        setStatsData(allData['linesAndStats']['stats']);
                        setFieldsData(allData['linesAndStats']['fields']);
                        setCountsData(allData['linesAndStats']['counts']);

                        setPageData(allData['pagesData']['page_num_events']);
                        setClustersData(allData['pagesData']['clusters']);
                        setFeaturesData(allData['pagesData']['features']);

                        setCacheData(allData['cacheData']);

                        setLoading(false);
                    });
        }
    }, []);

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            {
            loading && 
            <Box id='loadingBox' >
                <LinearProgress />
            </Box>
            }
            {
            !loading &&
            <Grid container 
                id='visPanelGrid'
                rowSpacing={2}
                columnSpacing={2} >
                <Grid 
                    className='visPanel'
                    size={8.5} >
                    <Pages
                        pages={pageData}
                        // clustersData={clustersData}
                        features={featuresData}
                        pageSize={pageSize}
                        perf={perfData}
                        colourOfType={colourOfType}
                        currTs={currTs}
                        cacheLineSize={cacheLineSize}
                        clusterAlg={clusterAlg}
                        maxRunLength={maxRunLength}
                        maxRunsPerCluster={maxRunsPerCluster}
                        typesToSample={typesToSample} />
                </Grid>
                <Grid
                    className='visPanel'
                    size={3.5} >
                    <CacheSets
                        cacheData={cacheData}
                        cacheInfo={cacheInfo}
                        bucketIdx={getBucketIdx(currTs)} />
                </Grid>

                <Grid
                    className='visPanel' 
                    size={6} >
                    <TimeGraph
                        lines={lineData}
                        maxPointsPerLine={MAX_POINTS_PER_LINE}
                        colourOfType={colourOfType}
                        currTs={currTs}
                        setCurrTs={setCurrTs}
                        timeRange={timeRange}
                        numBuckets={numBuckets} />
                </Grid>
                <Grid 
                    className='visPanel'
                    size={6} >
                    <Legend 
                        colourOfType={colourOfType}
                        setColourOfType={setColourOfType}
                        typeStats={countsData} />
                </Grid>
            </Grid>
            }
        </ThemeProvider>
    );
}