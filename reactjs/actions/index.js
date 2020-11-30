import {
    ADD_CONTESTANT,
    GET_CONTEST_SUCCESSFUL,
    GET_CONTESTANT_DATA_SUCCESSFUL,
    SET_DISPLAY
} from "../constants/action-types";
import axios from "axios";

export function addContestant(payload) {
    return {type: ADD_CONTESTANT, payload}
}

export function setDisplay(payload) {
    return {type: SET_DISPLAY, payload}
}

export const fetchContest = (contestId) => (dispatch) => {
    $.ajax({
        url: "/display/api/contest/detail/" + contestId,
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTEST_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}


export const fetchContestantData = (contestantId, fromTime) => (dispatch) => {
    let url = "/display/api/contestant/track_data/" + contestantId
    if (fromTime !== undefined) {
        url += "?from_time=" + fromTime.toISOString()
    }
    $.ajax({
        url: url,
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTESTANT_DATA_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}
