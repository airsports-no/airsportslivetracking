import { getTrackValue, getGateInScorecard, getGateValue } from './scorecardUtils';
import type { Scorecard } from '../types';

function makeScorecard(overrides: Partial<Scorecard> = {}): Scorecard {
  return {
    gatescore_set: [
      { gate_type: 'sp', graceperiod_before: 2, graceperiod_after: 2, penalty_per_second: 3, maximum_penalty: 100, missed_penalty: 200 },
      { gate_type: 'tp', graceperiod_before: 1, graceperiod_after: 1, penalty_per_second: 1, maximum_penalty: 50, missed_penalty: 100 },
    ],
    task_type: ['precision'],
    corridor_width: 0.5,
    ...overrides,
  };
}

describe('getTrackValue', () => {
  it('reads a top-level scorecard field by name', () => {
    const scorecard = makeScorecard({ corridor_width: 1.5 });
    expect(getTrackValue(scorecard, 'corridor_width')).toBe(1.5);
  });
});

describe('getGateInScorecard', () => {
  it('finds the gate rule matching the given gate type', () => {
    const scorecard = makeScorecard();
    expect(getGateInScorecard(scorecard, 'tp')?.penalty_per_second).toBe(1);
  });

  it('returns undefined when no gate rule matches', () => {
    const scorecard = makeScorecard();
    expect(getGateInScorecard(scorecard, 'fp')).toBeUndefined();
  });
});

describe('getGateValue', () => {
  it('reads a field off the matching gate rule', () => {
    const scorecard = makeScorecard();
    expect(getGateValue(scorecard, 'sp', 'maximum_penalty')).toBe(100);
  });

  it('returns null when no gate rule matches the gate type', () => {
    const scorecard = makeScorecard();
    expect(getGateValue(scorecard, 'fp', 'maximum_penalty')).toBeNull();
  });
});
