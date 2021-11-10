import {
    DISPLAY_ALL_TRACKS,
    EXCLUSIVE_DISPLAY_TRACK_FOR_CONTESTANT,
    GET_NAVIGATION_TASK_SUCCESSFUL,
    GET_CONTESTANT_DATA_SUCCESSFUL,
    SET_DISPLAY,
    EXPAND_TRACKING_TABLE,
    SHRINK_TRACKING_TABLE,
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
    HIGHLIGHT_CONTESTANT_TABLE,
    REMOVE_HIGHLIGHT_CONTESTANT_TABLE,
    FULL_HEIGHT_TABLE,
    HALF_HEIGHT_TABLE,
    EXPLICITLY_DISPLAY_ALL_TRACKS,
    TRACCAR_DATA_RECEIVED,
    GET_CONTESTS_SUCCESSFUL,
    GET_CONTEST_NAVIGATION_TASKS_SUCCESSFUL,
    GLOBAL_MAP_ZOOM_FOCUS_CONTEST,
    DISPLAY_PAST_EVENTS_MODAL,
    DISPLAY_DISCLAIMER_MODAL,
    FETCH_DISCLAIMER_SUCCESSFUL,
    DISPLAY_ABOUT_MODAL,
    FETCH_MY_PARTICIPATING_CONTESTS_SUCCESSFUL,
    REGISTER_FOR_CONTEST,
    UPDATE_CONTEST_REGISTRATION,
    CANCEL_CONTEST_REGISTRATION,
    GET_CONTESTS,
    FETCH_MY_PARTICIPATING_CONTESTS,
    SELF_REGISTER_TASK,
    TOGGLE_OPEN_AIP,
    GET_ONGOING_NAVIGATION_SUCCESSFUL,
    TOGGLE_SECRET_GATES,
    TOGGLE_BACKGROUND_MAP,
    FETCH_EDITABLE_ROUTE_SUCCESSFUL,
    FETCH_EDITABLE_ROUTE, FETCH_INITIAL_TRACKS, FETCH_INITIAL_TRACKS_SUCCESS, TOGGLE_PROFILE_PICTURES
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

export function fullHeightTable() {
    return {type: FULL_HEIGHT_TABLE}
}

export function halfHeightTable() {
    return {type: HALF_HEIGHT_TABLE}
}

export function initialLoading(contestantId) {
    return {type: INITIAL_LOADING, contestantId: contestantId}
}

export function initialLoadingComplete(contestantId) {
    return {type: INITIAL_LOADING_COMPLETE, contestantId: contestantId}
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


export const fetchNavigationTask = (contestId, navigationTaskId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/navigationtasks/" + navigationTaskId + "/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_NAVIGATION_TASK_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
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


// Global map
export const dispatchTraccarData = (data) => (dispatch) => {
    dispatch({type: TRACCAR_DATA_RECEIVED, payload: data})
}

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

export const toggleDisplayOpenAip = () => (dispatch) => {
    dispatch({type: TOGGLE_OPEN_AIP})
}

export const fetchInitialTracks = (contestId, navigationTaskId, contestantId) => (dispatch) => {
    dispatch({type: FETCH_INITIAL_TRACKS})
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/navigationtasks/" + navigationTaskId + "/contestants/" + contestantId + "/initial_track_data/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: FETCH_INITIAL_TRACKS_SUCCESS, payload: value, contestantId: contestantId}),
        error: error => console.log(error)
    });
}
