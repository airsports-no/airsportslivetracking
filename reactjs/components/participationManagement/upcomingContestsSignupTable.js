import React, {Component} from "react";
import {connect} from "react-redux";
import {fetchMoreContests} from "../../actions";
import {Loading} from "../basicComponents";
import Icon from "@mdi/react";
import {mdiCheck} from "@mdi/js";
import {ASTable} from "../filteredSearchableTable";
import {withParams} from "../../utilities";

const mapStateToProps = (state, props) => ({
    upcomingContests: state.contests.filter((contest) => {
        return new Date(contest.finish_time).getTime() > new Date().getTime()
    }),
    myParticipatingContests: state.myParticipatingContests,
    loadingContests: state.loadingContests
})

class ConnectedUpcomingContestsSignupTable extends Component {
    componentDidMount() {
        this.props.fetchMoreContests()
    }

    showRegistrationForm(contest) {
        this.props.navigate("/participation/" + contest.id + "/register/")
    }

    render() {
        const columns = [
            {
                Header: "",
                id: "Logo",
                accessor: (row, index) => {
                    return <img src={row.contest.logo} alt={"logo"} style={{width: "50px"}}/>
                },
                disableSortBy: true,
                disableFilters: true
            },
            {
                Header: "Contest",
                accessor: "contest.name",
                disableSortBy: true,
                filter: 'fuzzyText',
            },
            {
                Header: "Start date",
                accessor: (row, index) => {
                    return new Date(row.contest.start_time).toDateString()
                },
                disableFilters: true
            },
            {
                Header: "Registered",
                accessor: (row, index) => {
                    if (row.registered) {
                        return <Icon path={mdiCheck} size={2} color={"green"}/>
                    }
                    return null
                },
                disableFilters: true,
                disableSortBy: true,
            }
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
            onClick: (row) => {
                if (!row.registered) {
                    this.showRegistrationForm(row.contest)
                } else {

                }
            }
        }
        const loading = this.props.loadingContests ? <Loading/> : null

        return <div>
            {loading}
            <ASTable data={data} columns={columns} rowEvents={rowEvents} initialState={{
                sortBy: [
                    {id: "Start date", desc: true}
                ]
            }}
 className={"table table-striped table-hover table-condensed"}
            />
        </div>
    }

}

const UpcomingContestsSignupTable = connect(mapStateToProps,
    {
        fetchMoreContests,
    }
)(ConnectedUpcomingContestsSignupTable)
export default withParams(UpcomingContestsSignupTable)