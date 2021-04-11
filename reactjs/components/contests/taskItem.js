import React, {Component} from "react";

export default class TaskItem extends Component {


    handleClick() {
        window.location.href = document.configuration.navigationTaskMap(this.props.navigationTask.pk)
    }

    render() {
        return <a href={document.configuration.navigationTaskMap(this.props.navigationTask.pk)}
                  type={"button"} className={"btn btn-primary flex-even"}
                  style={{color: "white"}}
                  onClick={() => this.handleClick()}>{this.props.navigationTask.name}</a>
    }
}

