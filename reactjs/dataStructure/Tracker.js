import Cesium from 'cesium/Cesium';
import {TraccarDevice, TraccarDeviceList} from "./TraccarDevices";
import {TraccarDeviceTracks} from "./TraccarDeviceTrack";

export class Tracker {
    constructor(viewer, contest) {
        this.contest = contest;
        this.traccarDeviceList = new TraccarDeviceList();
        this.traccarDeviceTracks = new TraccarDeviceTracks(this.traccarDeviceList, viewer, new Date(this.contest.startTime), new Date(this.contest.finishTime), this.contest.contestant_set, this.contest.track);
        this.viewer = viewer;
        this.renderTrack();
    }

    renderTrack() {
        for (const key in this.contest.track.gates) {
            if (this.contest.track.gates.hasOwnProperty(key)) {
                let gate = this.contest.track.gates[key];
                this.viewer.entities.add(new Cesium.Entity({
                    name: name + "_gate",
                    polyline: {
                        positions: [new Cesium.Cartesian3.fromDegrees(gate[0], gate[1]), new Cesium.Cartesian3.fromDegrees(gate[2], gate[3])],
                        width: 2,
                        material: Cesium.Color.BLUEVIOLET
                    }

                }));
            }
        }
        let turningPoints = this.contest.track.waypoints.filter((waypoint) => {
            return waypoint.type === "tp"
        }).map((waypoint) => {
            return Cesium.Cartesian3.fromDegrees(waypoint.longitude, waypoint.latitude)
        });
        this.contest.track.waypoints.map((waypoint) => {
            this.viewer.entities.add(new Cesium.Entity({
                name: waypoint.name,
                position: Cesium.Cartesian3.fromDegrees(waypoint.longitude, waypoint.latitude),
                // point: {
                //     pixelSize: 4,
                //     color: Cesium.Color.WHITE,
                //     outlineColor: Cesium.Color.WHITE,
                //     outlineWidth: 2
                // },
                label: {
                    text: waypoint.name,
                    font: '14pt monospace',
                    outlineWidth: 2,
                    verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                    pixelOffset: new Cesium.Cartesian2(0, -9)
                }

            }))
        });

        this.trackEntity = this.viewer.entities.add({
            name: this.contest.name + "_track",
            polyline: {
                positions: turningPoints,
                width: 2,
                material: Cesium.Color.BLUEVIOLET
            }
        })
        this.viewer.flyTo(this.trackEntity);
    }

    appendPositionReports(data) {
        if (data.positions) {
            for (let position in data.positions) {
                this.traccarDeviceTracks.appendPositionReport(data.positions[position])
            }
        }
    }

}