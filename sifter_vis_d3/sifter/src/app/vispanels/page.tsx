'use client';
import { forwardRef, useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import Legend, { SubtypeEntry } from '../ui/legendComponent';
import { createTheme, Theme, ThemeProvider } from '@mui/material/styles';
import { Box, Stack } from '@mui/system';
import Grid from '@mui/material/Grid2';
import Pages, { PerfMap } from '../ui/pagesComponent';
import { testCacheInfo, testColourOfType, testLineData, testMaxPointsPerLine, testMaxTs, testMinTs, testNumBuckets, testPageData, testPerfData, testTypeStats } from '../ui/testdata';
import TimeGraph, { SIZE_UNIT_SUFF, SIZE_UNITS, SizePoint } from '../ui/timeGraphComponent';
import CssBaseline from '@mui/material/CssBaseline';
import CacheSets, { CacheInfoMap } from '../ui/cacheSetComponent';
import { theme } from '../page';
import { useSearchParams } from 'next/navigation';
import { Divider, FormControl, IconButton, InputLabel, LinearProgress, MenuItem, Paper, Popover, Select, Slider, Tab, Tabs, TextareaAutosize, TextField, ToggleButton, ToggleButtonGroup, Tooltip, Typography } from '@mui/material';
import { flushSync } from 'react-dom';
import { ArrowBack, Cached, Close, EditNote, Settings } from '@mui/icons-material';
import Draggable, { DraggableData, DraggableEvent } from 'react-draggable';

export interface TypeToColourMap {
    [ tp: string ]: d3.RGBColor | d3.HSLColor | null
};

const INIT_PAGE_SIZE = 4096;
const INIT_CACHELINE_SIZE = 64;
const INIT_NUM_BUCKETS = 2000;
const INIT_MAX_RUN_LENGTH = 5;
const INIT_MAX_RUNS_PER_CLUSTER = 3;
const INIT_CLUSTER_ALG = 'mbkmeans';
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

export function getSubtypeName(tp: string, st: string) {
    return '>' + tp + '|' + st;
}

export function getTypeName(st: string) {
    const tpReg = /^>([^|]+)|[^|]+/.exec(st);
    return tpReg ? tpReg[1] : '';
}

function a11yProps(value: string) {
    return {
        id: `simple-tab-${value}`,
        'aria-controls': `simple-tabpanel-${value}`
    };
}

function getPageVis(typeVisMatrix: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}}) {
    return Object.keys(typeVisMatrix).reduce((map: {[a: string]: boolean}, tp: string) => {
        map[tp] = typeVisMatrix[tp].pageVis;
        return map;
    }, {});
}

const SettingsButton = forwardRef(({ maxRunLength, setMaxRunLength, maxRunsPerCluster, setMaxRunsPerCluster,
                         clusterAlg, setClusterAlg, numBucketsSetting, setNumBucketsSetting,
                         pageSizeSetting, setPageSizeSetting, cacheInfoSetting, setCacheInfoSetting,
                         cacheLineSizeSetting, setCacheLineSizeSetting, ...props } : 
    {
        maxRunLength: number,
        setMaxRunLength: (a: number) => void,
        maxRunsPerCluster: number,
        setMaxRunsPerCluster: (a: number) => void,
        clusterAlg: 'mbkmeans' | 'kmeans' | 'dbscan' | 'agglomerative' | 'meanshift',
        setClusterAlg: (a: 'mbkmeans' | 'kmeans' | 'dbscan' | 'agglomerative' | 'meanshift') => void,
        numBucketsSetting: number,
        setNumBucketsSetting: (a: number) => void,
        pageSizeSetting: number,
        setPageSizeSetting: (a: number) => void,
        cacheInfoSetting: CacheInfoMap,
        setCacheInfoSetting: (a: CacheInfoMap) => void,
        cacheLineSizeSetting: number,
        setCacheLineSizeSetting: (a: number) => void
    }, ref) => {
    const [menuAnchor, setMenuAnchor] = useState<HTMLButtonElement | null>(null);
    const [tabValue, setTabValue] = useState<'sample' | 'pages' | 'cache'>('sample');
    const [cacheSizeUnitSetting, setCacheSizeUnitSetting] = useState(Object.keys(cacheInfoSetting).reduce((map: {[a: string]: 0 | 1 | 2}, cname: string) => {
        map[cname] = 1;
        return map;
    }, {}));
    return (
        <>
            <IconButton
                {...props}
                ref={ref}
                onClick={(e) => setMenuAnchor(e.currentTarget)} >
                <Settings />
            </IconButton>
            <Popover
                open={Boolean(menuAnchor)}
                anchorEl={menuAnchor}
                onClose={() => setMenuAnchor(null)}
                anchorOrigin={{
                    vertical: 'top',
                    horizontal: 'right'
                }}
                transformOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right'
                }} >
                <Box id='settingsPopoverContent' >
                    <Tabs
                        value={tabValue}
                        onChange={(e, v) => setTabValue(v)} >
                        <Tab
                            value={'sample'}
                            label='Sample settings'
                            {...a11yProps('sample')} />
                        <Tab
                            value={'pages'}
                            label='Page settings'
                            {...a11yProps('pages')} />
                        <Tab
                            value={'cache'}
                            label='Cache settings'
                            {...a11yProps('cache')} />
                    </Tabs>
                    <div id='settingsPopoverGridContainer' >
                    {/* Sample settings grid */}
                    {tabValue == 'sample' &&
                    <Grid
                        container
                        spacing={2}
                        id={'simple-tabpanel-sample'}
                        aria-labelledby={'simple-tab-sample'} >
                        <Grid
                            className='settingsTextLabel'
                            size={6}>
                            <Box>
                                Page clustering algorithm:
                            </Box>
                        </Grid>
                        <Grid size={6}>
                            <FormControl>
                                <InputLabel id='alg-select-label' >Select Algorithm</InputLabel>
                                <Select 
                                    value={clusterAlg}
                                    labelId='alg-select-label'
                                    label='Select algorithm'
                                    onChange={(e) => setClusterAlg(e.target.value as 'mbkmeans' | 'kmeans' | 'dbscan' | 'agglomerative' | 'meanshift')} >
                                    <MenuItem value='mbkmeans' >Mini batch k-means</MenuItem>
                                    <MenuItem value='kmeans' >K-means</MenuItem>
                                    <MenuItem value='dbscan' >DBSCAN</MenuItem>
                                    <MenuItem value='agglomerative' >Agglomerative</MenuItem>
                                    <MenuItem value='meanshift' >Mean shift</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid
                            className='settingsTextLabel'
                            size={6}>
                            <Box>
                                Max run length:
                            </Box>
                        </Grid>
                        <Grid size={6}>
                            <Box
                                className='settingsSliderBox' >
                                <Slider
                                    className='settingsSlider' 
                                    value={maxRunLength}
                                    step={1}
                                    min={1}
                                    max={20}
                                    onChange={(e, v: number) => setMaxRunLength(v)} />
                                <Box>{maxRunLength}</Box>
                            </Box>
                        </Grid>

                        <Grid
                            className='settingsTextLabel'
                            size={6}>
                            <Box>
                                Max runs per cluster:
                            </Box>
                        </Grid>
                        <Grid size={6}>
                            <Box
                                className='settingsSliderBox' >
                                <Slider 
                                    className='settingsSlider'
                                    value={maxRunsPerCluster}
                                    step={1}
                                    min={1}
                                    max={10}
                                    onChange={(e, v: number) => setMaxRunsPerCluster(v)} />
                                <Box>{maxRunsPerCluster}</Box>
                            </Box>
                        </Grid>

                        <Grid
                            className='settingsTextLabel'
                            size={6}>
                            <Box>
                                Number of buckets:
                            </Box>
                        </Grid>
                        <Grid size={6}>
                            <TextField 
                                label=''
                                value={numBucketsSetting}
                                size='small'
                                onChange={(e) => setNumBucketsSetting(parseInt(e.target.value))}
                                type='number'
                                sx={{
                                    width: '120px'
                                }} />
                        </Grid>
                    </Grid>
                    }

                    {/* Page settings grid */}
                    {tabValue == 'pages' &&
                    <Grid
                        container
                        spacing={2}
                        id={'simple-tabpanel-sample'}
                        aria-labelledby={'simple-tab-sample'} >
                        <Grid
                            className='settingsTextLabel'
                            size={6}>
                            <Box>
                                Page size:
                            </Box>
                        </Grid>
                        <Grid size={6}>
                            <ToggleButtonGroup 
                                value={pageSizeSetting}
                                exclusive
                                onChange={(e, v) => setPageSizeSetting(v)} >
                                <ToggleButton value={4096} >4 KiB</ToggleButton>
                                <ToggleButton value={2097152} >2 MiB</ToggleButton>
                            </ToggleButtonGroup>
                        </Grid>
                    </Grid>
                    }

                    {/* Cache settings grid */}
                    {tabValue == 'cache' &&
                    <Grid
                        container
                        spacing={2}
                        id={'simple-tabpanel-sample'}
                        aria-labelledby={'simple-tab-sample'} >
                        <Grid
                            className='settingsTextLabel'
                            size={5}>
                            <Box>
                                Cache line size:
                            </Box>
                        </Grid>
                        <Grid size={7}>
                            <ToggleButtonGroup 
                                value={cacheLineSizeSetting}
                                exclusive
                                size='small'
                                onChange={(e, v) => setCacheLineSizeSetting(v)} >
                                <ToggleButton value={16} >16 B</ToggleButton>
                                <ToggleButton value={32} >32 B</ToggleButton>
                                <ToggleButton value={64} >64 B</ToggleButton>
                                <ToggleButton value={128} >128 B</ToggleButton>
                                <ToggleButton value={256} >256 B</ToggleButton>
                            </ToggleButtonGroup>
                        </Grid>
                        {
                            Object.keys(cacheInfoSetting).map((cname) =>    <>
                                                                                <Grid
                                                                                    className='settingsTextLabel'
                                                                                    size={3}>
                                                                                    <Box>
                                                                                        {cname} Size:
                                                                                    </Box>
                                                                                </Grid>
                                                                                <Grid size={9}>
                                                                                    <Box className='cacheParamsContainer' >
                                                                                        <TextField
                                                                                            label=''
                                                                                            value={cacheInfoSetting[cname].size / SIZE_UNITS[cacheSizeUnitSetting[cname]]}
                                                                                            onChange={(e) => {
                                                                                                const newCacheInfoSetting = structuredClone(cacheInfoSetting);
                                                                                                newCacheInfoSetting[cname].size = parseInt(e.target.value)*SIZE_UNITS[cacheSizeUnitSetting[cname]];
                                                                                                setCacheInfoSetting(newCacheInfoSetting);
                                                                                            }}
                                                                                            size='small'
                                                                                            type='number'
                                                                                            sx={{
                                                                                                width: '130px'
                                                                                            }} />
                                                                                        <ToggleButtonGroup 
                                                                                            value={cacheSizeUnitSetting[cname]}
                                                                                            exclusive
                                                                                            size='small'
                                                                                            onChange={(e, v) => {
                                                                                                const newCacheSizeUnitSetting = structuredClone(cacheSizeUnitSetting);
                                                                                                newCacheSizeUnitSetting[cname] = v;
                                                                                                setCacheSizeUnitSetting(newCacheSizeUnitSetting);
                                                                                            }} >
                                                                                            {
                                                                                                SIZE_UNIT_SUFF.slice(0, 3).map((suff, i) => <ToggleButton value={i} >{suff}</ToggleButton>)
                                                                                            }
                                                                                        </ToggleButtonGroup>
                                                                                        <Box>Associativity:</Box>
                                                                                        <TextField
                                                                                            label=''
                                                                                            value={cacheInfoSetting[cname].assoc}
                                                                                            onChange={(e) => {
                                                                                                const newCacheInfoSetting = structuredClone(cacheInfoSetting);
                                                                                                newCacheInfoSetting[cname].assoc = parseInt(e.target.value);
                                                                                                setCacheInfoSetting(newCacheInfoSetting);
                                                                                            }}
                                                                                            size='small'
                                                                                            type='number'
                                                                                            sx={{
                                                                                                width: '80px'
                                                                                            }} />
                                                                                    </Box>
                                                                                </Grid>
                                                                            </>)
                        }
                    </Grid>
                    }
                    </div>
                </Box>
            </Popover>
        </>
    );
});

export default function VisPanels() {
    const shouldInitialize = useRef(true);
    const searchParams = useSearchParams();
    const fname = searchParams.get('fname');
    const [loading, setLoading] = useState(true);
    const [pageSize, setPageSize] = useState(INIT_PAGE_SIZE);
    const [currTs, setCurrTs] = useState(0);
    const [cacheLineSize, setCacheLineSize] = useState(INIT_CACHELINE_SIZE);
    const [colourOfType, setColourOfType] = useState({});
    const [lineData, setLineData] = useState<{[tp: string]: SizePoint[]}>({});
    const [statsData, setStatsData] = useState({});
    const [fieldsData, setFieldsData] = useState<{[tp: string]: SubtypeEntry[]}>({});
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
    const [typeVisMatrix, setTypeVisMatrix] = useState<{[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}}>({});
    const [selCacheName, setSelCacheName] = useState<string>(Object.keys(cacheInfo)[0]);
    const [resampling, setResampling] = useState<boolean>(false);
    const [expandedTypes, setExpandedTypes] = useState<{[tp: string]: boolean}>({});

    /*  State for settings menu. Variables with suffix "Setting" are used
        to update the corresponding state variable only upon resample. */
    const [maxRunLength, setMaxRunLength] = useState(INIT_MAX_RUN_LENGTH);
    const [maxRunsPerCluster, setMaxRunsPerCluster] = useState(INIT_MAX_RUNS_PER_CLUSTER);
    const [clusterAlg, setClusterAlg] = useState<'mbkmeans' | 'kmeans' | 'dbscan' | 'agglomerative' | 'meanshift'>(INIT_CLUSTER_ALG);
    const [numBucketsSetting, setNumBucketsSetting] = useState(INIT_NUM_BUCKETS);
    const [pageSizeSetting, setPageSizeSetting] = useState(INIT_PAGE_SIZE);
    const [cacheInfoSetting, setCacheInfoSetting] = useState(INIT_CACHE_INFO);
    const [cacheLineSizeSetting, setCacheLineSizeSetting] = useState(INIT_CACHELINE_SIZE);

    /*  State and refs for notes. */
    const nodeRef = useRef(null);
    const [notesOpen, setNotesOpen] = useState<boolean>(false);
    const [notesPosition, setNotesPosition] = useState({x: 0, y: 0});

    useEffect(() => {
        if (shouldInitialize.current) {
            shouldInitialize.current = false;
            getData(`init-app/${fname}-${pageSize}-${cacheLineSize}-${numBuckets}-${clusterAlg}-${maxRunLength}-${maxRunsPerCluster}-${Object.values(INIT_CACHE_INFO)[0].size}-${Object.values(INIT_CACHE_INFO)[0].assoc}`, null)
                    .then((resp) => resp.json())
                    .then((allData) => {
                        // setTypesToSample(allData['types'].reduce((map: {[a: string]: boolean}, tp: string) => {
                        //     map[tp] = true;
                        //     return map;
                        // }, {}));
                        const allFieldNames: string[] = [];
                        Object.keys(allData['linesAndStats']['fields']).forEach((tp: string) => {
                            allData['linesAndStats']['fields'][tp].forEach((field: SubtypeEntry) => allFieldNames.push(getSubtypeName(tp, field.subtype)));
                        });
                        console.log('ALL FIELD NAMES:');
                        console.log(allFieldNames.sort());
                        setTypeVisMatrix(allData['types'].concat(allFieldNames)
                            .reduce((map: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}}, tp: string) => {
                                map[tp] = {lineVis: true, pageVis: true, cacheVis: true};
                                return map;
                        }, {}));
                        setExpandedTypes(allData['types'].reduce((map: {[tp: string]: boolean}, tp: string) => {
                            map[tp.replace(/\s+/g, '')] = false;
                            return map;
                        }, {}));
                        setColourOfType(generateColours(allData['types'].concat(allFieldNames)));

                        const sortedLineData = Object.keys(allData['linesAndStats']['pts']).reduce((map: {[tp: string]: SizePoint[]}, tp: string) => {
                            map[tp] = allData['linesAndStats']['pts'][tp].toSorted((a: SizePoint, b: SizePoint) => a.ts - b.ts)
                                        .filter((sp: SizePoint, i: number) => i == allData['linesAndStats']['pts'][tp].length - 1 || sp.ts < allData['linesAndStats']['pts'][tp][i+1].ts);
                            return map;
                        }, {});

                        const minTs: number = allData['linesAndStats']['minTs'];
                        const maxTs: number = allData['linesAndStats']['maxTs'];

                        // sortedLineData["void"] = [
                        //     {size: 33554432, ts: minTs + 9213287},
                        //     {size: 67108864, ts: minTs + 714029707},
                        //     {size: 134217728, ts: minTs + 1948610102},
                        //     {size: 268435456, ts: minTs + 5564825068}
                        // ]; // TODO REMOVE THIS PLACEHOLDER DATA
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
                        if (fname == 'setbench_bst_chrom_n48_u0.sqlite') {
                            allData['linesAndStats']['perf'][0x7fba06e32000] = {hitm: 0.94, stores: 394, loads: 483};
                            allData['linesAndStats']['perf'][0x7fba06e32000 + 2688] = {hitm: 0.12, stores: 101, loads: 2450};
                            allData['linesAndStats']['perf'][0x7fba086f4000 + 384] = {hitm: 0.02, stores: 2, loads: 3914};
                            allData['linesAndStats']['perf'][0x7fba086f4000 + 1536] = {hitm: 0.01, stores: 2, loads: 4113};
                            allData['linesAndStats']['perf'][0x7fba0694c000 + 2048] = {hitm: 0.01, stores: 3, loads: 2918};
                        }
                        const retPerfData: PerfMap = Object.keys(allData['linesAndStats']['perf'])
                            .map((straddr: string) => parseInt(straddr))
                            .filter((addr) => addr >= 0)
                            .sort((a, b) => allData['linesAndStats']['perf'][b] - allData['linesAndStats']['perf'][a])
                            .reduce((map: PerfMap, addr) => {
                                map.addrs[addr] = allData['linesAndStats']['perf'][addr];
                                if (!map.addrs[addr].stores)
                                    map.addrs[addr].stores = 0;
                                if (!map.addrs[addr].loads)
                                    map.addrs[addr].loads = 0;
                                map.avgAccesses += (map.addrs[addr].stores + map.addrs[addr].loads) / Object.keys(allData['linesAndStats']['perf']).length;
                                return map;
                            }, {addrs: {}, avgAccesses: 0});
                        setPerfData(retPerfData);

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
            <Grid 
                container 
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
                        typesToSample={typesToSample}
                        typeVisMatrix={typeVisMatrix}
                        fieldsData={fieldsData}
                        expandedTypes={expandedTypes}
                        setExpandedTypes={setExpandedTypes}
                        getBucketIdx={getBucketIdx}
                        timeRange={timeRange}
                        numBuckets={numBuckets} />
                </Grid>
                <Grid
                    className='visPanel'
                    size={3.5} >
                    <CacheSets
                        cacheData={cacheData}
                        cacheInfo={cacheInfo}
                        bucketIdx={getBucketIdx(currTs)}
                        typeVisMatrix={typeVisMatrix}
                        selCacheName={selCacheName}
                        setSelCacheName={setSelCacheName}
                        fname={fname}
                        pageSize={pageSize}
                        cacheLineSize={cacheLineSize}
                        numBuckets={numBuckets}
                        expandedTypes={expandedTypes}
                        setCacheData={setCacheData} />
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
                        numBuckets={numBuckets}
                        typeVisMatrix={typeVisMatrix} />
                </Grid>
                <Grid 
                    className='visPanel'
                    size={6} >
                    <Legend 
                        colourOfType={colourOfType}
                        setColourOfType={setColourOfType}
                        typeStats={countsData}
                        typeVisMatrix={typeVisMatrix}
                        setTypeVisMatrix={setTypeVisMatrix}
                        fieldsData={fieldsData}
                        expandedTypes={expandedTypes}
                        setExpandedTypes={setExpandedTypes} />
                    <Box
                        id='settingsButtonContainer' >
                        <Tooltip
                            title={'Back to selection menu'}
                            placement='top' >
                            <IconButton
                                href={'/'} >
                                <ArrowBack />
                            </IconButton>
                        </Tooltip>
                        <Tooltip
                            title={notesOpen ? 'Close notes' : 'Open notes'}
                            placement='top' >
                            <IconButton
                                onClick={() => setNotesOpen(!notesOpen)} >
                                <EditNote />
                            </IconButton>
                        </Tooltip>
                        <Tooltip
                            title={resampling ? 'Resampling...' : 'Resample'}
                            placement='top' >
                            <IconButton
                                className={resampling ? 'resamplingButtonLoading' : ''}
                                onClick={() => {
                                    if (!resampling) {
                                        const fname = searchParams.get('fname');
                                        setResampling(true);
                                        getData(`get-pages-and-cache-data/${fname}-${pageSizeSetting}-${cacheLineSizeSetting}-${numBucketsSetting}-${clusterAlg}-${maxRunLength}-${maxRunsPerCluster}-${cacheInfoSetting[selCacheName].size}-${cacheInfoSetting[selCacheName].assoc}`, getPageVis(typeVisMatrix))
                                                .then((resp) => resp.json())
                                                .then((allData) => {
                                                    setNumBuckets(numBucketsSetting);
                                                    const sizeOfBucket = Math.max(Math.floor((timeRange.max - timeRange.min) / numBucketsSetting), 1);
                                                    setGetBucketTs(() => {
                                                        return (ts: number) => {
                                                            return Math.ceil((ts - timeRange.min) / sizeOfBucket);
                                                        }
                                                    });
                                                    setPageSize(pageSizeSetting);
                                                    setCacheLineSize(cacheLineSizeSetting);
                                                    setPageData(allData['pagesData']['page_num_events']);
                                                    setClustersData(allData['pagesData']['clusters']);
                                                    setFeaturesData(allData['pagesData']['features']);

                                                    setCacheInfo(cacheInfoSetting);
                                                    setCacheData(allData['cacheData']);

                                                    setResampling(false);
                                                });
                                    }
                                }} >
                                <Cached />
                            </IconButton>
                        </Tooltip>
                        <Tooltip
                            title={'Settings'}
                            placement='top' >
                            <SettingsButton
                                maxRunLength={maxRunLength}
                                setMaxRunLength={setMaxRunLength}
                                maxRunsPerCluster={maxRunsPerCluster}
                                setMaxRunsPerCluster={setMaxRunsPerCluster}
                                clusterAlg={clusterAlg}
                                setClusterAlg={setClusterAlg}
                                numBucketsSetting={numBucketsSetting}
                                setNumBucketsSetting={setNumBucketsSetting}
                                pageSizeSetting={pageSizeSetting}
                                setPageSizeSetting={setPageSizeSetting}
                                cacheInfoSetting={cacheInfoSetting}
                                setCacheInfoSetting={setCacheInfoSetting}
                                cacheLineSizeSetting={cacheLineSizeSetting}
                                setCacheLineSizeSetting={setCacheLineSizeSetting} />
                        </Tooltip>
                    </Box>
                </Grid>
            </Grid>
            }
            {
            notesOpen &&
            <div
                id='notesContainer' >
                <Draggable
                    nodeRef={nodeRef}
                    defaultPosition={notesPosition}
                    onStop={(e: DraggableEvent, d: DraggableData) => setNotesPosition({x: d.lastX, y: d.lastY})} >
                    <Paper
                        ref={nodeRef}
                        id='notesBackground'
                        elevation={5} >
                        <div
                            id='notesHeader' >
                            <Typography
                                id='notesHeaderText'
                                variant='h6' >
                                Notepad
                            </Typography>
                            <div id='notesCloseButton' >
                                <IconButton
                                    onClick={() => setNotesOpen(false)}
                                    size='small' >
                                    <Close />
                                </IconButton>
                            </div>
                        </div>
                        <Divider />
                        <TextareaAutosize
                            id='notesTextArea'
                            minRows={5}
                            maxRows={12} />
                    </Paper>
                </Draggable>
            </div>
            }
        </ThemeProvider>
    );
}