import {
    ADD_CONTESTANT,
    DISPLAY_ALL_TRACKS,
    DISPLAY_TRACK_FOR_CONTESTANT,
    EXCLUSIVE_DISPLAY_TRACK_FOR_CONTESTANT,
    GET_CONTEST_SUCCESSFUL,
    GET_CONTESTANT_DATA_SUCCESSFUL,
    HIDE_ALL_TRACKS,
    SET_DISPLAY, TOGGLE_EXPANDED_HEADER
} from "../constants/action-types";
import {SIMPLE_RANK_DISPLAY} from "../constants/display-types";

const initialState = {
    contest: {track: {waypoints: []}},
    contestantData: {},
    currentDisplay: {displayType: SIMPLE_RANK_DISPLAY},
    displayTracks: null,
    displayExpandedHeader: false
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
    if (action.type === GET_CONTEST_SUCCESSFUL) {
        return Object.assign({}, state, {
            contest: action.payload
        })
    }
    if (action.type === GET_CONTESTANT_DATA_SUCCESSFUL) {
        return {
            ...state,
            contestantData: {
                ...state.contestantData,
                [action.payload.contestant_id]: action.payload
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