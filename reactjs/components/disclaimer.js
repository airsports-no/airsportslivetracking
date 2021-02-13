import React, {Component} from "react";

export default class Disclaimer extends Component {

    render() {
        return <div id={"disclaimer"}>
            <img src={"/static/img/hub.png"} className={"logo"}/>
            THIS SERVICE IS PROVIDED BY AIR SPORTS LIVE TRACKING, <br/>AND IS INTENDED FOR ENTERTAINMENT ONLY! PLEASE
            READ THE - <a href={"#"} style={{color: "white"}}>USER INFORMATION AND DISCLAIMER</a>
        </div>
    }
}

