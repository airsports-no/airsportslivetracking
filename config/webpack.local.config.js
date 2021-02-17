var config = require('./webpack.base.config.js')

config.devtool = "#eval-source-map";
config.watch = true;
config.watchOptions = {
    poll: 1000,
    ignored: /node_modules|bower_components/
};
config.mode = "development"
module.exports = config;