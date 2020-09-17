import 'regenerator-runtime/runtime'
import React from "react";
import axios from "axios";
import {Tracker} from "../dataStructure/Tracker";
import {render} from "react-dom";
import Cesium from 'cesium/Cesium';


class CesiumContainer extends React.Component {
    constructor(props) {
        super(props);
        // console.log(this.props)
        this.state = {initiated: false};
        this.client = null;
        this.viewer = null;
        this.tracker = {contest: {name: ""}}
        this.contest_id = document.configuration.contest_id;
        this.liveMode = document.configuration.live_mode;
        this.contest = null;
        console.log("contest_id = " + this.contest_id)
    }

    fetchContest(contestId) {
        this.initialising = true;
        axios.get("/display/api/contest/detail/" + contestId).then(res => {
            console.log("contest data:")
            console.log(res)
            this.contest = res.data;
            if (new Date() > new Date(this.contest.start_time))
                this.liveMode = false;
            this.initialiseCesium()
            this.setState({initiated: true})
            const startTime = Cesium.JulianDate.fromDate(new Date(this.contest.start_time))
            const finishTime = Cesium.JulianDate.fromDate(new Date(this.contest.finish_time))
            if (!this.liveMode) {
                this.viewer.clock.startTime = startTime.clone()
                this.viewer.clock.stopTime = finishTime.clone()
                this.viewer.clock.currentTime = startTime.clone()
                this.viewer.clock.clockRange = Cesium.ClockRange.LOOP_STOP
                this.viewer.clock.multiplier = 10
                this.viewer.clock.shouldAnimate = true
                this.viewer.timeline.zoomTo(startTime, finishTime)
            } else {
                // Remove timeline controls
                this.viewer.animation.container.style.visibility = "hidden"
                this.viewer.timeline.container.style.visibility = "hidden"
                this.viewer.forceResize()
            }
            this.initialising = false;

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

    // componentWillMount() {
    // }
    //
    componentDidMount() {
        this.fetchContest(this.contest_id)
        // this.viewer.zoomTo(this.viewer.entities);
    }

    render() {
        let TrackerDisplay = <div/>
        if (this.state.initiated)
            TrackerDisplay = <Tracker viewer={this.viewer} contest={this.contest} liveMode={this.liveMode}/>
        return (
            <div id='main_div'>
                <div id="cesiumContainer"></div>
                <div className="backdrop" id="menu">
                    {TrackerDisplay}
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
