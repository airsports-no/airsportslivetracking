import React, {Component} from "react";
import {connect} from "react-redux";
import {contestRegistrationFormReturn, fetchContests, registerForContest} from "../actions";
import {Loading} from "./basicComponents";
import BootstrapTable from "react-bootstrap-table-next";
import 'react-bootstrap-table2-filter/dist/react-bootstrap-table2-filter.min.css';
import filterFactory, {textFilter, dateFilter, selectFilter} from 'react-bootstrap-table2-filter';
import Icon from "@mdi/react";
import {mdiCheck} from "@mdi/js";

const mapStateToProps = (state, props) => ({
    upcomingContests: state.contests.filter((contest) => {
        return new Date(contest.finish_time).getTime() > new Date().getTime()
    }),
    myParticipatingContests: state.myParticipatingContests,
})

function add_months(dt, n) {
    return new Date(dt.setMonth(dt.getMonth() + n));
}

class ConnectedUpcomingContestsSignupTable extends Component {
    componentDidMount() {
        this.props.fetchContests()
    }

    showRegistrationForm(contest) {
        this.props.registerForContest(contest)
    }

    filteredByPeriod(filterVal, data) {
        let start = new Date()
        if (filterVal === "0") {
            start = add_months(start, 1)
        } else if (filterVal === "1") {
            start = add_months(start, 3)
        } else if (filterVal === "2") {
            start = add_months(start, 6)
        } else if (filterVal === "3") {
            start = add_months(start, 12)
        }
        if (filterVal) {
            return data.filter(cell => new Date(cell.contest.start_time) > start);
        }
        return data;
    }

    render() {
        const timePeriods = {
            0: "After a month",
            1: "After three months",
            2: "After six months",
            3: "After a year"
        }


        const columns = [
            {
                text: "",
                dataField: "contest.logo",
                formatter: (cell, row) => {
                    return <img src={cell} alt={"logo"} style={{width: "50px"}}/>
                }
            },
            {
                text: "Contest",
                dataField: "contest.name",
                filter: textFilter(),
                sort: true
            },
            {
                text: "Start date",
                dataField: "contest.start_time",
                formatter: (cell, row) => {
                    return new Date(cell).toDateString()
                },
                sort: true,
                filter: selectFilter({
                    onFilter: this.filteredByPeriod,
                    options: timePeriods
                }),
            },
            {
                text: "Registered",
                dataField: "registered",
                formatter: (cell, row) => {
                    if (cell) {
                        return <Icon path={mdiCheck} size={2} color={"green"}/>
                    }
                    return null
                }
            }
            // {
            //     text: "Country",
            //     dataField: "contest.country"
            // }
        ]
        const data = this.props.upcomingContests.map((contest) => {
            const matchingContest = this.props.myParticipatingContests.find((contestTeam) => {
                return contestTeam.contest.id === contest.id
            })
            return {
                contest: contest,
                registered: matchingContest != null
            }
        })
        const rowEvents = {
            onClick: (e, row, rowIndex) => {
                if (!row.registered) {
                    this.showRegistrationForm(row.contest)
                } else {

                }
            }
        }
        const loading = this.props.initialLoading ? <Loading/> : <div/>
        return <div>
            {loading}
            <BootstrapTable keyField={"contest.id"} data={data} columns={columns}
                            classes={"table"} filter={filterFactory()}
                            bootstrap4 striped hover condensed rowEvents={rowEvents}
                            bordered={false}//pagination={paginationFactory(paginationOptions)}
            />
        </div>
    }

}

const UpcomingContestsSignupTable = connect(mapStateToProps,
    {
        fetchContests,
        registerForContest,
    }
)(ConnectedUpcomingContestsSignupTable)
export default UpcomingContestsSignupTable