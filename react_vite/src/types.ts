export interface Editor {
  email: string;
  first_name: string;
  last_name: string;
}

export interface Route {
  id: number;
  name: string;
  number_of_waypoints: number;
  route_length: number;
  editors: Editor[];
  thumbnail: string;
  is_editor: boolean;
}

export interface LatLng {
  lat: number;
  lng: number;
}

export interface RoutePoint extends LatLng {
  id: string;
  name: string;
  type: "sp" | "tp" | "secret" | "fp";
  segmentType: "straight" | "curved";
  controlLat?: number;
  controlLng?: number;
  width: number;
  isTiming: boolean;
  isPassing: boolean;
  isSecret?: boolean;
}

export interface Gate {
  id: string;
  name: string;
  type: "landing" | "takeoff";
  p1: LatLng;
  p2: LatLng;
  width: number;
}

export interface ObservationMarker extends LatLng {
  id: string;
  name: string;
  notes?: string;
}

export interface Polygon {
  id: string;
  name: string;
  type: "prohibited" | "penalty" | "info" | "waypoint";
  points: LatLng[];
}

export type SelectionType = "point" | "gate" | "observation" | "polygon" | "settings" | "help";
export type Mode = "view" | "add_point" | "add_landing" | "add_takeoff" | "add_observation" | "add_polygon";
