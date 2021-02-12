import React, {Component} from "react";

export default class TaskItem extends Component {


    handleClick() {
        window.location.href = document.configuration.navigationTaskMap(this.props.navigationTask.pk)
    }

    render() {
        return <a href={"#"} className={"list-group-item list-group-item-secondary list-group-item-action"} onClick={()=>this.handleClick()}>
            <i className={"mdi mdi-keyboard-tab"}/>{this.props.navigationTask.name}<i className={"mdi mdi-zoom-in"}/>
        </a>
    }
}

