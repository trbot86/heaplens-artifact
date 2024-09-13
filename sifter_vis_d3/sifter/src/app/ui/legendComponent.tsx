'use client';
import { useState } from 'react';
import * as d3 from 'd3';
import { Paper, TextField } from '@mui/material';
import KeyboardArrowLeftIcon from '@mui/icons-material/KeyboardArrowLeft';
import VisibilityIcon from '@mui/icons-material/Visibility';
import './componentStyles.scss';
import { TypeToColourMap } from '../vispanels/page';

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
                        <div className='inline'>
                            <KeyboardArrowLeftIcon />
                            <VisibilityIcon />
                        </div>
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

function LegendTableFooter({ filterText, onFilterTextChange } : 
    {
        filterText: string,
        onFilterTextChange: (a: string) => void
    }) {
    return (
        <tfoot>
            <tr>
                <td></td>
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

    console.log('Here is the colour:');
    console.log(colour);

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

export default function Legend({ colourOfType, typeStats } : 
    {   
        colourOfType: TypeToColourMap, 
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
                filterText={filterText}
                onFilterTextChange={setFilterText} />
        </table>
    );
}