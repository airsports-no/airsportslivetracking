import {divIcon} from "leaflet";

const size = 20

export const anomalyAnnotationIcon = divIcon({
    html: '<i class="fas fa-exclamation" style="color: red"></i>',
    iconSize: [size, size],
    // iconAnchor: [size / 2, size / 2],
    className: "myAnnotationIcon"
})
export const informationAnnotationIcon = divIcon({
    html: '<i class="fas fa-info" style="color: orange"></i>',
    iconSize: [size, size],
    // iconAnchor: [size / 2, size / 2],
    className: "myAnnotationIcon"
})
