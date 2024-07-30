import React, {Component} from "react";
import ProgressBar from "react-bootstrap/ProgressBar";
import {connect} from "react-redux";

const mapStateToProps = (state, props) => ({
    initialLoading: state.initialLoadingContestantData,
    totalInitialPositionCountForContestant:state.totalInitialPositionCountForContestant,
    currentInitialPositionCountForContestant:state.currentInitialPositionCountForContestant
})


class ConnectedTrackLoadingIndicator extends Component {
    getPercentageCompletedLoading() {
        if (Object.keys(this.props.totalInitialPositionCountForContestant).length == 0){
            return 0
        }
        let total = 0,current=0;
        Object.keys(this.props.totalInitialPositionCountForContestant).map((key, index) => {
            total+=this.props.totalInitialPositionCountForContestant[key]
            current+=this.props.currentInitialPositionCountForContestant[key]!==undefined?this.props.currentInitialPositionCountForContestant[key]:0
        })
        return Math.round(100 * current / total)
    }

    render() {
        if (this.props.numberOfContestants === 0) {
            return <div/>
        }
        const now = this.getPercentageCompletedLoading();
        return now !== 100 ? <ProgressBar max={100} now={now} label={now + "%"}/> : <div/>
    }
}

const TrackLoadingIndicator = connect(mapStateToProps)(ConnectedTrackLoadingIndicator);
export default TrackLoadingIndicator;