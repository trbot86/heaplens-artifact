'use client';
import {useEffect, useRef, useState} from 'react';
import {Box, Button} from '@mui/material';
import {openSnapshotSink, writePageSnapshots, SnapshotPages, SnapshotClusters, SnapshotFields} from './snapshotExport';

// Keep export progress local so it does not rerender every page row.
export default function SnapshotExportButton({pages, clustersData, fieldsData, pageSize}: {
    pages: SnapshotPages; clustersData: SnapshotClusters; fieldsData: SnapshotFields; pageSize: number;
}) {
    const exportController = useRef<AbortController | null>(null);
    const [exportProgress, setExportProgress] = useState<number | null>(null);
    const [exportMessage, setExportMessage] = useState('');
    useEffect(() => {
        setExportProgress(null); setExportMessage('');
        return () => {
            exportController.current?.abort();
            exportController.current = null;
        };
    }, [pages]);
    const exportSnapshots = async () => {
        if (exportController.current) return;
        const controller = new AbortController();
        exportController.current = controller;
        setExportProgress(0); setExportMessage('');
        try {
            const sink = await openSnapshotSink();
            await writePageSnapshots(pages, clustersData, fieldsData, pageSize, sink, {
                signal: controller.signal,
                onProgress: ({fraction}) => {
                    if (exportController.current === controller)
                        setExportProgress(Math.floor(fraction * 100));
                }
            });
            if (exportController.current === controller) setExportMessage('Export saved.');
        } catch (error) {
            if (exportController.current === controller)
                setExportMessage(error instanceof Error && error.name === 'AbortError'
                    ? 'Export cancelled.' : error instanceof Error ? error.message : 'Export failed.');
        } finally {
            if (exportController.current === controller) {
                exportController.current = null; setExportProgress(null);
            }
        }
    };

    return (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap'}}>
            <Button size='small' onClick={exportSnapshots}
                disabled={exportProgress !== null || !Object.keys(pages).length}>
                Export 5 snapshots
            </Button>
            {exportProgress !== null && <>
                <span role='status' style={{minWidth: 115, fontVariantNumeric: 'tabular-nums'}}>Exporting: {exportProgress}%</span>
                <Button size='small' onClick={() => exportController.current?.abort()}>Cancel export</Button>
            </>}
            {exportMessage && <span role='status'>{exportMessage}</span>}
        </Box>
    );
}
