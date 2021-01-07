import {
    DISPLAY_ALL_TRACKS,
    EXCLUSIVE_DISPLAY_TRACK_FOR_CONTESTANT,
    GET_NAVIGATION_TASK_SUCCESSFUL,
    GET_CONTESTANT_DATA_SUCCESSFUL,
    SET_DISPLAY,
    EXPAND_TRACKING_TABLE,
    SHRINK_TRACKING_TABLE,
    GET_CONTESTANT_DATA_FAILED,
    GET_CONTESTANT_DATA_REQUEST,
    INITIAL_LOADING,
    INITIAL_LOADING_COMPLETE,
    CHECK_FOR_NEW_CONTESTANTS_SUCCESSFUL,
    SHOW_LOWER_THIRDS,
    HIDE_LOWER_THIRDS,
    HIGHLIGHT_CONTESTANT,
    REMOVE_HIGHLIGHT_CONTESTANT,
    REMOVE_HIGHLIGHT_CONTESTANT_TRACK,
    HIGHLIGHT_CONTESTANT_TRACK,
    HIGHLIGHT_CONTESTANT_TABLE, REMOVE_HIGHLIGHT_CONTESTANT_TABLE
} from "../constants/action-types";

export function setDisplay(payload) {
    return {type: SET_DISPLAY, payload}
}

export function showLowerThirds(contestantId) {
    return {type: SHOW_LOWER_THIRDS, contestantId: contestantId}
}

export function hideLowerThirds() {
    return {type: HIDE_LOWER_THIRDS}
}

export function displayOnlyContestantTrack(contestantId) {
    return {type: EXCLUSIVE_DISPLAY_TRACK_FOR_CONTESTANT, payload: {contestantId: contestantId}}
}

export function displayAllTracks() {
    return {type: DISPLAY_ALL_TRACKS}
}

export function expandTrackingTable() {
    return {type: EXPAND_TRACKING_TABLE}
}

export function shrinkTrackingTable() {
    return {type: SHRINK_TRACKING_TABLE}
}

export function initialLoading(contestantId) {
    return {type: INITIAL_LOADING, contestantId: contestantId}
}

export function initialLoadingComplete(contestantId) {
    return {type: INITIAL_LOADING_COMPLETE, contestantId: contestantId}
}

export function highlightContestantTrack(contestantId){
    return {type: HIGHLIGHT_CONTESTANT_TRACK, contestantId: contestantId}
}

export function removeHighlightContestantTrack(contestantId){
    return {type: REMOVE_HIGHLIGHT_CONTESTANT_TRACK, contestantId: contestantId}
}

export function highlightContestantTable(contestantId){
    return {type: HIGHLIGHT_CONTESTANT_TABLE, contestantId: contestantId}
}

export function removeHighlightContestantTable(contestantId){
    return {type: REMOVE_HIGHLIGHT_CONTESTANT_TABLE, contestantId: contestantId}
}


export const fetchNavigationTask = (contestId, navigationTaskId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/navigationtasks/" + navigationTaskId + "/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_NAVIGATION_TASK_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}


export const dispatchContestantData = (data) => (dispatch) => {
    dispatch({type: GET_CONTESTANT_DATA_SUCCESSFUL, payload: data})
}

export const fetchContestantData = (contestId, navigationTaskId, contestantId, fromTime) => (dispatch) => {
    dispatch({type: GET_CONTESTANT_DATA_REQUEST, id: contestantId})
    let url = "/api/v1/contests/" + contestId + "/navigationtasks/" + navigationTaskId + "/contestants/" + contestantId + "/track_frontend/"
    if (fromTime !== undefined) {
        url += "?from_time=" + fromTime.toISOString()
    }
    $.ajax({
        url: url,
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTESTANT_DATA_SUCCESSFUL, payload: value}),
        error: error => dispatch({type: GET_CONTESTANT_DATA_FAILED, id: contestantId}),
        timeout: 60000
    });
}
