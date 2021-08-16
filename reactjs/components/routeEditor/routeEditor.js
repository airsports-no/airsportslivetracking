import React, {Component} from "react";
import {connect} from "react-redux";
// import "leaflet-draw/dist/leaflet.draw.css"
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


class ConnectedRouteEditor extends Component {
    constructor(props) {
        super(props)
        this.map = null
        this.state = {featureEditLayer: null, currentName: null}
    }

    componentDidMount() {
        this.initialiseMap()
        if (this.props.routeId) {
            this.props.fetchEditableRoute(this.props.routeId)
        }
    }


    componentDidUpdate(prevProps, prevState, snapshot) {
        console.log("routeId: " + this.props.routeId)
        if (this.props.route !== prevProps.route) {
            this.renderRoute()
        }
    }

    handleSaveSuccess(id) {
        this.props.history.push("/routeeditor/" + id + "/")
    }

    saveRoute() {
        let features = []
        for (let l of this.drawnItems.getLayers()) {
            if (l.trackPoints !== undefined) {
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
        if (this.props.routeId) {
            method = "put"
            url += this.props.routeId + "/"
        }
        axios({
            method: method,
            url: url,
            data: {route: features, name: "Test"}
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
                        layer.trackPoints = r.track_points
                        layer.waypointNamesFeatureGroup = L.featureGroup().addTo(this.drawnItems);
                        layer.on("click", (item) => {
                            const layer = item.target
                            this.setState({featureEditLayer: layer})
                        })
                        // layer.addTo(this.drawnItems)
                        // if (r.layer_type === "polyline") {
                        this.renderWaypointNames(layer)
                    }
                }
            )
        }
    }

    saveLayer() {
        this.state.featureEditLayer.name = this.state.currentName
        if (this.state.featureEditLayer.layerType === "polyline") {
            let trackPoints = []
            const positions = this.state.featureEditLayer.getLatLngs()
            for (let i = 0; i < positions.length; i++) {
                try {
                    trackPoints.push({
                        latitude: positions[i].lat,
                        longitude: positions[i].lng,
                        name: this.state["waypointname" + i] || this.existingWaypointNames[i]
                    })
                } catch (e) {
                    console.log(e)
                    alert("Waypoint " + (i + 1) + " does not have a name")
                }
            }
            this.state.featureEditLayer.trackPoints = trackPoints
            this.renderWaypointNames(this.state.featureEditLayer)
        } else {
            this.state.featureEditLayer.bindTooltip(this.state.currentName, {permanent: true})
        }
        console.log(this.state.featureEditLayer)
        this.setState({featureEditLayer: null})
    }

    renderWaypointNames(track) {
        track.waypointNamesFeatureGroup.clearLayers()
        let index = 0
        for (let p of track.trackPoints) {
            const m = marker([p.latitude, p.longitude], {
                color: "blue",
                icon: divIcon({
                    html: '<i class="fas"><br/>' + p.name + '</i>',
                    iconSize: [60, 20],
                    className: "myGateIcon"
                })
            }).addTo(track.waypointNamesFeatureGroup)
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

                    {this.state.featureEditLayer && this.state.featureEditLayer.layerType === "polyline" ? this.trackContent() :
                        <div><Form.Label>Feature name:</Form.Label>&nbsp;
                            <Form.Control name={"feature_name"} type={"string"} placeholder={"Name"}
                                          defaultValue={this.state.featureEditLayer ? this.state.featureEditLayer.name : null}
                                          onChange={(e) => this.setState({currentName: e.target.value})}
                            /></div>}
                </Container>
            </Modal.Body>
            <Modal.Footer>
                <Button onClick={() => this.saveLayer()}>Save</Button>
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
            edit: {
                featureGroup: this.drawnItems,
                poly: {
                    allowIntersection: false
                }
            },
            draw: {
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
            this.drawnItems.addLayer(layer);
            this.setState({featureEditLayer: layer})
        });

    }

    render() {
        return <div>
            {this.featureEditModal()}
            <button id="routeSaveButton" onClick={() => this.saveRoute()}>Save</button>
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