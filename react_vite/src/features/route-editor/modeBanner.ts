import type { LatLng, Mode } from '../../types';
import type { RouteRequirementTool } from './api';
import { TOOL_ACTIONS } from './guideTools';

// What the banner over the map says while the editor is in a state where a click places something. One table for the
// toolbar's modes, and the guide's tools say it through TOOL_ACTIONS[tool].prompt.

// The look of a state: the icon (named here, drawn in the banner) and the colour (a DaisyUI colour name).
export type BannerIcon = 'plus' | 'tag' | 'camera' | 'hexagon' | 'anchor' | 'activity' | 'wand' | 'pointer';
export type BannerTone = 'success' | 'secondary' | 'warning' | 'primary' | 'info';
export type BannerKind = 'waypoints' | 'catalogue' | 'photos' | 'zone' | 'landing' | 'takeoff' | 'points' | 'leg' | 'pick' | 'guide';

export const BANNER_KINDS: Record<BannerKind, { icon: BannerIcon; tone: BannerTone }> = {
  waypoints: { icon: 'plus', tone: 'success' },
  catalogue: { icon: 'tag', tone: 'secondary' },
  photos: { icon: 'camera', tone: 'warning' },
  zone: { icon: 'hexagon', tone: 'secondary' },
  landing: { icon: 'anchor', tone: 'primary' },
  takeoff: { icon: 'activity', tone: 'warning' },
  // Standalone points of the guide (known time gates, circle markers, extension waypoints)
  points: { icon: 'plus', tone: 'success' },
  // A click on a leg inserts a point
  leg: { icon: 'plus', tone: 'info' },
  // A click on an existing waypoint chooses it
  pick: { icon: 'pointer', tone: 'info' },
  // A step with nothing to click for
  guide: { icon: 'wand', tone: 'warning' },
};

export type PlacingMode = Exclude<Mode, 'view'>;

export interface ModeText {
  kind: BannerKind;
  // What is being done, shown in bold.
  title: string;
  // What a click does now.
  instruction: string;
}

// The toolbar's modes. The gate modes have a text for each of their two clicks.
export const MODE_TEXTS: Record<PlacingMode, ModeText | { first: ModeText; second: ModeText }> = {
  add_point: { kind: 'waypoints', title: 'Adding waypoints', instruction: 'click the map to place the next one.' },
  add_catalogue_turnpoint: { kind: 'catalogue', title: 'Adding catalogue turn points', instruction: 'click the map to place one.' },
  add_observation: { kind: 'photos', title: 'Adding photos', instruction: 'click the map close to the route to place one.' },
  add_polygon: { kind: 'zone', title: 'Drawing a zone', instruction: 'click the map to add corners, click the first corner to close it.' },
  add_landing: {
    first: { kind: 'landing', title: 'Landing gate', instruction: 'click the map for the first end of the line.' },
    second: { kind: 'landing', title: 'Landing gate', instruction: 'click the map for the other end of the line.' },
  },
  add_takeoff: {
    first: { kind: 'takeoff', title: 'Take-off gate', instruction: 'click the map for the first end of the line.' },
    second: { kind: 'takeoff', title: 'Take-off gate', instruction: 'click the map for the other end of the line.' },
  },
};

// How each guide tool looks. Total over the tools the registry can name (modeBanner.test.ts checks it).
export const GUIDE_TOOL_KINDS: Record<RouteRequirementTool, BannerKind> = {
  route_waypoint: 'waypoints',
  hidden_gate: 'leg',
  known_time_gate: 'points',
  catalogue_turnpoint: 'catalogue',
  circle_start: 'points',
  circle_center: 'points',
  circle_entry: 'points',
  circle_exit: 'points',
  photo: 'photos',
  landing_area: 'zone',
  takeoff_gate: 'takeoff',
  landing_gate: 'landing',
  unknown_leg_point: 'pick',
  extension_waypoint: 'points',
  curved_leg: 'guide',
};

export interface ModeBannerState {
  mode: Mode;
  tempGatePoint: LatLng | null;
  // The guide step that is active, if any.
  activeGuideTool: RouteRequirementTool | null;
  // The text the editor itself has for the guide step (the unknown-leg phases say more than the tool's prompt).
  guidePrompt?: string | null;
  // A click on a leg inserts a point (hidden gate, unknown-leg point): a placing state in select mode.
  legInsertType?: string | null;
}

export interface ModeBanner extends ModeText {
  tone: BannerTone;
  icon: BannerIcon;
  fromGuide: boolean;
}

const bannerFor = (text: ModeText, fromGuide: boolean): ModeBanner => ({ ...text, ...BANNER_KINDS[text.kind], fromGuide });

const modeText = (mode: PlacingMode, tempGatePoint: LatLng | null): ModeText => {
  const entry = MODE_TEXTS[mode];
  return 'first' in entry ? (tempGatePoint ? entry.second : entry.first) : entry;
};

// The banner for the state the editor is in, or null in select mode with no guide step.
export const getModeBanner = (state: ModeBannerState): ModeBanner | null => {
  const { mode, tempGatePoint, activeGuideTool, guidePrompt, legInsertType } = state;
  if (activeGuideTool) {
    const kind = GUIDE_TOOL_KINDS[activeGuideTool];
    const prompt = guidePrompt || TOOL_ACTIONS[activeGuideTool].prompt;
    return bannerFor({ kind, title: '', instruction: prompt }, true);
  }
  if (mode !== 'view') return bannerFor(modeText(mode, tempGatePoint), false);
  // A click on a leg places a point (without a guide step this does not happen, the type comes from a step)
  if (legInsertType) return bannerFor({ kind: 'leg', title: 'Adding points', instruction: 'click a leg of the route to place one.' }, false);
  return null;
};

// A click on the map places something now (the cursor is a crosshair).
export const isPlacing = (state: Pick<ModeBannerState, 'mode' | 'legInsertType'>): boolean => (
  state.mode !== 'view' || !!state.legInsertType
);

export const bannerSentence = (banner: Pick<ModeText, 'title' | 'instruction'>): string => (
  banner.title ? `${banner.title}: ${banner.instruction}` : banner.instruction
);
