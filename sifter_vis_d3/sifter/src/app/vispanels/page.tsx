'use client';
import { useEffect, useState } from 'react';
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

export interface TypeToColourMap {
    [ tp: string ]: d3.RGBColor | d3.HSLColor | null
};

const INIT_PAGE_SIZE = 4096;
const INIT_CACHELINE_SIZE = 64;
const INIT_NUM_BUCKETS = 2000;
const INIT_MAX_RUN_LENGTH = 5;
const INIT_MAX_RUNS_PER_CLUSTER = 3;
const INIT_CLUSTER_ALG = 'agglomerative';
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

    const minTs = testMinTs;
    const maxTs = testMaxTs;

    const [numBuckets, setNumBuckets] = useState(INIT_NUM_BUCKETS);
    const [getBucketIdx, setGetBucketTs] = useState(() => (ts: number) => 0);

    useEffect(() => {
        const fname = searchParams.get('fname');

        getData(`init-sampler/${fname}-${pageSize}-${cacheLineSize}-${numBuckets}`, null)
                .then((resp) => resp.json())
                .then((types) => {
                    setColourOfType(generateColours(types));
                    Promise.all([
                        getData('get-lines', null),
                        getData(`get-pages/${clusterAlg}-${maxRunLength}-${maxRunsPerCluster}`, types.reduce((map: {[tp: string]: boolean}, tp: string) => {
                            map[tp] = true;
                            return map;
                        }, {}))
                    ]).then((resps) => resps.map((resp, i) => {
                        resp.json().then((data) => {
                            console.log('Here is the returned data:');
                            console.log(data);
                            if (i == 0) {
                                const sortedLineData = Object.keys(data['pts']).reduce((map: {[tp: string]: SizePoint[]}, tp: string) => {
                                    map[tp] = data['pts'][tp].toSorted((a: SizePoint, b: SizePoint) => a.ts - b.ts);
                                    return map;
                                }, {});

                                const minTs: number = Object.keys(sortedLineData)
                                        .reduce((min: number, tp: string) => Math.min(min, sortedLineData[tp][0].ts), Infinity);
                                const maxTs: number = Object.keys(sortedLineData)
                                        .reduce((max: number, tp: string) => Math.max(max, sortedLineData[tp][sortedLineData[tp].length - 1].ts), 0);
                                setGetBucketTs(() => {
                                    return (ts: number) => {
                                        const sizeOfBucket = Math.max(Math.floor((maxTs - minTs) / numBuckets), 1);
                                        return Math.floor((ts - minTs) / sizeOfBucket);
                                    }
                                });
                                setCurrTs(minTs);
                                setLineData(sortedLineData);
                                setStatsData(data['stats']);
                                setFieldsData(data['fields']);
                                setCountsData(data['counts']);
                            }
                            else if (i == 1) {
                                setPageData(data['page_num_events']);
                                setClustersData(data['clusters']);
                                setFeaturesData(data['features']);
                                setPerfData(data['perf']);
                            }
                            // setLoading(false);
                        });
                    }));
                });
    }, []);

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            {
            loading ? 
            <Box id='loadingBox' >
                <LinearProgress />
            </Box>
            :
            <Grid container 
                id='visPanelGrid'
                rowSpacing={2}
                columnSpacing={2} >
                <Grid 
                    className='visPanel'
                    size={8} >
                    <Pages
                        pageSize={pageSize}
                        pages={pageData}
                        perf={perfData}
                        colourOfType={colourOfType}
                        currTs={currTs}
                        cacheLineSize={cacheLineSize} />
                </Grid>
                <Grid
                    className='visPanel'
                    size={4} >
                    <CacheSets
                        cacheInfo={testCacheInfo}
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
                        setCurrTs={setCurrTs} />
                </Grid>
                <Grid 
                    className='visPanel'
                    size={6} >
                    <Legend 
                        colourOfType={colourOfType}
                        setColourOfType={setColourOfType}
                        typeStats={statsData} />
                </Grid>
            </Grid>
            }
        </ThemeProvider>
    );
}