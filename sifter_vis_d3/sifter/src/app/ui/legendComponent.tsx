'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Checkbox, IconButton, Menu, MenuItem, Paper, Popover, TextField, Tooltip, Typography } from '@mui/material';
import './componentStyles.scss';
import { generateColours, getSubtypeName, TypeToColourMap } from './appShared';
import { BarChart, Casino, Close, InsertChart, KeyboardArrowLeft, KeyboardArrowRight, StackedLineChart, Window } from '@mui/icons-material';
import { Box, styled } from '@mui/system';
import { MaterialPicker, PhotoshopPicker, SketchPicker } from 'react-color';

export interface SubtypeEntry {
    name: string,
    offset: number,
    size: number,
    subtype: string
}

interface TypeStat {
    numAllocs: number,
    numPages: number
}

interface TypeToStatsMap {
    [ tp: string ]: TypeStat
}

interface LegendRowSortMode {
    mode: 'names' | 'allocs' | 'pages',
    rev: boolean
}

const ALIGN_SIZE_WIDTH = 500;
const ALIGN_SIZE_HEIGHT = 300;
const ALIGN_SIZE_MARGIN = 40;
const ALIGN_SIZE_BANDSPACE = 8;
const VisCheckbox = styled(Checkbox)({
    padding: '2.5px',
});

function LegendTableHeader({ visExpanded, setVisExpanded, currSortMode, setCurrSortMode } :
    {
        visExpanded: boolean,
        setVisExpanded: (a: boolean) => void,
        currSortMode: LegendRowSortMode,
        setCurrSortMode: (a: LegendRowSortMode) => void
    }) {
    return (
        <thead className={visExpanded ? 'visExpanded' : ''} >
            <tr className={visExpanded ? 'visExpanded' : ''} >
                {
                visExpanded &&
                <th>
                    <div id='visibilityHeaders' >
                        <Tooltip
                            title='Line graph visibility'
                            placement='top' >
                            <StackedLineChart />
                        </Tooltip>
                        <Tooltip
                            title='Pages visibility'
                            placement='top' >
                            <BarChart
                                sx={{
                                    transform: 'rotate(90deg)'
                                }} />
                        </Tooltip>
                        <Tooltip
                            title='Cache visibility'
                            placement='top' >
                            <Window />
                        </Tooltip>
                    </div>
                </th>
                }
                <th>
                    <IconButton
                        className='centerTableCell'
                        onClick={() => setVisExpanded(!visExpanded)} >
                        {
                        !visExpanded &&
                        <KeyboardArrowLeft />
                        }
                        {
                        visExpanded &&
                        <KeyboardArrowRight />
                        }
                    </IconButton>
                </th>
                <th />
                <th />
                <th>
                    <div
                        className='legendColumnLabel'
                        onClick={() => setCurrSortMode(currSortMode.mode == 'names' ? {mode: 'names', rev: !currSortMode.rev} : {mode: 'names', rev: false})} >
                        Type names{currSortMode.mode == 'names' ? (currSortMode.rev ? ' ▲' : ' ▼') : ''}
                    </div>
                </th>
                <th style={{
                    textAlign: 'left'
                }}>
                    <div
                        className='legendColumnLabel'
                        onClick={() => setCurrSortMode(currSortMode.mode == 'allocs' ? {mode: 'allocs', rev: !currSortMode.rev} : {mode: 'allocs', rev: false})} >
                        # allocs{currSortMode.mode == 'allocs' ? (currSortMode.rev ? '▲' : '▼') : ''}
                    </div>
                </th>
                <th style={{
                    textAlign: 'left'
                }}>
                    <div
                        className='legendColumnLabel'
                        onClick={() => setCurrSortMode(currSortMode.mode == 'pages' ? {mode: 'pages', rev: !currSortMode.rev} : {mode: 'pages', rev: false})} >
                        # pages{currSortMode.mode == 'pages' ? (currSortMode.rev ? '▲' : '▼') : ''}
                    </div>
                </th>
            </tr>
        </thead>
    );
}

function LegendTableFooter({ types, setFilterText, setColourOfType, visExpanded } :
    {
        types: string[],
        setFilterText: (a: string) => void,
        setColourOfType: (a: TypeToColourMap) => void,
        visExpanded: boolean
    }) {
    return (
        <tfoot className={visExpanded ? 'visExpanded' : ''} >
            <tr className={visExpanded ? 'visExpanded' : ''} >
                {
                visExpanded &&
                <td />
                }
                <td>
                    <div className='centerTableCell' >
                        <Tooltip
                            title='Randomize colours'
                            placement='bottom' >
                            <IconButton
                                id='randColours'
                                onClick={() => setColourOfType(generateColours(types))} >
                                <Casino />
                            </IconButton>
                        </Tooltip>
                    </div>
                </td>
                <td />
                <td />
                <td>
                    <TextField
                            id='typeFilter'
                            label='Filter types'
                            variant='filled'
                            size='small'
                            fullWidth
                            maxRows={1}
                            onChange={(e) => setFilterText(e.target.value)} />
                </td>
                <td></td>
                <td></td>
            </tr>
        </tfoot>
    );
}

function VisRightClickMenu({ rightClickAnchor, setRightClickAnchor, label, visMatrix,
                             typeName, setVisMatrix } :
    {
        rightClickAnchor: HTMLElement | null,
        setRightClickAnchor: (a: HTMLElement | null) => void,
        label: string | undefined,
        visMatrix: {[tp: string]: boolean},
        setVisMatrix: (a: {[tp: string]: boolean}) => void,
        typeName: string
    }) {
    return (
        <Menu
            className='visRightClickMenu'
            anchorEl={rightClickAnchor}
            open={rightClickAnchor !== null}
            onClose={() => setRightClickAnchor(null)}
            MenuListProps={{
                'aria-labelledby': label
            }} >
            <MenuItem
                onClick={() => {
                    const newVisMatrix = structuredClone(visMatrix);
                    Object.keys(newVisMatrix).forEach((tp) => newVisMatrix[tp] = tp == typeName);
                    setVisMatrix(newVisMatrix);
                    setRightClickAnchor(null);
                }} >
                Only this type
            </MenuItem>
            <MenuItem
                onClick={() => {
                    const newVisMatrix = structuredClone(visMatrix);
                    Object.keys(newVisMatrix).forEach((tp) => newVisMatrix[tp] = tp != typeName);
                    setVisMatrix(newVisMatrix);
                    setRightClickAnchor(null);
                }}  >
                Everything but this type
            </MenuItem>
        </Menu>
    );
}

function LegendRow({ typeName, visExpanded, stats, lineVis, pageVis, cacheVis,
                     setLineVis, setPageVis, setCacheVis, fields, expandedTypes,
                     setExpandedTypes, colourOfType, setColourOfType,
                     setColourMenuAnchor, setSelMenuType, setCurrColourSel,
                     hasAlignData, setAlignTypeDisplay } :
    {
        typeName: string,
        colourOfType: {[tp: string]: d3.RGBColor | d3.HSLColor | null},
        setColourOfType: (a: TypeToColourMap) => void,
        visExpanded: boolean,
        stats: TypeStat,
        lineVis: {[tp: string]: boolean},
        pageVis: {[tp: string]: boolean},
        cacheVis: {[tp: string]: boolean},
        setLineVis: (a: {[tp: string]: boolean}) => void,
        setPageVis: (a: {[tp: string]: boolean}) => void,
        setCacheVis: (a: {[tp: string]: boolean}) => void,
        fields: SubtypeEntry[] | null,
        expandedTypes: {[tp: string]: boolean},
        setExpandedTypes: (a: {[tp: string]: boolean}) => void,
        setColourMenuAnchor: (a: HTMLDivElement | null) => void,
        setSelMenuType: (a: string | undefined) => void,
        setCurrColourSel: (a: string) => void,
        hasAlignData: boolean,
        setAlignTypeDisplay: (a: string) => void
    }) {
    const [rightClickAnchor, setRightClickAnchor] = useState<HTMLElement | null>(null);
    const [label, setLabel] = useState<string | undefined>(undefined);
    const [rightClickedType, setRightClickedType] = useState<string>('');

    return (
        <>
            <VisRightClickMenu
                rightClickAnchor={rightClickAnchor}
                setRightClickAnchor={setRightClickAnchor}
                label={label}
                visMatrix={label?.startsWith('line') ? lineVis :
                            label?.startsWith('page') ? pageVis :
                            cacheVis}
                setVisMatrix={label?.startsWith('line') ? setLineVis :
                            label?.startsWith('page') ? setPageVis :
                            setCacheVis}
                typeName={rightClickedType}
                />
            <tr className={visExpanded ? 'visExpanded' : ''} >
                {
                visExpanded &&
                <td>
                    <div className='legendVisCheckboxContainer' >
                        <VisCheckbox
                            id={`line-vis-${typeName}`}
                            checked={lineVis[typeName]}
                            size='small'
                            onContextMenu={(e) => {
                                e.preventDefault();
                                setLabel(`line-vis-${typeName}`);
                                setRightClickAnchor(e.currentTarget);
                                setRightClickedType(typeName);
                            }}
                            onChange={() => {
                                const newLineVis = structuredClone(lineVis);
                                newLineVis[typeName] = !lineVis[typeName];
                                setLineVis(newLineVis);
                            }} />
                        <VisCheckbox
                            id={`page-vis-${typeName}`}
                            checked={pageVis[typeName]}
                            size='small'
                            onContextMenu={(e) => {
                                e.preventDefault();
                                setLabel(`page-vis-${typeName}`);
                                setRightClickAnchor(e.currentTarget);
                                setRightClickedType(typeName);
                            }}
                            onChange={() => {
                                const newPageVis = structuredClone(pageVis);
                                newPageVis[typeName] = !pageVis[typeName];
                                setPageVis(newPageVis);
                            }} />
                        <VisCheckbox
                            id={`cache-vis-${typeName}`}
                            checked={cacheVis[typeName]}
                            size='small'
                            onContextMenu={(e) => {
                                e.preventDefault();
                                setLabel(`cache-vis-${typeName}`);
                                setRightClickAnchor(e.currentTarget);
                                setRightClickedType(typeName);
                            }}
                            onChange={() => {
                                const newCacheVis = structuredClone(cacheVis);
                                newCacheVis[typeName] = !cacheVis[typeName];
                                setCacheVis(newCacheVis);
                            }} />
                    </div>
                </td>
                }
                <td>
                    <div className='centerTableCell'>
                        <Paper
                            className='legendColourTile'
                            onClick={(e) => {
                                setSelMenuType(typeName);
                                setColourMenuAnchor(e.currentTarget);
                                setCurrColourSel(colourOfType[typeName] == null ? '#ffffff' : colourOfType[typeName].formatHex());
                            }}
                            sx={{
                                width: '20px',
                                height: '20px',
                                backgroundColor: colourOfType[typeName] == null ? 'white' : colourOfType[typeName].formatHex()
                            }} />
                    </div>
                </td>
                <td>
                    {
                    hasAlignData &&
                    <IconButton
                        className='alignDataButton'
                        size='small'
                        onClick={() => setAlignTypeDisplay(typeName)} >
                        <InsertChart/>
                    </IconButton>
                    }
                </td>
                <td>
                    <div
                        className='legendColumnLabel'
                        onClick={() => {
                            const newExpandedTypes = structuredClone(expandedTypes);
                            newExpandedTypes[typeName.replace(/\s+/g, '')] = !expandedTypes[typeName.replace(/\s+/g, '')];
                            setExpandedTypes(newExpandedTypes);
                        }} >
                    {
                        fields ? (expandedTypes[typeName.replace(/\s+/g, '')] ? '▾' :'▸') : ''
                    }
                    </div>
                </td>
                <td>
                    <Typography className='legendText' >
                        {typeName}
                    </Typography>
                </td>
                <td>
                    <Typography className='legendText numberText' >
                        {stats.numAllocs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
                    </Typography>
                </td>
                <td>
                    <Typography className='legendText numberText' >
                        {stats.numPages.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
                    </Typography>
                </td>
            </tr>
            {
            (fields && expandedTypes[typeName.replace(/\s+/g, '')]) &&
            <>
                {
                    fields.filter((field, i) => fields.findIndex((fd) => fd.subtype == field.subtype) === i)
                        .map((field) =>
                    <tr key={`str-${typeName}-${field.name}`} >
                        {
                        visExpanded &&
                        <td>
                            <div className='legendVisCheckboxContainer' >
                                <VisCheckbox
                                    checked={false}
                                    size='small'
                                    disabled />
                                <VisCheckbox
                                    id={`page-vis-${getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)}`}
                                    checked={pageVis[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)]}
                                    size='small'
                                    onContextMenu={(e) => {
                                        e.preventDefault();
                                        setLabel(`page-vis-${getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)}`);
                                        setRightClickAnchor(e.currentTarget);
                                        setRightClickedType(getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype));
                                    }}
                                    onChange={() => {
                                        const newPageVis = structuredClone(pageVis);
                                        newPageVis[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)] = !pageVis[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)];
                                        setPageVis(newPageVis);
                                    }} />
                                <VisCheckbox
                                    id={`cache-vis-${getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)}`}
                                    checked={cacheVis[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)]}
                                    size='small'
                                    onContextMenu={(e) => {
                                        e.preventDefault();
                                        setLabel(`cache-vis-${getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)}`);
                                        setRightClickAnchor(e.currentTarget);
                                        setRightClickedType(getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype));
                                    }}
                                    onChange={() => {
                                        const newCacheVis = structuredClone(cacheVis);
                                        newCacheVis[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)] = !cacheVis[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)];
                                        setCacheVis(newCacheVis);
                                    }} />
                            </div>
                        </td>
                        }
                        <td>
                            <div className='centerTableCell'>
                                <Paper
                                    className='legendColourTile'
                                    onClick={(e) => {
                                        setSelMenuType(getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype));
                                        setColourMenuAnchor(e.currentTarget);
                                    }}
                                    sx={{
                                        width: '20px',
                                        height: '20px',
                                        backgroundColor: colourOfType[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)]?.formatHex() ?? 'white'
                                    }} />
                            </div>
                        </td>
                        <td/>
                        <td/>
                        <td>
                            <Typography className='legendText' >
                                {'↳ ' + field.subtype}
                            </Typography>
                        </td>
                        <td/>
                        <td/>
                    </tr>)
                }
            </>
            }
        </>
    );
}

export function AlignAndSize({ data, setAlignTypeDisplay, colour } :
    {
        data: {size: number, align: number, count: number}[],
        setAlignTypeDisplay: (a: string | null) => void,
        colour: d3.Color
    }) {
    const barGroupRef = useRef<SVGGElement>(null);
    const svgRef = useRef<SVGSVGElement>(null);
    const [hiddenSizes, setHiddenSizes] = useState<Set<number>>(new Set());

    useEffect(() => {
        // ALIGNMENT is a capture-time histogram. Its offsets cannot be
        // reinterpreted at a different cache-line size without the raw input.
        const offsets = Array.from(new Set(data.map(entry => entry.align))).sort((a, b) => a - b);
        const counts = new Map(offsets.map(offset => [offset, 0]));
        const totals = new Map(counts);
        for (const entry of data) {
            totals.set(entry.align, totals.get(entry.align)! + entry.count);
            if (!hiddenSizes.has(entry.size)) counts.set(entry.align, counts.get(entry.align)! + entry.count);
        }
        const bars = Array.from(counts);
        const xScale = d3.scaleBand<number>().domain(offsets).range([0, ALIGN_SIZE_WIDTH]);
        const yScale = d3.scaleLinear().domain([d3.max(totals.values()) || 1, 0])
            .range([ALIGN_SIZE_MARGIN + 10, ALIGN_SIZE_HEIGHT]);
        const svg = d3.select(svgRef.current!);
        svg.select<SVGGElement>('#alignXAxisGroup').attr('transform', `translate(0,${ALIGN_SIZE_HEIGHT})`)
            .call(d3.axisBottom(xScale).tickSize(0));
        svg.select<SVGGElement>('#alignYAxisGroup').call(d3.axisLeft(yScale).tickFormat(value => {
            const count = Number(value);
            return count >= 1e9 ? `${(count / 1e9).toFixed(1)}B` : count >= 1e6 ? `${(count / 1e6).toFixed(1)}M`
                : count >= 1e3 ? `${(count / 1e3).toFixed(1)}K` : `${count}`;
        }));
        d3.select(barGroupRef.current!).selectAll<SVGRectElement, [number, number]>('.alignBar')
            .data(bars, entry => entry[0]).join('rect').attr('class', 'alignBar')
            .attr('x', entry => xScale(entry[0])! + ALIGN_SIZE_BANDSPACE / 2)
            .attr('y', entry => yScale(entry[1]))
            .attr('width', Math.max(0, xScale.bandwidth() - ALIGN_SIZE_BANDSPACE))
            .attr('height', entry => ALIGN_SIZE_HEIGHT - yScale(entry[1]))
            .attr('fill', colour.toString());
    }, [data, hiddenSizes, colour]);

    return (
        <div
            id='alignAndSizeContainer' >
            <div
                id='sizesTitleContainer' >
                <Typography
                    textAlign='center'
                    variant='h6' >
                        Sizes
                </Typography>
                <div
                    id='sizesContainer' >
                    {
                        data.map((d) => d.size)
                            .filter((val, ind, arr) => arr.indexOf(val) === ind)
                            .sort((a, b) => a - b)
                            .map((d) => <div key={d}
                                            className='sizeListItem' >
                                            <Checkbox
                                                className='sizeListItemCheckbox'
                                                checked={!hiddenSizes.has(d)}
                                                size='small'
                                                onChange={() => {
                                                    const newSizesToShow = new Set(hiddenSizes);
                                                    if (!newSizesToShow.delete(d))
                                                        newSizesToShow.add(d);
                                                    setHiddenSizes(newSizesToShow);
                                                }} />
                                            <Typography fontSize='10pt' >{d}</Typography>
                                        </div>)
                    }
                </div>
            </div>
            <div
                id='alignSVGTitleContainer' >
                <Typography
                    textAlign='center'
                    variant='h6' >
                        Recorded offsets (bytes)
                </Typography>
                <svg
                    id='alignSVG' ref={svgRef}
                    viewBox={`${-ALIGN_SIZE_MARGIN} ${ALIGN_SIZE_MARGIN} ${ALIGN_SIZE_WIDTH} ${ALIGN_SIZE_HEIGHT}`} >
                    <g
                        id='barGroup'
                        ref={barGroupRef} />
                    <g id='alignXAxisGroup' />
                    <g id='alignYAxisGroup' />
                </svg>
            </div>
            <IconButton
                id='alignCloseButton'
                onClick={() => setAlignTypeDisplay(null)} >
                <Close />
            </IconButton>
        </div>
    );
}

export default function Legend({ colourOfType, setColourOfType, typeStats, lineVis,
                                 pageVis, cacheVis, setLineVis, setPageVis, setCacheVis,
                                 fieldsData, expandedTypes, setExpandedTypes, alignData,
                                 cacheLineSize } :
    {
        colourOfType: TypeToColourMap,
        setColourOfType: (a: TypeToColourMap) => void,
        typeStats: TypeToStatsMap,
        lineVis: {[tp: string]: boolean},
        pageVis: {[tp: string]: boolean},
        cacheVis: {[tp: string]: boolean},
        setLineVis: (a: {[tp: string]: boolean}) => void,
        setPageVis: (a: {[tp: string]: boolean}) => void,
        setCacheVis: (a: {[tp: string]: boolean}) => void,
        fieldsData: {[tp: string]: SubtypeEntry[]},
        expandedTypes: {[tp: string]: boolean},
        setExpandedTypes: (a: {[tp: string]: boolean}) => void,
        alignData: {[tp: string]: [{size: number, align: number, count: number}]},
        cacheLineSize: number
    }) {
    const [filterText, setFilterText] = useState('');
    const [visExpanded, setVisExpanded] = useState(false);
    const [currSortMode, setCurrSortMode] = useState<LegendRowSortMode>({mode: 'allocs', rev: false});
    const [colourMenuAnchor, setColourMenuAnchor] = useState<HTMLDivElement | null>(null);
    const [selMenuType, setSelMenuType] = useState<string | undefined>(undefined);
    const [currColourSel, setCurrColourSel] = useState<string>('#ffffff');
    const [alignTypeDisplay, setAlignTypeDisplay] = useState<string | null>(null);

    return (
        <>
            <Popover
                open={Boolean(colourMenuAnchor)}
                anchorEl={colourMenuAnchor}
                onClose={() => setColourMenuAnchor(null)} >
                <PhotoshopPicker
                    color={currColourSel}
                    onAccept={() => {
                        if (selMenuType) {
                            const newColourOfType: TypeToColourMap = {};
                            Object.keys(colourOfType).forEach((tp: string) => {
                                newColourOfType[tp] = colourOfType[tp] ? colourOfType[tp].copy() : d3.color("white");
                            });
                            console.log("Here is newColourOfType:");
                            console.log(newColourOfType);
                            newColourOfType[selMenuType] = d3.color(currColourSel);
                            setColourOfType(newColourOfType);
                        }
                        setColourMenuAnchor(null);
                    }}
                    onCancel={() => setColourMenuAnchor(null)}
                    onChange={(col) => setCurrColourSel(col.hex)} />
            </Popover>
            {alignTypeDisplay == null ?
            <table
                id='legendTable'
                className={visExpanded ? 'visExpanded' : ''} >
                <LegendTableHeader
                    visExpanded={visExpanded}
                    setVisExpanded={setVisExpanded}
                    currSortMode={currSortMode}
                    setCurrSortMode={setCurrSortMode} />
                <tbody className={visExpanded ? 'visExpanded' : ''} >
                    {
                        Object.keys(colourOfType).filter((tp: string) => tp.includes(filterText) && typeStats[tp])
                            .sort((a, b) => {
                                if (currSortMode.mode == 'names')
                                    return currSortMode.rev ? b.localeCompare(a) : a.localeCompare(b);
                                else if (currSortMode.mode == 'allocs')
                                    return currSortMode.rev ? typeStats[a].numAllocs - typeStats[b].numAllocs : typeStats[b].numAllocs - typeStats[a].numAllocs;
                                else
                                    return currSortMode.rev ? typeStats[a].numPages - typeStats[b].numPages : typeStats[b].numPages - typeStats[a].numPages;
                            })
                            .map((tp: string) =>    <LegendRow
                                                        key={tp}
                                                        typeName={tp}
                                                        colourOfType={colourOfType}
                                                        visExpanded={visExpanded}
                                                        stats={typeStats[tp]}
                                                        lineVis={lineVis}
                                                        pageVis={pageVis}
                                                        cacheVis={cacheVis}
                                                        setLineVis={setLineVis}
                                                        setPageVis={setPageVis}
                                                        setCacheVis={setCacheVis}
                                                        fields={fieldsData[tp.replace(/\s+/g, '')] ? fieldsData[tp.replace(/\s+/g, '')] : null}
                                                        expandedTypes={expandedTypes}
                                                        setExpandedTypes={setExpandedTypes}
                                                        setColourOfType={setColourOfType}
                                                        setColourMenuAnchor={setColourMenuAnchor}
                                                        setSelMenuType={setSelMenuType}
                                                        setCurrColourSel={setCurrColourSel}
                                                        hasAlignData={tp in alignData}
                                                        setAlignTypeDisplay={setAlignTypeDisplay} />)
                    }
                </tbody>
                <LegendTableFooter
                    types={Object.keys(colourOfType)}
                    setFilterText={setFilterText}
                    setColourOfType={setColourOfType}
                    visExpanded={visExpanded} />
            </table> :
            <AlignAndSize key={alignTypeDisplay}
                data={alignData[alignTypeDisplay]}
                setAlignTypeDisplay={setAlignTypeDisplay}
                colour={colourOfType[alignTypeDisplay] ?? d3.rgb('white')} />
            }
        </>
    );
}
