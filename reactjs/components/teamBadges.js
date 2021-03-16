import React, {Component} from "react";
import {connect} from "react-redux";
import EllipsisWithTooltip from 'react-ellipsis-with-tooltip'
import Hand from "../react-playing-cards-local/src/PlayingCard/Hand/Hand";
import {teamLongForm} from "../utilities";

const question = "/static/img/questionmark.png"

export class TeamBadge extends Component {
    render() {
        if (this.props.team) {
            return <div className={"card team-badge"}>
                <div className={"card-body row"}>
                    <div className={'col-8'}>
                        <TeamPicture team={this.props.team}
                                        text={this.props.team.nation}/>
                    </div>
                    <div className={'col-4'}>
                        {/*<div className={"card-title"}>*/}
                        {/*    Crew*/}
                        {/*</div>*/}
                        {/*<div className={"card-text"}>*/}
                        {/*    {teamLongForm(this.props.team)}*/}
                        {/*</div>*/}
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
            {member.last_name ? member.last_name.toUpperCase() : ""}
        </EllipsisWithTooltip>
        <EllipsisWithTooltip>
            {member.first_name ? member.first_name : ""}
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


function CrewPictures(props) {
    if (props.contestant.team.crew.member2 != null) {
        return <div className={"row"}>
            <div className={"col-4"}/>
            <div className={"col-4 inheritDisplay"}>
                {memberOnePicture(props.contestant.team.crew)}
            </div>
            <div className={"col-4 inheritDisplay"}>
                {memberTwoPicture(props.contestant.team.crew)}
            </div>
        </div>
    } else {
        return <div className={"row"}>
            <div className={"col-4"}/>
            <div className={"col-8 inheritDisplay"}>
                {memberOnePicture(props.contestant.team.crew)}
            </div>
        </div>
    }
}

function CrewNames(props) {
    if (props.contestant.team.crew.member2 != null) {
        return <div className={"row"}>
            <div className={"col-6 text-center"}>
                {memberName(props.contestant.team.crew.member1)}
            </div>
            <div className={"col-6 text-center"}>
                {props.contestant.team.crew.member2 !== null ? memberName(props.contestant.team.crew.member2) : null}
            </div>
        </div>
    } else {
        return <div className={"row"}>
            <div className={"col-12 text-center"}>
                {memberName(props.contestant.team.crew.member1)}
            </div>
        </div>
    }
}

function ScoreAndNames(props) {
    return <div className={"bg-dark text-light lower-thirds-name-box"} style={{position: "relative", zIndex: 99}}>
        <div className={"row"}>
            <div className={"col-4"}>
                <div className={"row"}>
                    <div className={"text-center col-12"}>
                        <div className={"lower-thirds-current-score"}>
                            {props.contestantData.contestant_track.score.toFixed(0)}
                        </div>
                    </div>
                </div>
                <div className={"row"}>
                    <div className={"text-center col-12"}>
                        <div className={"lower-thirds-current-score-text"}>
                            LIVE SCORE
                        </div>
                    </div>
                </div>
                {/*<img className={"lowerThirdsTeamImage img-fluid rounded"}*/}
                {/*     src={this.props.contestant.team.logo ? this.props.contestant.team.logo : this.props.contestant.team.club && this.props.contestant.team.club.logo ? this.props.contestant.team.club.logo : ""}/>*/}
            </div>
            <div className={"col-8"}>
                <CrewNames contestant={props.contestant}/>
                <div className={"row"}>
                    <div className={"col-12 text-center"}>
                        <h4>{clubDisplay(props.contestant.team.club)}</h4>
                    </div>
                </div>
            </div>
        </div>
    </div>
}


function PlayingCards(props) {
    const cards = props.contestantData.contestant_track.playingcard_set.map((card) => {
        return card.card.toLowerCase()
    })
    return <Hand hide={false} layout={"fan"} cards={cards} cardSize={200}/>
}

class ConnectedLowerThirdTeam extends Component {

    singleCrew() {
        return this.props.contestant.team.crew.member2 == null
    }

    profileImages() {
        if (this.props.team === null) return null
        return <div className={"lowerThirdsScale"}>
            <div className={this.singleCrew() ? "lowerThirdsSingle" : "lowerThirdsDouble"}>
                <div className={"card-transparent"}>
                    <CrewPictures contestant={this.props.contestant}/>
                    <ScoreAndNames contestantData={this.props.contestantData} contestant={this.props.contestant}/>
                </div>
            </div>
        </div>
    }

    pokerHand() {
        if (this.props.team === null) return null
        return <div className={"lowerThirdsScale"}>
            <div className={this.singleCrew() ? "lowerThirdsSingle" : "lowerThirdsDouble"}>
                <div className={"card-transparent"}>
                    <PlayingCards contestantData={this.props.contestantData} contestant={this.props.contestant}/>
                    <ScoreAndNames contestantData={this.props.contestantData} contestant={this.props.contestant}/>
                </div>
            </div>
        </div>
    }

    render() {
        if (this.props.scorecard_data.task_type.includes("poker")) {
            return this.pokerHand()
        }
        return this.profileImages()
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
        return <ProfilePicture picture={aircraft.picture} text={aircraft.registration}/>
        // return <div className="aircraft-header-container">
        //     <div className="aircraft-header-img">
        //         <img alt={aircraft.registration} className="img-long" src={picture}/>
        //         <div className="rank-label-container">
        //             <span className="label label-default rank-label">{aircraft.registration}</span>
        //         </div>
        //     </div>
        // </div>
    }
}

export class TeamPicture extends Component {
    render() {
        if(this.props.team.picture){
            return <ProfilePicture picture={this.props.team.picture} text={this.props.text}/>
        }else {

            return <div>
                {<ProfilePicture picture={this.props.team.crew.member1.picture} text={this.props.team.crew.member1.first_name+' '+this.props.team.crew.member1.last_name}/>}
                {this.props.team.crew.member2?<ProfilePicture picture={this.props.team.crew.member2.picture} text={this.props.team.crew.member2.first_name+' '+this.props.team.crew.member2.last_name}/>:null}
            </div>
        }
    }
}

export class ProfilePicture extends Component {
    render() {
        return <div className="profile-header-container">
            <div className="profile-header-img">
                <img alt={this.props.text} className="img-square" src={this.props.picture?this.props.picture:question}/>
                <div className="rank-label-container">
                    <span className="label label-default rank-label">{this.props.text}</span>
                </div>
            </div>
        </div>
    }
}