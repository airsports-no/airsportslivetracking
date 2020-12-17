import React, {Component} from "react";
import {connect} from "react-redux";
import {fetchContestList} from "../../actions/resultsService";
import {teamLongForm} from "../../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import paginationFactory from 'react-bootstrap-table2-paginator';
import "bootstrap/dist/css/bootstrap.min.css"
import {ProgressCircle} from "../contestantProgress";
import {AircraftBadge, ProfileBadge, TeamBadge} from "../teamBadges";
import {Redirect, Link} from "react-router-dom";

const mapStateToProps = (state, props) => ({
    contests: state.contests
})

class ConnectedContestSummaryResultsTable extends Component {
    constructor(props) {
        super(props)
        this.props.fetchContestList()
    }

    buildData() {
        return this.props.contests.map((contest) => {
            const orderedResults = contest.contestsummary_set.sort((a, b) => {
                if (a.points < b.points) return contest.summary_score_sorting_direction === "asc" ? -1 : 1;
                if (a.points > b.points) return contest.summary_score_sorting_direction === "asc" ? 1 : -1;
                return 0;
            })
            return {
                name: contest.name,
                contestId: contest.id,
                first: orderedResults.length > 0 ? orderedResults[0].team : null
            }
        })
    }

    render() {
        const columns = [
            {
                dataField: "name",
                text: "Contest",
                formatter: (cell, row) => {
                    return <Link to={row.contestId + "/taskresults/"}>{cell}</Link>
                }
            },
            {
                dataField: "first",
                text: "Champion",
                formatter: (cell, row) => {
                    return <TeamBadge team={cell}/>
                }

            }
        ]
        const rowEvents = {
            onClick: (e, row, rowIndex) => {
                return <Redirect push to={row.contestId + "/taskresults/"}/>
            }
        }

        return <div className={'row fill'}>
            <div className={'row'}><h1>Contest results service</h1></div>
            <div className={'row fill'}>
                <div className={"col-12"}>
                    <BootstrapTable keyField={"contestId"} columns={columns} data={this.buildData()}
                                    rowEvents={rowEvents}/>
                </div>
            </div>
        </div>
    }
}

const
    ContestSummaryResultsTable = connect(mapStateToProps, {
        fetchContestList,
    })(ConnectedContestSummaryResultsTable);
export default ContestSummaryResultsTable;