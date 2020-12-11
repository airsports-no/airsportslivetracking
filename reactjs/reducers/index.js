import {
    ADD_CONTESTANT,
    DISPLAY_ALL_TRACKS,
    DISPLAY_TRACK_FOR_CONTESTANT,
    EXCLUSIVE_DISPLAY_TRACK_FOR_CONTESTANT,
    GET_NAVIGATION_TASK_SUCCESSFUL,
    GET_CONTESTANT_DATA_SUCCESSFUL,
    HIDE_ALL_TRACKS,
    SET_DISPLAY, TOGGLE_EXPANDED_HEADER, GET_CONTESTANT_DATA_REQUEST, GET_CONTESTANT_DATA_FAILED
} from "../constants/action-types";
import {SIMPLE_RANK_DISPLAY} from "../constants/display-types";

const initialState = {
    navigationTask: {track: {waypoints: []}},
    contestantData: {},
    currentDisplay: {displayType: SIMPLE_RANK_DISPLAY},
    displayTracks: null,
    displayExpandedHeader: false,
    isFetchingContestantData: {}
};

function rootReducer(state = initialState, action) {
    if (action.type === ADD_CONTESTANT) {
        return Object.assign({}, state, {
            contestants: state.contestants.concat(action.payload)
        });
    }
    if (action.type === SET_DISPLAY) {
        return Object.assign({}, state, {
            currentDisplay: action.payload
        })
    }
    if (action.type === GET_NAVIGATION_TASK_SUCCESSFUL) {
        return Object.assign({}, state, {
            navigationTask: action.payload
        })
    }
    if (action.type === GET_CONTESTANT_DATA_REQUEST) {
        return Object.assign({}, state, {
            ...state,
            isFetchingContestantData: {
                ...state.isFetchingContestantData,
                [action.id]: true
            }
        })
    }
    if (action.type === GET_CONTESTANT_DATA_FAILED) {
        return Object.assign({}, state, {
            ...state,
            isFetchingContestantData: {
                ...state.isFetchingContestantData,
                [action.id]: false
            }
        })
    }
    if (action.type === GET_CONTESTANT_DATA_SUCCESSFUL) {
        return {
            ...state,
            contestantData: {
                ...state.contestantData,
                [action.payload.contestant_id]: action.payload
            },
            isFetchingContestantData: {
                ...state.isFetchingContestantData,
                [action.payload.contestant_id]: false
            }
        }
    }
    if (action.type === DISPLAY_TRACK_FOR_CONTESTANT) {
        let existingTracks = state.displayTrack;
        if (!existingTracks) {
            existingTracks = []
        }
        return Object.assign({}, state, {
            displayTracks: existingTracks.concat(action.payload.contestantIds)
        });
    }
    if (action.type === DISPLAY_ALL_TRACKS) {
        return Object.assign({}, state, {
            displayTracks: null
        });
    }
    if (action.type === HIDE_ALL_TRACKS) {
        return Object.assign({}, state, {
            displayTracks: []
        });
    }
    if (action.type === EXCLUSIVE_DISPLAY_TRACK_FOR_CONTESTANT) {
        return Object.assign({}, state, {
            displayTracks: [action.payload.contestantId]
        });
    }
    if (action.type === TOGGLE_EXPANDED_HEADER) {
        return Object.assign({}, state, {
            displayExpandedHeader: !state.displayExpandedHeader
        });
    }
    return state;
}

export default rootReducer;