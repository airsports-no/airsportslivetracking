import React, {Component} from "react";
import Thermometer from 'react-thermometer-component'

export default class AirsportsThermometer extends Component {
    render() {
        return <div style={{width: "50px", marginLeft:"-25px"}}><Thermometer
            theme="dark"
            value={this.props.value}
            max="100"
            steps="1"
            format=""
            size="medium"
            height="300"
        />
        </div>
    }
}