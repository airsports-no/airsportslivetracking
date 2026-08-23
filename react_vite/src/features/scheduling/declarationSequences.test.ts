import {
  toDatetimeLocalValue,
  splitContractNavigationDeclaration,
  buildContractNavigationSequence,
  normalizeContractNavigationSequence,
  getCompiledPayload,
  getCompulsoryPointNames,
  getTurnpointHuntSequence,
  getContractNavigationSequence,
  normalizeTurnpointHuntSequence,
  buildFormState,
  moveItem,
  moveItemToInsertionIndex,
  type ContestantDeclarationData,
} from './declarationSequences';

describe('toDatetimeLocalValue', () => {
  // The function formats in the local timezone (that's the point - it feeds
  // an <input type="datetime-local">), so expectations are derived from a
  // real Date's own local getters rather than a hardcoded UTC literal, which
  // would be wrong whenever tests run outside UTC.
  function expectedLocalValue(iso: string): string {
    const date = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  it('formats an ISO string into a datetime-local value', () => {
    expect(toDatetimeLocalValue('2026-03-05T08:30:00Z')).toBe(expectedLocalValue('2026-03-05T08:30:00Z'));
  });

  it('returns an empty string for null/undefined/empty input', () => {
    expect(toDatetimeLocalValue(null)).toBe('');
    expect(toDatetimeLocalValue(undefined)).toBe('');
    expect(toDatetimeLocalValue('')).toBe('');
  });

  it('returns an empty string for an unparseable date', () => {
    expect(toDatetimeLocalValue('not a date')).toBe('');
  });

  it('pads single-digit month/day/hour/minute', () => {
    const value = toDatetimeLocalValue('2026-01-02T03:04:00Z');
    expect(value).toBe(expectedLocalValue('2026-01-02T03:04:00Z'));
    expect(value).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  });
});

describe('splitContractNavigationDeclaration', () => {
  it('splits a full SP..MP..FP sequence into before/after-MP lanes', () => {
    expect(splitContractNavigationDeclaration(['SP', 'A', 'B', 'MP', 'C', 'FP'])).toEqual({
      beforeMp: ['A', 'B'],
      afterMp: ['C'],
    });
  });

  it('drops a leading SP from the before-MP lane even without an explicit SP entry', () => {
    expect(splitContractNavigationDeclaration(['SP', 'MP', 'FP'])).toEqual({ beforeMp: [], afterMp: [] });
  });

  it('returns empty lanes when MP is missing', () => {
    expect(splitContractNavigationDeclaration(['SP', 'A', 'FP'])).toEqual({ beforeMp: [], afterMp: [] });
  });

  it('returns empty lanes when FP is missing', () => {
    expect(splitContractNavigationDeclaration(['SP', 'MP', 'A'])).toEqual({ beforeMp: [], afterMp: [] });
  });

  it('returns empty lanes when FP appears before MP', () => {
    expect(splitContractNavigationDeclaration(['SP', 'FP', 'MP'])).toEqual({ beforeMp: [], afterMp: [] });
  });

  it('returns empty lanes for a non-array input', () => {
    expect(splitContractNavigationDeclaration(undefined)).toEqual({ beforeMp: [], afterMp: [] });
    expect(splitContractNavigationDeclaration(null)).toEqual({ beforeMp: [], afterMp: [] });
  });

  it('filters out non-string entries', () => {
    expect(splitContractNavigationDeclaration(['SP', 1, 'A', 'MP', null, 'FP'])).toEqual({
      beforeMp: ['A'],
      afterMp: [],
    });
  });
});

describe('buildContractNavigationSequence', () => {
  it('assembles SP, before-MP, MP, after-MP, FP in order', () => {
    expect(buildContractNavigationSequence({ beforeMp: ['A', 'B'], afterMp: ['C'] })).toEqual([
      'SP', 'A', 'B', 'MP', 'C', 'FP',
    ]);
  });

  it('is the inverse of splitContractNavigationDeclaration for a well-formed sequence', () => {
    const sequence = ['SP', 'X', 'Y', 'MP', 'Z', 'FP'];
    expect(buildContractNavigationSequence(splitContractNavigationDeclaration(sequence))).toEqual(sequence);
  });

  it('produces the minimal SP/MP/FP sequence for empty lanes', () => {
    expect(buildContractNavigationSequence({ beforeMp: [], afterMp: [] })).toEqual(['SP', 'MP', 'FP']);
  });
});

describe('normalizeContractNavigationSequence', () => {
  it('keeps allowed turnpoints on the correct side of MP', () => {
    expect(normalizeContractNavigationSequence(['SP', 'A', 'MP', 'B', 'FP'], ['A', 'B'])).toEqual([
      'SP', 'A', 'MP', 'B', 'FP',
    ]);
  });

  it('drops turnpoints that are not in the allowed set', () => {
    expect(normalizeContractNavigationSequence(['SP', 'A', 'C', 'MP', 'FP'], ['A'])).toEqual(['SP', 'A', 'MP', 'FP']);
  });

  it('de-duplicates repeated turnpoints, keeping the first occurrence', () => {
    expect(normalizeContractNavigationSequence(['SP', 'A', 'A', 'MP', 'FP'], ['A'])).toEqual(['SP', 'A', 'MP', 'FP']);
  });

  it('treats every allowed turnpoint as before-MP when MP is absent from the input (itemIndex < -1 is always true)', () => {
    expect(normalizeContractNavigationSequence(['SP', 'A', 'B', 'FP'], ['A', 'B'])).toEqual(['SP', 'A', 'B', 'MP', 'FP']);
  });
});

describe('getCompiledPayload', () => {
  it('returns the compiled_effective_route_payload when present', () => {
    const payload = { compulsory_point_names: ['A'] };
    expect(getCompiledPayload({ compiled_effective_route_payload: payload })).toBe(payload);
  });

  it('returns an empty object for null/undefined contestant or missing payload', () => {
    expect(getCompiledPayload(null)).toEqual({});
    expect(getCompiledPayload(undefined)).toEqual({});
    expect(getCompiledPayload({})).toEqual({});
  });
});

describe('getCompulsoryPointNames', () => {
  it('prefers compulsory_point_names over compulsory_timing_gate_names', () => {
    const contestant = {
      compiled_effective_route_payload: {
        compulsory_point_names: ['A', 'B'],
        compulsory_timing_gate_names: ['X', 'Y'],
      },
    };
    expect(getCompulsoryPointNames(contestant)).toEqual(['A', 'B']);
  });

  it('falls back to compulsory_timing_gate_names', () => {
    const contestant = { compiled_effective_route_payload: { compulsory_timing_gate_names: ['X', 'Y'] } };
    expect(getCompulsoryPointNames(contestant)).toEqual(['X', 'Y']);
  });

  it('returns an empty array when neither is present', () => {
    expect(getCompulsoryPointNames({})).toEqual([]);
  });
});

describe('getTurnpointHuntSequence', () => {
  it('prefers an already-declared sequence', () => {
    const contestant = {
      declaration_payload: { declared_sequence: ['CP1', 'X', 'CP2'] },
      compiled_effective_route_payload: { free_target_names: ['X', 'Y'] },
    };
    expect(getTurnpointHuntSequence(contestant)).toEqual(['CP1', 'X', 'CP2']);
  });

  it('falls back to the compiled free target names when nothing is declared', () => {
    const contestant = { compiled_effective_route_payload: { free_target_names: ['X', 'Y'] } };
    expect(getTurnpointHuntSequence(contestant)).toEqual(['X', 'Y']);
  });

  it('returns an empty array when there is neither a declaration nor compiled targets', () => {
    expect(getTurnpointHuntSequence({})).toEqual([]);
  });
});

describe('getContractNavigationSequence', () => {
  it('prefers an already-declared sequence', () => {
    const contestant = { declaration_payload: { declared_sequence: ['SP', 'A', 'MP', 'FP'] } };
    expect(getContractNavigationSequence(contestant)).toEqual(['SP', 'A', 'MP', 'FP']);
  });

  it('defaults to the minimal SP/MP/FP sequence when nothing is declared', () => {
    expect(getContractNavigationSequence({})).toEqual(['SP', 'MP', 'FP']);
  });
});

describe('normalizeTurnpointHuntSequence', () => {
  it('interleaves free targets into their slot before/between/after the ordered compulsory points', () => {
    // X was declared before CP1 (slot 0), Y between CP1 and CP2 (slot 1).
    const result = normalizeTurnpointHuntSequence(['X', 'CP1', 'Y', 'CP2'], ['CP1', 'CP2'], ['X', 'Y']);
    expect(result).toEqual(['X', 'CP1', 'Y', 'CP2']);
  });

  it('places a free target declared after the last compulsory point at the end', () => {
    const result = normalizeTurnpointHuntSequence(['CP1', 'CP2', 'X'], ['CP1', 'CP2'], ['X']);
    expect(result).toEqual(['CP1', 'CP2', 'X']);
  });

  it('drops free targets that are not in the allowed set', () => {
    const result = normalizeTurnpointHuntSequence(['Z', 'CP1'], ['CP1'], ['X']);
    expect(result).toEqual(['CP1']);
  });

  it('de-duplicates repeated free targets, keeping the first occurrence and its slot', () => {
    const result = normalizeTurnpointHuntSequence(['X', 'CP1', 'X'], ['CP1'], ['X']);
    expect(result).toEqual(['X', 'CP1']);
  });

  it('returns just the compulsory points in order when there are no free targets', () => {
    expect(normalizeTurnpointHuntSequence([], ['CP1', 'CP2'], [])).toEqual(['CP1', 'CP2']);
  });
});

describe('buildFormState', () => {
  it('builds a full form state from a contract-navigation contestant', () => {
    const contestant: ContestantDeclarationData = {
      declaration_payload: {
        declared_sequence: ['SP', 'A', 'MP', 'B', 'FP'],
        declared_t_seconds: 600,
      },
    };
    const formState = buildFormState(contestant);
    expect(formState.contractNavigation).toEqual({ beforeMp: ['A'], afterMp: ['B'] });
    expect(formState.contractDeclaredTSeconds).toBe('600');
  });

  it('falls back to the compiled time model when no t_seconds is declared', () => {
    const contestant: ContestantDeclarationData = {
      compiled_effective_route_payload: { time_model: { t_seconds: 300 } },
    };
    expect(buildFormState(contestant).contractDeclaredTSeconds).toBe('300');
  });

  it('formats declared compulsory point times as datetime-local values', () => {
    const contestant: ContestantDeclarationData = {
      compiled_effective_route_payload: { compulsory_point_names: ['CP1'] },
      declaration_payload: { compulsory_point_times: { CP1: '2026-03-05T08:30:00Z' } },
    };
    expect(buildFormState(contestant).compulsoryPointTimes).toEqual({ CP1: toDatetimeLocalValue('2026-03-05T08:30:00Z') });
  });

  it('reads the declared endurance minutes from fuel metadata', () => {
    const contestant: ContestantDeclarationData = {
      declaration_payload: { fuel_metadata: { declared_endurance_minutes: 90 } },
    };
    expect(buildFormState(contestant).declaredEnduranceMinutes).toBe('90');
  });

  it('defaults declared endurance minutes to an empty string when absent', () => {
    expect(buildFormState({}).declaredEnduranceMinutes).toBe('');
  });
});

describe('moveItem', () => {
  it('moves an item from one index to another', () => {
    expect(moveItem(['a', 'b', 'c'], 0, 2)).toEqual(['b', 'c', 'a']);
  });

  it('moving an item to its own index is a no-op', () => {
    expect(moveItem(['a', 'b', 'c'], 1, 1)).toEqual(['a', 'b', 'c']);
  });

  it('does not mutate the input array', () => {
    const items = ['a', 'b', 'c'];
    moveItem(items, 0, 2);
    expect(items).toEqual(['a', 'b', 'c']);
  });
});

describe('moveItemToInsertionIndex', () => {
  it('moves an item forward to an insertion point', () => {
    // Moving 'a' (index 0) to insert before index 2 ('c') lands it between b and c.
    expect(moveItemToInsertionIndex(['a', 'b', 'c'], 0, 2)).toEqual(['b', 'a', 'c']);
  });

  it('moves an item backward to an insertion point', () => {
    expect(moveItemToInsertionIndex(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b']);
  });

  it('clamps the insertion index to the array bounds', () => {
    expect(moveItemToInsertionIndex(['a', 'b', 'c'], 0, 100)).toEqual(['b', 'c', 'a']);
    expect(moveItemToInsertionIndex(['a', 'b', 'c'], 2, -5)).toEqual(['c', 'a', 'b']);
  });
});
