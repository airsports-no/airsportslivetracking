import React, {Component} from "react";
import {connect} from "react-redux";
import {tileLayer} from "leaflet";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import {dispatchTraccarData} from "../actions";
import axios from "axios";

const L = window['L']
const server = "traccar.airsports.no";
const token = "f4DSCgfm46IqkRAxTb2N2VV6eGver6tt";
export const mapStateToProps = (state, props) => ({})
export const mapDispatchToProps = {
    dispatchTraccarData
}

class Aircraft {
    constructor(name, colour, initial_position, map) {
        this.map = map
        this.displayText = name
        this.colour = colour
        this.longform = ""
        this.dot = null
        this.dotText = null
        this.createLiveEntities(initial_position)
    }

    createAirplaneIcon(bearing) {
        const size = 32;
        return L.divIcon({
            html: '<i class="mdi mdi-airplanemode-active" style="color: ' + this.colour + '; transform: rotate(' + bearing + 'deg); font-size: ' + size + 'px"/>',
            iconAnchor: [size / 2, size / 2],
            className: "myAirplaneIcon"
        })

    }


    createAirplaneTextIcon() {
        const size = 20;
        return L.divIcon({
            html: '<div style="color: ' + this.colour + '; font-size: ' + size + 'px">' + this.displayText + '</div>',
            iconAnchor: [100, -16],
            iconSize: [200, size],
            className: "myAirplaneTextIcon text-center"
        })


    }

    createLiveEntities(position) {
        this.dot = L.marker([position.latitude, position.longitude], {icon: this.createAirplaneIcon(position.course)}).bindTooltip(this.longform, {
            permanent: false
        }).addTo(this.map)
        this.dotText = L.marker([position.latitude, position.longitude], {icon: this.createAirplaneTextIcon()}).bindTooltip(this.longform, {
            permanent: false
        }).addTo(this.map)
    }

    updatePosition(position) {
        this.dot.setLatLng([position.latitude, position.longitude])
        this.dotText.setLatLng([position.latitude, position.longitude])
        this.dot.setIcon(this.createAirplaneIcon(position.course))
    }
}

class ConnectedGlobalMapMap extends Component {
    constructor(props) {
        super(props);
        this.map = null;
        this.aircraft = {}  // deviceId is key
    }

    initiateSession() {
        axios.get("http://" + server + "/api/session?token=" + token, {withCredentials: true}).then(res => {
            this.client = new W3CWebSocket("wss://" + server + "/api/socket")
            console.log("Initiated session")
            console.log(res)

            this.client.onopen = () => {
                console.log("Client connected")
            };
            this.client.onmessage = (message) => {
                let data = JSON.parse(message.data);
                this.props.dispatchTraccarData(data)
            };

        })
    }


    handlePositions(positions) {
        positions.map((position) => {
            const now = new Date()
            const deviceTime = new Date(position.deviceTime)
            if (now.getTime() - deviceTime.getTime() < 60 * 60 * 1000 || true) {
                if (this.aircraft[position.deviceId] === undefined) {
                    this.aircraft[position.deviceId] = new Aircraft(position.deviceId, "blue", position)
                } else {
                    this.aircraft[position.deviceId].updatePosition(position)
                }

            }
        })

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
    }


    render() {
        return null;
    }

}

const GlobalMapMap = connect(mapStateToProps, mapDispatchToProps)(ConnectedGlobalMapMap);
export default GlobalMapMap;