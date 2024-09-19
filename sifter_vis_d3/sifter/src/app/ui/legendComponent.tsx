'use client';
import { useState } from 'react';
import * as d3 from 'd3';
import { IconButton, Paper, TextField, Tooltip } from '@mui/material';
import KeyboardArrowLeftIcon from '@mui/icons-material/KeyboardArrowLeft';
import './componentStyles.scss';
import { generateColours, TypeToColourMap } from '../vispanels/page';
import { Casino } from '@mui/icons-material';

interface TypeStat {
    allocs: number,
    pages: number
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

function LegendTableFooter({ types, onFilterTextChange, setColourOfType } : 
    {
        types: string[],
        onFilterTextChange: (a: string) => void,
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
                            onChange={(e) => onFilterTextChange(e.target.value)}
                            // sx={{
                            //     '@media (prefers-color-scheme: dark)': {
                            //         input: {
                            //             '&:hover': {
                            //                 backgroundColor: '#333333'
                            //             },
                            //             backgroundColor: '#2f2f2f',
                            //             color: 'e0e0e0'
                            //         },
                            //         '& .MuiInputLabel-root': {
                            //             color: '#a0a0a0',
                            //             '&.Mui-focused': {
                            //                 color: '#e0e0e0'
                            //             }
                            //         },
                            //         '& .MuiInputBase-input': {
                            //             color: '#e0e0e0'
                            //         },
                            //         '& .MuiFilledInput-underline': {
                            //             '&.Mui-focused:after': {
                            //                 borderBottomColor: '#e0e0e0'
                            //             },
                            //             '&:hover:before': {
                            //                 borderBottomColor: '#161616'
                            //             },
                            //             ':after': {
                            //                 borderBottomColor: '#161616'
                            //             }
                            //         }
                            //     }
                            // }} 
                            />
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
            <td>{stats.allocs}</td>
            <td>{stats.pages}</td>
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
                                                    stats={typeStats[tp]} />)
                }
            </tbody>
            <LegendTableFooter
                types={Object.keys(typeStats)}
                onFilterTextChange={setFilterText}
                setColourOfType={setColourOfType} />
        </table>
    );
}