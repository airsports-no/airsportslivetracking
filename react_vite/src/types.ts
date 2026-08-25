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
  // Task subtype keys (legacy shims and/or CIMA subtypes, see taskTemplates.ts) this route was
  // declared by its author to be designed for. User-editable, purely advisory - see
  // compatible_task_types for what actually gates task creation.
  intended_task_types: string[];
  // Task subtype keys this route's authored content actually satisfies the requirements of,
  // computed server-side (display.services.route_compatibility) and read-only here.
  compatible_task_types: string[];
}

export interface LatLng {
  lat: number;
  lng: number;
}

export interface RoutePoint extends LatLng {
  id: string;
  name: string;
  type: "sp" | "tp" | "secret" | "fp" | "anrtp" | "timed_turnpoint" | "catalogue_turnpoint" | "circle_center" | "circle_start" | "circle_entry" | "circle_exit" | "ul" | "unknown_leg" | "dummy";
  segmentType: "straight" | "curved";
  controlLat?: number;
  controlLng?: number;
  width: number;
  isTiming: boolean;
  isPassing: boolean;
  scoreValue?: number | null;
  unknownLegHeading?: number;
  triggerPointId?: string | null;
  branchSequence?: number | null;
  featureType?: "route_waypoint" | "catalogue_turnpoint" | "circle_center_marker" | "circle_start_marker" | "circle_entry_marker" | "circle_exit_marker" | "known_time_gate" | "dummy_branch_waypoint";
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
