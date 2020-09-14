var config = require('./webpack.base.config.js')

config.devtool = "#eval-source-map";
config.watch = true;
config.watchOptions = {
    ignored: /node_modules|bower_components/
};

module.exports = config;