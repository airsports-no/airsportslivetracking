import {
    GET_CONTEST_RESULTS_SUCCESSFUL,
    GET_CONTEST_TEAMS_LIST_SUCCESSFUL,
    SHOW_TASK_DETAILS,
    HIDE_ALL_TASK_DETAILS,
    HIDE_TASK_DETAILS,
    GET_TASKS_SUCCESSFUL,
    GET_TASK_TESTS_SUCCESSFUL,
    CREATE_TASK_SUCCESSFUL,
    CREATE_TASK_TEST_SUCCESSFUL,
    DELETE_TASK_SUCCESSFUL,
    DELETE_TASK_TEST_SUCCESSFUL,
    GET_CONTEST_RESULTS_FAILED
} from "../constants/resultsServiceActionTypes";

export const teamsData = (data, contestId) => (dispatch) => dispatch({
    type: GET_CONTEST_TEAMS_LIST_SUCCESSFUL,
    payload: data,
    contestId: contestId
})
export const tasksData = (data, contestId) => (dispatch) => dispatch({
    type: GET_TASKS_SUCCESSFUL,
    payload: data,
    contestId: contestId
})
export const testsData = (data, contestId) => (dispatch) => dispatch({
    type: GET_TASK_TESTS_SUCCESSFUL,
    payload: data,
    contestId: contestId
})
export const resultsData = (data, contestId) => (dispatch) => dispatch({
    type: GET_CONTEST_RESULTS_SUCCESSFUL,
    payload: data,
    contestId: contestId
})

export const fetchContestResults = (contestId) => (dispatch) => {
    $.ajax({
        url: document.configuration.contestResultsDetailsUrl(contestId),
        datatype: 'json',
        cache: false,
        success: value => dispatch({type: GET_CONTEST_RESULTS_SUCCESSFUL, payload: value, contestId: contestId}),
        error: error => dispatch({type: GET_CONTEST_RESULTS_FAILED, payload: error, contestId: contestId})
    });
}

export const createOrUpdateTask = (contestId, task) => (dispatch) => {
    let url = document.configuration.taskListUrl(contestId)
    let method = "POST"
    if (task.id !== undefined) {
        method = "PUT"
        url = document.configuration.taskDetailUrl(contestId, task.id)
    }
    $.ajax({
        url: url,
        datatype: 'json',
        method: method,
        data: task,
        cache: false,
        success: value => {
            console.log("Creating task success: " + value)
            dispatch({type: CREATE_TASK_SUCCESSFUL, contestId: contestId, payload: value})
        },
        error: error => alert(JSON.stringify(error))
    });
}

export const deleteTask = (contestId, taskId) => (dispatch) => {
    $.ajax({
        url: document.configuration.taskDetailUrl(contestId, taskId),
        datatype: 'json',
        method: "DELETE",
        cache: false,
        success: value => {
            console.log("Deleting task success: " + value)
            dispatch({type: DELETE_TASK_SUCCESSFUL, contestId: contestId, payload: taskId})
        },
        error: error => alert(JSON.stringify(error))
    });
}

export const createOrUpdateTaskTest = (contestId, taskTest) => (dispatch) => {
    let url = document.configuration.taskTestListUrl(contestId)
    let method = "POST"
    if (taskTest.id !== undefined) {
        method = "PUT"
        url = document.configuration.taskTestDetailUrl(contestId, taskTest.id)
    }
    $.ajax({
        url: url,
        datatype: 'json',
        method: method,
        data: taskTest,
        cache: false,
        success: value => {
            console.log("Creating task test success: " + value)
            dispatch({type: CREATE_TASK_TEST_SUCCESSFUL, contestId: contestId, payload: value})
        },
        error: error => alert(JSON.stringify(error))
    });
}

export const deleteTaskTest = (contestId, taskTestId) => (dispatch) => {
    $.ajax({
        url: document.configuration.taskTestDetailUrl(contestId, taskTestId),
        datatype: 'json',
        method: "DELETE",
        cache: false,
        success: value => {
            console.log("Deleting task test success: " + value)
            dispatch({type: DELETE_TASK_TEST_SUCCESSFUL, contestId: contestId, payload: taskTestId})
        },
        error: error => alert(JSON.stringify(error))
    });
}


export const putContestSummary = (contestId, teamId, points) => (dispatch) => {
    $.ajax({
        url: document.configuration.contestUpdateContestSummaryUrl(contestId),
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
        url: document.configuration.contestUpdateTaskSummaryUrl(contestId),
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
        url: document.configuration.contestUpdateTestResultUrl(contestId),
        datatype: 'json',
        method: "PUT",
        data: {task_test: taskTestId, team: teamId, points: points},
        cache: false,
        success: value => console.log("Successfully saved task summary"),
        // success: value => dispatch({type: GET_CONTEST_RESULTS_SUCCESSFUL, payload: value, contestId: contestId}),
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
