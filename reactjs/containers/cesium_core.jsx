import 'regenerator-runtime/runtime'
import React from "react";
import axios from "axios";
import {Tracker} from "../dataStructure/Tracker";
import {render} from "react-dom";
import {map, tileLayer} from "leaflet"

// import "leaflet/dist/leaflet.css"

class CesiumContainer extends React.Component {
    constructor(props) {
        super(props);
        // console.log(this.props)
        this.state = {initiated: false};
        this.client = null;
        this.viewer = null;
        this.tracker = {contest: {name: ""}}
        this.contest_id = document.configuration.contest_id;
        this.liveMode = document.configuration.liveMode;
        this.contest = null;
        console.log("contest_id = " + this.contest_id)
    }

    fetchContest(contestId) {
        axios.get("/display/api/contest/detail/" + contestId).then(res => {
            console.log("contest data:")
            console.log(res)
            this.contest = res.data;
            if (new Date() > new Date(this.contest.finish_time))
                this.liveMode = false;
            this.initialiseMap()
            this.setState({initiated: true})
        });
    }

    initialiseMap() {
        this.map = map('cesiumContainer')
        const token = "pk.eyJ1Ijoia29sYWYiLCJhIjoiY2tmNm0zYW55MHJrMDJ0cnZvZ2h6MTJhOSJ9.3IOApjwnK81p6_a0GsDL-A"
        tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
            attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
            maxZoom: 18,
            id: 'mapbox/streets-v11',
            tileSize: 512,
            zoomOffset: -1,
            accessToken: token
        }).addTo(this.map);
        const logoContainer = document.getElementById("logoContainer")
        const mapControlContainer = document.getElementsByClassName("leaflet-control")[0]
        mapControlContainer.appendChild(logoContainer)
    }

    componentDidMount() {
        this.fetchContest(this.contest_id)
        // this.viewer.zoomTo(this.viewer.entities);
    }

    render() {
        let TrackerDisplay = <div/>
        if (this.state.initiated)
            TrackerDisplay =
                <Tracker map={this.map} contest={this.contest} liveMode={this.liveMode} fetchInterval={5000}/>
        return (
            <div id="map-holder">
                <div id='main_div' className={"container-fluid fill"}>
                    <div className={"row fill"}>
                        <div className={"col-5"}>
                            {TrackerDisplay}
                        </div>
                        <div className={"col-7 fill"}>
                            <div id="cesiumContainer"></div>
                            <div id="logoContainer"><img src={"/static/img/AirSportsLogo.png"} className={"img-fluid"}/>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }
}

render(
    <CesiumContainer/>,
    document
        .getElementById(
            'cesiumContainerRoot'
        ))
;
