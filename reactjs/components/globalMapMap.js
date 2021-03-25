import React, {Component} from "react";
import {connect} from "react-redux";
import {tileLayer} from "leaflet";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import ContestsGlobalMap from "./contests/contestsGlobalMap";
import {zoomFocusContest} from "../actions";
import {SocialMediaLinks} from "./socialMediaLinks";
import ReactDOMServer from "react-dom/server";
import ContestPopupItem from "./contests/contestPopupItem";

const L = window['L']
const TRAIL_LENGTH = 180;
export const mapStateToProps = (state, props) => ({
    zoomContest: state.zoomContest,
    contests: state.contests
})
export const mapDispatchToProps = {
    zoomFocusContest
}

class Aircraft {
    constructor(name, colour, initial_position, map) {
        this.map = map
        this.displayText = name
        this.colour = colour
        this.longform = ""
        this.dot = null
        this.dotText = null
        this.trail = null;
        const position = this.replaceTime(initial_position)
        this.latestPosition = position
        this.trailPositions = [position]
        this.time = position.time
        this.ageTimeout = 15
        this.ageColour = "grey"
        this.navigation_task_link = this.getNavigationTaskLink(initial_position.navigation_task_id)
        this.createLiveEntities(position, new Date().getTime() - this.time.getTime() > this.ageTimeout * 1000 ? this.ageColour : this.colour)
        this.colourTimer = setTimeout(() => this.agePlane(), this.ageTimeout * 1000)
    }

    agePlane() {
        this.updateIcon(this.latestPosition, this.ageColour)
        this.trail.setStyle({
            color: this.ageColour
        })
    }

    getNavigationTaskLink(navigation_task_id) {
        return navigation_task_id ? "display/task/" + navigation_task_id + "/map/" : null
    }

    replaceTime(position) {
        position.time = new Date(position.time)
        return position
    }

    createAirplaneIcon(bearing, colour) {
        const size = 28;
        return L.divIcon({
            html: '<i class="mdi mdi-airplanemode-active" style="color: ' + colour + '; transform: rotate(' + bearing + 'deg); font-size: ' + size + 'px"/>',
            iconAnchor: [size / 2, size / 2],
            className: "myAirplaneIcon"
        })

    }


    createAirplaneTextIcon(altitude, speed, colour) {
        const size = 16;
        return L.divIcon({
            html: '<div><div style="color: ' + colour + '; font-size: ' + size + 'px;margin-bottom: -35px;">' + this.displayText + '<br/>' + speed.toFixed(0) + 'kn ' + altitude.toFixed(0) + 'ft</div><span style="color: ' + colour + ';font-size: 10px;">GPS</span></div>',
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

    createLiveEntities(position, colour) {
        const tooltipContents = this.navigation_task_link ? "Competing in navigation task" : ""
        this.dot = L.marker([position.latitude, position.longitude], {
            zIndexOffset: 99999
        }).bindTooltip(tooltipContents, {
            permanent: false
        }).on('click', (e) => {
            if (this.navigation_task_link) {
                window.location.href = this.navigation_task_link
            }
        }).addTo(this.map)
        this.dotText = L.marker([position.latitude, position.longitude], {
            zIndexOffset: 99999
        }).bindTooltip(tooltipContents, {
            permanent: false
        }).on('click', (e) => {
            if (this.navigation_task_link) {
                window.location.href = this.navigation_task_link
            }
        }).addTo(this.map)
        this.trail = L.polyline([[position.latitude, position.longitude]], {
            color: colour,
            opacity: 1,
            weight: 3
        }).addTo(this.map)
        this.updateIcon(position, colour)
    }

    updateTrail(position) {
        this.trailPositions.push(position)
        this.trail.setStyle({
            color: this.colour
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

    updatePosition(p) {
        clearTimeout(this.colourTimer)
        this.colourTimer = setTimeout(() => this.agePlane(), 15000)
        const position = this.replaceTime(p)
        this.latestPosition = position
        this.dot.setLatLng([position.latitude, position.longitude])
        this.dotText.setLatLng([position.latitude, position.longitude])
        this.updateIcon(position, this.colour)
        this.updateTrail(position)
        this.time = position.time
        this.updateNavigationTask(position)
    }

    updateIcon(position, colour) {
        this.dot.setIcon(this.createAirplaneIcon(position.course, colour))
        this.dotText.setIcon(this.createAirplaneTextIcon(position.altitude * 3.28084, position.speed, colour))
    }

    removeFromMap() {
        if (this.dot) {
            this.dot.removeFrom(this.map)
            this.trail.removeFrom(this.map)
            this.dotText.removeFrom(this.map)
        }
    }
}

class ConnectedGlobalMapMap
    extends Component {
    constructor(props) {
        super(props);
        this.state = {map: null}
        this.map = null;
        this.aircraft = {}  // deviceId is key
        this.purgeInterval = 180
        this.connectInterval = null;
        this.wsTimeOut = 1000
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
        };
        this.client.onmessage = (message) => {
            let data = JSON.parse(message.data);
            this.handlePositions([data])
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
                    this.aircraft[position.deviceId] = new Aircraft(position.name, "blue", position, this.map)
                } else {
                    this.aircraft[position.deviceId].updatePosition(position)
                }

            }
        })

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


    initialiseMap() {
        this.map = L.map('cesiumContainer', {
            zoomDelta: 0.25,
            zoomSnap: 0.25,
        })
        const token = "pk.eyJ1Ijoia29sYWYiLCJhIjoiY2tmNm0zYW55MHJrMDJ0cnZvZ2h6MTJhOSJ9.3IOApjwnK81p6_a0GsDL-A"
        tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
            attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
            maxZoom: 18,
            id: 'mapbox/streets-v11',
            tileSize: 512,
            zoomOffset: -1,
            accessToken: token
        }).addTo(this.map);
        // this.map.setView([0, 0], 2)
        this.map.locate({setView: true, maxZoom: 7})
        this.setState({map: this.map})
    }


    render() {
        return <ContestsGlobalMap map={this.state.map}/>
    }

}

const GlobalMapMap = connect(mapStateToProps, mapDispatchToProps)(ConnectedGlobalMapMap);
export default GlobalMapMap;