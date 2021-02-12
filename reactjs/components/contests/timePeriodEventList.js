import React, {Component} from "react";
import ContestItem from "./contestItem";


export default class TimePeriodEventList extends Component {
    render() {
        return <span className={"first-in-between"}>
            {this.props.contests.map((contest) => {
                return <ContestItem key={"contest" + contest.pk} contest={contest}/>
            })}
        </span>

    }
}

