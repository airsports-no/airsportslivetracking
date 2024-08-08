import React, { Component } from "react";
import ProgressBar from "react-bootstrap/ProgressBar";
import { connect } from "react-redux";

const mapStateToProps = (state, props) => ({
    initialLoadingContestantData: state.initialLoadingContestantData,
})


class ConnectedTrackLoadingIndicator extends Component {
    getPercentageCompletedLoading() {
        if (Object.keys(this.props.initialLoadingContestantData).length == 0) {
            return 0
        }
        let total = 0, current = 0;
        Object.keys(this.props.initialLoadingContestantData).map((key, index) => {
            total += 1
            if (!this.props.initialLoadingContestantData[key]) {
                current += 1
            }
        })
        if (total == 0) {
            return 100
        }
        return Math.round(100 * current / total)
    }

    render() {
        if (this.props.numberOfContestants === 0) {
            return <div />
        }
        const now = this.getPercentageCompletedLoading();
        return now !== 100 ? <ProgressBar max={100} now={now} label={now + "%"} /> : <div />
    }
}

const TrackLoadingIndicator = connect(mapStateToProps)(ConnectedTrackLoadingIndicator);
export default TrackLoadingIndicator;