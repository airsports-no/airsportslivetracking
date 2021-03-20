import {
    GET_CONTEST_RESULTS_SUCCESSFUL,
    GET_CONTEST_LIST_SUCCESSFUL,
    GET_CONTEST_TEAMS_LIST_SUCCESSFUL,
    SHOW_TASK_DETAILS,
    HIDE_ALL_TASK_DETAILS,
    SHOW_ALL_TASK_DETAILS,
    HIDE_TASK_DETAILS,
    GET_TASKS_SUCCESSFUL,
    GET_TASK_TESTS_SUCCESSFUL,
    CREATE_TASK_SUCCESSFUL,
    CREATE_TASK_TEST_SUCCESSFUL, DELETE_TASK_SUCCESSFUL, DELETE_TASK_TEST_SUCCESSFUL
} from "../constants/resultsServiceActionTypes";

export const fetchContestList = () => (dispatch) => {
    $.ajax({
        url: "/api/v1/contestresults/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTEST_LIST_SUCCESSFUL, payload: value}),
        error: error => console.log(error)
    });
}

export const fetchContestResults = (contestId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contestresults/" + contestId + "/details/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTEST_RESULTS_SUCCESSFUL, payload: value, contestId: contestId}),
        error: error => console.log(error)
    });
}

export const fetchContestTeams = (contestId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contestresults/" + contestId + "/teams/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTEST_TEAMS_LIST_SUCCESSFUL, payload: value, contestId: contestId}),
        error: error => console.log(error)
    });
}


export const fetchTasks = (contestId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/tasks/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_TASKS_SUCCESSFUL, payload: value, contestId: contestId}),
        error: error => console.log(error)
    });
}

export const fetchTaskTests = (contestId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/tasktests/",
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_TASK_TESTS_SUCCESSFUL, payload: value, contestId: contestId}),
        error: error => console.log(error)
    });
}

export const createNewTask = (contestId, taskName) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/tasks/",
        datatype: 'json',
        method: "POST",
        data: {summary_score_sorting_direction: "asc", name: taskName, heading: taskName, contest: contestId},
        cache: false,
        success: value => {
            console.log("Creating task success: " + value)
            dispatch({type: CREATE_TASK_SUCCESSFUL, contestId: contestId, payload: value})
        },
        error: error => console.log(error)
    });
}

export const deleteTask = (contestId, taskId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/tasks/" + taskId,
        datatype: 'json',
        method: "DELETE",
        cache: false,
        success: value => {
            console.log("Deleting task success: " + value)
            dispatch({type: DELETE_TASK_SUCCESSFUL, contestId: contestId, payload: taskId})
        },
        error: error => console.log(error)
    });
}

export const createNewTaskTest = (contestId, taskId, taskTestName) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/tasktests/",
        datatype: 'json',
        method: "POST",
        data: {index: 0, name: taskTestName, heading: taskTestName, task: taskId},
        cache: false,
        success: value => {
            console.log("Creating task test success: " + value)
            dispatch({type: CREATE_TASK_TEST_SUCCESSFUL, contestId: contestId, payload: value})
        },
        error: error => console.log(error)
    });
}

export const deleteTaskTest = (contestId, taskTestId) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/tasktests/" + taskTestId,
        datatype: 'json',
        method: "DELETE",
        cache: false,
        success: value => {
            console.log("Deleting task test success: " + value)
            dispatch({type: DELETE_TASK_TEST_SUCCESSFUL, contestId: contestId, payload: taskTestId})
        },
        error: error => console.log(error)
    });
}


export const putContestSummary = (contestId, teamId, points) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/update_contest_summary/",
        datatype: 'json',
        method: "PUT",
        data: {contest: contestId, team: teamId, points: points},
        cache: false,
        success: value => console.log("Successfully saved contest summary"),
        error: error => alert(JSON.stringify(error))
    });
}


export const putTaskSummary = (contestId, teamId, taskId, points) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/update_task_summary/",
        datatype: 'json',
        method: "PUT",
        data: {task: taskId, team: teamId, points: points},
        cache: false,
        success: value => console.log("Successfully saved task summary"),
        error: error => alert(JSON.stringify(error))
    });
}

export const putTestResult = (contestId, teamId, taskTestId, points) => (dispatch) => {
    $.ajax({
        url: "/api/v1/contests/" + contestId + "/update_test_result/",
        datatype: 'json',
        method: "PUT",
        data: {task_test: taskTestId, team: teamId, points: points},
        cache: false,
        success: value => console.log("Successfully saved contest summary"),
        error: error => alert(JSON.stringify(error))
    });
}


export const showTaskDetails = (taskId) => (dispatch) => {
    dispatch({type: SHOW_TASK_DETAILS, taskId: taskId})
}

export const hideTaskDetails = (taskId) => (dispatch) => {
    dispatch({type: HIDE_TASK_DETAILS, taskId: taskId})
}

export const hideAllTaskDetails = () => (dispatch) => {
    dispatch({type: HIDE_ALL_TASK_DETAILS})
}

export const showAllTaskDetails = () => (dispatch) => {
    dispatch({type: SHOW_ALL_TASK_DETAILS})
}

