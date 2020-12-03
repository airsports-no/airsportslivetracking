import React, {Component} from "react";
import {displayAllTracks, fetchContest, setDisplay} from "../actions";
import {connect} from "react-redux";
import {circle, divIcon, map, marker, polyline, tileLayer} from "leaflet";
import ContestantTrack from "./ContestantTrack";
import distinctColors from "distinct-colors";
import {compareContestantNumber} from "../utilities";
import ContestantRankTable from "./contestantRankTable";
import {CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY, TURNING_POINT_DISPLAY} from "../constants/display-types";
import ContestantDetailsDisplay from "./contestantDetailsDisplay";
import TurningPointLinks from "./turningPointLinks";
import TurningPointDisplay from "./turningPointDisplay";

const mapStateToProps = (state, props) => ({
    contest: state.contest,
    currentDisplay: state.currentDisplay
})

class ConnectedContest extends Component {
    constructor(props) {
        super(props);
        this.state = {colourMap: {}}
        this.handleContestHeadingClick = this.handleContestHeadingClick.bind(this)
    }

    handleContestHeadingClick() {
        this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
        this.props.displayAllTracks();
    }

    componentDidMount() {
        this.props.fetchContest(this.props.contestId);
        if (this.props.displayMap) {
            this.initialiseMap();
        }
    }

    buildColourMap() {
        const colours = distinctColors({count: this.props.contest.contestant_set.length})
        this.props.contest.contestant_set.sort(compareContestantNumber)
        let colourMap = {}
        this.props.contest.contestant_set.map((contestant, index) => {
            colourMap[contestant.contestant_number] = colours[index]
        })
        return colourMap
    }


    componentDidUpdate(previousProps) {
        if (this.props.contest !== previousProps.contest) {
            if (this.props.displayMap) {
                this.renderTrack()
            }
        }
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
        // const logoContainer = document.getElementById("logoContainer")
        // const mapControlContainer = document.getElementsByClassName("leaflet-control")[0]
        // mapControlContainer.appendChild(logoContainer)
    }

    renderTrack() {
        for (const key in this.props.contest.track.waypoints) {
            if (this.props.contest.track.waypoints.hasOwnProperty(key)) {
                let gate = this.props.contest.track.waypoints[key];
                polyline([[gate.gate_line[1], gate.gate_line[0]], [gate.gate_line[3], gate.gate_line[2]]], {
                    color: "blue"
                }).addTo(this.map)
            }
        }
        let turningPoints = this.props.contest.track.waypoints.filter((waypoint) => {
            return waypoint.type === "tp"
        }).map((waypoint) => {
            return [waypoint.latitude, waypoint.longitude]
        });
        this.props.contest.track.waypoints.map((waypoint) => {
            marker([waypoint.latitude, waypoint.longitude], {
                color: "blue",
                icon: divIcon({
                    html: '<i class="fas"><br/>' + waypoint.name + '</i>',
                    iconSize: [20, 20],
                    className: "myGateIcon"
                })
            }).bindTooltip(waypoint.name, {permanent: false}).addTo(this.map)
        });
        this.props.contest.track.waypoints.filter((waypoint) => {
            return waypoint.is_procedure_turn
        }).map((waypoint) => {
            circle([waypoint.latitude, waypoint.longitude], {
                radius: 500,
                color: "blue"
            }).addTo(this.map)
        })
        // Temporarily plot range circles
        // this.props.contest.track.waypoints.map((waypoint) => {
        //     circle([waypoint.latitude, waypoint.longitude], {
        //         radius: waypoint.insideDistance,
        //         color: "orange"
        //     }).addTo(this.map)
        // })
        // Plot starting line
        // const gate = this.props.contest.track.starting_line
        // polyline([[gate.gate_line[1], gate.gate_line[0]], [gate.gate_line[3], gate.gate_line[2]]], {
        //             color: "red"
        //         }).addTo(this.map)
        let route = polyline(turningPoints, {
            color: "blue"
        }).addTo(this.map)
        this.map.fitBounds(route.getBounds(), {padding: [50, 50]})

    }

    render() {
        if (this.props.contest.contestant_set !== undefined) {
            const colourMap = this.buildColourMap()
            let tableDisplay = <div/>
            if (this.props.displayTable) {
                let display = <div/>
                if (this.props.currentDisplay.displayType === SIMPLE_RANK_DISPLAY) {
                    display = <ContestantRankTable colourMap={colourMap}/>
                } else if (this.props.currentDisplay.displayType === CONTESTANT_DETAILS_DISPLAY) {
                    display = <ContestantDetailsDisplay contestantId={this.props.currentDisplay.contestantId}/>
                } else if (this.props.currentDisplay.displayType === TURNING_POINT_DISPLAY) {
                    display = <TurningPointDisplay turningPointName={this.props.currentDisplay.turningPoint}
                                                   colourMap={colourMap}/>
                }
                tableDisplay = <div>
                    <a href={"#"} onClick={this.handleContestHeadingClick}><h1>{this.props.contest.name}</h1></a>
                    <TurningPointLinks/>
                    {display}
                </div>
            }
            let mapDisplay = this.props.contest.contestant_set.map((contestant, index) => {
                    return <ContestantTrack map={this.map} key={contestant.id} fetchInterval={10000}
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
    Contest = connect(mapStateToProps, {fetchContest, setDisplay, displayAllTracks})(ConnectedContest);
export default Contest;