import React, {Component} from "react";
import ReactDOMServer from "react-dom/server";
import {connect} from "react-redux";
import ContestPopupItem from "./contestPopupItem";

const L = window['L']

export const mapStateToProps = (state, props) => ({
    zoomContest: state.zoomContest
})
export const mapDispatchToProps = {}

class ConnectedContestDisplayGlobalMap extends Component {
    constructor(props) {
        super(props)
        this.circle = null
    }

    componentDidMount() {
        // this.props.fetchContestsNavigationTaskSummaries(this.props.contest.id)
        this.circle = L.circle([this.props.contest.latitude, this.props.contest.longitude], {
            radius: 50000,
            color: "red",
            opacity: 0.3
        }).addTo(this.props.map)
        this.circle.bindPopup(ReactDOMServer.renderToString(<ContestPopupItem contest={this.props.contest}/>), {
            permanent: false,
            direction: "center"
        })
    }


    componentDidUpdate(prevProps) {
        if (prevProps.zoomContest !== this.props.zoomContest && this.props.zoomContest) {
            if (this.props.contest.id === this.props.zoomContest) {
                this.circle.openPopup()
            } else {
                this.circle.closePopup()
            }
        }
    }

    componentWillUnmount() {
        this.circle.removeFrom(this.props.map)
    }

    render() {
        return null
    }
}

const ContestDisplayGlobalMap = connect(mapStateToProps, mapDispatchToProps)(ConnectedContestDisplayGlobalMap);
export default ContestDisplayGlobalMap;