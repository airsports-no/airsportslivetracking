export interface RouteData {
  settings: {
    showCorridor?: boolean;
    maxObsDist?: number;
    hideLabels?: boolean;
    selectedTaskTemplateId?: string | null;
  };
  route: any; // This will contain the GeoJSON FeatureCollection
  name: string;
  id?: number; // Present on saved routes
}

export interface MapSource {
  key: string;
  label: string;
  origin: 'builtin' | 'user_upload';
  source_group?: 'external_base' | 'system_overlay' | 'uploaded_overlay';
  type: 'mbtiles' | 'raster_xyz';
  tile_url: string;
  attribution: string;
  min_zoom: number;
  max_zoom: number;
  default_zoom: number | null;
  is_overlay: boolean;
  allow_multiple: boolean;
  is_always_on_top: boolean;
  bounds?: [number, number, number, number] | null;
}

export interface SavePayload {
  name: string;
  route: any; // GeoJSON FeatureCollection
  settings: {
    showCorridor: boolean;
    maxObsDist: number;
    hideLabels: boolean;
    selectedTaskTemplateId?: string | null;
  };
}
