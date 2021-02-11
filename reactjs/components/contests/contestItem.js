import React, {Component} from "react";
import TaskItem from "./taskItem";

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

export default class ContestItem extends Component {
    render() {
        const tasks = this.props.contest.navigationtask_set.sort(sortTaskTimes)
        return <li>
            {this.props.contest.name}<br/>
            {this.props.contest.start_time}-{this.props.contest.finish_time}
            <ul>
                {tasks.map((task) => {
                    return <TaskItem key={"task" + task.pk} navigationTask={task}/>
                })}</ul>
        </li>
    }
}

