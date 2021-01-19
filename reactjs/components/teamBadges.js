import React, {Component} from "react";
import {connect} from "react-redux";
import EllipsisWithTooltip from 'react-ellipsis-with-tooltip'

const question = "/static/img/questionmark.png"

export class TeamBadge extends Component {
    render() {
        if (this.props.team) {
            return <div className={"card team-badge"}>
                <div className={"card-body row"}>
                    <div className={'col-6'}>
                        <ProfilePicture picture={this.props.team.picture ? this.props.team.picture : question}
                                        text={this.props.team.nation}/>
                    </div>
                    <div className={'col-6'}>
                        <div className={"card-title"}>
                            Crew
                        </div>
                        <div className={"card-text"}>
                            <TeamMembers crew={this.props.team.crew}/>
                        </div>
                        <LongAircraft aircraft={this.props.team.aeroplane}/>
                    </div>
                </div>
            </div>
        }
        return <div/>
    }
}

function memberOnePicture(crew) {
    return <img className={"lowerThirdsProfileImage img-fluid"} src={crew.member1.picture}/>
}

function memberTwoPicture(crew) {
    return crew.member2 ? <img className={"lowerThirdsProfileImage  img-fluid"} src={crew.member2.picture}/> : null
}

function memberName(member) {
    return <h4 className={"lower-thirds-pilot-names"}>
        <EllipsisWithTooltip>
            {member.last_name.toUpperCase()}
        </EllipsisWithTooltip>
        <EllipsisWithTooltip>
            {member.first_name}
        </EllipsisWithTooltip>
    </h4>
}

function clubDisplay(club) {
    if (club === null) {
        return null
    }
    const image = <img src={"/static/flags/3x2/" + club.country + ".svg"} className={"personalFlag img-fluid"}
                       alt={club.country}/>
    return <div>{image} {club.name}</div>
}

const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData[props.contestant.id],
})

class ConnectedLowerThirdTeam extends Component {

    render() {
        if (this.props.team === null) return null
        const singleCrew = this.props.contestant.team.crew.member2 == null
        let crewPictures = <div className={"row"}>
            <div className={"col-4"}/>
            <div className={"col-4 inheritDisplay"}>
                {memberOnePicture(this.props.contestant.team.crew)}
            </div>
            <div className={"col-4 inheritDisplay"}>
                {memberTwoPicture(this.props.contestant.team.crew)}
            </div>
        </div>
        if (singleCrew) {
            crewPictures = <div className={"row"}>
                <div className={"col-4"}/>
                <div className={"col-8 inheritDisplay"}>
                    {memberOnePicture(this.props.contestant.team.crew)}
                </div>
            </div>

        }
        let crewNames = <div className={"row"}>
            <div className={"col-6 text-center"}>
                {memberName(this.props.contestant.team.crew.member1)}
            </div>
            <div className={"col-6 text-center"}>
                {this.props.contestant.team.crew.member2 !== null ? memberName(this.props.contestant.team.crew.member2) : null}
            </div>
        </div>
        if (singleCrew) {
            crewNames = <div className={"row"}>
                <div className={"col-12 text-center"}>
                    {memberName(this.props.contestant.team.crew.member1)}
                </div>
            </div>

        }
        return <div className={"lowerThirdsScale"}>
            <div className={singleCrew ? "lowerThirdsSingle" : "lowerThirdsDouble"}>
                <div className={"card-transparent"}>
                    {crewPictures}
                    <div className={"bg-dark text-light lower-thirds-name-box"}>
                        <div className={"row"}>
                            <div className={"col-4"}>
                                <div className={"row"}>
                                    <div className={"text-center col-12"}>
                                        <div className={"lower-thirds-current-score"}>
                                            {this.props.contestantData.contestant_track.score}
                                        </div>
                                    </div>
                                </div>
                                <div className={"row"}>
                                    <div className={"text-center col-12"}>
                                        <div className={"lower-thirds-current-score-text"}>
                                            Live score
                                        </div>
                                    </div>
                                </div>
                                {/*<img className={"lowerThirdsTeamImage img-fluid rounded"}*/}
                                {/*     src={this.props.contestant.team.logo ? this.props.contestant.team.logo : this.props.contestant.team.club && this.props.contestant.team.club.logo ? this.props.contestant.team.club.logo : ""}/>*/}
                            </div>
                            <div className={"col-9"}>
                                {crewNames}
                                <div className={"row"}>
                                    <div className={"col-12 text-center"}>
                                        <h4>{clubDisplay(this.props.contestant.team.club)}</h4>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    }
}

export const LowerThirdTeam = connect(mapStateToProps)(ConnectedLowerThirdTeam)

export class TeamMembers
    extends Component {
    render() {
        return <div>
            Pilot: {this.props.crew.pilot}<br/>
            {this.props.crew.navigator ? "Navigator: " + this.props.crew.navigator : null}
        </div>
    }
}

export class LongAircraft extends Component {
    render() {
        const aircraft = this.props.aircraft;
        const picture = aircraft.picture ? aircraft.picture : question
        return <div className="aircraft-header-container">
            <div className="aircraft-header-img">
                <img alt={aircraft.registration} className="img-long" src={picture}/>
                <div className="rank-label-container">
                    <span className="label label-default rank-label">{aircraft.registration}</span>
                </div>
            </div>
        </div>
    }
}

export class ProfilePicture extends Component {
    render() {
        return <div className="profile-header-container">
            <div className="profile-header-img">
                <img alt={this.props.text} className="img-square" src={this.props.picture}/>
                <div className="rank-label-container">
                    <span className="label label-default rank-label">{this.props.text}</span>
                </div>
            </div>
        </div>
    }
}