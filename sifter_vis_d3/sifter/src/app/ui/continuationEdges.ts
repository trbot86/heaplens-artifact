// Unknown extents (legacy databases) suppress BOTH markers. Page-local size
// cannot distinguish an exact end from an object continuing into another page.
export function continuationEdges(obj: {addr: number; size: number; actualAddr?: number; actualSize?: number},
        pageStart: number, pageSize: number): {before: boolean; after: boolean} {
    const start = obj.actualAddr;
    const size = obj.actualSize;
    if (start == null || size == null || !Number.isSafeInteger(start) ||
        !Number.isSafeInteger(size) || size <= 0 || !Number.isSafeInteger(start + size)) {
        return {before: false, after: false};
    }
    const pageEnd = pageStart + pageSize;
    const intersects = obj.size > 0 && obj.addr < pageEnd && obj.addr + obj.size > pageStart;
    return {
        before: intersects && start < pageStart && obj.addr <= pageStart,
        after: intersects && start + size > pageEnd && obj.addr + obj.size >= pageEnd,
    };
}

// The huge-page overview shows density rather than individual rectangles.
// Aggregate only visible, live objects; stop once both boundaries are known.
export function visiblePageContinuation(events: Array<{addr: number; size: number; actualAddr?: number;
        actualSize?: number; allocTs: number; freeTs: number | null; type: string | null}>,
        pageStart: number, pageSize: number, time: number, visible: {[type: string]: boolean}) {
    const result = {before: false, after: false};
    for (const event of events) {
        if (!event.type || !visible[event.type] || event.allocTs > time ||
            (event.freeTs != null && event.freeTs < time)) continue;
        const edges = continuationEdges(event, pageStart, pageSize);
        result.before ||= edges.before;
        result.after ||= edges.after;
        if (result.before && result.after) break;
    }
    return result;
}
