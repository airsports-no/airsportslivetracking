import React, {Component} from "react";
import {connect} from "react-redux";
// import "leaflet-draw/dist/leaflet.draw.css"
// import 'leaflet-draw/dist/images/layers.png'
// import "leaflet/dist/leaflet.css"
// import Draw from "leaflet-draw"
// import L from "leaflet";
import "leaflet";
import "leaflet-draw";
// import "leaflet-draw-with-touch";
import "../../pointInPolygon"
import {Button, Container, Form, Modal, Row, Col, ToastContainer, Toast} from "react-bootstrap";
import {circle, divIcon, marker} from "leaflet";
import {fetchEditableRoute} from "../../actions";
import axios from "axios";
import {Link, withRouter} from "react-router-dom";
import IntroSlider from "react-intro-slider";
import Cookies from "universal-cookie";
import {fractionalDistancePoint, getBearing, getDistance, getHeadingDifference} from "../../utilities";

const gateTypes = [
    ["Starting point", "sp"],
    ["Finish point", "fp"],
    ["Turning point", "tp"],
    ["Secret gate", "secret"]
]

const featureStyles = {
    "track": {"color": "blue"},
    "to": {"color": "green"},
    "ldg": {"color": "crimson"},
    "prohibited": {"color": "crimson"},
    "info": {"color": "lightblue"},
    "penalty": {"color": "orange"},
    "gate": {"color": "blue"},
}

const generalTypes = {
    "track": [1, 1],
    "to": [0, 1],
    "ldg": [0, 1],
    "prohibited": [0, 1000],
    "info": [0, 1000],
    "gate": [0, 1000],
    "penalty": [0, 1000]
}

const featureTypeCounts = {
    "precision": generalTypes,
    "anr": generalTypes,
    "poker": generalTypes,
    "landing": {
        "track": [0, 1],
        "to": [0, 1],
        "ldg": [1, 1],
        "prohibited": [0, 1000],
        "info": [0, 1000],
        "gate": [0, 1000],
        "penalty": [0, 1000]
    }
}


const featureTypes = {
    polyline: [["Track", "track"], ["Takeoff gate", "to"], ["Landing gate", "ldg"]],
    polygon: [["Prohibited zone", "prohibited"], ["Penalty zone", "penalty"], ["Information zone", "info"], ["Gate zone", "gate"]],
}
const bgcolor = "darkgrey"
const slides = [
    {
        title: "Mouse required",
        description: "The route editor does unfortunately not work with touchscreen devices. Click next to continue the tutorial.",
        image: "/static/img/tutorial/0.png",
        background: bgcolor
    }, {
        title: "Enable editing",
        description: "Click 'Edit' to enable editing. Cancel resets and changes, and route list returns you to the list of all your routes.",
        image: "/static/img/tutorial/0.png",
        background: bgcolor
    },
    {
        title: "Create route",
        description: "Click icons to create a route or a zone (penalty zone, etc)",
        image: "/static/img/tutorial/1.png",
        background: bgcolor
    }, {
        title: "Draw track",
        description: "Draw the track by clicking the icon, the starting point, and then each subsequent turning point. Finish by clicking 'finish' or clicking on the last point created.",
        image: "/static/img/tutorial/2.png",
        background: bgcolor
    }, {
        title: "Track details",
        description: "Select type of route. You always need a track. Takeoff and landing gates should cross the runway, but not be crossed during taxi.",
        image: "/static/img/tutorial/3.png",
        background: bgcolor
    }, {
        title: "Edit waypoint details",
        description: "Choose a waypoint name, the waypoint type, and the width of the gate. This will determine the size of the gate or the corridor. Time check controls whether the gate gives penalties, secret waypoints are not visible to the pilots. ",
        image: "/static/img/tutorial/4.png",
        background: bgcolor
    }, {
        title: "Zones",
        description: "Optionally, create a prohibited zone (fixed penalty), penalty area (penalty per second), or information area. For certain types of tasks (poker run) you can create a gate area around a waypoint to represent the waypoint.",
        image: "/static/img/tutorial/5.png",
        background: bgcolor
    }, {
        title: "Zone details",
        description: "Select the type of zone and give a name. The name will be displayed on the map. Enter label x and y offset to control how the name is displayed. Make sure this looks good at multiple zoom levels.",
        image: "/static/img/tutorial/6.png",
        background: bgcolor
    }, {
        title: "Editing",
        description: "To edit an existing track or area, click and drag the available markers to the desired shape. Use the satellite view to pinpoint waypoint features.",
        image: "/static/img/tutorial/7.png",
        background: bgcolor
    }, {
        title: "Saving",
        description: "At any time, give the route a name and click save at the bottom of the map. This will validate that the route is set up correctly and save it for later editing and use.",
        image: "/static/img/tutorial/8.png",
        background: bgcolor
    }, {
        title: "Task creation",
        description: "Once the route is saved, go back to the root list and click 'Create task'. This will guide you through the task creation process. Note that you already have to have created a contest.",
        image: "/static/img/tutorial/9.png",
        background: bgcolor
    },

]

class ConnectedRouteEditor extends Component {
    constructor(props) {
        super(props)
        this.map = null
        this.mapReady = false
        this.drawControl = null
        this.drawingEnabledOptions = {
            marker: false,
            rectangle: false,
            circle: false,
            polyline: true,
            circlemarker: false,
            polygon: {
                allowIntersection: false,
                showArea: true
            }
        }
        this.drawingDisabledOptions = {
            marker: false,
            rectangle: false,
            circle: false,
            circlemarker: false,
            polygon: false,
            polyline: false
        }
        this.state = {
            featureEditLayer: null,
            featureType: null,
            currentName: null,
            xOffset: 0,
            yOffset: 0,
            routeName: null,
            changesSaved: false,
            displayTutorial: false,
            selectedWaypoint: null,
            globalEditingMode: false
        }
        this.usedGateNames = []
    }

    componentDidMount() {
        const cookies = new Cookies();
        const key = "aslt_routeeditor_visited"
        const visited = cookies.get(key)
        console.log("Visited: " + visited)
        if (!visited) {
            this.setState({displayTutorial: true})
            cookies.set(key, true)
        }
        this.initialiseMap()
        if (this.props.routeId) {
            this.reloadMap()
        }
    }

    reloadMap() {
        this.clearFormData()
        this.setState({changesSaved: false, validationErrors: null, saveFailed: null})
        this.props.fetchEditableRoute(this.props.routeId)
    }


    componentDidUpdate(prevProps, prevState, snapshot) {
        console.log("routeId: " + this.props.routeId)

        if (this.props.route !== prevProps.route && this.props.route) {
            this.renderRoute()
        }
        for (let l of this.drawnItems.getLayers().filter((a) => a.layerType !== undefined)) {
            if (this.state.globalEditingMode) {
                l.editing.enable()
            } else {
                l.editing.disable()
            }
        }
    }

    handleSaveSuccess(id) {
        this.setState({changesSaved: true, saveFailed: null, globalEditingMode: false})
        this.props.history.push("/routeeditor/" + id + "/")
    }

    existingFeatureTypes() {
        let existingFeatureTypes = {}
        for (let l of this.drawnItems.getLayers()) {
            if (existingFeatureTypes[l.featureType] === undefined) {
                existingFeatureTypes[l.featureType] = 1
            } else {
                existingFeatureTypes[l.featureType] += 1
            }
        }
        return existingFeatureTypes
    }

    saveRoute() {
        if (!this.state.globalEditingMode) {
            this.setState({globalEditingMode: true})
            return
        }
        let features = []
        let errors = []
        for (let l of this.drawnItems.getLayers().filter((a) => a.layerType !== undefined)) {
            errors = errors.concat(this.validateLayer(l))
            if (["polyline", "rectangle", "polygon"].includes(l.layerType)) {
                features.push({
                    name: l.name,
                    layer_type: l.layerType,
                    track_points: l.trackPoints,
                    feature_type: l.featureType,
                    tooltip_position: l.tooltipPosition,
                    geojson: l.toGeoJSON(),
                })
            }
        }
        let method = "post", url = "/api/v1/editableroutes/"
        let name = this.state.routeName
        if (this.props.routeId) {
            method = "put"
            url += this.props.routeId + "/"
            if (this.state.routeName) {
                name = this.state.routeName
            } else if (this.state.routeName === null) {
                name = this.props.route.name
            } else {
                errors.push("The route must have a name")
            }
        }
        if (!name || name === "") {
            errors.push("The route must have a name")
        }
        this.setState({validationErrors: errors})
        if (errors.length > 0) {
            return
        }
        axios({
            method: method,
            url: url,
            data: {route: features, name: name, route_type: this.props.routeType}
        }).then((res) => {
            console.log("Response")
            console.log(res)
            this.handleSaveSuccess(res.data.id)
        }).catch((e) => {
            console.error(e);
            console.log(e);
            this.setState({changesSaved: false, saveFailed: e})
        }).finally(() => {
        })
    }

    configureLayer(layer, name, layerType, featureType, trackPoints, tooltipPosition, created) {
        layer.addTo(this.drawnItems);
        layer.name = name
        layer.layerType = layerType
        layer.featureType = featureType
        layer.trackPoints = trackPoints
        layer.tooltipPosition = tooltipPosition
        layer.waypointNamesFeatureGroup = L.featureGroup().addTo(this.drawnItems);
        layer.on("click", (item) => {
            const layer = item.target
            if (this.state.globalEditingMode) {
                this.setState({featureEditLayer: layer})
            }
        })
        layer.on("edit", (item) => {
            const layer = item.target
            if (layer.featureType === "track") {
                // Editing already existing feature
                this.updateWaypoints(layer)
                this.renderWaypointNames(layer)
            }
            this.setState({changesSaved: false})
        })
        layer.setStyle(featureStyles[featureType])
        if (!created) {
            this.renderWaypointNames(layer)
        }
    }

    renderRoute() {
        this.drawnItems.clearLayers()
        console.log('renderRoute')
        console.log(this.props.route)
        let zoomed = false
        for (let r of this.props.route.route) {
            new L.GeoJSON(r.geojson, {
                    pointToLayer: (feature, latlng) => {
                        switch (feature.geometry.type) {
                            case 'Polygon':
                                //var ii = new L.Polygon(latlng)
                                //ii.addTo(drawnItems);
                                return L.polygon(latlng);
                            case 'LineString':
                                return L.polyline(latlng);
                            case 'Point':
                                return L.marker(latlng);
                            default:
                                return;
                        }
                    },
                    onEachFeature: (feature, layer) => {
                        if (r.feature_type === "track") {
                            zoomed = true
                            this.trackLayer = layer
                            this.map.fitBounds(layer.getBounds(), {padding: [50, 50]})
                        }
                        if (this.state.globalEditingMode) {
                            layer.editing.enable()
                        } else {
                            layer.editing.disable()
                        }
                        if (!r.tooltip_position) {
                            r.tooltip_position = [0, 0]
                        }
                        this.configureLayer(layer, r.name, r.layer_type, r.feature_type, r.track_points, r.tooltip_position, false)
                    }
                }
            )
        }
        if (!zoomed) {
            const layers = this.drawnItems.getLayers()
            if (layers.length > 0) {
                this.map.fitBounds(layers[0].getBounds(), {padding: [50, 50]})
            }
        }
    }

    highlightLayer(layer) {
        layer.setStyle({
            color: "red"
        })
    }

    validateLayer(layer) {
        let errors = []
        console.log("Validation")
        console.log(layer)
        // This must be run before validating the name since it sets the name
        if (layer.featureType === "gate") {
            // Verify that the gate surrounds exactly one turning point, and give the gate the same name as the turning point it surrounds
            errors = errors.concat(this.saveAndVerifyGatePolygons(layer))
        }
        if (layer.featureType === undefined || !layer.featureType) {
            errors.push("Feature type has not been selected for the highlighted (red) item")
            this.highlightLayer(layer)
        }
        if (layer.name === undefined || !layer.name || layer.name === "") {
            errors.push("Highlighted  (red) layer is missing name")
            this.highlightLayer(layer)
        }
        if (layer.featureType === "track") {
            if (layer.getLatLngs().length < 2) {
                errors.push("A track must have at least two waypoints")
            } else {
                let names = []
                for (let i = 0; i < layer.trackPoints.length; i++) {
                    if (names.includes(layer.trackPoints[i].name)) {
                        errors.push("Gate names must be unique. The name '" + layer.trackPoints[i].name + "' is used multiple times.")
                    }
                    names.push(layer.trackPoints[i].name)
                }
                if (layer.getLatLngs().length !== layer.trackPoints.length) {
                    errors.push("The length of points and the length of the names do not match")
                }
                const startingPoints = layer.trackPoints.filter((item) => {
                    return item.gateType === "sp"
                })
                if (!startingPoints || startingPoints.length !== 1) {
                    errors.push("The track must contain exactly one starting point")
                }
                if (layer.trackPoints[0].gateType !== "sp") {
                    errors.push("The first gate must be starting point")
                }
                if (layer.trackPoints[layer.trackPoints.length - 1].gateType !== "fp") {
                    errors.push("The last gate must be finish point")
                }
                const finishPoints = layer.trackPoints.filter((item) => {
                    return item.gateType === "fp"
                })
                if (!finishPoints || finishPoints.length !== 1) {
                    errors.push("The track must contain exactly one finish point")
                }
                const positions = layer.getLatLngs()
                for (let i = 0; i < layer.trackPoints.length; i++) {
                    if (i === 0 && layer.trackPoints[i].gateType === "secret") {
                        errors.push("The first gate cannot be secret")
                    } else if (i === layer.trackPoints.length - 1 && layer.trackPoints[i].gateType === "secret") {
                        errors.push("The last gate cannot be secret")
                    } else if (layer.trackPoints[i].gateType === "secret") {
                        // He we know there is at least one gate before and one after
                        const bearingToThis = getBearing(positions[i - 1].lat, positions[i - 1].lng, positions[i].lat, positions[i].lng)
                        const bearingFromThis = getBearing(positions[i].lat, positions[i].lng, positions[i + 1].lat, positions[i + 1].lng)
                        const bearingDifference = getHeadingDifference(bearingToThis, bearingFromThis)
                        if (Math.abs(bearingDifference) > 3) {
                            errors.push("The secret gate " + layer.trackPoints[i].name + " must lie on a straight line between " + layer.trackPoints[i - 1].name + " and " + layer.trackPoints[i + 1].name + ". The current bearing difference is " + bearingDifference.toFixed(2))
                        }
                    }
                }
            }
        }
        if (layer.featureType === "to" || layer.featureType === "ldg") {
            if (layer.getLatLngs().length !== 2) {
                errors.push(layer.name + ": Must be exactly 2 points")
            }
        }

        return errors
    }

    checkIfUpdateIsNeeded(layer) {
        if (layer.featureType === "track") {
            if (layer.getLatLngs().length !== layer.trackPoints.length) {
                layer.errors = "The length of points and the length of the names do not match"
                return true
            }
        }
        layer.errors = null
        return false
    }

    saveAndVerifyGatePolygons(layer) {
        // Verify that the gate surrounds exactly one turning point, and give the gate the same name as the turning point it surrounds
        const track = this.drawnItems.getLayers().find((l) => {
            return l.featureType === "track"
        })
        if (!track) {
            return ["You must have a track before you can start creating gate zones"]
        }
        let candidateWaypoints = []
        let index = 0
        for (const position of track.getLatLngs()) {
            if (layer.contains(position)) {
                candidateWaypoints.push(index)
            }
            index += 1
        }
        if (candidateWaypoints.length === 0) {
            return ["Gate polygon must wrap exactly one turning point, currently wraps 0"]
        }
        if (candidateWaypoints.length > 1) {
            return ["Gate polygon must wrap exactly one turning point, currently it wraps" + candidateWaypoints.length]
        }
        // Here everything is in order, so that the same name
        layer.name = track.trackPoints[candidateWaypoints[0]].name
        return []
    }

    saveLayer() {
        if (this.state.globalEditingMode) {
            this.state.featureEditLayer.editing.enable()
        }
        if (this.state.featureType) {
            this.state.featureEditLayer.featureType = this.state.featureType
        }
        if (!this.state.featureEditLayer.name || this.state.featureEditLayer.name === "") {
            this.state.featureEditLayer.name = featureTypes[this.state.featureEditLayer.layerType].find((item) => {
                return item[1] === this.state.featureEditLayer.featureType
            })[0]
        }
        if (this.state.currentName) {
            this.state.featureEditLayer.name = this.state.currentName
        }

        if (this.state.featureEditLayer.featureType === "track") {
            this.trackLayer = this.state.featureEditLayer
        }
        this.state.featureEditLayer.tooltipPosition = [parseInt(this.state.xOffset), parseInt(this.state.yOffset)]
        this.state.featureEditLayer.setStyle(featureStyles[this.state.featureEditLayer.featureType])
        // this.state.featureEditLayer.editing.disable()
        this.renderWaypointNames(this.state.featureEditLayer)

        console.log(this.state.featureEditLayer)
        const errors = this.validateLayer(this.state.featureEditLayer)
        this.setState({validationErrors: errors})
        if (errors.length === 0) {
            this.clearFormData()
        }
    }

    clearFormData() {
        this.setState({
            featureEditLayer: null,
            featureType: null,
            xOffset: 0,
            yOffset: 0,
            currentName: null,
            changesSaved: false,
            validationErrors: []
        })
    }

    renderWaypointNames(track) {
        track.unbindTooltip()
        if (track.featureType === "track") {
            track.waypointNamesFeatureGroup.clearLayers()
            let index = 0
            for (let p of track.getLatLngs()) {
                let distanceNext
                let bearingNext
                let waypointText = track.trackPoints[index].name
                if (index < track.getLatLngs().length - 1) {
                    const nextPosition = track.getLatLngs()[index + 1]
                    distanceNext = getDistance(p.lat, p.lng, nextPosition.lat, nextPosition.lng) / 1852
                    bearingNext = getBearing(p.lat, p.lng, nextPosition.lat, nextPosition.lng)
                    const midway = fractionalDistancePoint(p.lat, p.lng, nextPosition.lat, nextPosition.lng, 0.5)
                    const distanceText = distanceNext.toFixed(1) + 'NM, ' + bearingNext.toFixed(0) + '&deg;'
                    marker(midway, {
                        color: "blue",
                        index: index,
                        icon: divIcon({
                            html: '<span>' + distanceText + '</span>',
                            iconSize: [200, 20],
                            iconAnchor: [100, -10],
                            className: "myGateDistance",

                        })
                    }).addTo(track.waypointNamesFeatureGroup)
                }
                const m = marker([p.lat, p.lng], {
                    color: "blue",
                    index: index,
                    icon: divIcon({
                        html: '<span class="hover-underline"">' + waypointText + '</span>',
                        iconSize: [200, 20],
                        iconAnchor: [-15, 7],
                        className: "myGateLink",

                    })
                }).addTo(track.waypointNamesFeatureGroup).on("click", (item) => {
                    if (this.state.globalEditingMode) {
                        this.setState({selectedWaypoint: item.target.options.index})
                    }
                })
                circle([p.lat, p.lng], {
                    radius: track.trackPoints[index].gateWidth * 1852 / 2,
                    index: index,
                    color: track.trackPoints[index].timeCheck ? "blue" : "grey",
                    opacity: 0.05
                }).addTo(track.waypointNamesFeatureGroup).on("click", (item) => {
                    if (this.state.globalEditingMode) {
                        this.setState({selectedWaypoint: item.target.options.index})
                    }
                })
                index += 1
            }
        } else if (Object.keys(generalTypes).includes(track.featureType)) {
            let tooltipPosition = [0, 0]
            if (track.tooltipPosition) {
                tooltipPosition = track.tooltipPosition
            }
            track.bindTooltip(track.name, {
                permanent: true,
                direction: "center",
                className: "prohibitedTooltip",
                offset: tooltipPosition
            })
        }
    }


    isFeatureSelectable(featureType, checked) {
        const usedFeatureTypes = this.existingFeatureTypes()
        const limits = featureTypeCounts[this.props.routeType][featureType]
        return checked || usedFeatureTypes[featureType] === undefined || usedFeatureTypes[featureType] < limits[1];
    }

    renderFeatureSelect(layer) {
        const currentFeatureType = this.state.featureType || layer.featureType
        let options = featureTypes[layer.layerType] || []
        const checkboxes = options.map((item) => {
            const checked = layer.featureType === item[1]
            return <Form.Check inline key={item[1]} name={"featureType"} label={item[0]} type={"radio"}
                               onChange={(e) => {
                                   this.setState({featureType: item[1]})
                               }
                               } disabled={!this.isFeatureSelectable(item[1], checked)} defaultChecked={checked}/>
        })
        return <div>
            {layer.layerType !== "polyline" && currentFeatureType !== "gate" ?
                <div>
                    <Form.Label>Feature name:</Form.Label>&nbsp;
                    <Form.Control name={"feature_name"} type={"string"} placeholder={"Name"}
                                  defaultValue={layer.name}
                                  onChange={(e) => this.setState({currentName: e.target.value})}
                    />
                    <Form.Label>Label offset X</Form.Label>&nbsp;
                    <Form.Control name={"xOffset"} type={"number"} defaultValue={layer.tooltipPosition[0]}
                                  onChange={(e) => this.setState({xOffset: e.target.value})}
                    />
                    <Form.Label>Label offset Y</Form.Label>&nbsp;
                    <Form.Control name={"yOffset"} type={"number"} defaultValue={layer.tooltipPosition[1]}
                                  onChange={(e) => this.setState({yOffset: e.target.value})}
                    />
                </div> : null
            }
            {checkboxes}
        </div>

    }

    renderFeatureForm(layer) {
        return <Form>
            <div className={"alert-danger"}>
                <ul>{this.state.validationErrors ? this.state.validationErrors.map((item) =>
                    <li>{item}</li>) : null}</ul>
            </div>

            {this.renderFeatureSelect(layer)}
        </Form>
    }


    waypointModal() {
        let waypoint
        if (this.trackLayer && this.state.selectedWaypoint !== null) {
            waypoint = this.trackLayer.trackPoints[this.state.selectedWaypoint]
        } else {
            waypoint = {
                name: "invalid",
                gateType: "invalid",
                gateWidth: -1,
                timeCheck: false
            }
        }
        return <Modal
            show={this.state.selectedWaypoint !== null}
            aria-labelledby="contained-modal-title-vcenter">
            <Modal.Header closeButton={false}>
                <Modal.Title id="contained-modal-title-vcenter">
                    <h2>Edit feature</h2>
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="show-grid">
                <Container>
                    <Form>
                        <Form.Label>Waypoint name:</Form.Label>&nbsp;
                        <Form.Control type={"string"} placeholder={"Name"}
                                      defaultValue={waypoint.name}
                                      onChange={
                                          (e) => {
                                              waypoint["name"] = e.target.value
                                          }
                                      }/>
                        <Form.Label>Waypoint type:</Form.Label>&nbsp;
                        <Form.Control as="select"
                                      onChange={
                                          (e) => {
                                              waypoint["gateType"] = e.target.value
                                          }
                                      }
                                      defaultValue={waypoint.gateType}>
                            {gateTypes.map((item) => {
                                return <option key={item[1]} value={item[1]}>{item[0]}</option>
                            })}
                        </Form.Control>

                        <Form.Label>Gate width (NM):</Form.Label>&nbsp;
                        <Form.Control key={"Width"} placeholder={"Width"}
                                      type={"number"}
                                      onChange={
                                          (e) => {
                                              waypoint["gateWidth"] = e.target.value
                                          }
                                      }
                                      defaultValue={waypoint.gateWidth}/>
                        <Form.Check inline key={"timeCheck"} name={"timeCheck"} label={"Time check"}
                                    type={"checkbox"}
                                    onChange={
                                        (e) => {
                                            waypoint["timeCheck"] = e.target.checked
                                        }
                                    }
                                    defaultChecked={waypoint.timeCheck}/>
                    </Form>
                </Container>
            </Modal.Body>
            <Modal.Footer>
                <Button onClick={() => {
                    this.setState({selectedWaypoint: null})
                    this.renderWaypointNames(this.trackLayer)
                }}>Done</Button>
            </Modal.Footer>
        </Modal>
    }

    featureEditModal() {
        return <Modal
            show={this.state.featureEditLayer !== null}
            aria-labelledby="contained-modal-title-vcenter">
            <Modal.Header closeButton={false}>
                <Modal.Title id="contained-modal-title-vcenter">
                    <h2>Edit feature</h2>
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="show-grid">
                <Container>
                    {this.state.featureEditLayer ? this.renderFeatureForm(this.state.featureEditLayer) : null}
                </Container>
            </Modal.Body>
            <Modal.Footer>
                <Button onClick={() => this.saveLayer()}>Save</Button>
                <Button variant={"secondary"}
                        onClick={() => {
                            this.clearFormData()
                            this.setState({featureEditLayer: null, validationErrors: null})
                        }}>Cancel</Button>
                <Button variant={"danger"} onClick={() => {
                    this.state.featureEditLayer.waypointNamesFeatureGroup.clearLayers()
                    this.drawnItems.removeLayer(this.state.featureEditLayer)
                    this.clearFormData()
                }}>Delete
                </Button>
            </Modal.Footer>
        </Modal>
    }

    initialiseWaypoints(trackLayer) {
        return trackLayer.getLatLngs().map((position, index) => {
            let defaultValue = {
                name: "TP " + (index),
                gateType: "tp",
                timeCheck: true,
                gateWidth: 1,
                position: position
            }
            if (index === 0) {
                defaultValue = {
                    name: "SP",
                    gateType: "sp",
                    timeCheck: true,
                    gateWidth: 1,
                    position: position
                }
            } else if (index === trackLayer.getLatLngs().length - 1) {
                defaultValue = {
                    name: "FP",
                    gateType: "fp",
                    timeCheck: true,
                    gateWidth: 1,
                    position: position
                }
            }
            return defaultValue
        })
    }

    generateGateName(trackPoints) {
        const names = trackPoints.map((p) => {
            return p.name
        })
        let index = 1
        let name = "NEW"
        while (names.includes(name)) {
            name = "NEW" + index
            index++
        }
        return name
    }

    updateWaypoints(trackLayer) {
        const points = trackLayer.getLatLngs()
        let newTrackPoints = []
        let lastUsedPointIndex = 0
        if (points.length === trackLayer.trackPoints.length) {
            for (let i = 0; i < points.length; i++) {
                trackLayer.trackPoints[i].position = points[i]
            }
            return
        }
        for (let i = 0; i < points.length; i++) {
            let match = null
            for (let j = lastUsedPointIndex; j < trackLayer.trackPoints.length; j++) {
                if (points[i].lat.toFixed(6) === trackLayer.trackPoints[j].position.lat.toFixed(6) && points[i].lng.toFixed(6) === trackLayer.trackPoints[j].position.lng.toFixed(6)) {
                    match = trackLayer.trackPoints[j]
                    lastUsedPointIndex = j
                    break
                }
            }
            if (!match) {
                newTrackPoints.push({
                    name: this.generateGateName(trackLayer.trackPoints),
                    gateType: "tp",
                    timeCheck: true,
                    gateWidth: 1,
                    position: points[i]
                })
            } else {
                newTrackPoints.push(match)
            }
        }
        trackLayer.trackPoints = newTrackPoints
    }

    initialiseMap() {
        const Jawg_Sunny = L.tileLayer('https://{s}.tile.jawg.io/jawg-sunny/{z}/{x}/{y}{r}.png?access-token={accessToken}', {
            attribution: '<a href="http://jawg.io" title="Tiles Courtesy of Jawg Maps" target="_blank">&copy; <b>Jawg</b>Maps</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            minZoom: 0,
            maxZoom: 22,
            subdomains: 'abcd',
            accessToken: 'fV8nbLEqcxdUyjN5DXYn8OgCX8vdhBC5jYCkroqpgh6bzsEfb2hQkvDqRQs1GcXX'
        });
        const OpenAIP = L.tileLayer('http://{s}.tile.maps.openaip.net/geowebcache/service/tms/1.0.0/openaip_basemap@EPSG%3A900913@png/{z}/{x}/{y}.{ext}', {
            attribution: '<a href="http://www.openaip.net/">OpenAIP Data</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-NC-SA</a>)',
            ext: 'png',
            minZoom: 4,
            maxZoom: 14,
            tms: true,
            // detectRetina: true,
            subdomains: '1'
        });


        this.map = L.map('routeEditor', {
            zoomControl: true,
            preferCanvas: true,
            layers: [Jawg_Sunny]
        })
        console.log("Initialised map")
        // Jawg_Sunny.addTo(this.map)
        this.drawnItems = L.featureGroup().addTo(this.map)
        L.control.layers({
            "jawg": Jawg_Sunny,
            "google": L.tileLayer('http://www.google.cn/maps/vt?lyrs=s@189&gl=cn&x={x}&y={y}&z={z}', {
                attribution: 'google'
            })
        }, {"OpenAIP": OpenAIP}, {
            position: 'topleft',
            collapsed: false
        }).addTo(this.map);
        this.map.on("locationerror", (e) => {
            if (!this.props.routeId) {
                this.map.setView(L.latLng(59, 10.5), 7)
            }
        })
        if (!this.props.routeId) {
            this.map.locate({setView: true, maxZoom: 7})
        }
        this.drawControl = new L.Control.Draw({
            // edit: {
            //     featureGroup: this.drawnItems,
            //     poly: {
            //         allowIntersection: false
            //     }
            // },
            draw: this.drawingDisabledOptions
        })
        this.map.whenReady(() => {
            this.map.addControl(this.drawControl);
            this.mapReady = true
        })

        this.map.on(L.Draw.Event.EDITVERTEX, (event) => {
            console.log("editvertex")
            const layers = event.layers;
            layers.eachLayer((layer) => {
                console.log(layer)
                // if (layer.featureType === "track") {
                //     this.updateWaypoints(layer)
                // }
                this.renderWaypointNames(layer)
            })
        })
        this.map.on(L.Draw.Event.CREATED, (event) => {
            console.log(event)
            const layer = event.layer;

            let featureType = null
            let trackPoints = []
            if (this.isFeatureSelectable("track", false) && event.layerType === "polyline") {
                featureType = "track"
                trackPoints = this.initialiseWaypoints(layer)
            }
            this.configureLayer(layer, null, event.layerType, featureType, trackPoints, [0, 0], true)
            this.setState({featureEditLayer: layer})

        });

    }


    renderValidationErrors() {
        if (this.state.validationErrors) {
            return this.state.validationErrors.map((item) => {
                return <Toast bg={"danger"}>
                    <Toast.Header closeButton={false}>
                        <strong className="me-auto">Validation error</strong>
                    </Toast.Header>
                    <Toast.Body>{item}</Toast.Body>
                </Toast>
            })
        }
    }

    render() {
        if (this.mapReady) {
            if (this.state.globalEditingMode) {
                this.drawControl.setDrawingOptions(this.drawingEnabledOptions);
            } else {
                this.drawControl.setDrawingOptions(this.drawingDisabledOptions);
            }
            this.map.removeControl(this.drawControl)
            this.map.addControl(this.drawControl)
        }
        return <div>
            <div className={"toastContainer"}>
                {this.renderValidationErrors()}
                {this.state.changesSaved ? <Toast bg={"success"}>
                    <Toast.Header closeButton={false}>
                        <strong className="me-auto">Saved</strong>
                    </Toast.Header>
                    <Toast.Body>Route saved successfully</Toast.Body>
                </Toast> : null}
                {this.state.saveFailed ? <Toast bg={"danger"}>
                    <Toast.Header closeButton={false}>
                        <strong className="me-auto">Save failed</strong>
                    </Toast.Header>
                    <Toast.Body>{this.state.saveFailed}</Toast.Body>
                </Toast> : null}
            </div>
            <a href={"#"} className={"logoImageRE"} onClick={() => this.setState({displayTutorial: true})}>
                <img src={"/static/img/airsports_help.png"} style={{width: "50px"}} alt={"Help"}/>
            </a>

            {this.featureEditModal()}
            {this.waypointModal()}
            <div id="routeSaveButton">
                <Form.Control type={"string"} placeholder={"Route name"}
                              defaultValue={this.props.route ? this.props.route.name : ""}
                              onChange={(e) => this.setState({routeName: e.target.value})}/>
                <button className={"btn btn-primary"}
                        onClick={() => this.saveRoute()}>{this.state.globalEditingMode ? "Save" : "Edit"}</button>
                &nbsp;
                <button id="routeCancelButton" className={"btn btn-danger"}
                        onClick={() => this.reloadMap()}>Cancel
                </button>
                &nbsp;
                <button id="routeReturnButton" className={"btn btn-secondary"}
                        onClick={() => window.location = "/display/editableroute/"}>Route list
                </button>
            </div>
            {/*<IntroSlider slides={slides} size="fullscreen" handleDone={() => this.setState({displayTutorial: false})}*/}
            {/*                 handleClose={() => this.setState({displayTutorial: false})}/>*/}
            {this.state.displayTutorial ?
                <IntroSlider slides={slides} sliderIsOpen={this.state.displayTutorial} skipButton={true}
                             controllerOrientation={"horizontal"} size={"large"}
                             descriptionStyle={{fontSize: "1.1rem"}}
                             imageStyle={{padding: null}}
                             handleDone={() => this.setState({displayTutorial: false})}
                             handleClose={() => this.setState({displayTutorial: false})}/> : null}
        </div>
    }

}

const
    mapStateToProps = (state, props) => ({
            route: props.routeId
                ?
                state
                    .editableRoutes
                    [props.routeId] : null
        }

    )
const
    mapDispatchToProps =
        {
            fetchEditableRoute
        }

const
    RouteEditor = connect(mapStateToProps, mapDispatchToProps)(withRouter(ConnectedRouteEditor));
export default RouteEditor;