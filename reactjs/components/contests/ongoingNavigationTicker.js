import React, {Component} from "react";
import {connect} from "react-redux";
import ContestDisplayGlobalMap from "./contestDisplayGlobalMap";
import {fetchOngoingNavigation} from "../../actions";

const L = window['L']

export const mapStateToProps = (state, props) => ({
    ongoingNavigation: state.ongoingNavigation
})
export const mapDispatchToProps = {
    fetchOngoingNavigation
}

class ConnectedOngoingNavigationTicker extends Component {
    constructor(props) {
        super(props)
        this.state = {
            currentNavigationIndex: 0
        }
        this.cycleTimer = null
    }

    componentDidMount() {
        this.fetchOngoingNavigationTasks()
    }

    componentDidUpdate(prevProps, prevState, snapshot) {
        if (this.props.ongoingNavigation !== prevProps.ongoingNavigation) {
            this.setState({currentNavigationIndex: 0})
            this.cycleNavigation()
        }
    }

    cycleNavigation() {
        if (this.state.currentNavigationIndex >= this.props.ongoingNavigation.length - 1) {
            this.setState({currentNavigationIndex: 0})
        } else {
            this.setState({currentNavigationIndex: this.state.currentNavigationIndex + 1})
        }
        if (this.cycleTimer) {
            clearTimeout(this.cycleTimer)
        }
        this.cycleTimer = setTimeout(() => this.cycleNavigation(), 10 * 1000)
    }

    fetchOngoingNavigationTasks() {
        this.props.fetchOngoingNavigation()
        setTimeout(() => this.fetchOngoingNavigationTasks(), 60 * 1000)
    }

    render() {
        if (this.props.ongoingNavigation.length === 0) {
            return <b>No active contestants</b>
        }
        const currentNavigation = this.props.ongoingNavigation[this.state.currentNavigationIndex]
        return <div>
            Ongoing {this.state.currentNavigationIndex + 1}/{this.props.ongoingNavigation.length}:<br/>
            <a href={currentNavigation.tracking_link}>
                <b>{currentNavigation.contest.name} ({currentNavigation.name})</b><br/>
            </a>
            {currentNavigation.active_contestants.length} active {currentNavigation.active_contestants.length>1?"contestants":"contestant"}.
        </div>
    }
}

const OngoingNavigationTicker = connect(mapStateToProps, mapDispatchToProps)(ConnectedOngoingNavigationTicker);
export default OngoingNavigationTicker;