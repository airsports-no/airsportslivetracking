import React, {Component} from "react";
import ContestItem from "./contestItem";


export default class TimePeriodEventList extends Component {
    render() {
        return <div className={"card text-white bg-secondary"}>
            {this.props.contests.map((contest) => {
                return <ContestItem key={"contest" + contest.pk} contest={contest}/>
            })}
        </div>

    }
}

