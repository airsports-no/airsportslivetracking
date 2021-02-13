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
        return <span className={"second-in-between"}>
                <div
                    className={"list-group-item list-group-item-secondary list-group-item-action"}
                    onClick={() => this.handleClick()}
                >
                    <img className={"img-fluid"} src={this.props.contest.logo} alt={"Event logo"}
                         style={{width: "100%", maxHeight: "60px", maxWidth: "60px", float: "left"}}/>

                         <span className={"d-flex justify-content-between align-items-centre"}
                               style={{paddingLeft: "10px"}}>
                             <span>
                                 <b>{this.props.contest.name}</b><br/>
                                 {new Date(this.props.contest.start_time).toLocaleDateString()} -
                                 {new Date(this.props.contest.finish_time).toLocaleDateString()}
                             </span>
                             <i className={"mdi mdi-public"} style={{fontSize: "40px"}}/>
                    </span>
                    {/*{this.props.contest.latitude !== 0 && this.props.contest.longitude !== 0 ?*/}
                    {/*    <i className={"mdi mdi-zoom-in"} onClick={() => this.handleClick()}/> : null}*/}
                </div>
    </span>
    }
}


const ContestItem = connect(mapStateToProps, mapDispatchToProps)(ConnectedContestItem);
export default ContestItem;