import EllipsisWithTooltip from 'react-ellipsis-with-tooltip'
import React, {Component} from "react";

const R = 6371e3; // metres
export function getDistance(lat1, lon1, lat2, lon2) {
    const phi1 = lat1 * Math.PI / 180; // phi, lambda in radians
    const phi2 = lat2 * Math.PI / 180;
    const deltaphi = (lat2 - lat1) * Math.PI / 180;
    const deltalambda = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(deltaphi / 2) * Math.sin(deltaphi / 2) +
        Math.cos(phi1) * Math.cos(phi2) *
        Math.sin(deltalambda / 2) * Math.sin(deltalambda / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c; // in metres
}

export function getBearing(lat1, lon1, lat2, lon2) {
    lat1 *= Math.PI / 180
    lon1 *= Math.PI / 180
    lat2 *= Math.PI / 180
    lon2 *= Math.PI / 180
    const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) -
        Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
    const Theta = Math.atan2(y, x);
    return (Theta * 180 / Math.PI + 360) % 360; // in degrees
}


export function getHeadingDifference(heading1, heading2) {
    return (heading2 - heading1 + 540) % 360 - 180
}

function angularDistance(lat1, lon1, lat2, lon2) {
    return 2 * Math.asin(Math.sqrt(Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2))
}

export function crossTrackDistance(lat1, lon1, lat2, lon2, lat, lon) {
    const angularDistance13 = getDistance(lat1, lon1, lat, lon) / R
    const firstBearing = getBearing(lat1, lon1, lat, lon) * Math.PI / 180
    const secondBearing = getBearing(lat1, lon1, lat2, lon2) * Math.PI / 180
    return Math.asin(Math.sin(angularDistance13) * Math.sin(firstBearing - secondBearing)) * R
}

export function alongTrackDistance(lat1, lon1, lat, lon, crossTrackDistance) {
    const angularDistance13 = getDistance(lat1, lon1, lat, lon) / R
    return Math.acos(Math.cos(angularDistance13) / Math.cos(crossTrackDistance / R)) * R
}

export function sleep(milliseconds) {
    const date = Date.now();
    let currentDate = null;
    do {
        currentDate = Date.now();
    } while (currentDate - date < milliseconds);
}

export const pz = (n, z = 2, s = '0') =>
    (n + '').length <= z ? (['', '-'])[+(n < 0)] + (s.repeat(z) + Math.abs(n)).slice(-1 * z) : n + '';

export function compareScoreAscending(a, b) {
    if (a.track.current_state === "Waiting...") return 1;
    if (b.track.current_state === "Waiting...") return -1;
    if (a.track.score > b.track.score) return 1;
    if (a.track.score < b.track.score) return -1;
    return 0
}

export function compareScoreDescending(a, b) {
    if (a.track.current_state === "Waiting...") return 1;
    if (b.track.current_state === "Waiting...") return -1;
    if (a.track.score > b.track.score) return -1;
    if (a.track.score < b.track.score) return 1;
    return 0
}

export function compareContestantNumber(a, b) {
    if (a.contestant_number > b.contestant_number) return 1;
    if (a.contestant_number < b.contestant_number) return -1;
    return 0
}

export function contestantShortForm(contestant) {
    // return pz(contestant.contestant_number, 2) + " " + (contestant.team.crew ? contestant.team.crew.pilot : "Unknown")
    return contestant.team.crew ? contestant.team.crew.member1.first_name : "Unknown"
}

export function ordinal_suffix_of(i) {
    var j = i % 10,
        k = i % 100;
    if (j === 1 && k !== 11) {
        return i + "st";
    }
    if (j === 2 && k !== 12) {
        return i + "nd";
    }
    if (j === 3 && k !== 13) {
        return i + "rd";
    }
    return i + "th";
}

export function contestantTwoLines(contestant) {
    if (!contestant.team.crew) {
        return null
    }
    const memberOne = contestant.team.crew.member1.last_name.toUpperCase()
    const memberTwo = contestant.team.crew.member2 ? contestant.team.crew.member2.last_name.toUpperCase() : ""
    return <div>
        <EllipsisWithTooltip>{memberOne}</EllipsisWithTooltip><EllipsisWithTooltip>{memberTwo}</EllipsisWithTooltip>
    </div>

}

export function teamRankingTable(team) {
    let string = ""
    if (team.crew) {
        string = team.crew.member1.first_name + " " + team.crew.member1.last_name
        if (team.crew.member2) {
            string += "\n" + team.crew.member2.first_name + " " + team.crew.member2.last_name
        }
    }
    return <div className={"preWrap"}>{string}</div>
}

export function contestantLongForm(contestant) {
    return "Contestant: " + pz(contestant.contestant_number, 2) + "<br/>Pilot: " + (contestant.team.crew && contestant.team.crew.member1 ? contestant.team.crew.member1.first_name + " " + contestant.team.crew.member1.last_name : "Unknown") + "<br/>Navigator: " + (contestant.team.crew && contestant.team.crew.member2 ? contestant.team.crew.member2.first_name + " " + contestant.team.crew.member2.last_name : "") + "<br/>Airplane: " + contestant.team.aeroplane.registration
}

export function teamLongForm(team) {
    return <div>
        Pilot: {team.crew ? team.crew.member1.last_name + ', ' + team.crew.member1.first_name : "Unknown"}<br/>
        {team.crew && team.crew.member2 ? 'Navigator: ' + team.crew.member2.last_name + ', ' + team.crew.member2.first_name : ""}<br/>
        {team.aeroplane.registration}
    </div>
}


export function teamLongFormText(team) {
    return 'Pilot:' + (team.crew ? team.crew.member1.last_name + ', ' + team.crew.member1.first_name : "Unknown") + (team.crew && team.crew.member2 ? ' ;Navigator: ' + team.crew.member2.last_name + ', ' + team.crew.member2.first_name : "") + ' ;Aeroplane: ' + team.aeroplane.registration
}

export function calculateProjectedScore(score, progress, summary) {
    if (progress <= 0) {
        return 99999
    }
    if (progress < 5) {
        return 99999
    }
    const estimate = (100 * score / progress)
    const difference = estimate - score
    if (summary != null) {
        return summary + difference
    }
    return estimate
}

export const leadingZero = (num) => `0${num}`.slice(-2);

export const formatDate = (date) =>
    date ? "-" + date.getFullYear() + [date.getMonth() + 1, date.getDate()]
        .map(leadingZero)
        .join('-') : "";


export const formatTime = (date) =>
    date ? [date.getHours(), date.getMinutes(), date.getSeconds()]
        .map(leadingZero)
        .join(':') : "";
