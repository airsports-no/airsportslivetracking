import React, {Component} from "react";

export default class TaskItem extends Component {


    handleClick() {
        window.location.href = document.configuration.navigationTaskMap(this.props.navigationTask.pk)
    }

    render() {
        return <li className={"list-group-item list-group-item-secondary list-group-item-action"} onClick={()=>this.handleClick()}>{this.props.navigationTask.name}
        </li>
    }
}

