import React, {Component} from "react";
import {connect} from "react-redux";

import {w3cwebsocket as W3CWebSocket} from "websocket";
import {zoomFocusContest} from "../actions";
import ReactDOMServer from "react-dom/server";
import L from 'leaflet';
import {
    balloon,
    blimp,
    drone,
    glider,
    helicopter, internalColour,
    jet,
    ognColour, openSkyColour,
    paraglider,
    piston,
    skydiver,
    tower
} from "./aircraft/aircraft";

import marker from 'leaflet/dist/images/marker-icon.png';
import marker2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import {tileLayer} from "leaflet";

// delete L.Icon.Default.prototype._getIconUrl;
//
// L.Icon.Default.mergeOptions({
//     iconRetinaUrl: marker2x,
//     iconUrl: marker,
//     shadowUrl: markerShadow
// });
import ContestsGlobalMap from "./contests/contestsGlobalMap";

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


function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        let cls = 'number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'key';
            } else {
                cls = 'string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'boolean';
        } else if (/null/.test(match)) {
            cls = 'null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
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
export const mapStateToProps = (state, props) => ({
    zoomContest: state.zoomContest,
    contests: state.contests
})
export const mapDispatchToProps = {
    zoomFocusContest
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
        // this.trail.setStyle({
        //     opacity: 0.4,
        //     color: this.ageColour
        // })
    }

    getNavigationTaskLink(navigation_task_id) {
        return navigation_task_id ? "/display/task/" + navigation_task_id + "/map/" : null
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
            iconAnchor: [100, -11],
            iconSize: [200, size],
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
            // this.dotText.unbindTooltip()
            this.dot.unbindTooltip()
            this.dot.bindTooltip(tooltipContents, {
                permanent: true,
                interactive: true
            }).on('click', (ev) => {
                this.dot.toggleTooltip();
            });
            // this.dotText.bindTooltip(tooltipContents, {
            //     permanent: false
            // })
        }
    }

    createLiveEntities(position, colour) {
        const opacity = this.calculateOpacity(position.speed)
        this.dot = L.marker([position.latitude, position.longitude], {
            zIndexOffset: 99999
            // }).on('click', (e) => {
            //     if (this.navigation_task_link) {
            //         window.location.href = this.navigation_task_link
            //     }
        }).addTo(this.iconLayer)
        this.dotText = L.marker([position.latitude, position.longitude], {
            zIndexOffset: 99999
            // }).on('click', (e) => {
            //     if (this.navigation_task_link) {
            //         window.location.href = this.navigation_task_link
            //     }
        }).addTo(this.textLayer)
        // this.trail = L.polyline([[position.latitude, position.longitude]], {
        //     color: colour,
        //     opacity: opacity,
        //     weight: 3
        // }).addTo(this.map)
        if (this.trafficSource === "internal" || this.trafficSource === "ogn") {
            this.updateTooltip(position)
        }
        this.updateIcon(position, colour, opacity, this.map.getZoom())
    }

    updateTrail(position, colour, opacity) {
        this.trailPositions.push(position)
        this.trail.setStyle({
            color: colour, opacity: opacity
        })
        const latestTime = position.time.getTime()
        while (this.trailPositions.length > 0 && latestTime - this.trailPositions[0].time.getTime() > TRAIL_LENGTH * 1000) {
            this.trailPositions.shift()
        }
        const partial = this.trailPositions.map((internal_position) => {
            return [internal_position.latitude, internal_position.longitude]
        })
        if (partial.length > 0) {
            this.trail.setLatLngs(partial)
            this.trail.redraw()
        }

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
        // this.updateTrail(position, this.colour, opacity)
        this.time = position.time
        this.updateNavigationTask(position)
    }

    updateIcon(position, colour, opacity, zoomLevel) {
        this.dot.setIcon(this.createAirplaneIcon(position.course, colour, opacity, zoomLevel))
        this.dotText.setIcon(this.createAirplaneTextIcon(position.name, position.person_name, 100 * (Math.floor(position.altitude * 3.28084 / 100)), position.speed, colour, opacity, zoomLevel)
        )
    }

    removeFromMap() {
        if (this.dot) {
            this.dot.removeFrom(this.iconLayer)
            // this.trail.removeFrom(this.map)
            this.dotText.removeFrom(this.textLayer)
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


    // initiateSession() {
    //     axios.get("https://" + server + "/api/session?token=" + token, {withCredentials: true}).then(res => {
    //         this.client = new W3CWebSocket("wss://" + server + "/api/socket")
    //         console.log("Initiated session")
    //         console.log(res)
    //
    //         this.client.onopen = () => {
    //             console.log("Client connected")
    //         };
    //         this.client.onmessage = (message) => {
    //             let data = JSON.parse(message.data);
    //             if (data.positions !== undefined) {
    //                 this.handlePositions(data.positions)
    //             }
    //             if (data.devices !== undefined) {
    //                 this.handleDevices(data.devices)
    //             }
    //         };
    //
    //     })
    // }

    purgePositions() {
        for (let id of Object.keys(this.aircraft)) {
            const now = new Date()
            if (now.getTime() - this.aircraft[id].time.getTime() > this.purgeInterval * 1000) {
                this.aircraft[id].removeFromMap()
                delete this.aircraft[id]
            }
        }
    }

    handlePositions(positions) {
        positions.map((position) => {
            const now = new Date()
            const deviceTime = new Date(position.deviceTime)
            if (now.getTime() - deviceTime.getTime() < 60 * 60 * 1000 || true) {
                if (this.aircraft[position.deviceId] === undefined) {
                    if (position.traffic_source === "internal") {
                        this.aircraft[position.deviceId] = new Aircraft(position.name, internalColour, position, this.map,
                            this.internalPositionIcons, this.internalPositionText, 20, position.traffic_source)
                    } else if (position.traffic_source === "opensky") {
                        this.aircraft[position.deviceId] = new OGNAircraft(position.name, openSkyColour, position, this.map,
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

    redrawAircraft() {
        for (let a of Object.values(this.aircraft)) {
            a.redraw()
        }
    }

    componentDidUpdate(prevProps) {
        if (prevProps.zoomContest !== this.props.zoomContest && this.map && this.props.zoomContest) {
            const contest = this.props.contests.find((contest) => {
                if (contest.id === this.props.zoomContest) {
                    return contest
                }
            })
            if (contest) {
                this.map.flyTo([contest.latitude, contest.longitude], 8)
                // this.props.zoomFocusContest(null)
            }
        }
    }

    componentDidMount() {
        this.initialiseMap()
        this.initiateSession()
    }

// Create additional Control placeholders
//     addControlPlaceholders(map) {
//         var corners = map._controlCorners,
//             l = 'leaflet-',
//             container = map._controlContainer;
//
//         function createCorner(vSide, hSide) {
//             var className = l + vSide + ' ' + l + hSide;
//
//             corners[vSide + hSide] = L.DomUtil.create('div', className, container);
//         }
//
//         createCorner('almostbottom', 'left');
//         createCorner('almostbottom', 'right');
//     }

    sendUpdatedPosition() {
        if (this.client && this.client.readyState === WebSocket.OPEN) {
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

    initialiseMap() {
        this.map = L.map('cesiumContainer', {
            zoomDelta: 0.25,
            zoomSnap: 0.25,
            zoomControl: false,
            preferCanvas: true
        })

        this.internalPositionIcons = L.layerGroup().addTo(this.map)
        this.internalPositionText = L.layerGroup().addTo(this.map)
        this.externalPositionIcons = L.layerGroup().addTo(this.map)
        this.externalPositionText = L.layerGroup().addTo(this.map)
        // this.addControlPlaceholders(this.map);

        // Change the position of the Zoom Control to a newly created placeholder.
//         this.map.zoomControl.setPosition('almostbottomleft');

// You can also put other controls in the same placeholder.
        //         L.control.scale({position: 'almostbottomleft'}).addTo(this.map);

        // const token = "pk.eyJ1Ijoia29sYWYiLCJhIjoiY2tmNm0zYW55MHJrMDJ0cnZvZ2h6MTJhOSJ9.3IOApjwnK81p6_a0GsDL-A"
        // const Stadia_AlidadeSmooth = L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png?api_key=d818a148-b158-4268-b073-ee9b34f6a23b', {
        //     maxZoom: 20,
        //     attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors'
        // });
        // const mapbox = tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
        //     attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
        //     maxZoom: 18,
        //     id: 'mapbox/streets-v11',
        //     tileSize: 512,
        //     zoomOffset: -1,
        //     accessToken: token
        // })
        // const Esri_WorldGrayCanvas = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        //     attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
        //     maxZoom: 16
        // });
        const CartoDB_Positron = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19
        });
        const Jawg_Sunny = L.tileLayer('https://{s}.tile.jawg.io/jawg-sunny/{z}/{x}/{y}{r}.png?access-token={accessToken}', {
            attribution: '<a href="http://jawg.io" title="Tiles Courtesy of Jawg Maps" target="_blank">&copy; <b>Jawg</b>Maps</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            minZoom: 0,
            maxZoom: 22,
            subdomains: 'abcd',
            accessToken: 'fV8nbLEqcxdUyjN5DXYn8OgCX8vdhBC5jYCkroqpgh6bzsEfb2hQkvDqRQs1GcXX'
        });
        const OpenAIP = L.tileLayer('http://{s}.tile.maps.openaip.net/geowebcache/service/tms/1.0.0/openaip_basemap@EPSG%3A900913@png/{z}/{x}/{y}.{ext}', {
            attribution: '<a href="https://www.openaip.net/">openAIP Data</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-NC-SA</a>)',
            ext: 'png',
            minZoom: 4,
            maxZoom: 14,
            tms: true,
            detectRetina: true,
            subdomains: 'abcd'
        });
        Jawg_Sunny.addTo(this.map);
        // OpenAIP.addTo(this.map);
        // this.map.setView([0, 0], 2)
        this.map.locate({setView: true, maxZoom: 7})
        this.map.whenReady(() => {
            this.bounds = this.map.getBounds()
            this.sendUpdatedPosition()
        })

        this.setState({map: this.map})
        this.map.on("zoomend", (e) => {
            this.sendUpdatedPosition()
            if (this.map.getZoom() < 7) {
                this.externalPositionText.removeFrom(this.map)
                this.internalPositionText.removeFrom(this.map)
            } else {
                this.externalPositionText.addTo(this.map)
                this.internalPositionText.addTo(this.map)
            }
        })
        this.map.on("moveend", (e) => {
            this.bounds = this.map.getBounds()
            this.sendUpdatedPosition()
        })
    }


    render() {
        return <ContestsGlobalMap map={this.state.map}/>
    }

}

const GlobalMapMap = connect(mapStateToProps, mapDispatchToProps)(ConnectedGlobalMapMap);
export default GlobalMapMap;