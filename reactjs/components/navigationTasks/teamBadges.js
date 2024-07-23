import React, {Component} from "react";
import {connect} from "react-redux";
import Hand from "../../react-playing-cards-local/src/PlayingCard/Hand/Hand";
import {setDisplay, toggleDangerLevel, toggleGateArrow} from "../../actions";
import {CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY} from "../../constants/display-types";
import GateScoreArrow from "../gateScoreArrow/gateScoreArrow";
import DangerLevel from "./danger_thermometer/dangerLevel";
import Icon from "@mdi/react";
import {mdiThermometer} from "@mdi/js";


function memberOnePicture(crew) {
    return <img className={"lowerThirdsProfileImage"} src={crew.member1.picture}/>
}

function memberTwoPicture(crew) {
    return crew.member2 ? <img className={"lowerThirdsProfileImage"} src={crew.member2.picture}/> : null
}

function memberName(member) {
    return <h4 className={"lower-thirds-pilot-names"}>
        {member.last_name ? member.last_name.toUpperCase() : ""}<br/>
        {member.first_name ? member.first_name : ""}
    </h4>
}

function clubDisplay(club) {
    if (club === null) {
        return null
    }
    const image = <img src={document.configuration.STATIC_FILE_LOCATION+"flags/3x2/" + club.country + ".svg"} className={"personalFlag img-fluid"}
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
            <div className={"col-3"}/>
            <div className={"col-4 inheritDisplay"}>
                {memberOnePicture(props.contestant.team.crew)}
            </div>
            <div className={"col-4 inheritDisplay"}>
                {memberTwoPicture(props.contestant.team.crew)}
            </div>
            <div className={"col-1"}/>
        </div>
    } else {
        return <div className={"row"}>
            <div className={"col-4"}/>
            <div className={"col-7 inheritDisplay"}>
                {memberOnePicture(props.contestant.team.crew)}
            </div>
            <div className={"col-1"}/>
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
            <div className={props.contestant.team.crew.member2 != null ? "col-3" : "col-4"}>
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
            <div className={props.contestant.team.crew.member2 != null ? "col-8" : "col-7"}>
                <CrewNames contestant={props.contestant}/>
                <div className={"row"}>
                    <div className={"col-12 text-center"}>
                        <h4>{clubDisplay(props.contestant.team.club)}</h4>
                    </div>
                </div>
            </div>
            <div className={"col-1"}>
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
        const score = 10 * (Math.random() - 0.5)
        this.last = 0
        this.state = {
            score: score,
            crossing: -100
        }
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
                                        height={150}
                                        arrowData={{
                                            waypoint_name: "START",
                                            seconds_to_planned_crossing: 7,
                                            estimated_crossing_offset: this.state.crossing,
                                            estimated_score: this.state.score,
                                            final: false,
                                            missed: false
                                        }}
                        />
                    </div>
                    <div className={"p-2 clickable click-time-arrow"}>
                        <div className={"time-text"} onClick={() => this.props.toggleGateArrow()}>TIME</div>
                        <img src={document.configuration.STATIC_FILE_LOCATION+"img/expand_arrow.gif"} onClick={() => this.props.toggleGateArrow()}/>
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
                    <div className={"danger-level-gauge"}>
                        {this.props.displayDangerLevel ?
                            <DangerLevel contestantId={this.props.contestant.id}
                                         dangerData={{
                                             accumulated_score: 8,
                                             danger_level: 100
                                         }}/> : null}
                    </div>
                </div>
            </div>
        </div>
    }

    pokerHand() {
        if (this.props.team === null) return null
        return <div className={"lowerThirdsScale"}>
            <div className={this.singleCrew() ? "lowerThirdsSingle" : "lowerThirdsDouble"}>
                <div className={"d-flex align-items-end justify-content-end"}>
                    <div className={"p-2 gate-arrow-placeholder"} style={{marginBottom: "2px"}}>
                    </div>
                    <div
                        className={(this.singleCrew() ? "lower-thirds-inner-single" : "lower-thirds-inner-double") + " card-transparent p-2"}
                        style={{paddingLeft: "0px!important"}}>
                        <PlayingCards contestantData={this.props.contestantData} contestant={this.props.contestant}/>
                        <ScoreAndNames contestantData={this.props.contestantData} contestant={this.props.contestant}
                                       toggleDetails={this.toggleRankDetailsDisplay}/>
                    </div>
                </div>
            </div>
        </div>
    }

    render() {
        if (this.props.scorecard.task_type.includes("poker")) {
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

