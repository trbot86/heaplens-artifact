'use client';
import * as d3 from 'd3';
import { createTheme, Theme } from '@mui/material/styles';

export async function getNotesForFile(fname: string) {
    const data = await fetch(`http://localhost:5000/log-data/get-notes/${fname}`, {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    });
    const json = await data.json();
    return [fname, json];
}

export const theme: Theme = createTheme({
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

export interface TypeToColourMap {
    [ tp: string ]: d3.RGBColor | d3.HSLColor | null
};


function getRand(min: number, max: number): number {
    return min + Math.floor(Math.random() * (max - min + 1));
}

export function generateColours(types: string[]): TypeToColourMap {
    return types.reduce((map: TypeToColourMap, tp: string) => {
        map[tp] = d3.color(`hsl(${getRand(0, 360)}, ${getRand(20, 60)}%, ${getRand(35, 55)}%)`);
        return map;
    }, {});
}


export async function getData(url: string, postBody: {[tp: string]: boolean} | null) {
    const data = await fetch(`http://localhost:5000/${url}`, {
        method: postBody ? 'POST' : 'GET',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: postBody ? JSON.stringify(postBody) : null
    });
    if (!data.ok) {
        const detail = await data.json().catch(() => null);
        throw new Error(detail?.error || `The request failed (HTTP ${data.status}). Please try again.`);
    }
    return data;
}

export function requestErrorMessage(error: unknown): string {
    return error instanceof TypeError
        ? 'Could not reach the HeapLENS backend. Check that it is running, then try again. The previous view is unchanged.'
        : error instanceof Error ? error.message : 'Could not prepare this view. Please try again.';
}

export function getSubtypeName(tp: string, st: string) {
    return '>' + tp + '|' + st;
}

export function getTypeName(st: string) {
    const tpReg = /^>([^|]+)|[^|]+/.exec(st);
    return tpReg ? tpReg[1] : '';
}

