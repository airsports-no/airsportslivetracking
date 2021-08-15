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

// const L = window['L']


class ConnectedRouteEditor extends Component {
    constructor(props) {
        super(props)
        this.map = null
        this.state = {featureEditLayer: null, currentName: null}
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
        this.waypointNamesLayer.clearLayers()
        let index = 0
        for (let p of track.trackPoints) {
            const m = marker([p.latitude, p.longitude], {
                color: "blue",
                icon: divIcon({
                    html: '<i class="fas"><br/>' + p.name + '</i>',
                    iconSize: [60, 20],
                    className: "myGateIcon"
                })
            }).addTo(this.waypointNamesLayer)
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

                    {this.state.featureEditLayer && this.state.featureEditLayer.layerType === "polyline" ? this.trackContent() : <div><Form.Label>Feature name:</Form.Label>&nbsp;
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

    componentDidMount() {
        this.initialiseMap()
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
        this.waypointNamesLayer = L.featureGroup().addTo(this.map);
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

        this.map.on(L.Draw.Event.CREATED, (event) => {
            const layer = event.layer;
            console.log(event)
            layer.layerType = event.layerType
            layer.on("click", (item) => {
                console.log("Clicked on")
                console.log(item)
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
        </div>
    }

}

const
    mapStateToProps = (state, props) => ({})
const
    mapDispatchToProps = {}

const
    RouteEditor = connect(mapStateToProps, mapDispatchToProps)(ConnectedRouteEditor);
export default RouteEditor;