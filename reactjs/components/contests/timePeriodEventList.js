import React, {Component} from "react";
import ContestItem from "./contestItem";

function sortTaskTimes(a, b) {
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

export default class TimePeriodEventList extends Component {
    render() {
        return <span className={"first-in-between"}>
            {this.props.contests.map((contest) => {
                return <ContestItem key={"contest" + contest.id} contest={contest} onClick={(contest)=>this.props.onClick(contest)}/>
            })}
        </span>

    }
}

