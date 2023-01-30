var config = require('./webpack.base.config.js')

config.mode = "production";
config.devtool = "source-map";

module.exports = config;
