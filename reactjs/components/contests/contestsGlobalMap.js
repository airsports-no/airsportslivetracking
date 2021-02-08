import React, {Component} from "react";
import {connect} from "react-redux";
import ContestDisplayGlobalMap from "./contestDisplayGlobalMap";

const L = window['L']

export const mapStateToProps = (state, props) => ({
    contests: state.contests
})
export const mapDispatchToProps = {}

class ConnectedContestsGlobalMap extends Component {
    constructor(props) {
        super(props)
    }

    render() {
        if (this.props.map!==null) {
            const contests = this.props.contests.map((contest) => {
                return <ContestDisplayGlobalMap map={this.props.map} contest={contest}/>
            })
            return <div>{contests}</div>
        }
        return null
    }
}

const ContestsGlobalMap = connect(mapStateToProps, mapDispatchToProps)(ConnectedContestsGlobalMap);
export default ContestsGlobalMap;