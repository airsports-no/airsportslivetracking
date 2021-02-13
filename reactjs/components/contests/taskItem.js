import React, {Component} from "react";

export default class TaskItem extends Component {


    handleClick() {
        window.location.href = document.configuration.navigationTaskMap(this.props.navigationTask.pk)
    }

    render() {
        return <li className={"list-group-item list-group-item-secondary list-group-item-action d-flex justify-content-between align-items-center"}>
            {this.props.navigationTask.name}<button type={"button"} className={"btn btn-primary"} onClick={()=>this.handleClick()}>Show</button>
        </li>
    }
}

