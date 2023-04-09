import React, {Component} from "react";
import ReactDOMServer from "react-dom/server";
import {connect} from "react-redux";
import ContestPopupItem from "./contestPopupItem";


export const mapStateToProps = (state, props) => ({
    zoomContest: state.zoomContest,
    myParticipatingContests: state.myParticipatingContests
})
export const mapDispatchToProps = {}

class ConnectedContestDisplayGlobalMap extends Component {
    constructor(props) {
        super(props)
        this.circle = null
        this.L = window['L']
    }

    getCurrentParticipation(contestId) {
        if (!this.props.myParticipatingContests) return null
        return this.props.myParticipatingContests.find((participation) => {
            return participation.contest.id === contestId
        })
    }

    componentDidMount() {
        const now = new Date()
        this.circle = this.L.marker([this.props.contest.latitude, this.props.contest.longitude], {
            title: this.props.contest.name,
            zIndexOffset: 1000000,
            riseOnHover: true

        }).addTo(this.props.map)
        this.circle.bindPopup(ReactDOMServer.renderToString(<ContestPopupItem contest={this.props.contest}
                                                                              participation={this.getCurrentParticipation(this.props.contest.id)}/>), {
            className: "contest-popup",
            maxWidth: 350,
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