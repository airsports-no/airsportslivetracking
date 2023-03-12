import React, {Component} from "react";
import {connect} from "react-redux";
import {teamLongForm, teamRankingTable} from "../../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import "bootstrap/dist/css/bootstrap.min.css"
import {Redirect, Link} from "react-router-dom";
import {fetchContestsWithResults} from "../../actions";
import {Loading} from "../basicComponents";
import Navbar from "../navbar";

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
                dataField: "name",
                text: "Contest",
                formatter: (cell, row) => {
                    return <Link className="results-table" to={row.contestId + "/taskresults/"}>{cell}</Link>
                }
            },
            {
                dataField: "first",
                text: "Champions",
                formatter: (cell, row) => {
                    return cell ? <div className={"align-middle crew-name"}>{teamRankingTable(cell)}</div> : null
                }

            }
        ]
        const rowEvents = {
            onClick: (e, row, rowIndex) => {
                return <Redirect push to={row.contestId + "/taskresults/"}/>
            }
        }

        return <div>
            <Navbar/>
            <div className={'results-table container-xl'}>
                <div className={''}><h1 className={"results-table-contest-name"}>CONTEST RESULTS</h1></div>
                <div className={''}>
                    <div className={""}>
                        <BootstrapTable keyField={"contestId"} columns={columns} data={this.buildData()}
                                        classes={"table-dark bg-dark-transparent"}
                                        wrapperClasses={"text-dark"}
                                        bootstrap4 striped condensed
                                        rowEvents={rowEvents}/>
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