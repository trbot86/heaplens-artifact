// import initSqlJs from "sql.js";
// Following import required to let webpack know it needs to copy the wasm file to our assets
// import sqlWasm from "!!file-loader?name=sql-wasm-[contenthash].wasm!sql.js/dist/sql-wasm.wasm";
import * as d3 from 'd3';
import MainVisualization from './vis.js';

export let mainVis = undefined;

export function getCurrTime() {
    return mainVis.getGraphLayout().getCurrTime();
}

async function getDb(src) {
    // const SQL = await initSqlJs({locateFile: () => sqlWasm});

    try {
        fetch('/run-get-records')
            .then((allResponse) => allResponse.json())
            .then((allData) => {
                document.getElementById("dropPanels").remove();
                // console.log(allData['pts']
                mainVis = MainVisualization.build(allData);
                // fetch('/run-sampler')
                //     .then((sampleResponse) => sampleResponse.json())
                //     .then((sampleData) => {
                //         console.log('Data received from server.');
                //         mainVis.constructPageVis(sampleData);
                //     })
                //     .catch((error) => {
                //         console.error('Error: ', error);
                //     });
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