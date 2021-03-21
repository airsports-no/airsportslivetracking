import {
    GET_CONTEST_RESULTS_SUCCESSFUL,
    GET_CONTEST_LIST_SUCCESSFUL,
    GET_CONTEST_TEAMS_LIST,
    GET_CONTEST_TEAMS_LIST_SUCCESSFUL,
    SHOW_TASK_DETAILS,
    HIDE_ALL_TASK_DETAILS,
    HIDE_TASK_DETAILS,
    GET_TASKS_SUCCESSFUL,
    GET_TASK_TESTS_SUCCESSFUL,
    CREATE_TASK_SUCCESSFUL,
    CREATE_TASK_TEST_SUCCESSFUL,
    DELETE_TASK_SUCCESSFUL,
    DELETE_TASK_TEST_SUCCESSFUL, PUT_TEST_RESULT_SUCCESSFUL
} from "../constants/resultsServiceActionTypes";
import {fetchContestResults, fetchContestTeams, fetchTasks} from "../actions/resultsService";

const initialState = {
    contests: [],
    tasks: {},
    taskTests: {},
    contestResults: {},
    teams: null,
    visibleTaskDetails: {},
};

function rootReducer(state = initialState, action) {
    if (action.type === GET_CONTEST_LIST_SUCCESSFUL) {
        return Object.assign({}, state, {
            ...state,
            contests: action.payload
        })
    }
    if (action.type === GET_CONTEST_RESULTS_SUCCESSFUL) {
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
    if (action.type === CREATE_TASK_SUCCESSFUL) {
        const remaining = state.tasks[action.contestId].filter((task) => {
            return task.id !== action.payload.id
        })
        return Object.assign({}, state, {
            ...state,
            tasks: {
                ...state.tasks,
                [action.contestId]: remaining.concat([action.payload])
            }
        })
    }
    if (action.type === CREATE_TASK_TEST_SUCCESSFUL) {
        const remaining = state.taskTests[action.contestId].filter((taskTest) => {
            return taskTest.id !== action.payload.id
        })
        return Object.assign({}, state, {
            ...state,
            taskTests: {
                ...state.taskTests,
                [action.contestId]: remaining.concat([action.payload])
            }
        })
    }
    if (action.type === DELETE_TASK_SUCCESSFUL) {
        return Object.assign({}, state, {
            ...state,
            tasks: {
                ...state.tasks,
                [action.contestId]: state.tasks[action.contestId].filter((task) => {
                    return task.id !== action.payload
                })
            }
        })
    }
    if (action.type === DELETE_TASK_TEST_SUCCESSFUL) {
        return Object.assign({}, state, {
            ...state,
            taskTests: {
                ...state.taskTests,
                [action.contestId]: state.taskTests[action.contestId].filter((taskTest) => {
                    return taskTest.id !== action.payload
                })
            }
        })
    }
    if (action.type === GET_TASKS_SUCCESSFUL) {
        return Object.assign({}, state, {
            ...state,
            tasks: {
                ...state.tasks,
                [action.contestId]: action.payload
            }
        })
    }
    if (action.type === GET_TASK_TESTS_SUCCESSFUL) {
        return Object.assign({}, state, {
            ...state,
            taskTests: {
                ...state.taskTests,
                [action.contestId]: action.payload
            }
        })
    }
    if (action.type === GET_CONTEST_TEAMS_LIST_SUCCESSFUL) {
        let teamsMap = state.teams ? state.teams : {}
        action.payload.map((team) => {
            teamsMap[team.id] = team
        })
        return Object.assign({}, state, {
            ...state,
            teams: teamsMap,
        })
    }
    if (action.type === SHOW_TASK_DETAILS) {
        return Object.assign({}, state, {
            ...state,
            visibleTaskDetails: {
                ...state.visibleTaskDetails,
                [action.taskId]: true
            }
        })
    }
    if (action.type === HIDE_TASK_DETAILS) {
        return Object.assign({}, state, {
            ...state,
            visibleTaskDetails: {
                ...state.visibleTaskDetails,
                [action.taskId]: false
            }
        })
    }
    if (action.type === HIDE_ALL_TASK_DETAILS) {
        return Object.assign({}, state, {
            ...state,
            visibleTaskDetails: {}
        })
    }
    if (action.type===PUT_TEST_RESULT_SUCCESSFUL){
        fetchContestResults(action.contestId)
        return state
    }
    return state;
}

export default rootReducer;