const path = require("path");
const fs = require("fs");
const BundleTracker = require('webpack-bundle-tracker');
module.exports = {
    context: path.resolve(__dirname, '../'),
    mode: 'development',
    entry: fs.readdirSync("../reactjs/containers/")
        .filter(f => f.endsWith(".jsx"))
        .map(f => ({[path.basename(f, ".jsx")]: path.resolve(__dirname, `../reactjs/containers/${f}`)}))
        .reduce((a, b) => Object.assign(a, b), {}),

    output: {
        path: path.resolve('/assets/bundles/local/'),
        filename: "[name]-[fullhash].js",
        // Needed to compile multiline strings in Cesium
        sourcePrefix: ''
    },

    // Optimisation breaks react router
    // optimization: {
    //     runtimeChunk: 'single',
    //     splitChunks: {
    //         cacheGroups: {
    //             commons: {
    //                 test: /[\\/]node_modules[\\/]/,
    //                 chunks: "all",
    //                 name: "vendors"
    //             }
    //         }
    //     }
    // },
    // optimization: {
    // splitChunks: {
    //     cacheGroups: {
    //         styles: {
    //             name: 'styles',
    //             test: /\.css$/,
    //             chunks: 'all',
    //             enforce: true
    //         },
    //         vendor: {
    //             chunks: 'initial',
    //             test: 'vendor',
    //             name: 'vendor',
    //             enforce: true
    //         }
    //     }
    // }
    // },
    plugins: [
        new BundleTracker({filename: path.resolve(__dirname, '../webpack-stats-local.json')}),
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
                                localIdentName: '[path][name]__[local]--[fullhash:base64:5]',
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
                                localIdentName: '[path][name]__[local]--[fullhash:base64:5]',
                            },
                        },
                    },
                    'sass-loader',
                ],
            },
        ]
    },


    resolve: {
        fallback: {"https": false, "zlib": false, "http": false, "url": false},
        mainFiles: ['index', 'Cesium'],
        modules: ['node_modules', 'bower_components'],
        extensions: ['.js', '.jsx'],
    }
    ,
};