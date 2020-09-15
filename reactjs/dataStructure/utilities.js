function getDistance(lat1, lon1, lat2, lon2) {
    const R = 6371e3; // metres
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

function getBearing(lat1, lon1, lat2, lon2) {
    const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) -
        Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
    const Theta = Math.atan2(y, x);
    const brng = (Theta * 180 / Math.PI + 360) % 360; // in degrees
}