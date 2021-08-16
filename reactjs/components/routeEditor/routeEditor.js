import React, {Component} from "react";
import {connect} from "react-redux";
// import "leaflet-draw/dist/leaflet.draw.css"
// import 'leaflet-draw/dist/images/layers.png'
// import "leaflet/dist/leaflet.css"
// import Draw from "leaflet-draw"
// import L from "leaflet";
import "leaflet";
import "leaflet-draw";
import {Button, Container, Form, Modal, Row} from "react-bootstrap";
import {divIcon, marker} from "leaflet";
import {fetchEditableRoute} from "../../actions";
import axios from "axios";
import {Link, withRouter} from "react-router-dom";

const featureTypes = {
    polyline: [["Track", "track"], ["Takeoff gate", "to"], ["Landing gate", "ldg"]],
    polygon: [["Prohibited area", "prohibited"], ["Information zone", "info"], ["Gate area", "gate"]],
    rectangle: [["Prohibited area", "prohibited"], ["Information zone", "info"], ["Gate area", "gate"]]
}

class ConnectedRouteEditor extends Component {
    constructor(props) {
        super(props)
        this.map = null
        this.state = {featureEditLayer: null, featureType: null, currentName: null, routeName: null}
    }

    componentDidMount() {
        this.initialiseMap()
        if (this.props.routeId) {
            this.reloadMap()
        }
    }

    reloadMap() {
        this.props.fetchEditableRoute(this.props.routeId)
    }


    componentDidUpdate(prevProps, prevState, snapshot) {
        console.log("routeId: " + this.props.routeId)
        if (this.props.route !== prevProps.route && this.props.route) {
            this.renderRoute()
        }
    }

    handleSaveSuccess(id) {
        this.props.history.push("/routeeditor/" + id + "/")
    }


    saveRoute() {
        let features = []
        for (let l of this.drawnItems.getLayers()) {
            if (["polyline", "rectangle", "polygon"].includes(l.layerType)) {
                if (this.checkIfUpdateIsNeeded(l)) {
                    this.setState({featureEditLayer: l})
                    return
                }
                features.push({
                    name: l.name,
                    layer_type: l.layerType,
                    track_points: l.trackPoints,
                    feature_type: l.featureType,
                    geojson: l.toGeoJSON()
                })
            }
        }
        let method = "post", url = "/api/v1/editableroutes/"
        let name = this.state.routeName
        if (!name) {

        }
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
            data: {route: features, name: name}
        }).then((res) => {
            console.log("Response")
            console.log(res)
            this.handleSaveSuccess(res.data.id)
        }).catch((e) => {
            console.error(e);
            console.log(e);
        }).finally(() => {
        })
    }

    renderRoute() {
        this.drawnItems.clearLayers()
        console.log(this.props.route)
        for (let r of this.props.route.route) {
            let layer = new L.GeoJSON(r.geojson, {
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
                        layer.addTo(this.drawnItems);
                        layer.name = r.name
                        layer.layerType = r.layer_type
                        layer.featureType = r.feature_type
                        layer.trackPoints = r.track_points
                        layer.waypointNamesFeatureGroup = L.featureGroup().addTo(this.drawnItems);
                        layer.on("click", (item) => {
                            const layer = item.target
                            this.setState({featureEditLayer: layer})
                        })
                        layer.on("edit", (item) => {
                            const layer = item.target
                            this.renderWaypointNames(layer)
                        })
                        // layer.addTo(this.drawnItems)
                        // if (r.layer_type === "polyline") {
                        this.renderWaypointNames(layer)
                    }
                }
            )
        }
    }

    checkIfUpdateIsNeeded(layer) {
        if (layer.layerType === "polyline") {
            if (layer.getLatLngs().length !== layer.trackPoints.length) {
                layer.errors = "The length of points and the length of the names do not match"
                return true
            }
        }
        layer.errors = null
        return false
    }

    saveLayer() {
        this.state.featureEditLayer.name = this.state.currentName
        if (this.state.featureEditLayer.layerType === "polyline") {
            let trackPoints = []
            const positions = this.state.featureEditLayer.getLatLngs()
            for (let i = 0; i < positions.length; i++) {
                try {
                    trackPoints.push({
                        name: this.state["waypointname" + i] || this.existingWaypointNames[i]
                    })
                } catch (e) {
                    console.log(e)
                    alert("Waypoint " + (i + 1) + " does not have a name")
                }
            }
            this.state.featureEditLayer.trackPoints = trackPoints
        }
        this.state.featureEditLayer.editing.disable()
        this.renderWaypointNames(this.state.featureEditLayer)
        if (this.state.featureType) {
            this.state.featureEditLayer.featureType = this.state.featureType
        }
        console.log(this.state.featureEditLayer)
        this.setState({featureEditLayer: null, featureType: null})
    }

    renderWaypointNames(track) {
        if (track.layerType === "polyline") {
            track.waypointNamesFeatureGroup.clearLayers()
            let index = 0
            for (let p of track.getLatLngs()) {
                const m = marker([p.lat, p.lng], {
                    color: "blue",
                    icon: divIcon({
                        html: '<i class="fas"">' + track.trackPoints[index].name + '</i>',
                        iconSize: [20, 20],
                        iconAnchor: [10, -10],
                        className: "myGateIcon",

                    })
                }).addTo(track.waypointNamesFeatureGroup)
                index += 1
            }
        } else {
            track.unbindTooltip()
            track.bindTooltip(track.name, {permanent: true})
        }
    }

    trackContent() {
        this.existingWaypointNames = []
        return <Form.Group>
            {this.state.featureEditLayer.getLatLngs().map((position, index) => {
                let defaultName = "TP " + (index)
                if (index === 0) {
                    defaultName = "SP"
                } else if (index === this.state.featureEditLayer.getLatLngs().length - 1) {
                    defaultName = "FP"
                }
                const defaultValue = this.state.featureEditLayer && this.state.featureEditLayer.trackPoints && this.state.featureEditLayer.trackPoints.length > index ? this.state.featureEditLayer.trackPoints[index].name : defaultName
                this.existingWaypointNames.push(defaultValue)
                return <Row key={"waypoint" + index}>
                    <Form.Label>Waypoint {index + 1}</Form.Label>
                    <Form.Control type={"string"} placeholder={"Name"}
                                  defaultValue={defaultValue}
                                  onChange={(e) => this.setState({["waypointname" + index]: e.target.value})}/>
                </Row>
            })}
        </Form.Group>
    }

    renderFeatureSelect(layerType, current) {
        let options = featureTypes[layerType] || []
        return options.map((item) => {
            console.log(item)
            return <Form.Check inline key={item[1]} name={"featureType"} label={item[0]} type={"radio"} onChange={(e) => {
                this.setState({featureType: item[1]})
            }} defaultChecked={current === item[1]}/>
        })
    }

    featureEditModal() {
        return <Modal onHide={() => this.setState({featureEditLayer: null})}
                      show={this.state.featureEditLayer !== null}
                      aria-labelledby="contained-modal-title-vcenter">
            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    <h2>Edit feature</h2>
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="show-grid">
                <Container>
                    {this.state.featureEditLayer && this.state.featureEditLayer.errors ?
                        <div className={"alert-danger"}>{this.state.featureEditLayer.errors}</div> : null}
                    {this.state.featureEditLayer && this.state.featureEditLayer.layerType === "polyline" ? this.trackContent() :
                        <div><Form.Label>Feature name:</Form.Label>&nbsp;
                            <Form.Control name={"feature_name"} type={"string"} placeholder={"Name"}
                                          defaultValue={this.state.featureEditLayer ? this.state.featureEditLayer.name : null}
                                          onChange={(e) => this.setState({currentName: e.target.value})}
                            /></div>}
                    {this.state.featureEditLayer ?
                        this.renderFeatureSelect(this.state.featureEditLayer.layerType, this.state.featureEditLayer.featureType)
                        : null}
                </Container>
            </Modal.Body>
            <Modal.Footer>
                <Button onClick={() => this.saveLayer()}>Save</Button>
                {this.state.featureEditLayer && !this.state.featureEditLayer.editing.enabled() ?
                    <Button onClick={() => {
                        this.state.featureEditLayer.editing.enable()
                        this.setState({featureEditLayer: null})
                    }}>Edit points</Button> : null}
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
            const layer = event.layer;
            console.log(event)
            layer.layerType = event.layerType
            layer.waypointNamesFeatureGroup = L.featureGroup().addTo(this.drawnItems);
            layer.on("click", (item) => {
                const layer = item.target
                this.setState({featureEditLayer: layer})
            })
            layer.on("edit", (item) => {
                const layer = item.target
                this.renderWaypointNames(layer)
            })
            this.drawnItems.addLayer(layer);
            this.setState({featureEditLayer: layer})
        });

    }

    render() {
        return <div>
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
            </div>
        </div>
    }

}

const
    mapStateToProps = (state, props) => ({
        route: props.routeId ? state.editableRoutes[props.routeId] : null
    })
const
    mapDispatchToProps = {
        fetchEditableRoute
    }

const
    RouteEditor = connect(mapStateToProps, mapDispatchToProps)(withRouter(ConnectedRouteEditor));
export default RouteEditor;