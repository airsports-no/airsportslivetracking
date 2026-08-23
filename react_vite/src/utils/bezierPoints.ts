import { LatLng } from "../types";
import L from "leaflet";

// Split out of geoUtils.ts because this is the only function there that
// needs Leaflet (for its L.LatLng return type) - keeping it isolated lets
// geoUtils.ts's other pure math be imported and tested without a DOM.
export function getQuadraticBezierPoints(p1: LatLng, p2: LatLng, control: LatLng, numPoints = 20): L.LatLng[] {
  const points: L.LatLng[] = [];
  for (let i = 0; i <= numPoints; i++) {
    const t = i / numPoints;
    const lat = (1 - t) * (1 - t) * p1.lat + 2 * (1 - t) * t * control.lat + t * t * p2.lat;
    const lng = (1 - t) * (1 - t) * p1.lng + 2 * (1 - t) * t * control.lng + t * t * p2.lng;
    points.push(L.latLng(lat, lng));
  }
  return points;
}
