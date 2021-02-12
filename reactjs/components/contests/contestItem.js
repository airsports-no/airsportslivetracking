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
        return <span className={"second-in-between"}>
            <a href={"#contest" + this.props.contest.id}
               className={"list-group-item list-group-item-action list-group-item-secondary "}
               data-toggle="collapse">
                <div className={"d-flex justify-content-between align-items-centre"}>
                        <span>
                    <i className={"mdi mdi-keyboard-arrow-right"}/>
                            {this.props.contest.name}
                        </span>
                        <span>
                            {new Date(this.props.contest.start_time).toLocaleDateString()}
                        </span>
                    <i className={"mdi mdi-zoom-in"} onClick={() => this.handleClick()}/>
                    {/*{this.props.contest.latitude !== 0 && this.props.contest.longitude !== 0 ?*/}
                    {/*    <i className={"mdi mdi-zoom-in"} onClick={() => this.handleClick()}/> : null}*/}
                    <span style={{"padding-top": "0.5em"}}
                        className={"badge badge-dark badge-pill"}>{this.props.contest.navigationtask_set.length}</span>
                </div>
            </a>
            <div className={"list-group collapse"} id={"contest" + this.props.contest.id}>
                {tasks.map((task) => {
                    return <TaskItem key={"task" + task.pk} navigationTask={task}/>
                })}
            </div>
        </span>
    }
}


const ContestItem = connect(mapStateToProps, mapDispatchToProps)(ConnectedContestItem);
export default ContestItem;