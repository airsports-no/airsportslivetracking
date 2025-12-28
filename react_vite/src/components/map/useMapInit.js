import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';

/**
 * Hook to initialize the Leaflet map and tile layers.
 * @returns {React.MutableRefObject} The map instance ref.
 */
export default function useMapInit() {
  const mapRef = useRef(null);
  const [, setReady] = useState(false);

  useEffect(() => {
    if (mapRef.current) return; // Prevent double init

    const map = L.map('map-container', { zoomControl: false }).setView([51.505, -0.09], 13);
    map.locate({ setView: true, maxZoom: 11 });

    // Tile Layers
    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const googleSat = L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
      attribution: '&copy; Google'
    });

    const openAip = L.tileLayer('https://api.tiles.openaip.net/api/data/openaip/{z}/{x}/{y}.png?apiKey={apiKey}', {
      maxZoom: 14,
      minZoom: 4,
      attribution: '<a href="https://www.openaip.net/">OpenAIP Data</a>',
      apiKey: '3d5d3f82528731731362a23f445951d8'
    });

    L.control.layers({
      "OpenStreetMap": osm,
      "Google Satellite": googleSat
    }, {
      "OpenAIP Data": openAip
    }, { position: 'bottomright' }).addTo(map);

    mapRef.current = map;
    setReady(true);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return mapRef;
}