import * as d3 from 'd3';
import MainVisualization from './vis.js';
import { decodeAsync } from '@msgpack/msgpack';

export let mainVis = undefined;

export function getCurrTime() {
    return mainVis.getGraphLayout().getCurrTime();
}

const numBuckets = 5000;

async function getDb(srcName) {
    document.title = srcName;
    try {
        fetch(`/run-get-records/${srcName}-${numBuckets}`)
            .then((allResponse) => allResponse.text())
            .then((allResponse) => {
                let allData = JSON.parse(allResponse);
                document.getElementById("dropPanels").remove();
                mainVis = MainVisualization.build(srcName, allData);
                d3.select('#dropLoadingAnim')
                    .remove();
                // fetch(`/run-sampler/${mainVis.getFileName()}-0-0-dbscan-3-2`)
                //     .then((sampleResponse) => sampleResponse.text())
                //     .then((sampleResponse) => {
                //         let sampleData = JSON.parse(sampleResponse);
                //         console.log('Generating graphs');
                //         d3.select('#pageLayout').remove();
                //         d3.select('#cacheSetBox').remove();
        
                //         mainVis.constructPageVis(sampleData);
                //     })
                //     .catch((error) => {
                //         console.error('Error: ', error);
                //     });
            })
            .catch((error) => {
                console.error('Error: ', error);
            });
        d3.select('#dropArea')
            .append('div')
            .attr('id', 'dropLoadingAnim')
            .attr('class', 'loadingAnim');
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
        getDb(files[0].name);
    }
}

export default function initDB() {
    document.getElementById("dropArea").addEventListener("drop", dropListener);
}

dropArea.addEventListener("click", function () {
    // getDb('allocs');
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.style.display = "none";
    
    fileInput.addEventListener("change", function () {
        const selectedFile = fileInput.files[0];
        if (selectedFile) {
            console.log("Selected file: " + selectedFile.name);
        }
        getDb(selectedFile.name);
    });

    document.body.appendChild(fileInput);
    fileInput.click();
    document.body.removeChild(fileInput);
});