import React, {Component} from "react";
import {connect} from "react-redux";
import {dispatchTraccarData, fetchContests, fetchContestsNavigationTaskSummaries} from "../../actions";
import TimePeriodEventList from "./timePeriodEventList";

export const mapStateToProps = (state, props) => ({
    contests: state.contests
})
export const mapDispatchToProps = {}

function sortContestTimes(a, b) {
    const startTimeA = new Date(a.start_time)
    const finishTimeA = new Date(a.finish_time)
    const startTimeB = new Date(b.start_time)
    const finishTimeB = new Date(b.finish_time)
    if (startTimeA < startTimeB) {
        return -1;
    }
    if (startTimeA > startTimeB) {
        return 1;
    }
    if (finishTimeA < finishTimeB) {
        return -1;
    }
    if (finishTimeA > finishTimeB) {
        return 1;
    }
    return 0;
}

class ConnectedGlobalEventList extends Component {
    constructor(props) {
        super(props)
    }

    handleManagementClick() {
        window.location.href = document.configuration.managementLink
    }


    render() {
        let settingsButton = null
        if (document.configuration.managementLink) {
            settingsButton = <a className={"btn"} href={document.configuration.managementLink}>
                <i className={"taskTitle mdi mdi-settings"}/>
            </a>
        }

        const now = new Date()
        const upcomingEvents = this.props.contests.filter((contest) => {
            const startTime = new Date(contest.start_time)
            const finishTime = new Date(contest.finish_time)
            if (startTime > now) {
                return contest
            }
        }).sort(sortContestTimes)
        const ongoingEvents = this.props.contests.filter((contest) => {
            const startTime = new Date(contest.start_time)
            const finishTime = new Date(contest.finish_time)
            if (finishTime > now && startTime < now) {
                return contest
            }
        }).sort(sortContestTimes)
        const earlierEvents = this.props.contests.filter((contest) => {
            const startTime = new Date(contest.start_time)
            const finishTime = new Date(contest.finish_time)
            if (finishTime < now) {
                return contest
            }
        }).sort(sortContestTimes)
        return <div>
            <div className={"card text-white bg-dark"}>
                <div className={"card-header taskTitle"}>Events <span style={{float: "right"}}>{settingsButton}</span>
                </div>
                <div className={"card-body"}>
                    <div className={"list-group list-group-root"}>
                        <a href={"#ongoing"}
                           className={"list-group-item list-group-item-action list-group-item-secondary d-flex justify-content-between align-items-centre"}
                           data-toggle={"collapse"}><span><i className={"mdi mdi-keyboard-arrow-right"}/>
                           Ongoing events</span>
                            <span className={"badge badge-primary badge-pill"}>{ongoingEvents.length}</span>
                        </a>
                        <div className={"list-group collapse"} id={"ongoing"}>
                            <TimePeriodEventList contests={ongoingEvents}/>
                        </div>
                        <a href={"#upcoming"}
                           className={"list-group-item list-group-item-action list-group-item-secondary d-flex justify-content-between align-items-centre"}
                           data-toggle={"collapse"}>
                            <span><i className={"mdi mdi-keyboard-arrow-right"}/>Upcoming events</span>
                            <span className={"badge badge-primary badge-pill"}>{upcomingEvents.length}</span>
                        </a>
                        <div className={"list-group collapse"} id={"upcoming"}>
                            <TimePeriodEventList contests={upcomingEvents}/>
                        </div>
                        <a href={"#past"}
                           className={"list-group-item list-group-item-action list-group-item-secondary d-flex justify-content-between align-items-centre"}
                           data-toggle={"collapse"}>
                            <span>
                            <i className={"mdi mdi-keyboard-arrow-right"}/>Past events
                                </span>
                            <span className={"badge badge-primary badge-pill"}>{earlierEvents.length}</span>
                        </a>
                        <div className={"list-group collapse"} id={"past"}>
                            <TimePeriodEventList contests={earlierEvents}/>
                        </div>
                    </div>
                </div>
            </div>

        </div>
    }
}

const GlobalEventList = connect(mapStateToProps, mapDispatchToProps)(ConnectedGlobalEventList);
export default GlobalEventList;