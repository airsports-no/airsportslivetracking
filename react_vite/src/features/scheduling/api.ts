import { reverse } from "../../urls";
import { getCookie } from "../../utils/csrf";

export const scheduleContestants = async (
    contestId: number,
    navigationTaskId: number,
    payload: any
) => {
    const url = reverse("navigationtasks-schedule-contestants", contestId, navigationTaskId);
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")!,
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to schedule contestants");
    }

    return response.json();
};

export const fetchContestTeams = async (contestPk: number) => {
    const url = reverse("contestteams-list", contestPk);
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error("Failed to fetch contest teams");
    }
    return response.json();
};

export const fetchTeam = async (teamId: number) => {
    const url = reverse("teams-detail", teamId);
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch team ${teamId}`);
    }
    return response.json();
};

export const fetchNavigationTask = async (contestPk: number, navigationTaskPk: number) => {
    const url = reverse("navigationtasks-detail", contestPk, navigationTaskPk);
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error("Failed to fetch navigation task");
    }
    return response.json();
};

export const fetchContestant = async (contestId: number, navigationTaskId: number, contestantId: number) => {
    const url = reverse("contestants-detail", contestId, navigationTaskId, contestantId);
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch contestant ${contestantId}`);
    }
    return response.json();
};

export const updateContestant = async (contestId: number, navigationTaskId: number, contestantId: number, payload: any) => {
    const url = reverse("contestants-detail", contestId, navigationTaskId, contestantId);
    const response = await fetch(url, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")!,
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        const errorData = await response.json();
        // Extract error message from DRF response
        let errorMessage = "Failed to update contestant";
        if (errorData && typeof errorData === 'object') {
             const keys = Object.keys(errorData);
             if (keys.length > 0) {
                 const firstError = errorData[keys[0]];
                 if (Array.isArray(firstError)) {
                     errorMessage = `${keys[0]}: ${firstError[0]}`;
                 } else {
                     errorMessage = `${keys[0]}: ${firstError}`;
                 }
             }
        }
        throw new Error(errorMessage);
    }

    return response.json();
};

export const deleteContestant = async (contestId: number, navigationTaskId: number, contestantId: number) => {
    const url = reverse("contestants-detail", contestId, navigationTaskId, contestantId);
    const response = await fetch(url, {
        method: "DELETE",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")!,
        },
    });

    if (!response.ok) {
        throw new Error("Failed to delete contestant");
    }
};