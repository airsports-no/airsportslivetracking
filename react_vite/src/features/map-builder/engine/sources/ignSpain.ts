/**
 * Spain: the Base Topográfica Nacional (BTN) of the Instituto Geográfico Nacional, published as
 * vector tiles. Official survey data, CC BY 4.0. The attribute values below (`tipo_0605` and
 * friends) are the BTN's own feature-catalogue codes.
 */
import type { Bounds } from '../tiles';
import type { VectorSource } from './types';
import type { VectorTileRule } from './vectorTiles';
import { fetchVectorTiles } from './vectorTiles';

type Properties = Record<string, unknown>;

/** True when the attribute starts with any of the given code prefixes. */
const startsWith = (value: unknown, ...prefixes: string[]): boolean =>
    prefixes.some(prefix => String(value ?? '').startsWith(prefix));

const notMotorway = (p: Properties) => !startsWith(p.tipo_0605, '1');

export const IGN_RULES: Record<string, VectorTileRule> = {
    built_up: { tileLayers: ['btn0502s_ent_pob'] },
    quarry: { tileLayers: ['btn0540s_exp_min_s'] },
    solar_farm: { tileLayers: ['btn0713s_cen_elec'], match: p => /FOTOVOLTAICA|SOLAR/i.test(String(p.tipo_0713 ?? '')) },
    lake: {
        tileLayers: ['btn0325s_embalse', 'btn0316s_laguna', 'btn0328s_alm_agu', 'btn0302s_rio', 'btn0305s_cau_art'],
        match: (p, tileLayer) => tileLayer !== 'btn0328s_alm_agu' || !startsWith(p.tipo_0328, '01'),
    },
    stream: {
        tileLayers: ['btn0302l_rio'],
        match: p => !startsWith(p.persi_0302, '01') && !startsWith(p.compo_0302, '04'),
    },
    // Canals only: the BTN's irrigation ditches would swamp the map.
    canal: { tileLayers: ['btn0305l_cau_art'], match: p => startsWith(p.tipo_0305, '01') },
    river: {
        tileLayers: ['btn0302l_rio'],
        match: p => startsWith(p.persi_0302, '01') && !startsWith(p.compo_0302, '04'),
    },
    dam: { tileLayers: ['btn0552l_presa'] },
    track: { tileLayers: ['btn0623l_camino'] },
    local_road: {
        tileLayers: ['btn0605l_carretera'],
        match: p => notMotorway(p) && !startsWith(p.titul_0605, '01', '02', '03', '04'),
    },
    tertiary_road: { tileLayers: ['btn0605l_carretera'], match: p => notMotorway(p) && startsWith(p.titul_0605, '03', '04') },
    secondary_road: { tileLayers: ['btn0605l_carretera'], match: p => notMotorway(p) && startsWith(p.titul_0605, '02') },
    primary_road: { tileLayers: ['btn0605l_carretera'], match: p => notMotorway(p) && startsWith(p.titul_0605, '01') },
    motorway: { tileLayers: ['btn0605l_carretera'], match: p => !notMotorway(p) },
    railway: { tileLayers: ['btn0641l_fc_conv', 'btn0638l_fc_alt_vel', 'btn0644l_tra_esp'] },
    power_line: { tileLayers: ['btn0710l_lin_elec'], match: p => !startsWith(p.tensi_0710, '01') },
    minor_power_line: { tileLayers: ['btn0710l_lin_elec'], match: p => startsWith(p.tensi_0710, '01') },
    runway: { tileLayers: ['btn0662s_pis_ater'] },
    aerodrome: { tileLayers: ['btn0665s_zon_ater_s'] },
    peak: {
        tileLayers: ['btn0204p_pun_aco'],
        match: p => startsWith(p.tipo_0204, '02') && (!!p.nombre || !startsWith(p.jerar_0204, '05', '99')),
    },
    mast: { tileLayers: ['btn0725p_antena'] },
    castle: {
        tileLayers: ['btn0555s_con_his_s'],
        match: p => /CASTILLO|FORTALEZA|TORRE/i.test(String(p.tipo_0555 ?? '')),
    },
    mill: { tileLayers: ['btn0519s_molino'] },
    church: { tileLayers: ['btn0516s_edi_rel'] },
};

/** Rough outline of mainland Spain (the borders with Portugal and France; generous towards the sea). */
const MAINLAND: [number, number][] = [
    [-9.6, 43.9], [-8.9, 41.88], [-8.15, 42.2], [-6.6, 42.0], [-6.2, 41.6], [-6.95, 41.0], [-6.85, 40.25],
    [-7.05, 39.65], [-7.55, 39.65], [-7.05, 38.85], [-7.3, 38.2], [-6.95, 37.95], [-7.45, 37.15], [-7.6, 36.0],
    [-5.6, 35.7], [-2.0, 36.5], [-0.4, 37.4], [0.6, 38.7], [0.4, 39.9], [1.1, 40.7], [3.6, 42.0], [3.35, 42.45],
    [1.75, 42.45], [0.65, 42.85], [-0.75, 42.95], [-1.8, 43.35], [-1.6, 44.0], [-9.6, 44.0],
];

function pointInPolygon(x: number, y: number, polygon: [number, number][]): boolean {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const [xi, yi] = polygon[i];
        const [xj, yj] = polygon[j];
        if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
}

/** Whether the centre of the area is in Spain (mainland, Balearic Islands or Canary Islands). */
export function isInSpain(bounds: Bounds): boolean {
    const x = (bounds.west + bounds.east) / 2;
    const y = (bounds.south + bounds.north) / 2;
    return (
        pointInPolygon(x, y, MAINLAND) ||
        (x > 1.1 && x < 4.5 && y > 38.5 && y < 40.2) ||
        (x > -18.4 && x < -13.2 && y > 27.5 && y < 29.5)
    );
}

export const ignSpainSource: VectorSource = {
    id: 'ign-es',
    name: 'Spain: IGN National Topographic Base',
    shortName: 'IGN',
    description:
        'Official survey data from the Spanish Instituto Geográfico Nacional. Elements it does not have are filled in from OpenStreetMap.',
    attribution: 'BTN © IGN-CNIG (CC BY 4.0)',
    covers: isInSpain,
    layerIds: new Set(Object.keys(IGN_RULES)),
    fetch: (frame, _layerIds, context) => {
        // The detailed BTN layers (power lines, masts, mills) only exist from tile zoom 14.
        if (frame.zoom < 13) {
            context.reporter.log(
                'Note: below zoom 13 the IGN data has no power lines, masts or mills. Use a detail zoom of 13 or 14 to get them.',
                'warning',
            );
        }
        return fetchVectorTiles(
            {
                label: 'IGN Spain data',
                // This server orders its path row before column.
                tileUrl: (zoom, x, y) => `https://vt-btn.idee.es/1.0.0/btn/tile/${zoom}/${y}/${x}.pbf`,
                tileZoomFor: frameZoom => (frameZoom >= 13 ? 14 : 13),
                rules: IGN_RULES,
                // No tile exists over open sea, and the 404 comes without CORS headers.
                networkErrorMeansEmpty: true,
            },
            frame,
            context,
        );
    },
};
