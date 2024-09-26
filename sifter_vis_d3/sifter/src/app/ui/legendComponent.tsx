'use client';
import { useState } from 'react';
import * as d3 from 'd3';
import { IconButton, Paper, TextField, Tooltip } from '@mui/material';
import KeyboardArrowLeftIcon from '@mui/icons-material/KeyboardArrowLeft';
import './componentStyles.scss';
import { generateColours, TypeToColourMap } from '../vispanels/page';
import { Casino } from '@mui/icons-material';

interface TypeStat {
    numAllocs: number,
    numPages: number
}

interface TypeToStatsMap {
    [ tp: string ]: TypeStat
}

function LegendTableHeader() {
    return (
        <thead>
            <tr>
                <th>
                    <div className='justifyRightTableCell'>
                        <KeyboardArrowLeftIcon />
                    </div>
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

function LegendTableFooter({ types, setFilterText, setColourOfType } : 
    {
        types: string[],
        setFilterText: (a: string) => void,
        setColourOfType: (a: TypeToColourMap) => void
    }) {
    return (
        <tfoot>
            <tr>
                <td>
                    <div className='justifyRightTableCell' >
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

function LegendRow({ typeName, colour, stats } : 
    {   
        typeName: string,
        colour: d3.RGBColor | d3.HSLColor | null,
        stats: TypeStat
    }) {

    return (
        <tr>
            <td>
                <div className='justifyRightTableCell'>
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

export default function Legend({ colourOfType, setColourOfType, typeStats } : 
    {   
        colourOfType: TypeToColourMap,
        setColourOfType: (a: TypeToColourMap) => void,
        typeStats: TypeToStatsMap
    }) {
            
    const [filterText, setFilterText] = useState('');

    return (
        <table
            id='legendTable'>
            <LegendTableHeader />
            <tbody>
                {
                    Object.keys(colourOfType).filter((tp: string) => tp.includes(filterText))
                        .map((tp: string) =>    <LegendRow
                                                    key={tp}
                                                    typeName={tp}
                                                    colour={colourOfType[tp]}
                                                    stats={typeStats[tp] ? typeStats[tp] : {numAllocs: -1, numPages: -1}} />)
                }
            </tbody>
            <LegendTableFooter
                types={Object.keys(colourOfType)}
                setFilterText={setFilterText}
                setColourOfType={setColourOfType} />
        </table>
    );
}