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
            // return <div className="card transparent-partial">
            //     <div className={"card-body transparent-partial"}>
            //         <div className={"card-text"}>
            //             No active competitions
            //         </div>
            //     </div>
            // </div>
        }
        const currentNavigation = this.props.ongoingNavigation[this.state.currentNavigationIndex]
        return <div className="card">
            {/*<h5 className={"card-header"}>*/}
            {/*    Ongoing*/}
            {/*    competition*/}
            {/*</h5>*/}
            <div className={"card-body"}>
                <div className={"card-title"}>
                    <h3>{currentNavigation.contest.name}</h3>
                </div>
                <div className={"card-text row"}>
                    <div className={"col-4"}>
                            <img
                                src={currentNavigation.contest.logo && currentNavigation.contest.logo.length > 0 ? currentNavigation.contest.logo : "/static/img/airsportslogo.png"}
                                alt={"Contest promo image"}
                                style={{maxHeight: "200px", maxWidth: "100px", marginBottom: "5px"}}/>
                    </div>
                    <div className={"col-8"}>
                        <a href={currentNavigation.tracking_link}>
                            <h3>{currentNavigation.name}</h3>
                        </a>
                        {currentNavigation.active_contestants.length} active {currentNavigation.active_contestants.length > 1 ? "contestants" : "contestant"}
                    </div>
                </div>
            </div>
            <div className={"card-footer text-muted"}>
                {this.props.ongoingNavigation.length > 1 ?
                    <a href={"#"} onClick={() => this.cycleNavigation()} className={"float-right"}>&gt;</a> : null}
                Ongoing competition {this.state.currentNavigationIndex + 1}/{this.props.ongoingNavigation.length}
            </div>
        </div>
    }
}

const OngoingNavigationTicker = connect(mapStateToProps, mapDispatchToProps)(ConnectedOngoingNavigationTicker);
export default OngoingNavigationTicker;