import React from "react";
import axios from "axios";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import {Tracker} from "../dataStructure/Tracker";
import contest from "../dataStructure/contest.json";
import {render} from "react-dom";
import Cesium from 'cesium/Cesium';


const server = "home.kolaf.net:8082";
const token = "i2hvekMl21UUYIGzjSvezCTSOdxiv1a9";


class CesiumContainer extends React.Component {
    constructor(props) {
        super(props);
        // console.log(this.props)
        this.state = {contest_name: ""};
        this.client = null;
        this.viewer = null;
        this.tracker = {contest: {name: ""}}
        this.contest_id = document.configuration.contest_id;
        this.contest = null;
        console.log("contest_id = " + this.contest_id)
    }

    fetchContest(contestId) {
        this.initialising = true;
        axios.get("/display/api/contest/detail/" + contestId).then(res => {
            console.log("contest data:")
            console.log(res)
            this.contest = res.data;
            this.initialising = false;
            this.tracker = new Tracker(this.viewer, this.contest);
            this.setState({contestName: this.contest.name})
            this.initiateSession();
        });
    }


    initialiseCesium() {
        Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI5OTk4N2IyMi1lMjE4LTRjODctYTQyMS03MTc4OWU4Y2QwM2YiLCJpZCI6NzIzMiwic2NvcGVzIjpbImFzciIsImdjIl0sImlhdCI6MTU0ODc2NzIzNH0.YuwXvkKfzak9mFxdaSjGKcSNg5vtkCMXgVv9VcBoBR4';
        //////////////////////////////////////////////////////////////////////////
        // Creating the Viewer
        //////////////////////////////////////////////////////////////////////////
        let options = {
            projectionPicker: true,
            selectionIndicator: true,
            baseLayerPicker: true,
            fullscreenButton: true,
            requestRenderMode: true,
            maximumRenderTimeChange: 3,
            terrainProvider: Cesium.createWorldTerrain({
                requestVertexNormals: true,
                requestWaterMask: true
            })
        };
        this.viewer = new Cesium.Viewer('cesiumContainer', {});
        // this.viewer.scene.globe.enableLighting = true;
        // this.viewer.infoBox.frame.removeAttribute('sandbox');

        this.scene = this.viewer.scene;
    }


    initiateSession() {
        axios.get("http://" + server + "/api/session?token=" + token, {withCredentials: true}).then(res => {
            this.client = new W3CWebSocket("ws://" + server + "/api/socket")
            console.log("Initiated session")
            console.log(res)

            this.client.onopen = () => {
                console.log("Client connected")
            };
            this.client.onmessage = (message) => {
                let data = JSON.parse(message.data);
                this.tracker.appendPositionReports(data);
            };

        })
    }

    // componentWillMount() {
    // }
    //
    componentDidMount() {
        this.initialiseCesium()
        this.fetchContest(this.contest_id)
        // this.viewer.zoomTo(this.viewer.entities);
    }

    render() {
        return (
            <div id='main_div'>
                {this.state.contest_name}
                <div id="cesiumContainer"></div>
            </div>
        );
    }
}

render(<CesiumContainer/>, document.getElementById('cesiumContainerRoot'));
