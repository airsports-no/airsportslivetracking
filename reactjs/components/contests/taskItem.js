import React, {Component} from "react";

export default class TaskItem extends Component {
    render() {
        return <li><a
            href={document.configuration.navigationTaskMap(this.props.navigationTask.pk)}>{this.props.navigationTask.name}</a>
        </li>
    }
}

