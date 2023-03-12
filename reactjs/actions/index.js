import {
    DISPLAY_ALL_TRACKS,
    EXCLUSIVE_DISPLAY_TRACK_FOR_CONTESTANT,
    GET_NAVIGATION_TASK_SUCCESSFUL,
    GET_CONTESTANT_DATA_SUCCESSFUL,
    SET_DISPLAY,
    EXPAND_TRACKING_TABLE,
    SHRINK_TRACKING_TABLE,
    SHOW_LOWER_THIRDS,
    HIDE_LOWER_THIRDS,
    REMOVE_HIGHLIGHT_CONTESTANT_TRACK,
    HIGHLIGHT_CONTESTANT_TRACK,
    HIGHLIGHT_CONTESTANT_TABLE,
    REMOVE_HIGHLIGHT_CONTESTANT_TABLE,
    EXPLICITLY_DISPLAY_ALL_TRACKS,
    GET_CONTESTS_SUCCESSFUL,
    GLOBAL_MAP_ZOOM_FOCUS_CONTEST,
    DISPLAY_PAST_EVENTS_MODAL,
    DISPLAY_DISCLAIMER_MODAL,
    FETCH_DISCLAIMER_SUCCESSFUL,
    DISPLAY_ABOUT_MODAL,
    FETCH_MY_PARTICIPATING_CONTESTS_SUCCESSFUL,
    GET_CONTESTS,
    FETCH_MY_PARTICIPATING_CONTESTS,
    TOGGLE_OPEN_AIP,
    GET_ONGOING_NAVIGATION_SUCCESSFUL,
    TOGGLE_SECRET_GATES,
    TOGGLE_BACKGROUND_MAP,
    FETCH_EDITABLE_ROUTE_SUCCESSFUL,
    FETCH_EDITABLE_ROUTE,
    FETCH_INITIAL_TRACKS,
    FETCH_INITIAL_TRACKS_SUCCESS,
    TOGGLE_PROFILE_PICTURES,
    TOGGLE_GATE_ARROW,
    TOGGLE_DANGER_LEVEL,
    GET_NAVIGATION_TASK_FAILED,
    FETCH_INITIAL_TRACKS_FAILED,
    CURRENT_TIME, NEW_CONTESTANT, DELETE_CONTESTANT
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

export function highlightContestantTrack(contestantId) {
    return {type: HIGHLIGHT_CONTESTANT_TRACK, contestantId: contestantId}
}

export function removeHighlightContestantTrack(contestantId) {
    return {type: REMOVE_HIGHLIGHT_CONTESTANT_TRACK, contestantId: contestantId}
}

export function highlightContestantTable(contestantId) {
    return {type: HIGHLIGHT_CONTESTANT_TABLE, contestantId: contestantId}
}

export function removeHighlightContestantTable(contestantId) {
    return {type: REMOVE_HIGHLIGHT_CONTESTANT_TABLE, contestantId: contestantId}
}

export function toggleExplicitlyDisplayAllTracks() {
    return {type: EXPLICITLY_DISPLAY_ALL_TRACKS}
}

export function toggleGateArrow() {
    return {type: TOGGLE_GATE_ARROW}
}

export function toggleDangerLevel() {
    return {type: TOGGLE_DANGER_LEVEL}
}

export const toggleDisplayOpenAip = () => (dispatch) => {
    dispatch({type: TOGGLE_OPEN_AIP})
}

export const fetchNavigationTask = (contestId, navigationTaskId, contestantIds) => (dispatch) => {
    let url = "/api/v1/contests/" + contestId + "/navigationtasks/" + navigationTaskId + "/"
    if (contestantIds.length > 0) {
        url += "?contestantIds=" + contestantIds.join(",")
    }
    $.ajax({
        url: url,
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_NAVIGATION_TASK_SUCCESSFUL, payload: value}),
        error: error => dispatch({
            type: GET_NAVIGATION_TASK_FAILED,
            payload: error,
            contestId: contestId,
            navigationTaskId: navigationTaskId
        }),
    });
}

export const fetchDisclaimer = () => (dispatch) => {
    $.ajax({
        url: "/terms_and_conditions/",
        datatype: 'html',
        cache: false,
        success: value => dispatch({type: FETCH_DISCLAIMER_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}


export const dispatchContestantData = (data) => (dispatch) => {
    dispatch({type: GET_CONTESTANT_DATA_SUCCESSFUL, payload: data})
}

export const dispatchCurrentTime = (data) => (dispatch) => {
    dispatch({type: CURRENT_TIME, payload: data})
}
export const dispatchNewContestant = (data) => (dispatch) => {
    dispatch({type: NEW_CONTESTANT, payload: data})
}

export const dispatchDeleteContestant = (data) => (dispatch) => {
    dispatch({type: DELETE_CONTESTANT, payload: data})
}

// Global map
export const zoomFocusContest = (data) => (dispatch) => {
    dispatch({type: GLOBAL_MAP_ZOOM_FOCUS_CONTEST, payload: data})
}

export const displayPastEventsModal = () => (dispatch) => {
    dispatch({type: DISPLAY_PAST_EVENTS_MODAL, payload: true})
}

export const hidePastEventsModal = () => (dispatch) => {
    dispatch({type: DISPLAY_PAST_EVENTS_MODAL, payload: false})
}


export const displayDisclaimerModal = () => (dispatch) => {
    dispatch({type: DISPLAY_DISCLAIMER_MODAL, payload: true})
}

export const hideDisclaimerModal = () => (dispatch) => {
    dispatch({type: DISPLAY_DISCLAIMER_MODAL, payload: false})
}


export const displayAboutModal = () => (dispatch) => {
    dispatch({type: DISPLAY_ABOUT_MODAL, payload: true})
}

export const hideAboutModal = () => (dispatch) => {
    dispatch({type: DISPLAY_ABOUT_MODAL, payload: false})
}


export const toggleSecretGates = (visible) => (dispatch) => {
    dispatch({type: TOGGLE_SECRET_GATES, visible: visible})
}


export const toggleBackgroundMap = (visible) => (dispatch) => {
    dispatch({type: TOGGLE_BACKGROUND_MAP, visible: visible})
}
export const toggleProfilePictures = (visible) => (dispatch) => {
    dispatch({type: TOGGLE_PROFILE_PICTURES, visible: visible})
}

export const fetchContests = () => (dispatch) => {
    dispatch({type: GET_CONTESTS})
    $.ajax({
        url: "/api/v1/contests/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTESTS_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}


export const fetchContestsWithResults = () => (dispatch) => {
    dispatch({type: GET_CONTESTS})
    $.ajax({
        url: "/api/v1/contests/results/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTESTS_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}


export const fetchEditableRoute = (routeId) => (dispatch) => {
    dispatch({type: FETCH_EDITABLE_ROUTE})
    $.ajax({
        url: "/api/v1/editableroutes/" + routeId + "/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: FETCH_EDITABLE_ROUTE_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}

export const fetchOngoingNavigation = () => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/ongoing_navigation/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_ONGOING_NAVIGATION_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}

export const fetchMyParticipatingContests = () => (dispatch) => {
    dispatch({type: FETCH_MY_PARTICIPATING_CONTESTS})
    $.ajax({
        url: "/api/v1/userprofile/my_participating_contests/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: FETCH_MY_PARTICIPATING_CONTESTS_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}

export const fetchInitialTracks = (contestId, navigationTaskId, contestantId) => (dispatch) => {
    dispatch({type: FETCH_INITIAL_TRACKS})
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/navigationtasks/" + navigationTaskId + "/contestants/" + contestantId + "/initial_track_data/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: FETCH_INITIAL_TRACKS_SUCCESS, payload: value, contestantId: contestantId}),
        error: error => dispatch({type: FETCH_INITIAL_TRACKS_FAILED, payload: error, contestantId: contestantId})
    });
}
