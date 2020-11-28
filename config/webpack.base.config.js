const path = require("path");
const fs = require("fs");
const webpack = require('webpack');
const BundleTracker = require('webpack-bundle-tracker');
const CopyWebpackPlugin = require('copy-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');
// var CompressionPlugin = require("compression-webpack-plugin");
// var BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin;
const cesiumSource = 'node_modules/cesium/Source';
const cesiumWorkers = '../Build/Cesium/Workers';
module.exports = {
    context: path.resolve(__dirname, '../'),
    mode: 'development',
    entry: fs.readdirSync("../reactjs/containers/")
        .filter(f => f.endsWith(".jsx"))
        .map(f => ({[path.basename(f, ".jsx")]: path.resolve(__dirname, `../reactjs/containers/${f}`)}))
        .reduce((a, b) => Object.assign(a, b), {}),

    node: {
        fs: 'empty'
    },


    amd: {
        // Enable webpack-friendly use of require in Cesium
        toUrlUndefined: true
    },

    output: {
        path: path.resolve('/static/bundles/local/'),
        filename: "[name]-[hash].js",
        // Needed to compile multiline strings in Cesium
        sourcePrefix: ''
    },

    // externals: ["jquery"], // add all vendor libs
    optimization: {
        splitChunks: {
            cacheGroups: {
                commons: {
                    test: /[\\/]node_modules[\\/]/,
                    chunks: "all",
                    name: "vendors"
                }
            }
        }
    },
    plugins: [
        // new HtmlWebpackPlugin({
        //     template: 'src/index.html'
        // }),
        // Copy Cesium Assets, Widgets, and Workers to a static directory
        // new CopyWebpackPlugin([{from: path.join(cesiumSource, cesiumWorkers), to: 'Workers'}]),
        // new CopyWebpackPlugin([{from: path.join(cesiumSource, 'Assets'), to: 'Assets'}]),
        // new CopyWebpackPlugin([{from: path.join(cesiumSource, 'Widgets'), to: 'Widgets'}]),
        // new webpack.DefinePlugin({
        //     // Define relative base path in cesium for loading assets
        //     CESIUM_BASE_URL: JSON.stringify('')
        // }),
        new BundleTracker({filename: path.resolve(__dirname, '../webpack-stats-local.json')}),
        // new webpack.DefinePlugin({ // <-- key to reducing React's size
        //     'process.env': {
        //         'NODE_ENV': JSON.stringify('production')
        //     }
        // }),
        // new webpack.optimize.UglifyJsPlugin({
        //     compress: {
        //         warnings: false,
        //         screw_ie8: true,
        //         conditionals: true,
        //         unused: true,
        //         comparisons: true,
        //         sequences: true,
        //         dead_code: true,
        //         evaluate: true,
        //         if_return: true,
        //         join_vars: true
        //     },
        //     output: {
        //         comments: false
        //     }
        // }),
        // new webpack.HashedModuleIdsPlugin(),
        // new webpack.optimize.AggressiveMergingPlugin()//Merge chunks
    ], // add all common plugins here

    module: {

        rules: [
            {
                test: /\.(js|jsx)$/,
                exclude: /node_modules|bower_components/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ["@babel/env", "@babel/react"]
                    }
                }
            },
            {
                test: /\.css$/i,
                exclude: /\.module\.css$/i,
                use: ['style-loader', 'css-loader'],
            },
            {
                test: /\.module\.css$/i,
                use: [
                    'style-loader',
                     {
                         loader: 'css-loader',
                         options: {
                             modules: {
                                 mode: 'local',
                                 localIdentName: '[path][name]__[local]--[hash:base64:5]',
                             },
                         },
                     },
                ],
            },
            {
                test: /\.s[ac]ss$/i,
                exclude: /\.module\.s[ac]ss$/i,
                use: ['style-loader', 'css-loader', 'sass-loader'],
            },
            {
                test: /\.(png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)$/,
                use: ["file-loader"]
            },
            {
                test: /\.module\.s[ac]ss$/i,
                use: [
                    'style-loader',
                    {
                         loader: 'css-loader',
                         options: {
                             importLoaders: 1,
                             modules: {
                                 mode: 'local',
                                 localIdentName: '[path][name]__[local]--[hash:base64:5]',
                             },
                         },
                     },
                    'sass-loader',
                ],
            },
// {
//     test: /\.(png|gif|jpg|jpeg|svg|xml|json)$/,
//     use: ['url-loader']
// }
        ]
    },


    resolve: {
        modules: ['node_modules', 'bower_components'],
        extensions:
            ['.js', '.jsx'],
        alias:
            {
                // CesiumJS module name
                cesium: path.resolve(__dirname + "../../", cesiumSource)
            }
    }
    ,
};