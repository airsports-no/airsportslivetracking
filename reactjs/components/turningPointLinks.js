import React, {Component} from "react";
import {setDisplay} from "../actions";
import {TURNING_POINT_DISPLAY} from "../constants/display-types";

const mapDispatchToProps = (dispatch, props) => ({
    displayTurningPointsStandings: turningPoint => dispatch(setDisplay({
        displayType: TURNING_POINT_DISPLAY,
        turningPoint: turningPoint
    }))
})

const mapStateToProps = (state, props) => ({
    turningPoints: state.contest.track.waoypoints.map((a) => {
        return a.name
    })
})

class ConnectedTurningPointLinks extends Component {
    constructor(props) {
        super(props);
        this.turningPoints = props.turningPoints
        this.handleClick = this.handleClick.bind(this);
    }

    handleClick(turningPoint) {
        this.props.displayTurningPointsStandings(turningPoint)
    }

    render() {
        this.turningPoints.map((turningPoint) => {
            return <li><a href={"#"} onClick={() => {
                this.handleClick(turningPoint)
            }} key={"tplist" + turningPoint.name}>{turningPoint.name}</a></li>
        })
    }
}

const TurningPointLinks = connect(mapStateToProps, mapDispatchToProps)(ConnectedTurningPointLinks)

export default TurningPointLinks