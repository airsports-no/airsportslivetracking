import React, {Component} from "react";
import {connect} from "react-redux";
import {teamLongForm, teamRankingTable} from "../../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import "bootstrap/dist/css/bootstrap.min.css"
import {Redirect, Link} from "react-router-dom";
import {fetchContests} from "../../actions";

const mapStateToProps = (state, props) => ({
    contests: state.contests
})

class ConnectedContestSummaryResultsTable extends Component {
    constructor(props) {
        super(props)
        this.props.fetchContests()
    }

    componentWillUnmount() {
        document.body.classList.remove("results-table-background")
    }

    componentDidMount() {
        document.body.classList.add("results-table-background")
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
                    return cell ? <div className={"align-middle crew-name"}>{teamRankingTable(cell)}</div> : null
                    // return <TeamBadge team={cell}/>
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
                                    classes={"table-dark bg-dark-transparent"}
                                    wrapperClasses={"text-dark"}
                                    bootstrap4 striped condensed
                                    rowEvents={rowEvents}/>
                </div>
            </div>
            <div className={'text-muted'}>Photo by <a
                href="https://unsplash.com/@tadeu?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Tadeu
                Jnr</a> on <a
                href="https://unsplash.com/s/photos/propeller-airplane?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
            </div>
        </div>
    }
}

const
    ContestSummaryResultsTable = connect(mapStateToProps, {
        fetchContests,
    })(ConnectedContestSummaryResultsTable);
export default ContestSummaryResultsTable;