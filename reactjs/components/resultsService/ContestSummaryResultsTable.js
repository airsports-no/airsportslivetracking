import React, {Component} from "react";
import {connect} from "react-redux";
import {teamLongForm, teamRankingTable} from "../../utilities";
import "bootstrap/dist/css/bootstrap.min.css"
import {Redirect, Link} from "react-router-dom";
import {fetchContestsWithResults} from "../../actions";
import {Loading} from "../basicComponents";
import Navbar from "../navbar";
import {ResultsServiceTable} from "./resultsServiceTable";

const mapStateToProps = (state, props) => ({
    contests: state.contests
})

class ConnectedContestSummaryResultsTable extends Component {
    constructor(props) {
        super(props)
        this.props.fetchContestsWithResults()
    }

    componentWillUnmount() {
        document.body.classList.remove("results-table-background")
    }

    componentDidMount() {
        document.body.classList.add("results-table-background")
    }

    buildData() {
        return this.props.contests.map((contest) => {
            contest.contestsummary_set.sort((a, b) => {
                if (a.points < b.points) return contest.summary_score_sorting_direction === "asc" ? -1 : 1;
                if (a.points > b.points) return contest.summary_score_sorting_direction === "asc" ? 1 : -1;
                return 0;
            })
            return {
                name: contest.name,
                contestId: contest.id,
                first: contest.contestsummary_set.length > 0 ? contest.contestsummary_set[0].team : null
            }
        })
    }

    render() {
        if (!this.props.contests || this.props.contests.length === 0) {
            return <div>
                <Navbar/>
                <div className={"container-xl"}>
                    <div className={'row'}><h1>CONTEST RESULTS</h1></div>
                    <div className={'row'}><Loading/></div>
                </div>
            </div>
        }
        const columns = [
            {
                accessor: (row, index) => {
                    return <Link className="results-table" to={row.contestId + "/taskresults/"}>{row.name}</Link>
                },
                Header: "Contest",
            },
            {
                Header: "Champions",
                accessor: (row, index) => {
                    return row.first ?
                        <div className={"align-middle crew-name"}>{teamRankingTable(row.first)}</div> : null
                }

            }
        ]
        return <div>
            <Navbar/>
            <div className={'results-table container-xl'}>
                <div className={''}><h1 className={"results-table-contest-name"}>CONTEST RESULTS</h1></div>
                <div className={''}>
                    <div className={""}>
                        <ResultsServiceTable columns={columns} data={this.buildData()}
                                             className={"table table-dark bg-dark-transparent table-striped table-condensed table-bordered"}/>
                    </div>
                </div>
                <div className={'text-dark'}>Photo by <a
                    href="https://unsplash.com/@tadeu?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Tadeu
                    Jnr</a> on <a
                    href="https://unsplash.com/s/photos/propeller-airplane?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
                </div>
            </div>
        </div>
    }
}

const
    ContestSummaryResultsTable = connect(mapStateToProps, {
        fetchContestsWithResults,
    })(ConnectedContestSummaryResultsTable);
export default ContestSummaryResultsTable;