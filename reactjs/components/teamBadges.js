import React, {Component} from "react";

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

// export class LowerThirdTeam extends Component{
//     render(){
//         if (!this.props.team) return null
//         return <div className={"lowerThirds"}>
//             <div className={"card"}>
//                 <div className={"row"}>
//                     <div className={"col-2"}/>
//                         <img className={"col-5"} src={this.props.team.crew.pilot}/>
//
//                 <div className={"card-body"}>
//                     <div className={"card-title row"}>
//                         <div className={"col-1"}>
//                             <img src={this.props.team.picture}/>
//                         </div>
//                         <div className={co}
//                     </div>
//                 </div>
//             </div>
//         </div>
//
// }

export class TeamMembers extends Component{
    render(){
        return <div>
            Pilot: {this.props.crew.pilot}<br/>
            {this.props.crew.navigator?"Navigator: " + this.props.crew.navigator:null}
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