// Pure computations shared by the UI and equal-output regression tests.
interface SlotEvent {
    type: string | null;
    addr: number;
    actualAddr?: number;
    size: number;
    allocTs: number;
    freeTs: number | null;
}

// Preserve the existing overview: assign each object's bytes to its start slot,
// rather than splitting objects across slots. Bucket boundaries are unchanged.
export function getSlotDataAtBucket(events: SlotEvent[], pageAddr: number,
        pageSize: number, numSlots: number, getBucketIdx: (ts: number) => number,
        pageVis: {[tp: string]: boolean}, bucketIdx: number): number[] {
    const slots: number[] = Array(numSlots).fill(0);
    const slotSize = Math.floor(pageSize / numSlots);
    for (const event of events) {
        if (!event.type || !pageVis[event.type]) continue;
        const addr = event.actualAddr ? event.actualAddr : event.addr;
        if (Math.floor(addr / pageSize) !== Math.floor(pageAddr / pageSize)) continue;
        // Separate deltas also preserve the old result for unusual histories
        // whose free bucket precedes their allocation bucket.
        const allocated = getBucketIdx(event.allocTs) <= bucketIdx ? 1 : 0;
        const freed = event.freeTs && getBucketIdx(event.freeTs) <= bucketIdx ? 1 : 0;
        slots[Math.floor((addr % pageSize) / slotSize)] += (allocated - freed) * event.size;
    }
    return slots;
}

export function getCacheTotalsAtBucket(bucket: number[], numSets: number,
        numTypes: number, visibleTypes: boolean[]): number[] {
    const totals: number[] = Array(numSets).fill(0);
    bucket.forEach((v, i) => {
        totals[Math.floor(i / numTypes)] += visibleTypes[i % numTypes] ? v : 0;
    });
    return totals;
}
