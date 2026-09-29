// Text export is independent of React and writes bounded chunks to a sink.
// It preserves the existing text format and inclusive free-time boundary.
export const SNAPSHOT_COUNT = 5;
export const SNAPSHOT_FILE_NAME = 'page_layout_snapshots.txt';
export const DOWNLOAD_LIMIT_BYTES = 64 * 1024 * 1024;

interface SnapshotEvent {
    allocTs: number; freeTs: number | null; type: string | null;
    size: number; addr: number; actualAddr?: number;
}
export interface SnapshotPages {
    [addr: number]: {events: SnapshotEvent[]; cluster: number};
}
export interface SnapshotClusters {
    [cluster: number]: {pages: number[] | {page_num?: number[]; pages?: number[]}; size: number};
}
export interface SnapshotFields {
    [type: string]: {name: string; subtype: string; offset: number; size: number}[];
}
export interface SnapshotSink {
    write: (chunk: Uint8Array) => Promise<void>;
    close: () => Promise<void>;
    abort: () => Promise<void>;
}
export interface ExportProgress { fraction: number; bytes: number; }

function timesBetween(min: number, max: number, count: number): number[] {
    if (min === Infinity) return [0];
    return Array.from({length: count}, (_, i) =>
        Number((min + (max - min) / (count - 1) * i).toFixed(3)));
}

export async function writePageSnapshots(pages: SnapshotPages,
        clusters: SnapshotClusters, fields: SnapshotFields, pageSize: number,
        sink: SnapshotSink, options: {
            signal?: AbortSignal;
            onProgress?: (progress: ExportProgress) => void;
            snapshotCount?: number;
            generatedAt?: string;
        } = {}): Promise<void> {
    const count = options.snapshotCount ?? SNAPSHOT_COUNT;
    if (!Number.isInteger(count) || count < 2 || count > 8)
        throw new Error('Snapshot count must be between 2 and 8.');
    const addresses = Object.keys(pages).map(Number).sort((a, b) => a - b);
    const records = addresses.reduce((n, addr) => n + pages[addr].events.length, 0);
    let work = 0, bytes = 0, checks = 0;
    const totalWork = Math.max(1, records * (2 + count));
    const checkCancelled = () => {
        if (options.signal?.aborted) throw new DOMException('Export cancelled.', 'AbortError');
    };
    let lastYield = performance.now();
    const pause = async (force = false) => {
        checkCancelled();
        if (!force && performance.now() - lastYield < 8) return;
        options.onProgress?.({fraction: Math.min(work / totalWork, 1), bytes});
        await new Promise<void>(resolve => setTimeout(resolve, 0));
        lastYield = performance.now();
        checkCancelled();
    };
    let text = '', firstLine = true;
    const encoder = new TextEncoder();
    const flush = async () => {
        checkCancelled();
        if (!text) return;
        const chunk = encoder.encode(text);
        text = '';
        await sink.write(chunk);
        bytes += chunk.byteLength;
        await pause();
    };
    // Large individual type names are split too; no unbounded lines array.
    const line = async (value: string) => {
        let pending = (firstLine ? '' : '\n') + value;
        firstLine = false;
        while (pending.length) {
            let take = Math.min(16384 - text.length, pending.length);
            // Do not split a UTF-16 surrogate pair between encoded chunks.
            if (take < pending.length && take > 0 &&
                    pending.charCodeAt(take - 1) >= 0xD800 && pending.charCodeAt(take - 1) <= 0xDBFF)
                take--;
            if (!take) { await flush(); continue; }
            text += pending.slice(0, take);
            pending = pending.slice(take);
            if (text.length >= 16383) await flush();
        }
    };
    try {
        await pause(true);
        let min = Infinity, max = -Infinity;
        for (const addr of addresses) {
            for (const event of pages[addr].events) {
                min = Math.min(min, event.allocTs);
                max = Math.max(max, event.allocTs);
                work++;
                if (++checks % 2048 === 0) await pause();
            }
        }
        const times = timesBetween(min, max, count);
        // One byte per history record replaces repeated filtered object arrays.
        const masks = new Map<number, Uint8Array>();
        const counts = new Map<number, number[]>();
        for (const addr of addresses) {
            const events = pages[addr].events;
            const mask = new Uint8Array(events.length);
            const live = times.map(() => 0);
            for (let j = 0; j < events.length; j++) {
                const event = events[j];
                for (let i = 0; i < times.length; i++) {
                    if (event.allocTs <= times[i] && (event.freeTs === null || event.freeTs >= times[i])) {
                        mask[j] |= 1 << i;
                        live[i]++;
                    }
                }
                work++;
                if (++checks % 2048 === 0) await pause();
            }
            masks.set(addr, mask);
            counts.set(addr, live);
        }
        for (const value of ['MEMORY PAGE LAYOUT SNAPSHOTS', `SNAPSHOT_INTERVALS: ${count - 1}`,
                `PAGE_SIZE: ${pageSize}`, `TOTAL_PAGES: ${addresses.length}`,
                `GENERATED_AT: ${options.generatedAt ?? new Date().toISOString()}`, '', '', 'FIELDS_DATA:'])
            await line(value);
        const types = Object.keys(fields).sort();
        if (!types.length) await line('  NONE');
        for (const type of types) {
            await line(`- type: ${type}`);
            const entries = fields[type] ?? [];
            await line(entries.length ? '  subtypes:' : '  subtypes: []');
            for (const entry of entries) {
                await line(`    - name: ${entry.name}\n      subtype: ${entry.subtype}\n      offset: ${entry.offset}\n      size: ${entry.size}`);
            }
        }
        await line(''); await line('CLUSTERS:');
        const ids = Object.keys(clusters).map(Number).sort((a, b) => a - b);
        if (!ids.length) await line('  NONE');
        for (const id of ids) {
            const cluster = clusters[id];
            // Pandas emits {page_num: [...]}; saved payloads also use arrays.
            const members = Array.isArray(cluster.pages) ? cluster.pages :
                cluster.pages.page_num ?? cluster.pages.pages ?? [];
            const sorted = [...members].sort((a, b) => a - b);
            await line(`- cluster_id: ${id}\n  size: ${cluster.size}\n  page_count: ${sorted.length}\n  pages: [${sorted.join(', ')}]`);
        }
        await line(''); await line('SNAPSHOTS:');
        for (let i = 0; i < times.length; i++) {
            await line(`- snapshot_index: ${i}\n  time: ${times[i]}\n  pages:`);
            for (const addr of addresses) {
                const page = pages[addr], live = counts.get(addr)![i], mask = masks.get(addr)!;
                await line(`  - page_addr: ${addr}\n    cluster: ${page.cluster}\n    object_count: ${live}`);
                await line(live ? '    objects:' : '    objects: []');
                for (let j = 0; j < page.events.length; j++) {
                    if (mask[j] & (1 << i)) {
                        const obj = page.events[j];
                        await line(`      -\n        type: ${obj.type ?? 'UNKNOWN'}\n        size: ${obj.size}\n        actual_addr: ${obj.actualAddr ?? obj.addr}`);
                    }
                    work++;
                    if (++checks % 2048 === 0) await pause();
                }
            }
        }
        await flush();
        checkCancelled();
        await sink.close();
        options.onProgress?.({fraction: 1, bytes});
    } catch (error) {
        await sink.abort().catch(() => {});
        throw error;
    }
}

// Chromium can stream directly to a user-selected file. Other browsers get a
// bounded Blob download; exceeding the limit is an error, never a partial file.
export async function openSnapshotSink(): Promise<SnapshotSink> {
    type PickerWindow = Window & {showSaveFilePicker?: (options: object) => Promise<{
        createWritable: () => Promise<SnapshotSink>;
    }>};
    const picker = (window as PickerWindow).showSaveFilePicker;
    if (picker) {
        const handle = await picker.call(window, {suggestedName: SNAPSHOT_FILE_NAME,
            types: [{description: 'Text file', accept: {'text/plain': ['.txt']}}]});
        return handle.createWritable();
    }
    let parts: Uint8Array[] = [], bytes = 0;
    return {
        async write(chunk) {
            if (bytes + chunk.byteLength > DOWNLOAD_LIMIT_BYTES)
                throw new Error('Export exceeds the 64 MiB download limit. Select fewer pages, or use a browser with direct file saving (Chrome or Edge on localhost/HTTPS).');
            parts.push(chunk); bytes += chunk.byteLength;
        },
        async close() {
            const blob = new Blob(parts, {type: 'text/plain'});
            parts = [];
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url; link.download = SNAPSHOT_FILE_NAME;
            link.style.display = 'none';
            document.body.appendChild(link);
            try { link.click(); } finally { document.body.removeChild(link); }
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        },
        async abort() { parts = []; }
    };
}
