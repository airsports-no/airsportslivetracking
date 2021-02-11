import React, {Component} from "react";

export default class Disclaimer extends Component {

    render() {
        return <div id={"disclaimer"}>
            {/*<img src={"/static/img/nlf_white.png"} className={"logo"}/>*/}
            THIS SERVICE IS PROVIDED BY AIR SPORTS LIVE TRACKING, <r/>AND IS INTENDED ONLY AS ENTERTAINMENT - <a href={"#"} style={{color: "white"}}>FOR MORE
            INFO / DISCLAIMER</a>
        </div>
    }
}

