import React, {Component} from "react";

export default class AccumulatedScore extends Component {
    render() {
        return <div className={"danger-level-accumulated-score-container"}>
            {this.props.frozen ? <img src={document.configuration.STATIC_FILE_LOCATION+"img/gate_score_arrow_red.gif"} style={{width: "100%"}}/> :
                <img src={document.configuration.STATIC_FILE_LOCATION+"img/gate_score_arrow_black.gif"} style={{width: "100%"}}/>}
            <div className={"danger-level-accumulated-score-white"}>
                {this.props.value}
            </div>
        </div>
    }
}