// Timestamp units belong to the trace-producing clock, not the rendering host.
// Preserve original timestamps for all selection/lifetime calculations and
// convert only elapsed axis values. Never assume an unknown clock is 1 GHz.
export function parseTimestampHz(value: string | undefined): number | null {
    if (value === undefined || value.trim() === '') return null;
    const hz = Number(value);
    if (!Number.isFinite(hz) || hz <= 0) {
        throw new Error('HEAPLENS_TIMESTAMP_HZ must be a positive finite ticks-per-second value.');
    }
    return hz;
}

export function formatElapsedTimestamp(delta: number, hz: number | null): string {
    return hz === null ? `${delta.toFixed(0)} ticks` : `${(delta / hz).toFixed(2)} s`;
}
