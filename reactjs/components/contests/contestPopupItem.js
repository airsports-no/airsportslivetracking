import React, {Component} from "react";
import TaskItem from "./taskItem";
import {zoomFocusContest} from "../../actions";
import {connect} from "react-redux";
import EllipsisWithTooltip from "react-ellipsis-with-tooltip";


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

export default class ContestPopupItem extends Component {
    render() {
        const tasks = this.props.contest.navigationtask_set.sort(sortTaskTimes)
        return <div style={{width: "301px"}}>
            <div className={""} id={"contest" + this.props.contest.id}>
                <img className={"card-img-top"} src={this.props.contest.header_image} alt={"Contest promo image"}/>
                <div className={""}>
                    <h5 className={"card-title"}>{this.props.contest.name}</h5>
                    <h6 className={"card-subtitle mb-2 text-muted"}>
                        {new Date(this.props.contest.start_time).toLocaleDateString()} - {new Date(this.props.contest.finish_time).toLocaleDateString()}
                    </h6>
                    <p className={"card-text"}>
                        <ul className={"list-group list-group-flush"}>
                            {tasks.map((task) => {
                                return <TaskItem key={"task" + task.pk} navigationTask={task}/>
                            })}

                        </ul>

                    </p>
                </div>
            </div>
        </div>
    }
}


