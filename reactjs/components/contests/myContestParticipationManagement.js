import React, {Component} from "react";
import {connect} from "react-redux";
import MyParticipatingEventsList from "./myParticipatingEventsList";
import UpcomingContestsSignupTable from "../upcomingContestsSignupTable";
import ContestRegistrationForm from "../contestRegistrationForm";
import {fetchMyParticipatingContests} from "../../actions";

export const mapStateToProps = (state, props) => ({
    currentContestRegistration: state.currentContestRegistration,
    currentContestParticipation: state.currentContestParticipation
})
export const mapDispatchToProps = {
    fetchMyParticipatingContests
}


class ConnectedMyContestParticipationManagement extends Component {
    constructor(props) {
        super(props)
    }

    componentDidUpdate(prevProps) {
        this.props.fetchMyParticipatingContests()
    }


    render() {
        return <div className={"row"}>
            <div className={"col-3"}>
                <h2>My upcoming contests</h2>
                <MyParticipatingEventsList/>
            </div>
            <div className={"col-9"}>
                {this.props.currentContestRegistration || this.props.currentContestParticipation ?
                    <ContestRegistrationForm
                        contest={this.props.currentContestRegistration || this.props.currentContestParticipation.contest}
                        participation={this.props.currentContestParticipation}/> :
                    <UpcomingContestsSignupTable/>}
            </div>
        </div>
    }
}

const MyContestParticipationManagement = connect(mapStateToProps,
    mapDispatchToProps)(ConnectedMyContestParticipationManagement);
export default MyContestParticipationManagement;