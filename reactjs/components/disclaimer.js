import React, {Component} from "react";

export default class Disclaimer extends Component {

    render() {
        return <div id={"disclaimer"}>
            <img src={"/static/img/airsports_no_text_white.png"} className={"logo"}/>
            THIS SERVICE IS PROVIDED BY AIR SPORTS LIVE TRACKING, AND IS INTENDED FOR ENTERTAINMENT ONLY! PLEASE
            READ THE - <a href={"#"} style={{color: "white"}}>USER INFORMATION AND DISCLAIMER</a>
        </div>
    }
}

