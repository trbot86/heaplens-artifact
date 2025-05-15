'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Checkbox, IconButton, Menu, MenuItem, Paper, Popover, TextField, Tooltip, Typography } from '@mui/material';
import './componentStyles.scss';
import { generateColours, getSubtypeName, TypeToColourMap } from '../vispanels/page';
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
                        # allocs{currSortMode.mode == 'allocs' ? (currSortMode.rev ? ' ▲' : ' ▼') : ''}
                    </div>
                </th>
                <th style={{
                    textAlign: 'left'
                }}>
                    <div
                        className='legendColumnLabel'
                        onClick={() => setCurrSortMode(currSortMode.mode == 'pages' ? {mode: 'pages', rev: !currSortMode.rev} : {mode: 'pages', rev: false})} >
                        # pages{currSortMode.mode == 'pages' ? (currSortMode.rev ? ' ▲' : ' ▼') : ''}
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
                <td />
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
                                        backgroundColor: colourOfType[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)] == null ? 'white' : colourOfType[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)].formatHex()
                                    }} />
                            </div>
                        </td>
                        <td/>
                        <td>{'↳ ' + field.subtype}</td>
                        <td/>
                        <td/>
                    </tr>)
                }
            </>
            }
        </>
    );
}

function AlignAndSize({ data, setAlignTypeDisplay, cacheLineSize, colour } : 
    {   
        data: {size: number, align: number, count: number}[],
        setAlignTypeDisplay: (a: string | null) => void,
        cacheLineSize: number,
        colour: d3.Color
    }) {
    const barGroupRef = useRef(null);
    const [sizesToShow, setSizesToShow] = useState<Set<number>>(
        data.reduce((acc, curr) => {
            acc.add(curr.size);
            return acc;
        }, new Set<number>())
    );

    useEffect(() => {
        const gcd: (a: number, b: number) => number =
            (a, b) => (b == 0 ? a : gcd(a, a % b));
        const gran = data.reduce((acc: number, curr: {size: number, align: number, count: number}) => gcd(acc, curr.align), 8);
        const barData: {[align: string]: number} = new Array(cacheLineSize / gran).fill(0)
                            .reduce((map, curr, i) => {
                                map[`${i*gran}`] = 0;
                                return map;
                            }, {});
        data.forEach((entry: {size: number, align: number, count: number}) => {
            if (sizesToShow.has(entry.size))
                barData[`${entry.align}`] += entry.count;
        });
        const xScale = d3.scaleBand()
                        .domain(new Array(cacheLineSize / gran).fill(0)
                                    .map((d, i) => `${i*gran}`))
                        .range([0, ALIGN_SIZE_WIDTH]);
        const xAxis = d3.axisBottom(xScale)
                        .tickSize(0);
        d3.select('#alignXAxisGroup')
            .style('transform', `translateY(${ALIGN_SIZE_HEIGHT}px)`)
            .call(xAxis);

        const maxCount = data.reduce((acc: number, curr: {size: number, align: number, count: number}) => Math.max(acc, curr.count), 0);
        const yScale = d3.scaleLinear()
                        .domain([maxCount, 0])
                        .range([ALIGN_SIZE_MARGIN+10, ALIGN_SIZE_HEIGHT]);
        const yAxis = d3.axisLeft(yScale)
                        .tickFormat((d: number) =>  d >= 1000000000 ? `${(d / 1000000000).toFixed(1)}B` :
                                                    d >= 1000000 ? `${(d / 1000000).toFixed(1)}M` :
                                                    d >= 1000 ? `${(d / 1000).toFixed(1)}K` :
                                                    `${d}`);
        d3.select('#alignYAxisGroup')
            .call(yAxis);

        d3.select(barGroupRef.current)
            .selectAll('.alignBar')
            .data(Object.entries(barData))
            .enter()
            .append('rect')
            .attr('class', 'alignBar')
            .attr('x', (d) => xScale(d[0]) + (ALIGN_SIZE_BANDSPACE / 2))
            .attr('y', (d) => yScale(0))
            .attr('width', xScale.bandwidth() - ALIGN_SIZE_BANDSPACE)
            .attr('height', 0)
            .attr('fill', colour.toString());

        d3.selectAll('.alignBar')
            .transition()
            .duration(600)
            .attr('y', (d) => yScale(d[1]))
            .attr('height', (d) => ALIGN_SIZE_HEIGHT - yScale(d[1]))
            .delay((d, i) => i*70);
    }, [data, sizesToShow]);

    return (
        <div
            id='alignAndSizeContainer' >
            <div
                id='sizesTitleContainer' >
                <Typography textAlign='center' >Sizes</Typography>
                <div
                    id='sizesContainer' >
                    {
                        data.map((d) => d.size)
                            .filter((val, ind, arr) => arr.indexOf(val) === ind)
                            .sort((a, b) => a - b)
                            .map((d) => <div
                                            className='sizeListItem' >
                                            <Checkbox
                                                className='sizeListItemCheckbox'
                                                defaultChecked
                                                size='small'
                                                onChange={() => {
                                                    const newSizesToShow = structuredClone(sizesToShow);
                                                    if (!newSizesToShow.delete(d))
                                                        newSizesToShow.add(d);
                                                    setSizesToShow(newSizesToShow);
                                                }} />
                                            <Typography fontSize='10pt' >{d}</Typography>
                                        </div>)
                    }
                </div>
            </div>
            <div
                id='alignSVGTitleContainer' >
                <Typography textAlign='center' >Alignments</Typography>
                <svg
                    id='alignSVG'
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
                    {/* TODO: Get the following "OK" and "Cancel" buttons to work */}
                <PhotoshopPicker
                    color={currColourSel}
                    onChange={(col) => setCurrColourSel(col.hex)}
                    onChangeComplete={(col) => {
                        if (selMenuType) {
                            const newColourOfType = colourOfType;
                            newColourOfType[selMenuType] = d3.color(col.hex);
                            setColourOfType(newColourOfType);
                        }
                    }} />
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
            <AlignAndSize
                data={alignData[alignTypeDisplay]}
                setAlignTypeDisplay={setAlignTypeDisplay}
                cacheLineSize={cacheLineSize}
                colour={colourOfType[alignTypeDisplay] ? colourOfType[alignTypeDisplay] : d3.color('white')} />
            }
        </>
    );
}