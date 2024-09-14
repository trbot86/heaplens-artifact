'use client';

interface SizePoint {
    ts: number,
    size: number
}

interface LineData {
    [tp: string]: SizePoint[]
};

function getSampledAndSortedLine(line: SizePoint[], maxPointsPerLine: number): SizePoint[] {
    const sortedLine = line.toSorted((a, b) => a.ts - b.ts);
    const retLine: SizePoint[] = [];
    const minTs = line[0].ts;
    const maxTs = line[line.length - 1].ts;
    const quantum: number = (maxTs - minTs) / maxPointsPerLine;
    
    let prevDiv = 0,
        prevSize = 0;
    sortedLine.forEach((pt) => {
        const currDiv = Math.ceil(pt.ts / quantum);
        if (currDiv > prevDiv || line.length <= maxPointsPerLine) {
            retLine.push({ts: pt.ts, size: prevSize});
            retLine.push(pt);
            prevDiv = currDiv;
            prevSize = pt.size;
        }
    });

    return retLine;
}

function ZoomableLineGraph({ lines } :
    {
        lines: LineData
    }) {
    
    return (
        <></>
    );
}

export default function TimeGraph({ lines, maxPointsPerLine } :
    {
        lines: LineData,
        maxPointsPerLine: number
    }) {

    const sampledAndSortedLines = Object.keys(lines).reduce((retLines: LineData, tp: string) => {
        retLines[tp] = getSampledAndSortedLine(lines[tp], maxPointsPerLine);
        return retLines;
    }, {});
    const minTs: number = Object.keys(sampledAndSortedLines)
            .reduce((min: number, tp: string) => Math.min(min, lines[tp][0].ts), Infinity);
    const maxTs: number = Object.keys(sampledAndSortedLines)
            .reduce((max: number, tp: string) => Math.max(max, lines[tp][lines[tp].length - 1].ts), 0);
    Object.keys(sampledAndSortedLines).forEach((tp) => {
        if (sampledAndSortedLines[tp][0].ts > minTs) {
            sampledAndSortedLines[tp].unshift({ts: minTs, size: 0});
        }
        if (sampledAndSortedLines[tp][sampledAndSortedLines[tp].length - 1].ts < maxTs) {
            sampledAndSortedLines[tp].push({ts: maxTs, size: sampledAndSortedLines[tp][sampledAndSortedLines[tp].length - 1].size});
        }
    });

    return (
        <div>
            <ZoomableLineGraph lines={sampledAndSortedLines} />
        </div>
    );
}