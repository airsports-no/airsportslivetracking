import React, {Component} from "react";
import {connect} from "react-redux";

import {w3cwebsocket as W3CWebSocket} from "websocket";
import {fetchMyParticipatingContests, globalMapStoreVisibleContests, zoomFocusContest} from "../../actions";
import ReactDOMServer from "react-dom/server";
import {
    balloon,
    blimp,
    drone,
    glider,
    helicopter, internalColour,
    jet,
    ognColour, safeskyColour,
    paraglider,
    piston,
    skydiver,
    tower
} from "../aircraft/aircraft";

import {Jawg_Sunny} from "../leafletLayers";
import ContestPopupItem from "../contests/contestPopupItem";

const ognAircraftTypeMap = {
    0: jet,
    1: glider,
    2: piston,
    3: helicopter,
    4: skydiver,
    5: piston,
    6: paraglider,
    7: paraglider,
    8: piston,
    9: jet,
    10: jet,
    11: balloon,
    12: blimp,
    13: drone,
    14: jet,
    15: tower
}


const ZOOM_LEVELS = {
    20: 1128.497220,
    19: 2256.994440,
    18: 4513.988880,
    17: 9027.977761,
    16: 18055.955520,
    15: 36111.911040,
    14: 72223.822090,
    13: 144447.644200,
    12: 288895.288400,
    11: 577790.576700,
    10: 1155581.153000,
    9: 2311162.307000,
    8: 4622324.614000,
    7: 9244649.227000,
    6: 18489298.450000,
    5: 36978596.910000,
    4: 73957193.820000,
    3: 147914387.600000,
    2: 295828775.300000,
    1: 591657550.500000,
}

const TRAIL_LENGTH = 180;
const mapStateToProps = (state, props) => ({
    zoomContest: state.zoomContest,
    upcomingContests: state.upcomingContests
})
const mapDispatchToProps = {
    zoomFocusContest,
    fetchMyParticipatingContests,
    globalMapStoreVisibleContests
}

function arrayEquals(a, b) {
    return Array.isArray(a) &&
        Array.isArray(b) &&
        a.length === b.length &&
        a.every((val, index) => val === b[index]);
}


class Aircraft {
    constructor(name, colour, initial_position, map, iconLayer, textLayer, ageTimeout, trafficSource) {
        this.map = map
        this.iconLayer = iconLayer
        this.textLayer = textLayer
        this.displayText = name
        this.colour = colour
        this.longform = ""
        this.trafficSource = trafficSource
        this.dot = null
        this.dotText = null
        this.trail = null;
        const position = this.replaceTime(initial_position)
        this.latestPosition = position
        this.trailPositions = [position]
        this.time = position.time
        this.ageTimeout = ageTimeout
        this.speedLimit = 50
        this.ageColour = "grey"
        this.navigation_task_link = this.getNavigationTaskLink(initial_position.navigation_task_id)
        this.createLiveEntities(position, new Date().getTime() - this.time.getTime() > this.ageTimeout * 1000 ? this.ageColour : this.colour)
        this.colourTimer = setTimeout(() => this.agePlane(), this.ageTimeout * 1000)
        this.tooltipContents = null
    }

    agePlane() {
        this.updateIcon(this.latestPosition, this.ageColour, 0.4, this.map.getZoom())
    }

    getNavigationTaskLink(navigation_task_id) {
        return navigation_task_id ? document.configuration.navigationTaskMap(navigation_task_id) : null
    }

    replaceTime(position) {
        position.time = new Date(position.time)
        return position
    }

    getAircraftSize(zoomLevel) {
        return 10 + 30 * zoomLevel / 20;
    }

    getTextSize(zoomLevel) {
        return 8 + 7 * zoomLevel / 20;
    }

    createAirplaneIcon(bearing, colour, opacity, zoomLevel) {
        const size = this.getAircraftSize(zoomLevel)
        let html = '<div style="color: ' + colour + ';opacity: ' + opacity + '; transform: rotate(' + bearing + 'deg); width: ' + size + 'px">' + piston(colour) + '</div>'
        return L.divIcon({
            html: html,
            iconAnchor: [size / 2, size / 2],
            className: "myAirplaneIcon"
        })

    }


    createAirplaneTextIcon(name, person_name, altitude, speed, colour, opacity, zoomLevel) {
        const size = this.getTextSize(zoomLevel);
        const smallSize = size - 2
        if (!speed) {
            speed = 0
        }
        if (!altitude) {
            altitude = 0
        }
        return L.divIcon({
            html: '<div style="opacity: ' + opacity + '"><span style="color: ' + colour + '; font-size: ' + size + 'px;position: relative;top: 0px;">' + name + '</span><br/><span style="color: ' + colour + ';font-size: ' + smallSize + 'px; position: relative;top: -10px;">GPS Approx</span><br/><span style="color: ' + colour + ';font-size: ' + smallSize + 'px; position: relative;top: -18px;">' + speed.toFixed(0) + 'kn ' + altitude.toFixed(0) + 'ft</span></div>',
            iconAnchor: [50, -11],
            iconSize: [100, size],
            className: "myAirplaneTextIcon text-center"
        })


    }

    updateNavigationTask(position) {
        if (this.getNavigationTaskLink(position.navigation_task_id) !== this.navigation_task_link && this.dot) {
            this.navigation_task_link = this.getNavigationTaskLink(position.navigation_task_id)
        }
    }

    updateTooltip(position) {
        let tooltipContents = null
        if (position.person) {
            tooltipContents = <div style={{width: "200px"}}>
                <img src={position.person.picture} style={{float: "left", width: "75px"}}/>
                <h6>{position.person.first_name}</h6>
                <h6>{position.person.last_name}</h6>
                <h4>{position.name}</h4>
                {this.navigation_task_link ?
                    <a href={this.navigation_task_link}>Flying in competition</a> : null}
            </div>
        } else if (this.navigation_task_link) {
            tooltipContents = <div>
                {this.navigation_task_link ?
                    <a href={this.navigation_task_link}>Flying in competition</a> : null}
            </div>
        } else if (position.raw_data) {
            tooltipContents = '<pre>' + JSON.stringify(position.raw_data, null, 2) + '</pre>'
        }
        if (this.tooltipContents === tooltipContents) {
            tooltipContents = null
        } else {
            this.tooltipContents = tooltipContents
            if (typeof tooltipContents !== "string") {
                tooltipContents = ReactDOMServer.renderToString(tooltipContents)
            }
        }
        if (tooltipContents) {
            this.dot.unbindTooltip()
            this.dot.bindTooltip(tooltipContents, {
                permanent: false,
                interactive: true
            })
            this.dot.bindPopup(tooltipContents, {
                permanent: false,
            })
        }
    }

    createLiveEntities(position, colour) {
        const opacity = this.calculateOpacity(position.speed)
        this.dot = L.marker([position.latitude, position.longitude], {
            zIndexOffset: 99999
        }).addTo(this.iconLayer)
        this.dotText = L.marker([position.latitude, position.longitude], {
            zIndexOffset: 99999
        }).addTo(this.textLayer)
        if (this.trafficSource === "internal" || this.trafficSource === "ogn") {
            this.updateTooltip(position)
        }
        this.updateIcon(position, colour, opacity, this.map.getZoom())
    }

    calculateOpacity(speed) {
        return speed < this.speedLimit ? 0.4 : 1
    }

    redraw() {
        this.renderPosition(this.latestPosition)
    }

    updatePosition(p) {
        clearTimeout(this.colourTimer)
        const position = this.replaceTime(p)
        this.renderPosition(position)
    }

    renderPosition(position) {
        this.colourTimer = setTimeout(() => this.agePlane(), this.ageTimeout * 1000)
        const opacity = this.calculateOpacity(position.speed)
        if ((position.person && !this.latestPosition.person) || (!position.person && this.latestPosition.person)) {
            this.updateTooltip(position)
        }
        this.latestPosition = position
        this.dot.setLatLng([position.latitude, position.longitude])
        this.dotText.setLatLng([position.latitude, position.longitude])
        this.updateIcon(position, this.colour, opacity, this.map.getZoom())
        this.time = position.time
        this.updateNavigationTask(position)
    }

    updateIcon(position, colour, opacity, zoomLevel) {
        this.dot.setIcon(this.createAirplaneIcon(position.course, colour, opacity, zoomLevel))
        this.dotText.setIcon(this.createAirplaneTextIcon(position.name, position.person_name, 100 * (Math.floor(position.altitude * 3.28084 / 100)), position.speed, colour, opacity, zoomLevel)
        )
    }

    visible() {
        return this.map.getBounds().contains(this.dot.getLatLng())
    }

    removeFromMap() {
        if (this.dot) {
            this.dot.removeFrom(this.iconLayer)
            // this.trail.removeFrom(this.map)
            this.dotText.removeFrom(this.textLayer)
        }
    }

    addToMap() {
        if (this.dot) {
            this.dot.addTo(this.iconLayer)
            if (this.map.getZoom() >= 7) {
                this.dotText.addTo(this.textLayer)
            }
        }
    }
}


class OGNAircraft extends Aircraft {

    constructor(name, colour, initial_position, map, iconLayer, textLayer, ageTimeout, trafficSource, aircraftType) {
        super(name, colour, initial_position, map, iconLayer, textLayer, ageTimeout, trafficSource)
        this.aircraftType = aircraftType
    }

    createAirplaneIcon(bearing, colour, opacity, zoomLevel) {
        const size = this.getAircraftSize(zoomLevel)
        let html = '<div style="color: ' + colour + ';opacity: ' + opacity + '; transform: rotate(' + bearing + 'deg); width: ' + size + 'px">' + jet(colour) + '</div>'
        if (ognAircraftTypeMap[this.aircraftType]) {
            html = '<div style="color: ' + colour + ';opacity: ' + opacity + '; transform: rotate(' + bearing + 'deg); width: ' + size + 'px">' + ognAircraftTypeMap[this.aircraftType](colour) + '</div>'
        }

        return L.divIcon({
            html: html,
            iconAnchor: [size / 2, size / 2],
            iconSize: [size, size],
            className: "myAirplaneIcon"
        })

    }
}

class ConnectedGlobalMapMap
    extends Component {
    constructor(props) {
        super(props);
        this.state = {map: null}
        this.map = null;
        this.internalPositionIcons = null
        this.internalPositionText = null
        this.externalPositionIcons = null
        this.externalPositionText = null
        this.aircraft = {}  // deviceId is key
        this.purgeInterval = 180
        this.connectInterval = null;
        this.wsTimeOut = 1000
        this.bounds = null
        this.L = window['L']
        this.markers = {}
        this.mapReady = false
        this.purgePositions = this.purgePositions.bind(this)
        setInterval(this.purgePositions, this.purgeInterval * 1000)
    }

    check() {
        if (!this.client || this.client.readyState === WebSocket.CLOSED) this.initiateSession(); //check if websocket instance is closed, if so call `connect` function.
    };

    initiateSession() {
        let getUrl = window.location;
        let protocol = "wss"
        if (getUrl.host.includes("localhost")) {
            protocol = "ws"
        }
        this.client = new W3CWebSocket(protocol + "://" + getUrl.host + "/ws/tracks/global/")
        this.client.onopen = () => {
            console.log("Client connected")
            clearTimeout(this.connectInterval)
            this.sendUpdatedPosition()
        };
        this.client.onmessage = (message) => {
            try {
                let data = JSON.parse(message.data);
                this.handlePositions([data])
            } catch (e) {
                console.log(e)
                console.log(message.data)
            }
        };
        this.client.onclose = (e) => {
            console.log(
                `Socket is closed. Reconnect will be attempted in ${Math.min(
                    10000 / 1000,
                    (this.timeout + this.timeout) / 1000
                )} second.`,
                e.reason
            );

            this.timeout = this.timeout + this.timeout; //increment retry interval
            this.connectInterval = setTimeout(() => this.check(), Math.min(10000, this.wsTimeOut)); //call check function after timeout
        };
        this.client.onerror = err => {
            console.error(
                "Socket encountered error: ",
                err.message,
                "Closing socket"
            );
            this.client.close();
        };
    }


    purgePositions() {
        for (let id of Object.keys(this.aircraft)) {
            const now = new Date()
            if (now.getTime() - this.aircraft[id].time.getTime() > this.purgeInterval * 1000) {
                this.aircraft[id].removeFromMap()
                delete this.aircraft[id]
            }
        }
    }

    clearAircraftNotVisible() {
        for (let id of Object.keys(this.aircraft)) {
            if (!this.aircraft[id].visible()) {
                this.aircraft[id].removeFromMap()
            } else {
                this.aircraft[id].addToMap()
            }
        }
    }

    handlePositions(positions) {
        positions.map((position) => {
            const now = new Date()
            const deviceTime = new Date(position.deviceTime)
            if (this.aircraft[position.deviceId] !== undefined) {
                if (this.aircraft[position.deviceId].latestPosition.time >= deviceTime) {
                    return
                }
            }

            if (now.getTime() - deviceTime.getTime() < 60 * 60 * 1000 || true) {
                if (this.aircraft[position.deviceId] === undefined) {
                    if (position.traffic_source === "internal") {
                        this.aircraft[position.deviceId] = new Aircraft(position.name, internalColour, position, this.map,
                            this.internalPositionIcons, this.internalPositionText, 20, position.traffic_source)
                    } else if (position.traffic_source === "opensky") {
                        this.aircraft[position.deviceId] = new OGNAircraft(position.name, safeskyColour, position, this.map,
                            this.externalPositionIcons, this.externalPositionText, 60, position.traffic_source, position.aircraft_type)

                    } else if (position.traffic_source === "ogn") {
                        this.aircraft[position.deviceId] = new OGNAircraft(position.name, ognColour, position, this.map,
                            this.externalPositionIcons, this.externalPositionText, 60, position.traffic_source, position.aircraft_type)
                    }
                } else {
                    if (this.aircraft[position.deviceId].displayText === "" && position.name.length > 0) {
                        this.aircraft[position.deviceId].displayText = position.name
                    }
                    this.aircraft[position.deviceId].updatePosition(position)
                }

            }
        })

    }

    componentDidUpdate(prevProps) {
        if (this.props.upcomingContests && this.props.upcomingContests.length > 0 && !arrayEquals(prevProps.upcomingContests, this.props.upcomingContests)) {
            this.createMarkers()
        }
        if (this.map && this.props.zoomContest) {
            if (prevProps.zoomContest) {
                this.markers[prevProps.zoomContest].closePopup()
            }
            this.markers[this.props.zoomContest].openPopup()
            this.map.flyTo(this.markers[this.props.zoomContest].getLatLng(), 7)
        }

    }

    componentDidMount() {
        this.props.fetchMyParticipatingContests()
        this.initialiseMap()
        this.initiateSession()
    }

    sendUpdatedPosition() {
        if (this.client && this.client.readyState === WebSocket.OPEN && this.bounds) {
            const position = this.map.getCenter()
            const extent = this.map.getBounds()
            const diagonalLength = extent.getNorthEast().distanceTo(extent.getSouthWest())
            const radius_km = diagonalLength / 2000
            const data = {
                type: "location",
                latitude: position.lat,
                longitude: position.lng,
                range: radius_km
            }
            this.client.send(JSON.stringify(data))
        }
    }

    updateVisibleContests() {
        if (this.mapReady && Object.keys(this.markers).length > 0) {
            const extent = this.map.getBounds()
            let visibleIds = []
            for (const [key, value] of Object.entries(this.markers)) {
                if (extent.contains(value.getLatLng())) {
                    visibleIds.push(parseInt(key))
                }
            }
            this.props.globalMapStoreVisibleContests(visibleIds)
        }
    }

    initialiseMap() {
        if (!this.map) {
            this.map = L.map('cesiumContainer', {
                zoomDelta: 0.25,
                zoomSnap: 0.25,
                zoomControl: false,
                preferCanvas: true
            })
            this.createMarkers()

            this.internalPositionIcons = L.layerGroup().addTo(this.map)
            this.internalPositionText = L.layerGroup().addTo(this.map)
            this.externalPositionIcons = L.layerGroup().addTo(this.map)
            this.externalPositionText = L.layerGroup().addTo(this.map)
            Jawg_Sunny().addTo(this.map);
            // OpenAIP.addTo(this.map);
            this.map.on("locationerror", (e) => {
                this.map.setView(L.latLng(59, 10.5), 7)
            })
            this.map.locate({setView: true, maxZoom: 7})
            this.map.whenReady(() => {
                this.mapReady = true
                this.bounds = this.map.getBounds()
                this.sendUpdatedPosition()
                this.map.on("zoomend", (e) => {
                    this.sendUpdatedPosition()
                    this.updateVisibleContests()
                    if (this.map.getZoom() < 7) {
                        this.externalPositionText.removeFrom(this.map)
                        this.internalPositionText.removeFrom(this.map)
                    } else {
                        this.externalPositionText.addTo(this.map)
                        this.internalPositionText.addTo(this.map)
                    }
                    this.clearAircraftNotVisible()
                })
                this.map.on("moveend", (e) => {
                    if (this.bounds) {
                        // Only when loaded
                        this.bounds = this.map.getBounds()
                    }
                    this.sendUpdatedPosition()
                    this.updateVisibleContests()
                    this.clearAircraftNotVisible()
                })
                this.updateVisibleContests()
            })
        }
    }

    getCurrentParticipation(contestId) {
        if (!this.props.myParticipatingContests) return null
        return this.props.myParticipatingContests.find((participation) => {
            return participation.contest.id === contestId
        })
    }

    createMarkers() {
        if (this.props.upcomingContests && Object.keys(this.markers).length == 0) {
            for (let contest of this.props.upcomingContests) {
                this.markers[contest.id] = new this.L.marker([contest.latitude, contest.longitude], {
                    title: contest.name,
                    zIndexOffset: 1000000,
                    riseOnHover: true

                }).addTo(this.map)
                this.markers[contest.id].bindPopup(ReactDOMServer.renderToString(<ContestPopupItem contest={contest}
                                                                                                   participation={this.getCurrentParticipation(contest.id)}/>), {
                    className: "contest-popup",
                    maxWidth: 350,
                    permanent: false,
                    direction: "center"
                })
            }
            this.updateVisibleContests()
        }
    }


    render() {
        return null
    }

}

const GlobalMapMap = connect(mapStateToProps, mapDispatchToProps)(ConnectedGlobalMapMap);
export default GlobalMapMap;