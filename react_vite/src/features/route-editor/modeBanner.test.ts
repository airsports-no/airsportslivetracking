import { describe, expect, it } from 'vitest';
import { ROUTE_REQUIREMENT_TOOLS } from './api';
import { TOOL_ACTIONS } from './guideTools';
import { bannerSentence, BANNER_KINDS, getModeBanner, GUIDE_TOOL_KINDS, isPlacing, MODE_TEXTS, type PlacingMode } from './modeBanner';

const PLACING_MODES = Object.keys(MODE_TEXTS) as PlacingMode[];
const state = (overrides = {}) => ({ mode: 'view' as const, tempGatePoint: null, activeGuideTool: null, ...overrides });

describe('mode banner', () => {
  it('has a text, an icon and a colour for every placing mode', () => {
    expect(PLACING_MODES.sort()).toEqual(['add_catalogue_turnpoint', 'add_hidden_gate', 'add_landing', 'add_observation', 'add_point', 'add_polygon', 'add_takeoff']);
    for (const mode of PLACING_MODES) {
      for (const tempGatePoint of [null, { lat: 1, lng: 2 }]) {
        const banner = getModeBanner(state({ mode, tempGatePoint }));
        expect(banner, mode).not.toBeNull();
        expect(banner!.title, mode).toBeTruthy();
        expect(banner!.instruction, mode).toBeTruthy();
        expect(banner!.icon, mode).toBeTruthy();
        expect(banner!.tone, mode).toBeTruthy();
        expect(banner!.fromGuide).toBe(false);
      }
    }
  });

  it('says what the hidden gate tool does', () => {
    expect(bannerSentence(getModeBanner(state({ mode: 'add_hidden_gate' }))!)).toBe('Hidden gate: click a leg of the route to place one.');
    expect(isPlacing({ mode: 'add_hidden_gate', legInsertType: null })).toBe(true);
  });

  it('says what a click does now', () => {
    expect(bannerSentence(getModeBanner(state({ mode: 'add_point' }))!)).toBe('Adding waypoints: click the map to place the next one.');
    const first = getModeBanner(state({ mode: 'add_landing' }))!.instruction;
    const second = getModeBanner(state({ mode: 'add_landing', tempGatePoint: { lat: 1, lng: 1 } }))!.instruction;
    expect(first).not.toBe(second);
  });

  it('has a banner for every guide tool, with the tool prompt', () => {
    expect(Object.keys(GUIDE_TOOL_KINDS).sort()).toEqual([...ROUTE_REQUIREMENT_TOOLS].sort());
    for (const tool of ROUTE_REQUIREMENT_TOOLS) {
      expect(BANNER_KINDS[GUIDE_TOOL_KINDS[tool]], tool).toBeTruthy();
      const banner = getModeBanner(state({ activeGuideTool: tool }));
      expect(banner, tool).not.toBeNull();
      expect(banner!.instruction).toBe(TOOL_ACTIONS[tool].prompt);
      expect(banner!.fromGuide).toBe(true);
    }
  });

  it('prefers the editor\'s own text for a guide step', () => {
    expect(getModeBanner(state({ activeGuideTool: 'extension_waypoint', guidePrompt: 'Pick an amber point.' }))!.instruction).toBe('Pick an amber point.');
  });

  it('has no banner in select mode', () => {
    expect(getModeBanner(state())).toBeNull();
    expect(isPlacing(state())).toBe(false);
  });

  it('counts a click on a leg in select mode as placing', () => {
    expect(isPlacing(state({ legInsertType: 'secret' }))).toBe(true);
    expect(isPlacing(state({ mode: 'add_polygon' }))).toBe(true);
  });
});
