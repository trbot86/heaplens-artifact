import express from "express";
import webpack from "webpack";
import webpackDevMiddleware from "webpack-dev-middleware";
import { spawn } from 'child_process';

const app = express();
import { default as config } from './webpack.config.js';
const compiler = webpack(config);

const port = 8000;

app.use(
    webpackDevMiddleware(compiler, {
        publicPath: config.output.publicPath,
    })
);

// app.use('/run-sampler', (req, res, next) => {
//     // Set timeout for 10 minutes just in case
//     req.setTimeout(10*60*1000, () => {
//       const err = new Error('Request Timeout');
//       err.status = 408; // HTTP status code for request timeout
//       next(err);
//     });
//     next();
// });

app.get('/run-get-records', (req, res) => {
    // Execute a child process
    const samplerProcess = spawn('python', ['sampler.py', 'all']);
    console.log('Received request for all records.');

    let result = '';

    samplerProcess.stdout.on('data', (data) => {
        console.log('Data received.');
        result += data;
    });

    samplerProcess.stderr.on('data', (data) => {
        console.error(`Error from script: ${data.toString()}`);
        res.status(500).send('Error executing sampler.py');
    });

    samplerProcess.on('close', (code) => {
        console.log(`Sampler script process exited with code ${code} - passing data to frontend.`);
        res.send(result);
    });
});

app.get('/run-sampler/:startTs-:endTs-:alg-:runLen-:maxRuns', (req, res) => {
    // Execute a child process
    console.log('Received sample request.');
    const samplerProcess = spawn('python', ['sampler.py', 'sample', req.params.startTs, req.params.endTs,
                                            req.params.alg, req.params.runLen, req.params.maxRuns]);

    let result = '';

    samplerProcess.stdout.on('data', (data) => {
        console.log('Data received.');
        result += data;
    });

    samplerProcess.stderr.on('data', (data) => {
        console.error(`Error from sampler script: ${data.toString()}`);
        res.status(500).send('Error executing sampler.py');
    });

    samplerProcess.on('close', (code) => {
        console.log(`Sampler script process exited with code ${code} - passing data to frontend.`);
        res.send(result);
    });
});

app.listen(port, function() {
        console.log(`App is running on http://localhost:${port}...\n`)
    }
);