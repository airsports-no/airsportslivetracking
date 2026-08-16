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
  type: "sp" | "tp" | "secret" | "fp" | "anrtp" | "known_time_gate" | "timed_turnpoint" | "hidden_gate" | "catalogue_turnpoint" | "circle_center" | "circle_start" | "circle_entry" | "circle_exit" | "ul" | "unknown_leg" | "dummy";
  segmentType: "straight" | "curved";
  controlLat?: number;
  controlLng?: number;
  width: number;
  isTiming: boolean;
  isPassing: boolean;
  isSecret?: boolean;
  scoreValue?: number | null;
  unknownLegHeading?: number;
  triggerPointId?: string | null;
  branchSequence?: number | null;
  featureType?: "route_waypoint" | "catalogue_turnpoint" | "circle_center_marker" | "circle_start_marker" | "circle_entry_marker" | "circle_exit_marker" | "known_time_gate" | "hidden_gate" | "dummy_branch_waypoint";
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
  targetName?: string;
}

export interface Polygon {
  id: string;
  name: string;
  type: "prohibited" | "penalty" | "info" | "duration_landing_area";
  points: LatLng[];
}

export type SelectionType = "point" | "standalone_point" | "gate" | "observation" | "polygon" | "settings" | "help" | "wizard";
export type Mode = "view" | "add_point" | "add_catalogue_turnpoint" | "add_landing" | "add_takeoff" | "add_observation" | "add_polygon";
