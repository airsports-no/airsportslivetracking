import React, {Component} from "react";
import {connect} from "react-redux";


export const mapStateToProps = (state, props) => ({
})
export const mapDispatchToProps = {}


class ConnectedContestItem extends Component {
    handleClick() {
        if (this.props.onClick) {
            this.props.onClick(this.props.contest)
        }
    }

    render() {
        return <span className={"second-in-between"}>
                <div
                    className={"list-group-item list-group-item-secondary list-group-item-action"}
                    onClick={() => this.handleClick()}
                >
                    <img className={"img-fluid"}
                         src={this.props.contest.logo && this.props.contest.logo.length > 0 ? this.props.contest.logo : "/static/img/airsportslogo.png"}
                         alt={"Event logo"}
                         style={{width: "100%", maxHeight: "60px", maxWidth: "60px", float: "left"}}/>

                         <span className={"d-flex justify-content-between align-items-centre"}
                               style={{paddingLeft: "10px"}}>
                             <span>
                                 <b>{this.props.contest.name}</b>
                                 <br/>
                                 {new Date(this.props.contest.start_time).toLocaleDateString()} -
                                 {new Date(this.props.contest.finish_time).toLocaleDateString()}
                             </span>
                             <img src={this.props.contest.country_flag_url} style={{height: "15px"}}
                                  alt={this.props.contest.country}/>
                    </span>
                </div>
    </span>
    }
}


const ContestItem = connect(mapStateToProps, mapDispatchToProps)(ConnectedContestItem);
export default ContestItem;