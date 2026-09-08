import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Import images directly so Vite handles pathing.
import iconRetinaUrl from '/leaflet/marker-icon-2x.png';
import iconUrl from '/leaflet/marker-icon.png';
import shadowUrl from '/leaflet/marker-shadow.png';

// Fix for Leaflet's default icon path issue with bundlers.
// This directly manipulates the prototype to ensure all new markers
// use the correct, imported assets.
// @ts-ignore
delete L.Icon.Default.prototype._getIconUrl;

L.Icon.Default.mergeOptions({
  iconRetinaUrl: iconRetinaUrl,
  iconUrl: iconUrl,
  shadowUrl: shadowUrl,
});


/**
 * Hook to initialize the Leaflet map and tile layers.
 * @returns {React.MutableRefObject} The map instance ref.
 */
export default function useMapInit(): React.MutableRefObject<L.Map | null> {
  const mapRef = useRef<L.Map | null>(null);
  const [, setReady] = useState(false);

  useEffect(() => {
    if (mapRef.current) return; // Prevent double init

    const map = L.map('map-container', { zoomControl: false }).setView([51.505, -0.09], 13);

    mapRef.current = map;
    setReady(true);

    return () => {
      // Leaflet workaround (Sentry JAVASCRIPT-REACT-5): map.remove() stops pan/fly animations
      // and removes the map's DOM pane, but never resets _animatingZoom nor cancels the raw
      // setTimeout(_onZoomTransitionEnd, 250) that _animateZoom schedules. If we unmount mid
      // zoom-animation, that timeout later fires _onZoomTransitionEnd against an already-removed
      // map and crashes. _onZoomTransitionEnd's own first line is `if (!this._animatingZoom)
      // return;`, so forcing the flag off here makes the stale timeout a no-op.
      (map as unknown as { _animatingZoom?: boolean })._animatingZoom = false;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return mapRef;
}