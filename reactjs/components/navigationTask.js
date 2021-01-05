import React, {Component} from "react";
import {
    displayAllTracks,
    expandTrackingTable,
    fetchNavigationTask,
    setDisplay,
    shrinkTrackingTable,
    hideLowerThirds, dispatchContestantData
} from "../actions";
import {connect} from "react-redux";
import {circle, divIcon, marker, polyline, tileLayer} from "leaflet";
import ContestantTrack from "./contestantTrack";
import distinctColors from "distinct-colors";
import {compareContestantNumber} from "../utilities";
import ContestantRankTable from "./contestantRankTable";
import {CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY, TURNING_POINT_DISPLAY} from "../constants/display-types";
import ContestantDetailsDisplay from "./contestantDetailsDisplay";
import TurningPointDisplay from "./turningPointDisplay";
import {w3cwebsocket as W3CWebSocket} from "websocket";

const L = window['L']


const mapStateToProps = (state, props) => ({
    navigationTask: state.navigationTask,
    currentDisplay: state.currentDisplay,
    displayExpandedTrackingTable: state.displayExpandedTrackingTable,
})

class ConnectedNavigationTask extends Component {
    constructor(props) {
        super(props);
        this.resetToAllContestants = this.resetToAllContestants.bind(this)
        this.handleMapTurningPointClick = this.handleMapTurningPointClick.bind(this)
        this.rendered = false
        this.client = null;
    }

    initiateSession() {
        let getUrl = window.location;
        let baseUrl = getUrl.protocol + "//" + getUrl.host + "/" + getUrl.pathname.split('/')[1]
        this.client = new W3CWebSocket("ws://" + getUrl.host + "/ws/tracks/" + this.props.navigationTaskId + "/")
        this.client.onopen = () => {
            console.log("Client connected")
        };
        this.client.onmessage = (message) => {
            let data = JSON.parse(message.data);
            console.log("WS data")
            console.log(data)
            this.props.dispatchContestantData(data)
        };

    }

    handleMapTurningPointClick(turningPoint) {
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
        this.props.setDisplay({
            displayType: TURNING_POINT_DISPLAY,
            turningPoint: turningPoint
        })
    }

    resetToAllContestants(e) {
        L.DomEvent.stopPropagation(e)
        this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
    }

    fetchNavigationTask() {
        this.props.fetchNavigationTask(this.props.contestId, this.props.navigationTaskId);
        setTimeout(() => this.fetchNavigationTask(), 300000)
    }

    componentDidMount() {
        this.fetchNavigationTask()
        if (this.props.displayMap) {
            this.initialiseMap();
        }
    }


    buildColourMap() {
        const colours = distinctColors({count: this.props.navigationTask.contestant_set.length})
        this.props.navigationTask.contestant_set.sort(compareContestantNumber)
        let colourMap = {}
        this.props.navigationTask.contestant_set.map((contestant, index) => {
            colourMap[contestant.contestant_number] = colours[index]
        })
        return colourMap
    }


    componentDidUpdate(previousProps) {
        if (this.props.navigationTask.route !== previousProps.navigationTask.route) {
            if (this.props.displayMap && !this.rendered) {
                this.renderRoute()
                this.rendered = true;
                this.initiateSession()
            }
        }
    }

    initialiseMap() {
        this.map = L.map('cesiumContainer', {
            zoomDelta: 0.25,
            zoomSnap: 0.25,
        }).on('contextmenu', (e) => this.resetToAllContestants(e))
        const token = "pk.eyJ1Ijoia29sYWYiLCJhIjoiY2tmNm0zYW55MHJrMDJ0cnZvZ2h6MTJhOSJ9.3IOApjwnK81p6_a0GsDL-A"
        tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
            attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
            maxZoom: 18,
            id: 'mapbox/streets-v11',
            tileSize: 512,
            zoomOffset: -1,
            accessToken: token
        }).addTo(this.map);
        // const logoContainer = document.getElementById("logoContainer")
        // const mapControlContainer = document.getElementsByClassName("leaflet-control")[0]
        // mapControlContainer.appendChild(logoContainer)
    }

    renderRoute() {
        this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return waypoint.gate_check || waypoint.time_check
        }).map((gate) => {
            polyline([[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]], {
                color: "blue"
            }).addTo(this.map)
            // }
        })
        let tracks = []
        let currentTrack = []
        const typesToIgnore = ["to", "ldg", "ildg"]
        for (const waypoint of this.props.navigationTask.route.waypoints) {
            if (waypoint.type === 'isp') {
                tracks.push(currentTrack)
                currentTrack = []
            }
            if (!typesToIgnore.includes(waypoint.type)) {
                if (waypoint.is_procedure_turn) {
                    currentTrack.push(...waypoint.procedure_turn_points)
                } else {
                    currentTrack.push([waypoint.latitude, waypoint.longitude])
                }
            }
        }
        tracks.push(currentTrack)
        // let turningPoints = this.props.navigationTask.route.waypoints.filter((waypoint) => {
        //     return true //waypoint.type === "tp"
        // }).map((waypoint) => {
        //     return [waypoint.latitude, waypoint.longitude]
        // });
        this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return waypoint.gate_check || waypoint.time_check
        }).map((waypoint) => {
            marker([waypoint.latitude, waypoint.longitude], {
                color: "blue",
                icon: divIcon({
                    html: '<i class="fas"><br/>' + waypoint.name + '</i>',
                    iconSize: [20, 20],
                    className: "myGateIcon"
                })
            }).bindTooltip(waypoint.name, {permanent: false}).on('click', () => {
                this.handleMapTurningPointClick(waypoint.name)
            }).addTo(this.map)
        });
        // this.props.navigationTask.route.waypoints.filter((waypoint) => {
        //     return waypoint.is_procedure_turn
        // }).map((waypoint) => {
        //     circle([waypoint.latitude, waypoint.longitude], {
        //         radius: 500,
        //         color: "blue"
        //     }).addTo(this.map)
        // })
        // Temporarily plot range circles
        // this.props.navigationTask.track.waypoints.map((waypoint) => {
        //     circle([waypoint.latitude, waypoint.longitude], {
        //         radius: waypoint.insideDistance,
        //         color: "orange"
        //     }).addTo(this.map)
        // })
        // Plot starting line
        // const gate = this.props.navigationTask.track.starting_line
        // polyline([[gate.gate_line[1], gate.gate_line[0]], [gate.gate_line[3], gate.gate_line[2]]], {
        //             color: "red"
        //         }).addTo(this.map)
        let route;
        for (const track of tracks) {
            route = polyline(track, {
                color: "blue"
            }).addTo(this.map)
        }
        this.map.fitBounds(route.getBounds(), {padding: [50, 50]})

    }

    render() {
        if (this.props.navigationTask.contestant_set !== undefined) {
            const colourMap = this.buildColourMap()
            let display = <div/>
            if (this.props.currentDisplay.displayType === SIMPLE_RANK_DISPLAY) {
                display = <ContestantRankTable colourMap={colourMap}
                                               numberOfContestants={this.props.navigationTask.contestant_set.length}/>
            } else if (this.props.currentDisplay.displayType === CONTESTANT_DETAILS_DISPLAY) {
                display = <ContestantDetailsDisplay contestantId={this.props.currentDisplay.contestantId}/>
                this.props.shrinkTrackingTable();
            } else if (this.props.currentDisplay.displayType === TURNING_POINT_DISPLAY) {
                display = <TurningPointDisplay turningPointName={this.props.currentDisplay.turningPoint}
                                               colourMap={colourMap}/>
                this.props.shrinkTrackingTable();
            }
            const tableDisplay = <div>
                <div className={"card text-light collapse bg-dark"} id={"insetMenu"} aria-expanded={false}
                     aria-controls={"insetMenu"}>
                    {/*<div className={"card-body"}>*/}
                    <div className={"card–text"}>
                        {/*<div className={"card-title"}>*/}
                        {/*</div>*/}
                        {display}
                    </div>
                    {/*</div>*/}
                </div>
            </div>
            const mapDisplay = this.props.navigationTask.contestant_set.map((contestant, index) => {
                return <ContestantTrack map={this.map} key={contestant.id} fetchInterval={10000}
                                        contestant={contestant} contestId={this.props.contestId}
                                        navigationTaskId={this.props.navigationTaskId}
                                        displayMap={this.props.displayMap}
                                        colour={colourMap[contestant.contestant_number]}/>
            });
            return <div>
                {mapDisplay}
                {tableDisplay}
            </div>
        }
        return <div/>
    }

}

const NavigationTask = connect(mapStateToProps, {
    fetchNavigationTask,
    dispatchContestantData,
    setDisplay,
    displayAllTracks,
    expandTrackingTable,
    shrinkTrackingTable,
    hideLowerThirds
})(ConnectedNavigationTask);
export default NavigationTask;