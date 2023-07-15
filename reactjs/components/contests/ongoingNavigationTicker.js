import React, {Component} from "react";
import {connect} from "react-redux";
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
            return null
        }
        const currentNavigation = this.props.ongoingNavigation[this.state.currentNavigationIndex]
        if (currentNavigation === undefined) {
            return null
        }
        return <span className={"second-in-between"}>
                <div
                    className={"list-group-item list-group-item-secondary list-group-item-action"}
                >
                    {this.props.ongoingNavigation.length > 1 ?
                        <a href={"#"} onClick={() => this.cycleNavigation()}
                           className={"float-right"}>&gt;</a> : null}
                    <b>Ongoing {this.state.currentNavigationIndex + 1}/{this.props.ongoingNavigation.length}</b>
                    <br/>
                    <img className={"img-fluid"}
                         src={currentNavigation.contest.logo && currentNavigation.contest.logo.length > 0 ?
                             currentNavigation.contest.logo : "/static/img/airsportslogo.png"}
                         alt={"Event logo"}
                         style={{width: "100%", maxHeight: "60px", maxWidth: "60px", float: "left"}}/>

                         <span className={"d-flex justify-content-between align-items-centre"}
                               style={{paddingLeft: "10px"}}>
                             <span>
                                 <b>{currentNavigation.contest.name}</b>
                                 <a href={currentNavigation.tracking_link}>
                                    <h5>{currentNavigation.name}</h5>
                                </a>
                             </span>
                             <img src={currentNavigation.contest.country_flag_url} style={{height: "15px"}}
                                  alt={"Country flag"}/>
                    </span>
                </div>
    </span>
    }
}

const OngoingNavigationTicker = connect(mapStateToProps, mapDispatchToProps)(ConnectedOngoingNavigationTicker);
export default OngoingNavigationTicker;