import React, {Component} from "react";
import {connect} from "react-redux";
import {contestRegistrationFormReturn, fetchContests, registerForContest} from "../actions";
import {Loading} from "./basicComponents";
import BootstrapTable from "react-bootstrap-table-next";
import 'react-bootstrap-table2-filter/dist/react-bootstrap-table2-filter.min.css';
import filterFactory, {textFilter, dateFilter} from 'react-bootstrap-table2-filter';
import Icon from "@mdi/react";
import {mdiCheck} from "@mdi/js";

const mapStateToProps = (state, props) => ({
    upcomingContests: state.contests.filter((contest) => {
        return new Date(contest.finish_time).getTime() > new Date().getTime()
    }),
    myParticipatingContests: state.myParticipatingContests,
})

class ConnectedUpcomingContestsSignupTable extends Component {
    componentDidMount() {
        this.props.fetchContests()
    }

    showRegistrationForm(contest) {
        this.props.registerForContest(contest)
    }

    render() {
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
                filter: dateFilter(),
            },
            {
                text: "Finish date",
                dataField: "contest.finish_time",
                formatter: (cell, row) => {
                    return new Date(cell).toDateString()
                },
                filter: dateFilter(),
                sort: true
            },
            {
                text: "Registered", 
                dataField: "contest", 
                formatter: (cell, row) => {
                    const matchingContest = this.props.myParticipatingContests.find((contest)=>{
                        return contest.id === cell.id
                    })
                    if(matchingContest){
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
            return {
                contest: contest
            }
        })
        const rowEvents = {
            onClick: (e, row, rowIndex) => {
                this.showRegistrationForm(row.contest)
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