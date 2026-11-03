interface DetailEvent {
    addr: number;
    actualAddr?: number;
    size: number;
    type: string | null;
    allocTs: number;
    freeTs: number | null;
}

interface FieldInterval {
    offset: number;
    size: number;
}

// Select before constructing React components. Keep enclosing/crossing objects,
// not just objects whose starting address lies inside the selected region.
export function selectDetailEvents<T extends DetailEvent>(
    events: readonly T[], start: number, size: number, time: number,
    visible: Readonly<Record<string, boolean>>,
    fields: Readonly<Record<string, readonly FieldInterval[]>>,
    expanded: Readonly<Record<string, boolean>>,
): T[] {
    if (!(size > 0)) return [];
    const end = start + size;
    const intersects = (address: number, length: number) =>
        length > 0 ? address < end && address + length > start
                   : length === 0 && address >= start && address < end;
    return events.filter(event => {
        // Match HoverableSplitBlock's inclusive allocation/free endpoints.
        if (!(event.allocTs <= time && (event.freeTs == null || event.freeTs >= time)
              && event.type && visible[event.type])) return false;
        if (intersects(event.addr, event.size)) return true;
        const type = event.type.replace(/\s+/g, '');
        // Existing field rendering uses the original allocation address. Retain
        // a parent whose expanded field reaches the region even if its stored
        // fragment does not; do not assume metadata lies within that fragment.
        return !!expanded[type] && !!fields[type]?.some(field =>
            intersects((event.actualAddr || event.addr) + field.offset, field.size));
    }).sort((a, b) => a.allocTs - b.allocTs);
}
