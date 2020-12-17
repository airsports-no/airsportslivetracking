import {
    GET_CONTEST_RESULTS_SUCCESSFUL,
    GET_CONTEST_LIST_SUCCESSFUL, GET_CONTEST_TEAMS_LIST,
    GET_CONTEST_TEAMS_LIST_SUCCESSFUL
} from "../constants/resultsServiceActionTypes";
import {fetchContestTeams} from "../actions/resultsService";

const initialState = {
    contests: [],
    contestResults: {},
    teams: {}
};

function rootReducer(state = initialState, action) {
    if (action.type === GET_CONTEST_LIST_SUCCESSFUL) {
        return Object.assign({}, state, {
            ...state,
            contests: action.payload
        })
    }
    if (action.type === GET_CONTEST_RESULTS_SUCCESSFUL) {
        fetchContestTeams(action.contestId)
        return Object.assign({}, state, {
            ...state,
            contestResults: {
                ...state.contestResults,
                [action.contestId]: {
                    ...state.contestResults[action.contestId],
                    results: action.payload
                }
            }
        })
    }
    if (action.type === GET_CONTEST_TEAMS_LIST_SUCCESSFUL) {
        let teamsMap = {}
        action.payload.map((team) => {
            teamsMap[team.id] = team
        })
        return Object.assign({}, state, {
            ...state,
            teams: Object.assign(state.teams, teamsMap),
            contestResults: {
                ...state.contestResults,
                [action.contestId]: {
                    ...state.contestResults[action.contestId],
                    teams: Object.keys(teamsMap)
                }
            }
        })
    }
    return state;
}

export default rootReducer;