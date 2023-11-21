import express from "express";
import webpack from "webpack";
import webpackDevMiddleware from "webpack-dev-middleware";

const app = express();
import { default as config } from './webpack.config.js';
const compiler = webpack(config);

const port = 8000;

app.use(
    webpackDevMiddleware(compiler, {
        publicPath: config.output.publicPath,
    })
);

app.listen(port, function() {
        console.log(`App is running on http://localhost:${port}...\n`)
    } 
);