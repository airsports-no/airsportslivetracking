import {divIcon} from "leaflet";


const size = 20

export const anomalyAnnotationIcon = divIcon({
    html: '<span class="iconify" data-icon="mdi-error" style="color: red"/>',
    iconSize: [size, size],
    className: "myAnnotationIcon"
})
export const informationAnnotationIcon = divIcon({
    html: '<span class="iconify" data-icon="mdi-info" style="color: orange"/>',
    iconSize: [size, size],
    className: "myAnnotationIcon"
})
