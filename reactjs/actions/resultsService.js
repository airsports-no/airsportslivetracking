import {
    GET_CONTEST_RESULTS_SUCCESSFUL,
    GET_CONTEST_LIST_SUCCESSFUL,
    GET_CONTEST_TEAMS_LIST_SUCCESSFUL
} from "../constants/resultsServiceActionTypes";

export const fetchContestList = () => (dispatch) => {
    $.ajax({
        url: "/api/v1/contestresults/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTEST_LIST_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}

export const fetchContestResults = (contestId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contestresults/" + contestId + "/details/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTEST_RESULTS_SUCCESSFUL, payload: value, contestId: contestId}),
        error: error => console.log(error)
    });
}

export const fetchContestTeams = (contestId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contestresults/" + contestId + "/teams/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTEST_TEAMS_LIST_SUCCESSFUL, payload: value, contestId: contestId}),
        error: error => console.log(error)
    });
}