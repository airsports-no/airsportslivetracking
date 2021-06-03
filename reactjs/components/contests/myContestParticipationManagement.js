import React, {Component} from "react";
import {connect} from "react-redux";
import MyParticipatingEventsList from "./myParticipatingEventsList";
import UpcomingContestsSignupTable from "../upcomingContestsSignupTable";
import ContestRegistrationForm from "../contestRegistrationForm";
import {fetchContests, fetchMyParticipatingContests} from "../../actions";
import {withRouter} from "react-router-dom";

export const mapStateToProps = (state, props) => ({
    currentContestRegistration: state.currentContestRegistration,
    currentContestParticipation: state.currentContestParticipation,
    contests: state.contests,
    myParticipatingContests: state.myParticipatingContests,
})
export const mapDispatchToProps = {
    fetchMyParticipatingContests,
    fetchContests
}


class ConnectedMyContestParticipationManagement extends Component {
    constructor(props) {
        super(props)
    }

    componentDidMount() {
        if (!document.configuration.authenticatedUser) {
            window.location.href = "/accounts/login/?next=" + window.location.pathname
        }
        this.props.fetchContests()
        this.props.fetchMyParticipatingContests()
    }

    componentDidUpdate(prevProps) {
        if (!document.configuration.authenticatedUser) {
            window.location.href = "/accounts/login/?next=" + window.location.pathname
        }
    }


    render() {
        let registerContest = null
        let currentParticipation = this.props.currentParticipationId ? this.props.myParticipatingContests.find((contestTeam) => {
            return contestTeam.id === this.props.currentParticipationId
        }) : null
        let currentParticipationRegistration = null
        if (this.props.registerContestId) {
            currentParticipationRegistration = this.props.myParticipatingContests.find((contestTeam) => {
                return contestTeam.contest.id === this.props.registerContestId
            })
            registerContest = this.props.contests.find((contest) => {
                return contest.id === this.props.registerContestId
            })
        }
        return <div>
            <div className={"row"}>
                <div className={"col-lg-4"}>
                    <h2>My participation</h2>
                    <MyParticipatingEventsList currentParticipation={currentParticipation}
                                               navigationTaskId={this.props.navigationTaskId}/>
                </div>
                <div className={"col-lg-8"}>
                    <h3>Upcoming contests</h3><UpcomingContestsSignupTable/></div>
                {this.props.registerContestId ? <ContestRegistrationForm
                    contest={registerContest}
                    participation={currentParticipationRegistration}/> : null}
            </div>
        </div>
    }
}

const MyContestParticipationManagement = connect(mapStateToProps,
    mapDispatchToProps)(withRouter(ConnectedMyContestParticipationManagement));
export default MyContestParticipationManagement;