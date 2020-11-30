import {
    ADD_CONTESTANT,
    GET_CONTEST_SUCCESSFUL,
    GET_CONTESTANT_DATA_SUCCESSFUL,
    SET_DISPLAY
} from "../constants/action-types";

const initialState = {
    contestantData: {}
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
                [action.payload.contestant.id]: action.payload
            }
        }
    }
    return state;
}

export default rootReducer;