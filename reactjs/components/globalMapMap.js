import React, {Component} from "react";
import {connect} from "react-redux";
import {tileLayer} from "leaflet";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import ContestsGlobalMap from "./contests/contestsGlobalMap";
import {zoomFocusContest} from "../actions";
import {SocialMediaLinks} from "./socialMediaLinks";

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
        this.trailPositions = [position]
        this.time = position.time
        this.createLiveEntities(position)
    }

    replaceTime(position) {
        position.time = new Date(position.time)
        return position
    }

    createAirplaneIcon(bearing) {
        const size = 28;
        return L.divIcon({
            html: '<i class="mdi mdi-airplanemode-active" style="color: ' + this.colour + '; transform: rotate(' + bearing + 'deg); font-size: ' + size + 'px"/>',
            iconAnchor: [size / 2, size / 2],
            className: "myAirplaneIcon"
        })

    }


    createAirplaneTextIcon() {
        const size = 16;
        return L.divIcon({
            html: '<div style="color: ' + this.colour + '; font-size: ' + size + 'px">' + this.displayText + '</div>',
            iconAnchor: [100, -16],
            iconSize: [200, size],
            className: "myAirplaneTextIcon text-center"
        })


    }

    createLiveEntities(position) {
        this.dot = L.marker([position.latitude, position.longitude], {
            icon: this.createAirplaneIcon(position.course),
            zIndexOffset: 99999
        }).bindTooltip(this.longform, {
            permanent: false
        }).addTo(this.map)
        this.dotText = L.marker([position.latitude, position.longitude], {
            icon: this.createAirplaneTextIcon(),
            zIndexOffset: 99999
        }).bindTooltip(this.longform, {
            permanent: false
        }).addTo(this.map)
        this.trail = L.polyline([[position.latitude, position.longitude]], {
            color: this.colour,
            opacity: 1,
            weight: 3
        }).addTo(this.map)
    }

    updateTrail(position) {
        this.trailPositions.push(position)

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
        const position = this.replaceTime(p)
        this.dot.setLatLng([position.latitude, position.longitude])
        this.dotText.setLatLng([position.latitude, position.longitude])
        this.dot.setIcon(this.createAirplaneIcon(position.course))
        this.updateTrail(position)
        this.time = position.time
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
        this.purgeInterval = 1200
        this.purgePositions = this.purgePositions.bind(this)
        setInterval(this.purgePositions, this.purgeInterval * 1000)
    }

    initiateSession() {
        let getUrl = window.location;
        let baseUrl = getUrl.protocol + "//" + getUrl.host + "/" + getUrl.pathname.split('/')[1]
        let protocol = "wss"
        if (getUrl.host.includes("localhost")) {
            protocol = "ws"
        }
        this.client = new W3CWebSocket(protocol + "://" + getUrl.host + "/ws/tracks/global/")
        this.client.onopen = () => {
            console.log("Client connected")
        };
        this.client.onmessage = (message) => {
            let data = JSON.parse(message.data);
            this.handlePositions([data])
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
        this.map.locate({setView: true, maxZoom: 5})
        this.setState({map: this.map})
    }


    render() {
        return <ContestsGlobalMap map={this.state.map}/>
    }

}

const GlobalMapMap = connect(mapStateToProps, mapDispatchToProps)(ConnectedGlobalMapMap);
export default GlobalMapMap;