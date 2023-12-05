import * as d3 from 'd3';
import allocsOverTimeLayout from './timeGraphLayout.js';
import objectLayout from './objectFieldLayout.js';
import legendLayout from './legend.js';
import cacheSetLayout from './cacheSetLayout.js';
import pageLayout from './pageLayout.js';

export const colourOfType = {};

class MainVisualization {

    constructor(pages) {
        const pageSize = 4096;

        // let pages = objects.reduce((acc, curr) => {
        //         let pageNum = curr.alloc_addr - (curr.alloc_addr % pageSize);
        //         acc[pageNum] ? acc[pageNum].push(curr) : acc[pageNum] = [curr];
        //         return acc;
        //     }, {});

        let pagesJoined = {};

        for (let page of Object.keys(pages)) {
            pagesJoined[parseInt(page)] = {'events': [], 'cluster': pages[page]['cluster']};
        }
        let currID = 0;

        /*  TODO: in order to change page sizes, you will need to not change the objects
            when constructing the pages */
        for (let [page, attrs] of Object.entries(pages)) {
            page = parseInt(page);
            let allocs = attrs.events.filter((event) => event.is_alloc == 1).sort((a, b) => a.addr == b.addr ? a.ts - b.ts : a.addr - b.addr);
            let frees = attrs.events.filter((event) => event.is_alloc == 0).sort((a, b) => a.addr == b.addr ? a.ts - b.ts : a.addr - b.addr);
            let joined = [];
            let iAlloc = 0, iFree = 0;
            while (iAlloc < allocs.length) {
                while (iFree < frees.length) {
                    if (allocs[iAlloc].addr == frees[iFree].addr && allocs[iAlloc].ts <= frees[iFree].ts) {
                        joined.push({'file': allocs[iAlloc].file,
                                    'size': allocs[iAlloc].size,
                                    'addr': allocs[iAlloc].addr,
                                    'type': allocs[iAlloc].type,
                                    'allocTs': allocs[iAlloc].ts,
                                    'freeTs': frees[iFree].ts,
                                    'isDup': false,
                                    'ID': currID
                                });
                        currID++;
                        break;
                    }
                    iFree++;
                }
                iAlloc++;
            }
            
            pagesJoined[page]['events'] = pagesJoined[page]['events'].concat(joined);

            for (let event of pagesJoined[page]['events']) {
                let endOffsetLastObject = (event.addr % pageSize) + event.size;
                let iPage = page + 1;
                while (endOffsetLastObject > pageSize && pagesJoined[iPage]) {
                    /*  NOTE: at this point, we rely on the fact that the objects are sorted in ascending order
                        by the address. */
                    let newEvent = structuredClone(event);
                    newEvent.size = Math.min(endOffsetLastObject - pageSize, pageSize);
                    newEvent.addr = iPage * pageSize;
                    // newObj.alloc_addr = (objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) -
                    //     ((objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) % pageSize);
                    newEvent.isDup = true;
                    newEvent.ID = currID;
                    currID++;

                    pagesJoined[iPage]['events'].push(newEvent);
                    // objs[objs.length - 1].alloc_size -= newObj.alloc_size;
                    endOffsetLastObject -= pageSize;
                    iPage++;
                }
            }
        }

        const objects = Object.values(pagesJoined).map((page) => page.events.filter((event) => !event.isDup)).reduce((acc, curr) => acc.concat(curr), []);
        const types = [...new Set(objects.map((obj) => obj.type))];
        const colScale = d3.scaleSequential()
                            .domain([0, types.length])
                            .interpolator(d3.interpolateRainbow);
        let col = 0;
        for (let type of types) {
            colourOfType[type] = colScale(col);
            col++;
        }

        let initTs = allocsOverTimeLayout(objects);
        cacheSetLayout(objects, 64, {associativity: 8, size: 32768},
                                    {associativity: 8, size: 2097152},
                                    {associativity: 8, size: 4194304});

        pageLayout(pagesJoined, initTs, pageSize);
        legendLayout();
    }

    static build(pages) {
        d3.select("body")
            .append("g")
            .attr("id", "visPanels");

        return new MainVisualization(pages);
    }
}

export default MainVisualization;