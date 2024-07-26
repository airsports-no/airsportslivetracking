import React, {Component} from "react";
import {connect} from "react-redux";
import MyParticipatingEventsList from "./myParticipatingEventsList";
import UpcomingContestsSignupTable from "../participationManagement/upcomingContestsSignupTable";
import ContestRegistrationForm from "../participationManagement/contestRegistrationForm";
import {fetchMoreContests, fetchMyParticipatingContests} from "../../actions";
import Navbar from "../navbar";
import {withParams} from "../../utilities";

export const mapStateToProps = (state, props) => ({
    currentContestRegistration: state.currentContestRegistration,
    currentContestParticipation: state.currentContestParticipation,
    contests: state.contests,
    myParticipatingContests: state.myParticipatingContests,
})
export const mapDispatchToProps = {
    fetchMyParticipatingContests,
    fetchMoreContests
}


class ConnectedMyContestParticipationManagement extends Component {
    constructor(props) {
        super(props)
    }

    componentDidMount() {
        if (!document.configuration.authenticatedUser) {
            window.location.href = "/accounts/login/?next=" + window.location.pathname
        }
        this.props.fetchMoreContests()
    }

    componentDidUpdate(prevProps) {
        if (prevProps.registrationContestId !== this.props.registrationContestId) {
            this.props.fetchMyParticipatingContests()
        }

        if (!document.configuration.authenticatedUser) {
            window.location.href = "/accounts/login/?next=" + window.location.pathname
        }
    }


    render() {
        let registerContest = null
        let currentParticipation = this.props.params.currentParticipationId ? this.props.myParticipatingContests.find((contestTeam) => {
            return contestTeam.id === parseInt(this.props.params.currentParticipationId)
        }) : null
        let currentParticipationRegistration = null
        if (this.props.params.registerContestId) {
            currentParticipationRegistration = this.props.myParticipatingContests.find((contestTeam) => {
                return contestTeam.contest.id === parseInt(this.props.params.registerContestId)
            })
            registerContest = this.props.contests.find((contest) => {
                return contest.id === parseInt(this.props.params.registerContestId)
            })
        }
        return <div>
            <Navbar/>
            <div className={"row container-xl"}>
                <div className={"col-lg-4"}>
                    <h2>My participation</h2>
                    <MyParticipatingEventsList currentParticipation={currentParticipation}
                                               navigationTaskId={parseInt(this.props.params.navigationTaskId)}/>
                </div>
                <div className={"col-lg-8"}>
                    <h3>Upcoming contests</h3><UpcomingContestsSignupTable/></div>
                {registerContest ? <ContestRegistrationForm
                    contest={registerContest}
                    participation={currentParticipationRegistration}/> : null}
            </div>
        </div>
    }
}

const MyContestParticipationManagement = connect(mapStateToProps,
    mapDispatchToProps)(ConnectedMyContestParticipationManagement);
export default withParams(MyContestParticipationManagement);