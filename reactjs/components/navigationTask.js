import React, {Component} from "react";
import {displayAllTracks, fetchNavigationTask, setDisplay} from "../actions";
import {connect} from "react-redux";
import {circle, divIcon, marker, polyline, tileLayer} from "leaflet";
import ContestantTrack from "./contestantTrack";
import distinctColors from "distinct-colors";
import {compareContestantNumber} from "../utilities";
import ContestantRankTable from "./contestantRankTable";
import {CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY, TURNING_POINT_DISPLAY} from "../constants/display-types";
import ContestantDetailsDisplay from "./contestantDetailsDisplay";
import TurningPointLinks from "./turningPointLinks";
import TurningPointDisplay from "./turningPointDisplay";

const L = window['L']

const mapStateToProps = (state, props) => ({
    navigationTask: state.navigationTask,
    currentDisplay: state.currentDisplay
})

class ConnectedNavigationTask extends Component {
    constructor(props) {
        super(props);
        this.state = {colourMap: {}}
        this.handleNavigationTaskHeadingClick = this.handleNavigationTaskHeadingClick.bind(this)
    }

    handleNavigationTaskHeadingClick() {
        this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
        this.props.displayAllTracks();
    }

    componentDidMount() {
        this.props.fetchNavigationTask(this.props.navigationTaskId);
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
        if (this.props.navigationTask !== previousProps.navigationTask) {
            if (this.props.displayMap) {
                this.renderRoute()
            }
        }
    }

    initialiseMap() {
        this.map = L.map('cesiumContainer', {
            zoomDelta: 0.25,
            zoomSnap: 0.25,
        })
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
            return waypoint.gate_check
        }).map((gate) => {
            polyline([[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]], {
                color: "blue"
            }).addTo(this.map)
            // }
        })
        let turningPoints = this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return true //waypoint.type === "tp"
        }).map((waypoint) => {
            return [waypoint.latitude, waypoint.longitude]
        });
        this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return waypoint.gate_check
        }).map((waypoint) => {
            marker([waypoint.latitude, waypoint.longitude], {
                color: "blue",
                icon: divIcon({
                    html: '<i class="fas"><br/>' + waypoint.name + '</i>',
                    iconSize: [20, 20],
                    className: "myGateIcon"
                })
            }).bindTooltip(waypoint.name, {permanent: false}).addTo(this.map)
        });
        this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return waypoint.is_procedure_turn
        }).map((waypoint) => {
            circle([waypoint.latitude, waypoint.longitude], {
                radius: 500,
                color: "blue"
            }).addTo(this.map)
        })
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
        let route = polyline(turningPoints, {
            color: "blue"
        }).addTo(this.map)
        this.map.fitBounds(route.getBounds(), {padding: [50, 50]})

    }

    render() {
        if (this.props.navigationTask.contestant_set !== undefined) {
            const colourMap = this.buildColourMap()
            let tableDisplay = <div/>
            if (this.props.displayTable) {
                let display = <div/>
                if (this.props.currentDisplay.displayType === SIMPLE_RANK_DISPLAY) {
                    display = <ContestantRankTable colourMap={colourMap} numberOfContestants={this.props.navigationTask.contestant_set.length}/>
                } else if (this.props.currentDisplay.displayType === CONTESTANT_DETAILS_DISPLAY) {
                    display = <ContestantDetailsDisplay contestantId={this.props.currentDisplay.contestantId}/>
                } else if (this.props.currentDisplay.displayType === TURNING_POINT_DISPLAY) {
                    display = <TurningPointDisplay turningPointName={this.props.currentDisplay.turningPoint}
                                                   colourMap={colourMap}/>
                }
                tableDisplay = <div>
                    <a href={"#"} onClick={this.handleNavigationTaskHeadingClick}><h1>{this.props.navigationTask.name}</h1></a>
                    <TurningPointLinks/>
                    {display}
                </div>
            }
            let mapDisplay = this.props.navigationTask.contestant_set.map((contestant, index) => {
                return <ContestantTrack map={this.map} key={contestant.id} fetchInterval={6000}
                                        contestant={contestant} displayMap={this.props.displayMap}
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

const
    NavigationTask = connect(mapStateToProps, {fetchNavigationTask, setDisplay, displayAllTracks})(ConnectedNavigationTask);
export default NavigationTask;