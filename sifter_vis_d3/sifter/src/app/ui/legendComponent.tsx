'use client';
import { useState } from 'react';
import * as d3 from 'd3';
import { Checkbox, IconButton, Paper, TextField, Tooltip } from '@mui/material';
import './componentStyles.scss';
import { generateColours, TypeToColourMap } from '../vispanels/page';
import { BarChart, Casino, KeyboardArrowLeft, KeyboardArrowRight, StackedLineChart, Window } from '@mui/icons-material';
import { Box, styled } from '@mui/system';

interface TypeStat {
    numAllocs: number,
    numPages: number
}

interface TypeToStatsMap {
    [ tp: string ]: TypeStat
}

const VisCheckbox = styled(Checkbox)({
    padding: '2.5px',
});

function LegendTableHeader({ visExpanded, setVisExpanded } : 
    {
        visExpanded: boolean,
        setVisExpanded: (a: boolean) => void
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
                <th>Type names</th>
                <th style={{
                    textAlign: 'left'
                }}>
                    # allocs
                </th>
                <th style={{
                    textAlign: 'left'
                }}>
                    # pages
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

function LegendRow({ typeName, colour, visExpanded, stats, typeVisMatrix, setTypeVisMatrix } : 
    {   
        typeName: string,
        colour: d3.RGBColor | d3.HSLColor | null,
        visExpanded: boolean,
        stats: TypeStat,
        typeVisMatrix: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}},
        setTypeVisMatrix: (a: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}}) => void
    }) {
    return (
        <tr className={visExpanded ? 'visExpanded' : ''} >
            {
            visExpanded &&
            <td>
                <div className='legendVisCheckboxContainer' >
                    <VisCheckbox
                        checked={typeVisMatrix[typeName].lineVis}
                        size='small'
                        onChange={() => {
                            const newTypeVisMatrix = structuredClone(typeVisMatrix);
                            newTypeVisMatrix[typeName].lineVis = !typeVisMatrix[typeName].lineVis;
                            setTypeVisMatrix(newTypeVisMatrix);
                        }} />
                    <VisCheckbox
                        checked={typeVisMatrix[typeName].pageVis}
                        size='small'
                        onChange={() => {
                            const newTypeVisMatrix = structuredClone(typeVisMatrix);
                            newTypeVisMatrix[typeName].pageVis = !typeVisMatrix[typeName].pageVis;
                            setTypeVisMatrix(newTypeVisMatrix);
                        }} />
                    <VisCheckbox
                        checked={typeVisMatrix[typeName].cacheVis}
                        size='small'
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
                        sx={{
                            width: '20px',
                            height: '20px',
                            backgroundColor: colour == null ? 'white' : colour.formatHex()
                        }} />
                </div>
            </td>
            <td>{typeName}</td>
            <td>{stats.numAllocs}</td>
            <td>{stats.numPages}</td>
        </tr>
    );
}

export default function Legend({ colourOfType, setColourOfType, typeStats, typeVisMatrix, setTypeVisMatrix } : 
    {   
        colourOfType: TypeToColourMap,
        setColourOfType: (a: TypeToColourMap) => void,
        typeStats: TypeToStatsMap,
        typeVisMatrix: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}},
        setTypeVisMatrix: (a: {[tp: string]: {lineVis: boolean, pageVis: boolean, cacheVis: boolean}}) => void
    }) {
    const [filterText, setFilterText] = useState('');
    const [visExpanded, setVisExpanded] = useState(false);

    return (
        <table
            id='legendTable'
            className={visExpanded ? 'visExpanded' : ''} >
            <LegendTableHeader
                visExpanded={visExpanded}
                setVisExpanded={setVisExpanded} />
            <tbody className={visExpanded ? 'visExpanded' : ''} >
                {
                    Object.keys(colourOfType).filter((tp: string) => tp.includes(filterText))
                        .map((tp: string) =>    <LegendRow
                                                    key={tp}
                                                    typeName={tp}
                                                    colour={colourOfType[tp]}
                                                    visExpanded={visExpanded}
                                                    stats={typeStats[tp] ? typeStats[tp] : {numAllocs: -1, numPages: -1}}
                                                    typeVisMatrix={typeVisMatrix}
                                                    setTypeVisMatrix={setTypeVisMatrix} />)
                }
            </tbody>
            <LegendTableFooter
                types={Object.keys(colourOfType)}
                setFilterText={setFilterText}
                setColourOfType={setColourOfType}
                visExpanded={visExpanded} />
        </table>
    );
}