'use client';
import { useState } from 'react';
import Legend from '../ui/legendComponent';
import { testLegendData } from '../ui/testdata';
import { createTheme, Theme, ThemeProvider } from '@mui/material/styles';
import { Grid } from '@mui/system';
import Pages from '../ui/pagesComponent';

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
            default: '#212121',
            paper: '#212121',
        },
        success: {
            main: '#42c947',
        },
    },
});

export default function VisPanels() {
    return (
        <ThemeProvider theme={theme}>
            <Grid container spacing={2}>
                <Grid size={9}>
                    <Pages />
                </Grid>
                <Grid size={3}></Grid>

                <Grid size={7}></Grid>
                <Grid size={5}>
                    <Legend 
                        colourOfType={testLegendData.colourOfType}
                        typeStats={testLegendData.typeStats} />
                </Grid>
            </Grid>
        </ThemeProvider>
    );
}