'use client';
import { TypeToColourMap, generateColours, getData, requestErrorMessage, getSubtypeName, getTypeName } from '../ui/appShared';
import { Fragment, Suspense, ChangeEvent, forwardRef, useEffect, useRef, useState } from 'react';
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
import { getNotesForFile, theme } from '../ui/appShared';
import { useSearchParams } from 'next/navigation';
import { Badge, Divider, FormControl, IconButton, InputLabel, LinearProgress, MenuItem, Paper, Popover, Select, Slider, Tab, Tabs, TextareaAutosize, TextField, ToggleButton, ToggleButtonGroup, Tooltip, Typography } from '@mui/material';
import { flushSync } from 'react-dom';
import { ArrowBack, Cached, Close, EditNote, Settings } from '@mui/icons-material';
import Draggable, { DraggableData, DraggableEvent } from 'react-draggable';
import { Alert, Snackbar } from '@mui/material';

interface LogBody {
    'myNotes': string,
    'colours': {'type': string, 'colour': string}[]
};

interface LinePoint {
    'type': number,
    'bucket': number,
    'size': number
};

const INIT_PAGE_SIZE = 4096;
const INIT_CACHELINE_SIZE = 64;
const INIT_NUM_BUCKETS = 2000;
const INIT_MAX_RUN_LENGTH = 5;
const INIT_MAX_RUNS_PER_CLUSTER = 3;
const INIT_PAGE_BUDGET = 128;
const INIT_RECORD_BUDGET = 1000000;
const INIT_CLUSTER_ALG = 'mbkmeans';
const INIT_CACHE_SIZE = 32768;
const INIT_CACHE_ASSOC = 8;
const INIT_TIME_RANGE = {min: 0, max: 1};
const INIT_CACHE_INFO: CacheInfoMap = {
    'L1': {size: 32768, assoc: 8},
    'L2': {size: 2097152, assoc: 8},
    'L3': {size: 4194304, assoc: 8}
};
const INIT_CACHE_DATA: {occ: number[][]; idxToTpAndSt: string[]; numSets: number} = {occ: [[]], idxToTpAndSt: [''], numSets: 1};
const MAX_POINTS_PER_LINE = 3000;

async function logData(fname: string, logBody: LogBody) {
    const resp = await fetch(`http://localhost:5000/log-data/${fname}`, {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(logBody)
    });
    return resp;
}

function a11yProps(value: string) {
    return {
        id: `simple-tab-${value}`,
        'aria-controls': `simple-tabpanel-${value}`
    };
}

const SettingsButton = forwardRef(function SettingsButton({ maxRunLength, setMaxRunLength, maxRunsPerCluster, setMaxRunsPerCluster,
                         clusterAlg, setClusterAlg, numBucketsSetting, setNumBucketsSetting,
                         pageSizeSetting, setPageSizeSetting, cacheInfoSetting, setCacheInfoSetting,
                         cacheLineSizeSetting, setCacheLineSizeSetting,
                         pageBudget, setPageBudget, recordBudget, setRecordBudget, selectionSeed, setSelectionSeed, ...props } :
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
        setCacheLineSizeSetting: (a: number) => void,
        pageBudget: number, setPageBudget: (a: number) => void,
        recordBudget: number, setRecordBudget: (a: number) => void,
        selectionSeed: number, setSelectionSeed: (a: number) => void
    }, ref: React.ForwardedRef<HTMLButtonElement>) {
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
                        <Grid size={6}>
                            <TextField label='Maximum pages' type='number' value={pageBudget}
                                inputProps={{min: 1, step: 1}}
                                onChange={e => setPageBudget(Number(e.target.value))} />
                        </Grid>
                        <Grid size={6}>
                            <TextField label='Maximum history records' type='number' value={recordBudget}
                                inputProps={{min: 1, step: 1}}
                                onChange={e => setRecordBudget(Number(e.target.value))} />
                        </Grid>
                        <Grid size={6}>
                            <TextField label='Selection seed' type='number' value={selectionSeed}
                                inputProps={{min: 0, max: 4294967295, step: 1}}
                                onChange={e => setSelectionSeed(Number(e.target.value))} />
                        </Grid>
                        <Grid size={12}>
                            Both limits apply on Resample. Paper settings: 128 pages, 1,000,000 records, 2000 time buckets. Perf-directed pages are retained even if they exceed a limit.
                        </Grid>
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
                                    onChange={(e, v) => { if (typeof v === 'number') setMaxRunLength(v); }} />
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
                                    onChange={(e, v) => { if (typeof v === 'number') setMaxRunsPerCluster(v); }} />
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
                                onChange={(e, v) => { if (v !== null) setPageSizeSetting(v); }} >
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
                                onChange={(e, v) => { if (v !== null) setCacheLineSizeSetting(v); }} >
                                <ToggleButton value={16} >16 B</ToggleButton>
                                <ToggleButton value={32} >32 B</ToggleButton>
                                <ToggleButton value={64} >64 B</ToggleButton>
                                <ToggleButton value={128} >128 B</ToggleButton>
                                <ToggleButton value={256} >256 B</ToggleButton>
                            </ToggleButtonGroup>
                        </Grid>
                        {
                            Object.keys(cacheInfoSetting).map((cname) =>    <Fragment key={cname}>
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
                                                                                                if (v === null) return;
                                                                                                const newCacheSizeUnitSetting = structuredClone(cacheSizeUnitSetting);
                                                                                                newCacheSizeUnitSetting[cname] = v;
                                                                                                setCacheSizeUnitSetting(newCacheSizeUnitSetting);
                                                                                            }} >
                                                                                            {
                                                                                                SIZE_UNIT_SUFF.slice(0, 3).map((suff, i) => <ToggleButton key={suff} value={i} >{suff}</ToggleButton>)
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
                                                                            </Fragment>)
                        }
                    </Grid>
                    }
                    </div>
                </Box>
            </Popover>
        </>
    );
});

function VisPanels({fname, initialBuckets}: {fname: string | null; initialBuckets: number}) {
    const [loading, setLoading] = useState(true);
    const [initialized, setInitialized] = useState(false);
    const [requestError, setRequestError] = useState<string | null>(null);
    const [cacheRequestLoading, setCacheRequestLoading] = useState(false);
    const [pageSize, setPageSize] = useState(INIT_PAGE_SIZE);
    const [currTs, setCurrTs] = useState(0);
    const [cacheLineSize, setCacheLineSize] = useState(INIT_CACHELINE_SIZE);
    const [colourOfType, setColourOfType] = useState<TypeToColourMap>({});
    const [lineData, setLineData] = useState<{[tp: string]: SizePoint[]}>({});
    const [statsData, setStatsData] = useState({});
    const [fieldsData, setFieldsData] = useState<{[tp: string]: SubtypeEntry[]}>({});
    const [countsData, setCountsData] = useState({});
    const [pageData, setPageData] = useState({});
    const [selection, setSelection] = useState<{
        selected_pages: number; selected_records: number; page_budget: number; record_budget: number;
        represented_clusters: number; available_clusters: number; omitted_types: string[];
        perf_budget_excess: number; perf_record_budget_excess: number;
        omitted_history_extremes: {cluster: number; end: string; records: number}[];
    } | null>(null);
    const [clustersData, setClustersData] = useState({});
    const [sumClusterSizes, setSumClusterSizes] = useState<number>(0);
    const [numClusters, setNumClusters] = useState<number>(0);
    const [featuresData, setFeaturesData] = useState({});
    const [perfData, setPerfData] = useState<PerfMap>({addrs: {}, avgAccesses: 0});
    const [cacheInfo, setCacheInfo] = useState(INIT_CACHE_INFO);
    const [cacheData, setCacheData] = useState(INIT_CACHE_DATA);
    const [numBuckets, setNumBuckets] = useState(initialBuckets);
    const [timeRange, setTimeRange] = useState(INIT_TIME_RANGE);
    const [timestampHz, setTimestampHz] = useState<number | null>(null);
    const [getBucketIdx, setGetBucketTs] = useState(() => (ts: number) => 0);
    const [typesToSample, setTypesToSample] = useState({});
    const [alignData, setAlignData] = useState({});

    const [lineVis, setLineVis] = useState<{[tp: string]: boolean}>({});
    const [pageVis, setPageVis] = useState<{[tp: string]: boolean}>({});
    const [cacheVis, setCacheVis] = useState<{[tp: string]: boolean}>({});
    // const [typeVisMatrix, setTypeVisMatrix] = useState<{[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}}>({});

    const [selCacheName, setSelCacheName] = useState<string>(Object.keys(cacheInfo)[0]);
    const [resampling, setResampling] = useState<boolean>(false);
    const [expandedTypes, setExpandedTypes] = useState<{[tp: string]: boolean}>({});

    /*  State for settings menu. Variables with suffix "Setting" are used
        to update the corresponding state variable only upon resample. */
    const [maxRunLength, setMaxRunLength] = useState(INIT_MAX_RUN_LENGTH);
    const [maxRunsPerCluster, setMaxRunsPerCluster] = useState(INIT_MAX_RUNS_PER_CLUSTER);
    const [clusterAlg, setClusterAlg] = useState<'mbkmeans' | 'kmeans' | 'dbscan' | 'agglomerative' | 'meanshift'>(INIT_CLUSTER_ALG);
    const [numBucketsSetting, setNumBucketsSetting] = useState(initialBuckets);
    const [pageSizeSetting, setPageSizeSetting] = useState(INIT_PAGE_SIZE);
    const [cacheInfoSetting, setCacheInfoSetting] = useState(INIT_CACHE_INFO);
    const [cacheLineSizeSetting, setCacheLineSizeSetting] = useState(INIT_CACHELINE_SIZE);
    const [pageBudget, setPageBudget] = useState(INIT_PAGE_BUDGET);
    const [recordBudget, setRecordBudget] = useState(INIT_RECORD_BUDGET);
    const [selectionSeed, setSelectionSeed] = useState(0);

    /*  State and refs for notes. */
    const nodeRef = useRef(null);
    const notesTextRef = useRef<HTMLTextAreaElement>(null);
    const [notesOpen, setNotesOpen] = useState<boolean>(false);
    const [notesPosition, setNotesPosition] = useState({x: 0, y: 0});
    const [notesText, setNotesText] = useState<string>('');

    useEffect(() => {
        let cancelled = false;
        async function initialize() {
            try {
                if (!fname) throw new Error('Select a trace to open.');
                // Initial settings belong to this trace. Editing settings later
                // only takes effect through the explicit Resample action.
                const resp = await getData(`init-app/${fname}-${INIT_PAGE_SIZE}-${INIT_CACHELINE_SIZE}-${initialBuckets}-${INIT_CLUSTER_ALG}-${INIT_MAX_RUN_LENGTH}-${INIT_MAX_RUNS_PER_CLUSTER}-${INIT_CACHE_INFO.L1.size}-${INIT_CACHE_INFO.L1.assoc}?page_budget=${INIT_PAGE_BUDGET}&record_budget=${INIT_RECORD_BUDGET}&seed=0`, null);
                const allData = await resp.json();
                if (cancelled) return;
                const allFieldNames: string[] = [];
                Object.keys(allData.linesAndStats.fields).forEach(tp => {
                    allData.linesAndStats.fields[tp].forEach((field: SubtypeEntry) => allFieldNames.push(getSubtypeName(tp, field.subtype)));
                });
                const typeNames: string[] = allData.types.concat(allFieldNames);
                let colours = generateColours(typeNames);
                let notes = '';
                try {
                    const [savedColours, savedNotes] = await Promise.all([
                        getData(`log-data/get-colours/${fname}`, null).then(response => response.json()),
                        getNotesForFile(fname),
                    ]);
                    for (const entry of savedColours) colours[entry.type] = d3.color(entry.colour);
                    notes = savedNotes[1];
                } catch (error) {
                    if (!cancelled) setRequestError(requestErrorMessage(error));
                }
                if (cancelled) return;
                const allMaps = Object.fromEntries(typeNames.map(type => [type, true]));
                setLineVis(allMaps); setPageVis(allMaps); setCacheVis(allMaps);
                setExpandedTypes(Object.fromEntries(allData.types.map((type: string) => [type.replace(/\s+/g, ''), false])));
                setColourOfType(colours); setNotesText(notes);
                const minTs: number = allData.linesAndStats.minTs;
                const maxTs: number = allData.linesAndStats.maxTs;
                setTimeRange({min: minTs, max: maxTs});
                const bucketSize = Math.max(Math.floor((maxTs - minTs) / initialBuckets), 1);
                setGetBucketTs(() => (ts: number) => Math.ceil((ts - minTs) / bucketSize));
                setCurrTs(minTs);
                setTimestampHz(allData.traceClock?.timestamp_hz ?? null);
                setLineData(allData.linesAndStats.pts);
                setStatsData(allData.linesAndStats.stats);
                setFieldsData(allData.linesAndStats.fields);
                setCountsData(allData.linesAndStats.counts);
                const align: {[tp: string]: {size: number; align: number; count: number}[]} = {};
                for (const entry of allData.linesAndStats.align) (align[entry.type] ??= []).push(entry);
                setAlignData(align);
                const perf: PerfMap = {addrs: {}, avgAccesses: 0};
                const perfEntries = Object.entries(allData.linesAndStats.perf)
                    .map(([address, counters]) => [Number(address), counters] as const).filter(([address]) => address >= 0);
                for (const [address, raw] of perfEntries) {
                    const counters = raw as PerfMap['addrs'][number];
                    perf.addrs[address] = {...counters, loads: counters.loads || 0, stores: counters.stores || 0};
                    perf.avgAccesses += (perf.addrs[address].loads + perf.addrs[address].stores) / perfEntries.length;
                }
                setPerfData(perf);
                setPageData(allData.pagesData.page_num_events);
                setSelection(allData.pagesData.selection ?? null);
                setClustersData(allData.pagesData.clusters);
                setSumClusterSizes(allData.pagesData.sum_cluster_sizes);
                setNumClusters(allData.pagesData.num_clusters);
                setFeaturesData(allData.pagesData.features);
                setCacheData(allData.cacheData);
                setInitialized(true);
            } catch (error) {
                if (!cancelled) setRequestError(requestErrorMessage(error));
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        void initialize();
        return () => { cancelled = true; };
    }, [fname, initialBuckets]);

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Snackbar open={requestError !== null} anchorOrigin={{vertical: 'top', horizontal: 'center'}}>
                <Alert severity='error' onClose={initialized ? () => setRequestError(null) : undefined} sx={{maxWidth: 700}}>
                    {requestError}
                    {!initialized && requestError?.includes('memory budget') && numBuckets > 1 &&
                        <div><a href={`?fname=${encodeURIComponent(fname || '')}&buckets=${Math.max(1, Math.floor(numBuckets / 2))}`}>
                            Retry with fewer time buckets ({Math.max(1, Math.floor(numBuckets / 2))})
                        </a></div>}
                    {!initialized && <div><a href='/'>Back to database selection</a></div>}
                </Alert>
            </Snackbar>
            {
            loading && 
            <Box id='loadingBox' >
                <LinearProgress />
            </Box>
            }
            {
            !loading && initialized &&
            <Grid 
                container 
                id='visPanelGrid'
                rowSpacing={2}
                columnSpacing={2} >
                <Grid 
                    className='visPanel'
                    size={8.5} sx={{flexDirection: 'column', alignItems: 'stretch'}} >
                    {selection && <Alert severity={
                        selection.represented_clusters < selection.available_clusters || selection.omitted_types.length > 0 ||
                        selection.perf_budget_excess > 0 || selection.perf_record_budget_excess > 0 ? 'warning' : 'info'}>
                        Showing {selection.selected_pages}/{selection.page_budget} pages and {selection.selected_records?.toLocaleString()}
                        /{selection.record_budget?.toLocaleString()} history records; {selection.represented_clusters}/{selection.available_clusters} clusters.
                        {selection.omitted_types.length > 0 && ` ${selection.omitted_types.length} types are not represented.`}
                        {(selection.perf_budget_excess > 0 || selection.perf_record_budget_excess > 0) &&
                            ' Mandatory perf-directed pages exceed the limits.'}
                        {(selection.omitted_history_extremes?.length ?? 0) > 0 &&
                            ` ${selection.omitted_history_extremes.length} within-cluster history-count extremes are not represented.`}
                        {selection.represented_clusters < selection.available_clusters &&
                            ' Increase the limits in Sample settings to inspect more clusters.'}
                    </Alert>}
                    <Pages
                        pages={pageData}
                        clustersData={clustersData}
                        sumClusterSizes={sumClusterSizes}
                        numClusters={numClusters}
                        features={featuresData}
                        pageSize={pageSize}
                        perf={perfData}
                        colourOfType={colourOfType}
                        currTs={currTs}
                        cacheLineSize={cacheLineSize}
                        clusterAlg={clusterAlg}
                        maxRunLength={maxRunLength}
                        maxRunsPerCluster={maxRunsPerCluster}
                        pageVis={pageVis}
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
                        cacheVis={cacheVis}
                        selCacheName={selCacheName}
                        setSelCacheName={setSelCacheName}
                        fname={fname}
                        pageSize={pageSize}
                        cacheLineSize={cacheLineSize}
                        numBuckets={numBuckets}
                        expandedTypes={expandedTypes}
                        busy={resampling}
                        onBusyChange={setCacheRequestLoading}
                        setCacheData={setCacheData} />
                </Grid>

                <Grid
                    className='visPanel' 
                    size={6} >
                    <TimeGraph
                        lines={lineData}
                        colourOfType={colourOfType}
                        currTs={currTs}
                        setCurrTs={setCurrTs}
                        timeRange={timeRange}
                        timestampHz={timestampHz}
                        numBuckets={numBuckets}
                        lineVis={lineVis} />
                </Grid>
                <Grid 
                    className='visPanel'
                    size={6} >
                    <Legend 
                        colourOfType={colourOfType}
                        setColourOfType={setColourOfType}
                        typeStats={countsData}
                        lineVis={lineVis}
                        pageVis={pageVis}
                        cacheVis={cacheVis}
                        setLineVis={setLineVis}
                        setPageVis={setPageVis}
                        setCacheVis={setCacheVis}
                        fieldsData={fieldsData}
                        expandedTypes={expandedTypes}
                        setExpandedTypes={setExpandedTypes}
                        alignData={alignData}
                        cacheLineSize={cacheLineSize} />
                    <Box
                        id='settingsButtonContainer' >
                        <Tooltip
                            title={'Back to selection menu'}
                            placement='top' >
                            <IconButton
                                onClick={() => {
                                    const logBody: LogBody = {
                                        'myNotes': notesText,
                                        'colours': Object.entries(colourOfType)
                                                            .map((pair: [string, d3.RGBColor | d3.HSLColor | null]) => ({'type': pair[0], 'colour': pair[1] ? pair[1].toString() : '#ffffff'}))
                                    };
                                    if (fname) {
                                        logData(fname, logBody)
                                            .then((resp) => {
                                                window.location.href = "http://localhost:3000/";
                                            });
                                    }
                                }} >
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
                            <span>
                            <IconButton
                                aria-label={resampling ? 'Resampling...' : 'Resample'}
                                className={resampling ? 'resamplingButtonLoading' : ''}
                                disabled={resampling || cacheRequestLoading}
                                onClick={() => {
                                    if (!resampling && !cacheRequestLoading) {
                                        setRequestError(null);
                                        setResampling(true);
                                        getData(`get-pages-and-cache-data/${fname}-${pageSizeSetting}-${cacheLineSizeSetting}-${numBucketsSetting}-${clusterAlg}-${maxRunLength}-${maxRunsPerCluster}-${cacheInfoSetting[selCacheName].size}-${cacheInfoSetting[selCacheName].assoc}?page_budget=${pageBudget}&record_budget=${recordBudget}&seed=${selectionSeed}`, pageVis)
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
                                                    setSelection(allData['pagesData']['selection'] ?? null);
                                                    setClustersData(allData['pagesData']['clusters']);
                                                    setSumClusterSizes(allData['pagesData']['sum_cluster_sizes']);
                                                    setNumClusters(allData['pagesData']['num_clusters']);
                                                    setFeaturesData(allData['pagesData']['features']);

                                                    setCacheInfo(cacheInfoSetting);
                                                    setCacheData(allData['cacheData']);
                                                    console.log(`cache sets in settings: ${Math.floor(cacheInfoSetting[selCacheName].size / cacheLineSizeSetting)}, cache sets in data: ${allData['cacheData'].numSets}`);

                                                })
                                                .catch((error: unknown) => setRequestError(requestErrorMessage(error)))
                                                .finally(() => setResampling(false));
                                    }
                                }} >
                                {
                                (Math.floor(cacheInfoSetting[selCacheName].size / (cacheLineSizeSetting*cacheInfoSetting[selCacheName].assoc)) == cacheData.numSets || resampling) ?
                                <Cached />
                                :
                                <Badge
                                    color='secondary'
                                    variant='dot' >
                                    <Cached />
                                </Badge>
                                }
                            </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip
                            title={'Settings'}
                            placement='top' >
                            <SettingsButton
                                pageBudget={pageBudget} setPageBudget={setPageBudget}
                                recordBudget={recordBudget} setRecordBudget={setRecordBudget}
                                selectionSeed={selectionSeed} setSelectionSeed={setSelectionSeed}
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
                                    onClick={() => {
                                        setNotesOpen(false);
                                        setNotesText(notesTextRef.current ? notesTextRef.current.value : '');
                                    }}
                                    size='small' >
                                    <Close />
                                </IconButton>
                            </div>
                        </div>
                        <Divider />
                        <TextareaAutosize
                            id='notesTextArea'
                            ref={notesTextRef}
                            defaultValue={notesText}
                            placeholder='Enter notes here'
                            minRows={5}
                            maxRows={12} />
                    </Paper>
                </Draggable>
            </div>
            }
        </ThemeProvider>
    );
}

function SelectedTrace() {
    const params = useSearchParams();
    const fname = params.get('fname');
    const requestedBuckets = Number(params.get('buckets'));
    const initialBuckets = Number.isInteger(requestedBuckets) && requestedBuckets >= 1 && requestedBuckets <= INIT_NUM_BUCKETS
        ? requestedBuckets : INIT_NUM_BUCKETS;
    return <VisPanels key={`${fname}:${initialBuckets}`} fname={fname} initialBuckets={initialBuckets} />;
}

export default function VisPanelsPage() {
    return <Suspense fallback={<div>Loading trace settings…</div>}><SelectedTrace /></Suspense>;
}
