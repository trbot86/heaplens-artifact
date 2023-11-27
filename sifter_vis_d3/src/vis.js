import * as d3 from 'd3';
import allocsOverTimeLayout from './timeGraphLayout.js';
import objectLayout from './objectFieldLayout.js';
import legendLayout from './legend.js';
import cacheSetLayout from './cacheSetLayout.js';
import pageLayout from './pageLayout.js';

const pageSize = 4096;

export const CACHELINE_SIZE = 64;
export const colour_of_type = {};

async function initVis(objects) {
    d3.select("body")
        .append("g")
        .attr("id", "visPanels");

    console.log("TESTING");
    console.log(objects.sort((a, b) => a.alloc_size - b.alloc_size));

    const types = [...new Set(objects.map((obj) => obj.alloc_type))];
    const colScale = d3.scaleSequential()
                        .domain([0, types.length])
                        .interpolator(d3.interpolateRainbow);
    let col = 0;
    for (let type of types) {
        colour_of_type[type] = colScale(col);
        col++;
    }

    let initTs = allocsOverTimeLayout(objects);
    cacheSetLayout(objects, 64, {associativity: 8, size: 32768},
                                {associativity: 8, size: 2097152},
                                {associativity: 8, size: 4194304});

    let pages = objects.reduce((acc, curr) => {
            let pageNum = curr.alloc_addr - (curr.alloc_addr % pageSize);
            acc[pageNum] ? acc[pageNum].push(curr) : acc[pageNum] = [curr];
            return acc;
        }, {});

    /*  TODO: in order to change page sizes, you will need to not change the objects
        when constructing the pages */
    for (let [page, objs] of Object.entries(pages)) {
        page = parseInt(page);
        let endOffsetLastObject = (objs[objs.length - 1].alloc_addr % pageSize) + objs[objs.length - 1].alloc_size;
        while (endOffsetLastObject > pageSize) {
            /*  NOTE: at this point, we rely on the fact that the objects are sorted in ascending order
                by the address. */
            let newObj = structuredClone(objs[objs.length - 1]);
            newObj.alloc_size = Math.min(endOffsetLastObject - pageSize, pageSize);
            newObj.alloc_addr = (Math.floor(objs[objs.length - 1].alloc_addr / pageSize) + 1)*pageSize;
            // newObj.alloc_addr = (objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) -
            //     ((objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) % pageSize);
            newObj.isDup = true;
            pages[page + pageSize] ? pages[page + pageSize].push(newObj) : pages[page + pageSize] = [newObj];
            // objs[objs.length - 1].alloc_size -= newObj.alloc_size;
            endOffsetLastObject -= pageSize;
        }

        // if (endOffsetLastObject > pageSize) {
        //     let newObj = structuredClone(objs[objs.length - 1]);
        //     newObj.alloc_size = endOffsetLastObject - pageSize;
        //     newObj.alloc_addr = (objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) -
        //         ((objs[objs.length - 1].alloc_addr + objs[objs.length - 1].alloc_size) % pageSize);
        //     // TODO: figure out a better way to do this; unshift shifts the entire array forward
        //     pages[page + pageSize] ? pages[page + pageSize].push(newObj) : pages[page + pageSize] = [newObj];
        //     objs[objs.length - 1].alloc_size -= newObj.alloc_size;
        // }
    }

    // console.log(pages);
    // console.log(Object.entries(pages));

    // let initTs = allocsOverTimeLayout(Object.values(pages).reduce((acc, curr) => acc.concat(curr),[]));
    pageLayout(pageSize, pages, initTs);
    // objectLayout(objects, initTs);
    legendLayout();
}

export default initVis;