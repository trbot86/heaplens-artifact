'use client';
import { useState } from 'react';
import * as d3 from 'd3';
import { Checkbox, IconButton, Menu, MenuItem, Paper, Popover, TextField, Tooltip } from '@mui/material';
import './componentStyles.scss';
import { generateColours, getSubtypeName, TypeToColourMap } from '../vispanels/page';
import { BarChart, Casino, KeyboardArrowLeft, KeyboardArrowRight, StackedLineChart, Window } from '@mui/icons-material';
import { Box, styled } from '@mui/system';
import { MaterialPicker, PhotoshopPicker } from 'react-color';

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

function VisRightClickMenu({ rightClickAnchor, setRightClickAnchor, label, typeVisMatrix,
                             typeName, setTypeVisMatrix } : 
    {
        rightClickAnchor: HTMLElement | null,
        setRightClickAnchor: (a: HTMLElement | null) => void,
        label: string | undefined,
        typeVisMatrix: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}},
        setTypeVisMatrix: (a: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}}) => void,
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
                    const newTypeVisMatrix = structuredClone(typeVisMatrix);
                    if (label?.startsWith('line')) {
                        Object.keys(newTypeVisMatrix).forEach((tp) => newTypeVisMatrix[tp].lineVis = tp == typeName);
                    }
                    else if (label?.startsWith('page')) {
                        Object.keys(newTypeVisMatrix).forEach((tp) => newTypeVisMatrix[tp].pageVis = tp == typeName);
                    }
                    else {
                        Object.keys(newTypeVisMatrix).forEach((tp) => newTypeVisMatrix[tp].cacheVis = tp == typeName);
                    }
                    setTypeVisMatrix(newTypeVisMatrix);
                    setRightClickAnchor(null);
                }} >
                Only this type
            </MenuItem>
            <MenuItem
                onClick={() => {
                    const newTypeVisMatrix = structuredClone(typeVisMatrix);
                    if (label?.startsWith('line')) {
                        Object.keys(newTypeVisMatrix).forEach((tp) => newTypeVisMatrix[tp].lineVis = tp != typeName);
                    }
                    else if (label?.startsWith('page')) {
                        Object.keys(newTypeVisMatrix).forEach((tp) => newTypeVisMatrix[tp].pageVis = tp != typeName);
                    }
                    else {
                        Object.keys(newTypeVisMatrix).forEach((tp) => newTypeVisMatrix[tp].cacheVis = tp != typeName);
                    }
                    setTypeVisMatrix(newTypeVisMatrix);
                    setRightClickAnchor(null);
                }}  >
                Everything but this type
            </MenuItem>
        </Menu>
    );
}

function LegendRow({ typeName, visExpanded, stats, typeVisMatrix, setTypeVisMatrix,
                     fields, expandedTypes, setExpandedTypes, colourOfType,
                     setColourOfType, setColourMenuAnchor, setSelMenuType } : 
    {   
        typeName: string,
        colourOfType: {[tp: string]: d3.RGBColor | d3.HSLColor | null},
        setColourOfType: (a: TypeToColourMap) => void,
        visExpanded: boolean,
        stats: TypeStat,
        typeVisMatrix: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}},
        setTypeVisMatrix: (a: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}}) => void,
        fields: SubtypeEntry[] | null,
        expandedTypes: {[tp: string]: boolean},
        setExpandedTypes: (a: {[tp: string]: boolean}) => void,
        setColourMenuAnchor: (a: HTMLDivElement | null) => void,
        setSelMenuType: (a: string | undefined) => void
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
                typeVisMatrix={typeVisMatrix}
                setTypeVisMatrix={setTypeVisMatrix}
                typeName={rightClickedType}
                />
            <tr className={visExpanded ? 'visExpanded' : ''} >
                {
                visExpanded &&
                <td>
                    <div className='legendVisCheckboxContainer' >
                        <VisCheckbox
                            id={`line-vis-${typeName}`}
                            checked={typeVisMatrix[typeName].lineVis}
                            size='small'
                            onContextMenu={(e) => {
                                e.preventDefault();
                                setLabel(`line-vis-${typeName}`);
                                setRightClickAnchor(e.currentTarget);
                                setRightClickedType(typeName);
                            }}
                            onChange={() => {
                                const newTypeVisMatrix = structuredClone(typeVisMatrix);
                                newTypeVisMatrix[typeName].lineVis = !typeVisMatrix[typeName].lineVis;
                                setTypeVisMatrix(newTypeVisMatrix);
                            }} />
                        <VisCheckbox
                            id={`page-vis-${typeName}`}
                            checked={typeVisMatrix[typeName].pageVis}
                            size='small'
                            onContextMenu={(e) => {
                                e.preventDefault();
                                setLabel(`page-vis-${typeName}`);
                                setRightClickAnchor(e.currentTarget);
                                setRightClickedType(typeName);
                            }}
                            onChange={() => {
                                const newTypeVisMatrix = structuredClone(typeVisMatrix);
                                newTypeVisMatrix[typeName].pageVis = !typeVisMatrix[typeName].pageVis;
                                setTypeVisMatrix(newTypeVisMatrix);
                            }} />
                        <VisCheckbox
                            id={`cache-vis-${typeName}`}
                            checked={typeVisMatrix[typeName].cacheVis}
                            size='small'
                            onContextMenu={(e) => {
                                e.preventDefault();
                                setLabel(`cache-vis-${typeName}`);
                                setRightClickAnchor(e.currentTarget);
                                setRightClickedType(typeName);
                            }}
                            onChange={() => {
                                const newTypeVisMatrix = structuredClone(typeVisMatrix);
                                newTypeVisMatrix[typeName].cacheVis = !typeVisMatrix[typeName].cacheVis;
                                setTypeVisMatrix(newTypeVisMatrix);
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
                            }}
                            sx={{
                                width: '20px',
                                height: '20px',
                                backgroundColor: colourOfType[typeName] == null ? 'white' : colourOfType[typeName].formatHex()
                            }} />
                    </div>
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
                <td>{typeName}</td>
                <td>{stats.numAllocs}</td>
                <td>{stats.numPages}</td>
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
                                    checked={typeVisMatrix[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)].pageVis}
                                    size='small'
                                    onContextMenu={(e) => {
                                        e.preventDefault();
                                        setLabel(`page-vis-${getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)}`);
                                        setRightClickAnchor(e.currentTarget);
                                        setRightClickedType(getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype));
                                    }}
                                    onChange={() => {
                                        const newTypeVisMatrix = structuredClone(typeVisMatrix);
                                        newTypeVisMatrix[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)].pageVis = !typeVisMatrix[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)].pageVis;
                                        setTypeVisMatrix(newTypeVisMatrix);
                                    }} />
                                <VisCheckbox
                                    id={`cache-vis-${getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)}`}
                                    checked={typeVisMatrix[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)].cacheVis}
                                    size='small'
                                    onContextMenu={(e) => {
                                        e.preventDefault();
                                        setLabel(`cache-vis-${getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)}`);
                                        setRightClickAnchor(e.currentTarget);
                                        setRightClickedType(getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype));
                                    }}
                                    onChange={() => {
                                        const newTypeVisMatrix = structuredClone(typeVisMatrix);
                                        newTypeVisMatrix[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)].cacheVis = !typeVisMatrix[getSubtypeName(typeName.replace(/\s+/g, ''), field.subtype)].cacheVis;
                                        setTypeVisMatrix(newTypeVisMatrix);
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

export default function Legend({ colourOfType, setColourOfType, typeStats, typeVisMatrix, setTypeVisMatrix,
                                 fieldsData, expandedTypes, setExpandedTypes } : 
    {   
        colourOfType: TypeToColourMap,
        setColourOfType: (a: TypeToColourMap) => void,
        typeStats: TypeToStatsMap,
        typeVisMatrix: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}},
        setTypeVisMatrix: (a: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}}) => void,
        fieldsData: {[tp: string]: SubtypeEntry[]},
        expandedTypes: {[tp: string]: boolean},
        setExpandedTypes: (a: {[tp: string]: boolean}) => void
    }) {
    const [filterText, setFilterText] = useState('');
    const [visExpanded, setVisExpanded] = useState(false);
    const [currSortMode, setCurrSortMode] = useState<LegendRowSortMode>({mode: 'allocs', rev: false});
    const [colourMenuAnchor, setColourMenuAnchor] = useState<HTMLDivElement | null>(null);
    const [selMenuType, setSelMenuType] = useState<string | undefined>(undefined);

    return (
        <>
            <Popover
                open={Boolean(colourMenuAnchor)}
                anchorEl={colourMenuAnchor}
                onClose={() => setColourMenuAnchor(null)} >
                <MaterialPicker
                    color={selMenuType ? colourOfType[selMenuType]?.toString() : '#ffffff'}
                    onChangeComplete={(col) => {
                        if (selMenuType) {
                            const newColourOfType = colourOfType;
                            newColourOfType[selMenuType] = d3.color(col.hex);
                            setColourOfType(newColourOfType);
                        }
                    }}
                     />
            </Popover>
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
                                                        typeVisMatrix={typeVisMatrix}
                                                        setTypeVisMatrix={setTypeVisMatrix}
                                                        fields={fieldsData[tp.replace(/\s+/g, '')] ? fieldsData[tp.replace(/\s+/g, '')] : null}
                                                        expandedTypes={expandedTypes}
                                                        setExpandedTypes={setExpandedTypes}
                                                        setColourOfType={setColourOfType}
                                                        setColourMenuAnchor={setColourMenuAnchor}
                                                        setSelMenuType={setSelMenuType} />)
                    }
                </tbody>
                <LegendTableFooter
                    types={Object.keys(colourOfType)}
                    setFilterText={setFilterText}
                    setColourOfType={setColourOfType}
                    visExpanded={visExpanded} />
            </table>
        </>
    );
}