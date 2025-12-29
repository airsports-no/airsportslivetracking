import React, { useEffect, useRef } from 'react';
import L from 'leaflet';

const ObservationThumbnail = ({ lat, lng, type = 'circle' }) => {
  const mapContainerRef = useRef(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [lat, lng],
      zoom: 16,
      zoomControl: false,
      attributionControl: false,
      dragging: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      touchZoom: false,
      boxZoom: false,
      keyboard: false
    });

    L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
    }).addTo(map);

    if (type === 'circle') {
      L.circle([lat, lng], {
        radius: 100,
        color: '#eab308',
        weight: 2,
        fill: false
      }).addTo(map);
    } else {
      // Pin for waypoints
      const icon = L.divIcon({
        className: 'bg-transparent',
        html: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#ef4444" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 100%; height: 100%; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3" fill="white"></circle></svg>`,
        iconSize: [32, 32],
        iconAnchor: [16, 32]
      });
      
      L.marker([lat, lng], { icon }).addTo(map);
    }

    return () => {
      map.remove();
    };
  }, [lat, lng, type]);

  return <div ref={mapContainerRef} className="w-full h-64 rounded border border-base-300 mt-2 bg-base-200" />;
};

export default ObservationThumbnail;