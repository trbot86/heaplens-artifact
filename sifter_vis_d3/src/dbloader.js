// import initSqlJs from "sql.js";
// Following import required to let webpack know it needs to copy the wasm file to our assets
// import sqlWasm from "!!file-loader?name=sql-wasm-[contenthash].wasm!sql.js/dist/sql-wasm.wasm";
import MainVisualization from './vis.js';

async function getDb(src) {
    // const SQL = await initSqlJs({locateFile: () => sqlWasm});

    try {
        // const db = new SQL.Database(src);
        // const MAIN_TABLE = "SUPERTABLE";

        // const data = [];
        /*  The following statement matches all of the allocations with
            corresponding frees. The following statement:
                (SELECT COUNT(*) FROM Allocs WHERE alloc_timestamp <= a.alloc_timestamp)
            simply labels the rows from 1 to n, where n is the total
            number of allocations. These unique IDs are needed for D3 to
            efficiently update the visualization based on changes to the data. */
        // const stmt = db.prepare(`WITH Allocs AS (
        //                             SELECT FILE AS alloc_file,
        //                                 SIZE AS alloc_size,
        //                                 ADDRESS AS alloc_addr,
        //                                 TYPE AS alloc_type,
        //                                 TIMESTAMP AS alloc_timestamp
        //                             FROM SUPERTABLE
        //                             WHERE isNew=1
        //                         ),
        //                         Frees AS (
        //                             SELECT ADDRESS AS free_addr,
        //                                 TIMESTAMP AS FREE_TIMESTAMP
        //                             FROM SUPERTABLE
        //                             WHERE isNew=0
        //                         )
        //                         SELECT a.alloc_file,
        //                             a.alloc_size,
        //                             a.alloc_addr,
        //                             a.alloc_type,
        //                             a.alloc_timestamp,
        //                             MIN(f.FREE_TIMESTAMP) AS free_timestamp,
        //                             (SELECT COUNT(*) FROM Allocs WHERE alloc_timestamp <= a.alloc_timestamp) AS ID
        //                         FROM Allocs a
        //                         LEFT JOIN Frees f ON a.alloc_addr = f.free_addr AND f.free_timestamp >= a.alloc_timestamp
        //                         GROUP BY a.alloc_addr, a.alloc_timestamp
        //                         ORDER BY a.alloc_addr ASC`);

        // const stmt = db.prepare(`SELECT FILE as allocFile,
        //                                 SIZE as size,
        //                                 ADDRESS as addr,
        //                                 TYPE as type,
        //                                 TIMESTAMP as timestamp,
        //                                 isNew as isAlloc
        //                         FROM SUPERTABLE`);

        // while (stmt.step()) {
        //     data.push(stmt.getAsObject());
        // }
        
        // stmt.free();
        // db.close();

        // document.getElementById("dropPanels").remove();

        fetch('/run-sampler')
            .then((response) => response.json())
            .then((data) => {
                console.log('Data received from server.');
                document.getElementById("dropPanels").remove();
                MainVisualization.build(data);
            })
            .catch((error) => {
                console.error('Error: ', error);
            });

        // TODO add loading animation/indicator while visualization initializes
        // initVis(data);
    }
    catch (err) {
        console.log("ERROR: " + err.message);
    }
}

async function dropListener(event) {
    event.preventDefault();
    const files = event.dataTransfer.files;

    if (files.length == 1) {
        console.log("Selected file: " + files[0].name);
        const reader = new FileReader();
        reader.onload = (f) => {
            /* Convert resulting ArrayBuffer into Uint8Array. Otherwise the
            Database initialization in getDb does not work. */
            getDb(new Uint8Array(f.target.result));
        }
        reader.readAsArrayBuffer(files[0]);
    }
}

function initDB() {
    document.getElementById("dropArea").addEventListener("drop", dropListener);
}

export default initDB;



dropArea.addEventListener("click", function () {
    console.log("CLICK");
    getDb();
//     const fileInput = document.createElement("input");
//     fileInput.type = "file";
//     fileInput.style.display = "none";
    
//     fileInput.addEventListener("change", function () {
//         const selectedFile = fileInput.files[0];
//         if (selectedFile) {
//             console.log("Selected file: " + selectedFile.name);
//         }
//     });

//     document.body.appendChild(fileInput);
//     fileInput.click();
//     document.body.removeChild(fileInput);
});