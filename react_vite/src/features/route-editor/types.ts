export interface RouteData {
    settings: {
        showCorridor?: boolean;
        maxObsDist?: number;
        hideLabels?: boolean;
    };
    route: any; // This will contain the GeoJSON FeatureCollection
    name: string;
    id?: number; // Present on saved routes
}

export interface SavePayload {
    name: string;
    route: any; // GeoJSON FeatureCollection
    settings: {
        showCorridor: boolean;
        maxObsDist: number;
        hideLabels: boolean;
    };
}
