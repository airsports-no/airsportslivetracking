import React, {Component} from "react";
import TaskItem from "./taskItem";
import {zoomFocusContest} from "../../actions";
import {connect} from "react-redux";
import EllipsisWithTooltip from "react-ellipsis-with-tooltip";


export const mapStateToProps = (state, props) => ({
    zoomContest: state.zoomContest
})
export const mapDispatchToProps = {
    zoomFocusContest
}


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

class ConnectedContestItem extends Component {
    handleClick() {
        this.props.zoomFocusContest(this.props.contest.id)
    }

    render() {
        const tasks = this.props.contest.navigationtask_set.sort(sortTaskTimes)
        return <div>
            <div className={"card-header active row"} onClick={() => this.handleClick()}>
                <div className={"col-8"}>
                    {this.props.contest.name}
                </div>
                <div className={"col-4"}>
                {new Date(this.props.contest.start_time).toLocaleDateString()}
                </div>
            </div>
            <ul className={"list-group list-group-flush"}>
                {tasks.map((task) => {
                    return <TaskItem key={"task" + task.pk} navigationTask={task}/>
                })}</ul>
        </div>
    }
}


const ContestItem = connect(mapStateToProps, mapDispatchToProps)(ConnectedContestItem);
export default ContestItem;