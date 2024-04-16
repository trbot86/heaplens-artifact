import path from "path"
import HtmlWebpackPlugin from "html-webpack-plugin";
import CopyWebpackPlugin from "copy-webpack-plugin";
import ImageMinimizerPlugin from "image-minimizer-webpack-plugin";
import webpack from "webpack";

const __dirname = path.resolve();

export default {
    mode: 'development',
    devtool: 'inline-source-map',
    entry: {
        index: './src/index.js'
    },
    devServer: {
        contentBase: path.resolve(__dirname, 'src/index.html'),
        port: 8000
    },
    output: {
        filename: 'index.bundle.js',
        path: path.resolve(__dirname, 'dist'),
        clean: true
    },
    plugins: [
        new ImageMinimizerPlugin({
            minimizer: {
                implementation: ImageMinimizerPlugin.imageminMinify,
                options: {
                    plugins: [
                        [
                        'imagemin-svgo',
                            {
                                plugins: [
                                    // SVGO options is here "https://github.com/svg/svgo#what-it-can-do"
                                    {
                                    name: 'preset-default',
                                    removeViewBox: false,
                                    removeXMLNS: true,
                                    },
                                ],
                            },
                        ],
                    ],
                },
            },
        }),
        new HtmlWebpackPlugin({
            template: "src/index.html",
            filename: "index.html",
            showErrors: true,
            assetModuleFilename: 'images/[hash][ext][query]',
        }),
        new CopyWebpackPlugin({
            patterns: [
                {from: "src/assets/", to: "assets/"}
            ]
        }),
        // new webpack.ProvidePlugin({
        //     $: "jquery",
        //     jQuery: "jquery"
        // })
    ],
    module: {
        rules: [
            {
            test: /\.svg$/,
            use: [
                {
                loader: "raw-loader"
                }
            ]
            },
            {
            test: /\.(png|jpe?g|gif)$/i,
            type: "asset/resource",
            generator: { filename: `assets/[name][ext]`},
            },
            {
            test: /\.wasm$/,
            type: 'javascript/auto'
            },
            {
            test: /\.css$/,
            use: [
                'style-loader',
                'css-loader'
            ]
            }
        ]
    },
    resolve: {
        fallback: {
            "fs": false,
            "crypto": false,
            "path": false
        }
    }
}

// module.exports = {
//   mode: 'development',
//   entry: {index: './src/index.js'},
//   output: {
//     path: path.resolve(__dirname, 'dist'),
//     filename: 'index.bundle.js',
//     clean: true,
//     publicPath: '/',
//   },
//   module: {
//     rules: [
//       {
//         test: /\.(png|jpe?g|gif)$/i,
//         type: "asset/resource",
//         generator: { filename: `assets/[name][ext]`},
//       },
//     ],
//   },
// };

// const path = require('path')
// const HtmlWebpackPlugin = require('html-webpack-plugin')

// module.exports = {
//     mode: 'development',
//     entry: {
//         index: './src/index.js'
//     },
//     devtool: 'incline-source-map',
//     plugins: [
//         new HtmlWebpackPlugin({
//             template: "src/index.html",
//             filename: "index.html",
//             showErrors: true,
//             assetModuleFilename: 'assets/[hash][ext][query]'
//         })
//     ],
//     output: {
//         filename: '[name].bundle.js',
//         path: path.resolve(__dirname, 'dist'),
//         clean: true
//     },
//     module: {
//         rules: [
//             {
//                 test: '/\.css$/i',
//                 use: ['style-loader', 'css-loader']
//             }

//         ]
//     },
//     resolve: {
//         extensions: ['.js']
//     },
// };