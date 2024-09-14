'use client';
import { useState } from 'react';
import Legend from '../ui/legendComponent';
import { createTheme, Theme, ThemeProvider } from '@mui/material/styles';
import { Grid } from '@mui/system';
import Pages from '../ui/pagesComponent';
import { testColourOfType, testPageData, testPerfData, testTypeStats } from '../ui/testdata';
import TimeGraph from '../ui/timeGraphComponent';
import CssBaseline from '@mui/material/CssBaseline';

export interface TypeToColourMap {
    [ tp: string ]: d3.RGBColor | d3.HSLColor | null
};

const theme: Theme = createTheme({
    palette: {
        mode: 'dark',
        primary: {
            main: '#e0e0e0',
            contrastText: '#e9e7e5',
        },
        secondary: {
            main: '#bea7da',
        },
        background: {
            default: '#282828',
            paper: '#212121',
        },
        success: {
            main: '#42c947',
        },
    },
});

const INIT_PAGE_SIZE = 4096;

export default function VisPanels() {
    const [pageSize, setPageSize] = useState(INIT_PAGE_SIZE);
    const [currTs, setCurrTs] = useState(0); //TODO: CHANGE TO INIT TS

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Grid container spacing={2}>
                <Grid size={9}>
                    <Pages
                        pageSize={pageSize}
                        pages={testPageData}
                        perf={testPerfData}
                        colourOfType={testColourOfType}
                        currTs={currTs} />
                </Grid>
                <Grid size={3}></Grid>

                <Grid size={7}>
                    <TimeGraph />
                </Grid>
                <Grid size={5}>
                    <Legend 
                        colourOfType={testColourOfType}
                        typeStats={testTypeStats} />
                </Grid>
            </Grid>
        </ThemeProvider>
    );
}