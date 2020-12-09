import {
    DISPLAY_ALL_TRACKS, EXCLUSIVE_DISPLAY_TRACK_FOR_CONTESTANT,
    GET_NAVIGATION_TASK_SUCCESSFUL,
    GET_CONTESTANT_DATA_SUCCESSFUL,
    SET_DISPLAY, TOGGLE_EXPANDED_HEADER
} from "../constants/action-types";

export function setDisplay(payload) {
    return {type: SET_DISPLAY, payload}
}

export function displayOnlyContestantTrack(contestantId) {
    return {type: EXCLUSIVE_DISPLAY_TRACK_FOR_CONTESTANT, payload: {contestantId: contestantId}}
}

export function displayAllTracks() {
    return {type: DISPLAY_ALL_TRACKS}
}

export function toggleExpandedHeader(){
    return {type: TOGGLE_EXPANDED_HEADER}
}


export const fetchNavigationTask = (navigationTaskId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/navigationtasks/" + navigationTaskId,
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_NAVIGATION_TASK_SUCCESSFUL, payload: value}),
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
