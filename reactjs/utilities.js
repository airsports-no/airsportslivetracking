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

export function compareScore(a, b) {
    if (a.score > b.score) return 1;
    if (a.score < b.score) return -1;
    return 0
}

export function compareContestantNumber(a, b) {
    if (a.contestant_number > b.contestant_number) return 1;
    if (a.contestant_number < b.contestant_number) return -1;
    return 0
}

export function contestantShortForm(contestant) {
    return pz(contestant.contestant_number, 2) + " " + contestant.team.crew ? contestant.team.crew.pilot : "Unknown"
}

export function contestantLongForm(contestant) {
    return "Contestant: " + pz(contestant.contestant_number, 2) + "<br/>Pilot: " + contestant.team.crew ? contestant.team.crew.pilot : "Unknown" + "<br/>Navigator: " + contestant.team.crew ? contestant.team.crew.navigator : "Unknown" + "<br/>Aeroplane: " + contestant.team.aeroplane.registration
}