import L from 'leaflet';

// Creates a DivIcon with a rotated airplane-like SVG, colored per contestant and labeled with contestant number
export function planeIcon(number: number, color: string, headingDeg: number): L.DivIcon {
  const size = 28;
  const svg = `
    <div style="position: relative; width: ${size}px; height: ${size}px;">
      <div style="position:absolute; left:0; top:0; width:${size}px; height:${size}px; transform: rotate(${headingDeg}deg); transform-origin: 50% 50%;">
        <svg viewBox="0 0 100 100" width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg">
          <g>
            <!-- Simple aircraft arrow -->
            <polygon points="50,5 65,50 50,45 35,50" fill="${color}" stroke="#111" stroke-width="2" />
            <!-- tail -->
            <rect x="47" y="45" width="6" height="40" fill="${color}" stroke="#111" stroke-width="2" />
            <!-- wings -->
            <polygon points="20,55 80,55 75,65 25,65" fill="${color}" opacity="0.8" />
          </g>
        </svg>
      </div>
      <div style="position:absolute; left:50%; top:50%; transform: translate(-50%, -50%); font-size:10px; font-weight:700; color:#fff; text-shadow: 0 0 2px #000;">
        ${number}
      </div>
    </div>`;

  return L.divIcon({
    className: 'plane-icon',
    html: svg,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}
