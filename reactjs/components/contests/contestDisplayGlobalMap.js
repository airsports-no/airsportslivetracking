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
        const now = new Date()
        let colour = "blue"
        if (new Date(this.props.contest.start_time).getTime() < now.getTime() && new Date(this.props.contest.finish_time).getTime() > now.getTime()) {
            colour = "red"
        }
        this.circle = L.marker([this.props.contest.latitude, this.props.contest.longitude], {
            title: this.props.contest.name,
            zIndexOffset: 5,
            riseOnHover: true

        }).addTo(this.props.map)
        this.circle.bindPopup(ReactDOMServer.renderToString(<ContestPopupItem contest={this.props.contest}/>), {
            className: "contest-popup",
            maxWidth: 350,
            // maxWidth: 500,
            // maxHeight: 300,
            // minWidth: 100,
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