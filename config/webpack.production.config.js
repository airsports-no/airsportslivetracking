const merge = require('webpack-merge');
var common = require('./webpack.base.config.js');

module.exports = merge(common, {
    mode: 'production',
    devtool: 'source-map',
});