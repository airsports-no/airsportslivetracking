import React, {Component} from "react";

export default class TaskItem extends Component {


    handleClick() {
        window.location.href = document.configuration.navigationTaskMap(this.props.navigationTask.pk)
    }

    render() {
        let text = this.props.navigationTask.name
        let style = "btn-primary"
        const now = new Date()
        if (new Date(this.props.navigationTask.start_time) < now && now < new Date(this.props.navigationTask.finish_time)) {
            text += "*"
            style = "btn-success"
        }

        return <a href={document.configuration.navigationTaskMap(this.props.navigationTask.pk)}
                  type={"button"} className={"btn " + style + " flex-even"}
                  style={{color: "white"}}
                  onClick={() => this.handleClick()}>{text}</a>
    }
}

