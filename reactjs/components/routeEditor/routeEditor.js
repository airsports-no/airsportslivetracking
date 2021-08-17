import React, {Component} from "react";
import {connect} from "react-redux";
// import "leaflet-draw/dist/leaflet.draw.css"
// import 'leaflet-draw/dist/images/layers.png'
// import "leaflet/dist/leaflet.css"
// import Draw from "leaflet-draw"
// import L from "leaflet";
import "leaflet";
import "leaflet-draw";
import {Button, Container, Form, Modal, Row, Col, ToastContainer, Toast} from "react-bootstrap";
import {divIcon, marker} from "leaflet";
import {fetchEditableRoute} from "../../actions";
import axios from "axios";
import {Link, withRouter} from "react-router-dom";

const gateTypes = [
    ["Starting point", "sp"],
    ["Finish point", "fp"],
    ["Turning point", "tp"],
    ["Secret gate", "secret"]
]

const featureStyles = {
    "track": {"color": "blue"},
    "to": {"color": "green"},
    "ldg": {"color": "red"},
    "prohibited": {"color": "red"},
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

class ConnectedRouteEditor extends Component {
    constructor(props) {
        super(props)
        this.map = null
        this.state = {
            featureEditLayer: null,
            featureType: null,
            currentName: null,
            routeName: null,
            gateType: null,
            timeCheck: null,
            gateCheck: null,
            changesSaved: false
        }
    }

    componentDidMount() {
        this.initialiseMap()
        if (this.props.routeId) {
            this.reloadMap()
        }
    }

    reloadMap() {
        this.setState({changesSaved: false, validationErrors: null, saveFailed: null})
        this.props.fetchEditableRoute(this.props.routeId)
    }


    componentDidUpdate(prevProps, prevState, snapshot) {
        console.log("routeId: " + this.props.routeId)
        if (this.props.route !== prevProps.route && this.props.route) {
            this.renderRoute()
        }
    }

    handleSaveSuccess(id) {
        this.setState({changesSaved: true, saveFailed: null})
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
        let features = []
        let errors = []
        for (let l of this.drawnItems.getLayers()) {
            errors = errors.concat(this.validateLayer(l))
            if (["polyline", "rectangle", "polygon"].includes(l.layerType)) {
                features.push({
                    name: l.name,
                    layer_type: l.layerType,
                    track_points: l.trackPoints,
                    feature_type: l.featureType,
                    geojson: l.toGeoJSON()
                })
            }
        }
        this.setState({validationErrors: errors})
        if (errors.length > 0) {
            return
        }
        let method = "post", url = "/api/v1/editableroutes/"
        let name = this.state.routeName
        if (this.props.routeId) {
            method = "put"
            url += this.props.routeId + "/"
            if (this.state.routeName) {
                name = this.state.routeName
            } else {
                name = this.props.route.name
            }
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

    configureLayer(layer, name, layerType, featureType, trackPoints) {
        layer.addTo(this.drawnItems);
        layer.name = name
        layer.layerType = layerType
        layer.featureType = featureType
        layer.trackPoints = trackPoints
        layer.waypointNamesFeatureGroup = L.featureGroup().addTo(this.drawnItems);
        layer.on("click", (item) => {
            const layer = item.target
            this.setState({featureEditLayer: layer})
        })
        layer.on("edit", (item) => {
            const layer = item.target
            this.renderWaypointNames(layer)
        })
        layer.setStyle(featureStyles[featureType])
        this.renderWaypointNames(layer)
    }

    renderRoute() {
        this.drawnItems.clearLayers()
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
                            this.map.fitBounds(layer.getBounds(), {padding: [50, 50]})
                        }
                        this.configureLayer(layer, r.name, r.layer_type, r.feature_type, r.track_points)
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

    validateLayer(layer) {
        let errors = []
        console.log("Validation")
        console.log(layer)
        if (layer.featureType === "track") {
            if (layer.getLatLngs().length < 2) {
                errors.push("A track must have at least two waypoints")
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
            const finishPoints = layer.trackPoints.filter((item) => {
                return item.gateType === "fp"
            })
            if (!finishPoints || finishPoints.length !== 1) {
                errors.push("The track must contain exactly one finish point")
            }
        }
        if (layer.featureType === "to" || layer.featureType === "to") {
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

    saveLayer() {
        if (this.state.featureType) {
            this.state.featureEditLayer.featureType = this.state.featureType
        }
        if (this.state.featureEditLayer.name === undefined || this.state.featureEditLayer.name === "") {
            this.state.featureEditLayer.name = featureTypes[this.state.featureEditLayer.layerType].find((item) => {
                return item[1] === this.state.featureEditLayer.featureType
            })[0]
        }
        if (this.state.currentName) {
            this.state.featureEditLayer.name = this.state.currentName
        }
        let trackPoints = []
        if (this.state.featureEditLayer.featureType === "track") {
            const positions = this.state.featureEditLayer.getLatLngs()
            for (let i = 0; i < positions.length; i++) {
                trackPoints.push({
                    ...this.existingWaypointConfiguration[i],
                    ...this.state["waypointname" + i] || {}
                })
            }
        }
        this.state.featureEditLayer.setStyle(featureStyles[this.state.featureEditLayer.featureType])
        this.state.featureEditLayer.trackPoints = trackPoints
        this.state.featureEditLayer.editing.disable()
        this.state.featureEditLayer.initialSaved = true
        this.renderWaypointNames(this.state.featureEditLayer)
        console.log(this.state.featureEditLayer)
        const errors = this.validateLayer(this.state.featureEditLayer)
        this.setState({validationErrors: errors})
        if (errors.length === 0) {
            this.setState({
                featureEditLayer: null,
                featureType: null,
                currentName: null,
                gateType: null,
                timeCheck: null,
                gateCheck: null,
                changesSaved: false
            })
        }
    }

    renderWaypointNames(track) {
        track.unbindTooltip()
        if (track.featureType === "track") {
            track.name = "Track"
            track.waypointNamesFeatureGroup.clearLayers()
            let index = 0
            for (let p of track.getLatLngs()) {
                const m = marker([p.lat, p.lng], {
                    color: "blue",
                    icon: divIcon({
                        html: '<i class="fas"">' + (track.trackPoints.length > index ? track.trackPoints[index].name : "Unknown") + '</i>',
                        iconSize: [20, 20],
                        iconAnchor: [10, -10],
                        className: "myGateIcon",

                    })
                }).addTo(track.waypointNamesFeatureGroup)
                index += 1
            }
        } else {
            track.bindTooltip(track.name, {permanent: true})
        }
    }

    trackContent() {
        this.existingWaypointConfiguration = []
        return <Form.Group>
            {this.state.featureEditLayer.getLatLngs().map((position, index) => {
                let defaultValue = {
                    name: "TP " + (index),
                    gateType: "tp",
                    timeCheck: true,
                    gateCheck: true,
                    gateWidth: 1
                }
                if (index === 0) {
                    defaultValue = {
                        name: "SP",
                        gateType: "sp",
                        timeCheck: true,
                        gateCheck: true,
                        gateWidth: 1
                    }
                } else if (index === this.state.featureEditLayer.getLatLngs().length - 1) {
                    defaultValue = {
                        name: "FP",
                        gateType: "fp",
                        timeCheck: true,
                        gateCheck: true,
                        gateWidth: 1
                    }
                }
                defaultValue = this.state.featureEditLayer && this.state.featureEditLayer.trackPoints && this.state.featureEditLayer.trackPoints.length > index ? this.state.featureEditLayer.trackPoints[index] : defaultValue
                this.existingWaypointConfiguration.push(defaultValue)
                return <div>
                    <Row>
                        <Form.Label>Waypoint {index + 1}</Form.Label>
                    </Row>
                    <Row key={"waypoint" + index}>
                        <Col xs={"auto"}>
                            <Form.Control type={"string"} placeholder={"Name"}
                                          defaultValue={defaultValue.name}
                                          onChange={(e) => this.setState({["waypointname" + index]: {["name"]: e.target.value}})}/>
                        </Col>
                        <Col xs={"auto"}>
                            <Form.Control as="select" onChange={e => {
                                console.log("e.target.value", e.target.value);
                                this.setState({["waypointname" + index]: {["gateType"]: e.target.value}});
                            }} defaultValue={defaultValue.gateType}>
                                {gateTypes.map((item) => {
                                    return <option value={item[1]}>{item[0]}</option>
                                })}
                            </Form.Control>

                        </Col>
                        <Col xs={"auto"}>
                            <Form.Control key={"gateCheck"} placeholder={"Width"}
                                          type={"number"}
                                          onChange={(e) => {
                                              this.setState({["waypointname" + index]: {["gateWidth"]: e.target.value}})
                                          }
                                          } defaultValue={defaultValue.gateWidth}/>
                        </Col>
                        <Col xs={"auto"}>
                            <Form.Check inline key={"gateCheck"} name={"gateCheck"} label={"Gate check"}
                                        type={"checkbox"}
                                        onChange={(e) => {
                                            this.setState({["waypointname" + index]: {["gateCheck"]: e.target.value}})
                                        }
                                        } defaultChecked={defaultValue.gateCheck}/>
                        </Col>
                        <Col xs={"auto"}>
                            <Form.Check inline key={"timeCheck"} name={"timeCheck"} label={"Time check"}
                                        type={"checkbox"}
                                        onChange={(e) => {
                                            this.setState({["waypointname" + index]: {["timeCheck"]: e.target.value}})
                                        }
                                        } defaultChecked={defaultValue.timeCheck}/>
                        </Col>
                    </Row>
                    <hr/>
                </div>
            })}
        </Form.Group>
    }

    isFeatureSelectable(featureType, checked) {
        const usedFeatureTypes = this.existingFeatureTypes()
        const limits = featureTypeCounts[this.props.routeType][featureType]
        return checked || usedFeatureTypes[featureType] === undefined || usedFeatureTypes[featureType] < limits[1];
    }

    renderFeatureSelect(layerType, current) {
        const currentFeatureType = this.state.featureType || current
        let options = featureTypes[layerType] || []
        const checkboxes = options.map((item) => {
            const checked = current === item[1]
            return <Form.Check inline key={item[1]} name={"featureType"} label={item[0]} type={"radio"}
                               onChange={(e) => {
                                   this.setState({featureType: item[1]})
                               }
                               } disabled={!this.isFeatureSelectable(item[1], checked)} defaultChecked={checked}/>
        })
        let extra = null
        if (currentFeatureType === "track") {
            extra = this.trackContent()
        }
        return <div>
            {checkboxes}
            {extra}
        </div>

    }

    renderFeatureForm(layer) {
        return <Form>
            <div className={"alert-danger"}>
                <ul>{this.state.validationErrors ? this.state.validationErrors.map((item) =>
                    <li>{item}</li>) : null}</ul>
            </div>
            {layer.layerType !== "polyline" ?
                <div>
                    <Form.Label>Feature name:</Form.Label>&nbsp;
                    <Form.Control name={"feature_name"} type={"string"} placeholder={"Name"}
                                  defaultValue={layer.name}
                                  onChange={(e) => this.setState({currentName: e.target.value})}
                    />
                </div> : null
            }
            {this.renderFeatureSelect(layer.layerType, layer.featureType)}
        </Form>
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
                        onClick={() => this.setState({featureEditLayer: null, validationErrors: null})}>Cancel</Button>
                {this.state.featureEditLayer && !this.state.featureEditLayer.editing.enabled() ?
                    <Button onClick={() => {
                        this.state.featureEditLayer.editing.enable()
                        this.setState({featureEditLayer: null})
                    }}>Edit points</Button> : null}
                <Button variant={"danger"} onClick={() => {
                    this.state.featureEditLayer.waypointNamesFeatureGroup.clearLayers()
                    this.drawnItems.removeLayer(this.state.featureEditLayer)
                    this.setState({featureEditLayer: null})
                }}>Delete
                </Button>
            </Modal.Footer>
        </Modal>
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
            attribution: '<a href="https://www.openaip.net/">openAIP Data</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-NC-SA</a>)',
            ext: 'png',
            minZoom: 4,
            maxZoom: 14,
            tms: true,
            detectRetina: true,
            subdomains: 'abcd'
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
        }, {'drawlayer': this.drawnItems, "OpenAIP": OpenAIP}, {
            position: 'topleft',
            collapsed: false
        }).addTo(this.map);
        this.map.on("locationerror", (e) => {
            this.map.setView(L.latLng(59, 10.5), 7)
        })
        this.map.locate({setView: true, maxZoom: 7})

        this.map.addControl(new L.Control.Draw({
            // edit: {
            //     featureGroup: this.drawnItems,
            //     poly: {
            //         allowIntersection: false
            //     }
            // },
            draw: {
                marker: false,
                rectangle: false,
                circle: false,
                circlemarker: false,
                polygon: {
                    allowIntersection: false,
                    showArea: true
                }
            }
        }));
        this.map.on(L.Draw.Event.EDITED, (event) => {
            const layers = event.layers;
            layers.eachLayer((layer) => {
                console.log(layer)
                if (this.checkIfUpdateIsNeeded(layer)) {
                    this.setState({featureEditLayer: layer})
                    return
                }
                this.renderWaypointNames(layer)
            })
        })
        this.map.on(L.Draw.Event.CREATED, (event) => {
            console.log(event)
            const layer = event.layer;
            this.configureLayer(layer, null, event.layerType, null, [])
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
            {this.featureEditModal()}
            <div id="routeSaveButton">
                <Form.Control type={"string"} placeholder={"Route name"}
                              defaultValue={this.props.route ? this.props.route.name : ""}
                              onChange={(e) => this.setState({routeName: e.target.value})}/>
                <button className={"btn btn-primary"} onClick={() => this.saveRoute()}>Save</button>
                &nbsp;
                <button id="routeCancelButton" className={"btn btn-danger"}
                        onClick={() => this.reloadMap()}>Cancel
                </button>
                &nbsp;
                <button id="routeReturnButton" className={"btn btn-secondary"}
                        onClick={() => window.location = "/display/editableroute/"}>Map list
                </button>
            </div>
        </div>
    }

}

const
    mapStateToProps = (state, props) => (
        {
            route: props.routeId ? state.editableRoutes[props.routeId] : null
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