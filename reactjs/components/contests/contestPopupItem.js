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
        return <div className={""} key={"contest" + this.props.contest.id}>
            <img className={"mx-auto d-block"}
                 src={this.props.contest.header_image && this.props.contest.header_image.length > 0 ? this.props.contest.header_image : "/static/img/airsportslogo.png"}
                 alt={"Contest promo image"} style={{maxHeight: "200px", maxWidth: "260px"}}/>
            <div className={""}>
                <h5 className={"card-title"}>{this.props.contest.name}</h5>
                <h6 className={"card-subtitle mb-2 text-muted"}>
                    <div className={"float-right"}>
                        {this.props.contest.contest_website.length > 0 ?
                            <a href={this.props.contest.contest_website}>Website</a> : ""}
                    </div>
                    {new Date(this.props.contest.start_time).toLocaleDateString()} - {new Date(this.props.contest.finish_time).toLocaleDateString()}
                </h6>
                {/*<p className={"card-text"}>*/}
                <ul className={"d-flex flex-wrap justify-content-around"}
                    style={{paddingLeft: "0px", columnGap: "5px", rowGap: "5px"}}>
                    {tasks.map((task) => {
                        return <TaskItem key={"task" + task.pk} navigationTask={task}/>
                    })}

                </ul>

                {/*</p>*/}
            </div>
        </div>
    }
}


