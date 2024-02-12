import MainVisualization from './vis.js';

export let mainVis = undefined;

export function getCurrTime() {
    return mainVis.getGraphLayout().getCurrTime();
}

async function getDb(srcName) {
    try {
        fetch(`/run-get-records/${srcName}`)
            .then((allResponse) => allResponse.json())
            .then((allData) => {
                document.getElementById("dropPanels").remove();
                mainVis = MainVisualization.build(srcName, allData);
            })
            .catch((error) => {
                console.error('Error: ', error);
            });
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