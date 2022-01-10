import React, {Component} from "react";
import {connect} from "react-redux";
import EllipsisWithTooltip from 'react-ellipsis-with-tooltip'
import Hand from "../react-playing-cards-local/src/PlayingCard/Hand/Hand";
import {teamLongForm} from "../utilities";
import {setDisplay, toggleDangerLevel, toggleGateArrow} from "../actions";
import {CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY} from "../constants/display-types";
import GateScoreArrow from "./gateScoreArrow/gateScoreArrow";
import DangerLevel from "./danger_thermometer/dangerLevel";
import Icon from "@mdi/react";
import {mdiThermometer} from "@mdi/js";


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
    return <img className={"lowerThirdsProfileImage"} src={crew.member1.picture}/>
}

function memberTwoPicture(crew) {
    return crew.member2 ? <img className={"lowerThirdsProfileImage"} src={crew.member2.picture}/> : null
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
    displayProfilePictures: state.displayProfilePictures,
    currentDisplay: state.currentDisplay,
    displayDangerLevel: state.displayDangerLevel
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
        <div className={"row"} style={{marginLeft: "0px"}}>
            <div className={"col-4"}>
                <div className={"row"}>
                    <div className={"text-center col-12"}>
                        <div className={"lower-thirds-current-score clickable"}>
                            <a href={"#"}
                               onClick={props.toggleDetails}>{props.contestantData.contestant_track.score.toFixed(0)}</a>
                        </div>
                    </div>
                </div>
                <div className={"row"}>
                    <div className={"text-center col-12"}>
                        <div className={"lower-thirds-current-score-text clickable"}>
                            <a href={"#"} onClick={props.toggleDetails}>DETAILED SCORE</a>
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
    const cards = props.contestantData.playing_cards.map((card) => {
        return card.card.toLowerCase()
    })
    return <Hand hide={false} layout={"fan"} cards={cards} cardSize={250}/>
}

class ConnectedLowerThirdTeam extends Component {
    constructor(props) {
        super(props);
        this.toggleRankDetailsDisplay = this.toggleRankDetailsDisplay.bind(this)
    }

    toggleRankDetailsDisplay() {
        console.log("Toggle")
        if (this.props.currentDisplay.displayType !== SIMPLE_RANK_DISPLAY) {
            this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
        } else if (this.props.currentDisplay.displayType !== CONTESTANT_DETAILS_DISPLAY) {
            this.props.setDisplay({displayType: CONTESTANT_DETAILS_DISPLAY, contestantId: this.props.contestantId})
        }
    }

    singleCrew() {
        return this.props.contestant.team.crew.member2 == null
    }

    profileImages() {
        if (this.props.team === null) return null
        return <div className={"lowerThirdsScale"}>
            <div className={this.singleCrew() ? "lowerThirdsSingle" : "lowerThirdsDouble"}>
                <div className={"d-flex align-items-end justify-content-end"}>
                    <div className={"p-2 gate-arrow-placeholder"} style={{marginBottom: "2px"}}>
                        <GateScoreArrow contestantId={this.props.contestant.id}
                                        width={400}
                                        height={150} arrowData={{
                            waypoint_name: "SP",
                            seconds_to_planned_crossing: 7,
                            estimated_crossing_offset: 5,
                            estimated_score: 9,
                            final: false,
                            missed: false
                        }}/>
                    </div>
                    <div className={"p-2 clickable"} style={{width: "30px"}}>
                        <img src={"/static/img/expand_arrow.gif"} onClick={() => this.props.toggleGateArrow()}/>
                    </div>
                    <div
                        className={(this.singleCrew() ? "lower-thirds-inner-single" : "lower-thirds-inner-double") + " card-transparent p-2"}
                        style={{paddingLeft: "0px!important"}}>
                        {this.props.displayProfilePictures ? <CrewPictures contestant={this.props.contestant}/> : null}
                        <ScoreAndNames contestantData={this.props.contestantData} contestant={this.props.contestant}
                                       toggleDetails={this.toggleRankDetailsDisplay}/>
                    </div>
                    <div className={"clickable danger-level-toggle"}>
                        <Icon path={mdiThermometer} size={1.5} color={"white"}
                              onClick={() => this.props.toggleDangerLevel()}/>
                    </div>
                    {this.props.displayDangerLevel ?
                        <DangerLevel contestantId={this.props.contestant.id}/> : null}
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

export const LowerThirdTeam = connect(mapStateToProps, {
    setDisplay,
    toggleGateArrow,
    toggleDangerLevel
})(ConnectedLowerThirdTeam)

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
        if (this.props.team.picture) {
            return <ProfilePicture picture={this.props.team.picture} text={this.props.text}/>
        } else {

            return <div>
                {<ProfilePicture picture={this.props.team.crew.member1.picture}
                                 text={this.props.team.crew.member1.first_name + ' ' + this.props.team.crew.member1.last_name}/>}
                {this.props.team.crew.member2 ? <ProfilePicture picture={this.props.team.crew.member2.picture}
                                                                text={this.props.team.crew.member2.first_name + ' ' + this.props.team.crew.member2.last_name}/> : null}
            </div>
        }
    }
}

export class ProfilePicture extends Component {
    render() {
        return <div className="profile-header-container">
            <div className="profile-header-img">
                <img alt={this.props.text} className="img-fluid profile-header-img"
                     src={this.props.picture ? this.props.picture : question}/>
                <div className="rank-label-container">
                    <span className="label label-default rank-label">{this.props.text}</span>
                </div>
            </div>
        </div>
    }
}