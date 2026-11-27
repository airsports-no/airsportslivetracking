import { describe, expect, it } from 'vitest';
import {
    addToLane,
    buildDeclarationPayload,
    buildSequence,
    clockTime,
    cutoffSentence,
    declarationActionText,
    declarationLabel,
    entrySeconds,
    hadDeclaration,
    formatEntry,
    initialFormState,
    laneCount,
    laneLabel,
    moveInLane,
    removeFromLane,
    secondsToEntry,
    sequenceShape,
    shouldPoll,
    splitSequence,
} from './declarationForm';
import { DeclarationForm, PilotDeclaration } from './types';

const declaration = (form: DeclarationForm, payload: Record<string, any> = {}, overrides: Partial<PilotDeclaration> = {}): PilotDeclaration => ({
    contestant_id: 5,
    contest_id: 1,
    navigation_task_id: 2,
    contest_name: 'Cup',
    navigation_task_name: 'Task',
    time_zone: 'Europe/Oslo',
    task_type: 'x',
    status: { need: 'required', state: 'missing', errors: [], can_edit: true, edit_until: '2026-08-01T07:55:00+00:00', edit_url: '/declaration/5' },
    read_only_reason: null,
    flight_order_status: null,
    declaration_payload: payload,
    form,
    ...overrides,
});

const TIMES: DeclarationForm = {
    time_points: ['TP1', 'FP'], declares_times: true, time_key: 'known_time_gate_predictions',
    adaptive_start: false, start_point_time: '2026-08-01T08:00:00+00:00',
};
const CONTRACT: DeclarationForm = {
    mandatory_points: ['SP', 'MP', 'FP'], turnpoints: ['A', 'B', 'C'], asks_for_period: true, declares_times: false, time_key: null,
};
const HUNT: DeclarationForm = {
    compulsory_points: ['CP1', 'CP2'], targets: ['T1', 'T2', 'T3'], asks_for_fuel_endurance: true, declares_times: true,
    time_key: 'compulsory_point_times', start_point_time: '2026-08-01T08:00:00+00:00',
};

describe('entries of minutes and seconds', () => {
    it('are whole seconds', () => {
        expect(entrySeconds({ minutes: '12', seconds: '30' })).toBe(750);
        expect(entrySeconds({ minutes: '', seconds: '45' })).toBe(45);
        expect(entrySeconds({ minutes: '3', seconds: '' })).toBe(180);
    });
    it('are nothing when empty and invalid when not numbers or seconds over 59', () => {
        expect(entrySeconds({ minutes: '', seconds: '' })).toBeNull();
        expect(entrySeconds({ minutes: '1x', seconds: '0' })).toBeNull();
        expect(entrySeconds({ minutes: '1', seconds: '60' })).toBeNull();
        expect(entrySeconds({ minutes: '-1', seconds: '0' })).toBeNull();
    });
    it('go both ways', () => {
        expect(secondsToEntry(750)).toEqual({ minutes: '12', seconds: '30' });
        expect(formatEntry({ minutes: '12', seconds: '5' })).toBe('12:05');
    });
});

describe('the clock time of a time after the start point', () => {
    it('is in the time zone of the contest', () => {
        // 08:00 UTC is 10:00 in Oslo in August; 12:30 later is 10:12:30
        expect(clockTime('2026-08-01T08:00:00+00:00', 750, 'Europe/Oslo')).toBe('10:12:30');
    });
    it('is nothing when the start is not known', () => {
        expect(clockTime(null, 750, 'Europe/Oslo')).toBe('');
        expect(clockTime('2026-08-01T08:00:00+00:00', null, 'Europe/Oslo')).toBe('');
    });
});

describe('the cut-off', () => {
    it('is said in the contest time zone', () => {
        const status = declaration(TIMES).status;
        expect(cutoffSentence(status, 'Europe/Oslo')).toBe('You can change this until 09:55 on 1 August 2026 (Europe/Oslo time).');
    });
    it('is not said when the declaration cannot be changed', () => {
        expect(cutoffSentence({ ...declaration(TIMES).status, can_edit: false }, 'Europe/Oslo')).toBeNull();
    });
});

describe('the form for times', () => {
    it('starts empty and builds seconds with the start point as the reference', () => {
        const state = initialFormState(declaration(TIMES));
        expect(Object.keys(state.times)).toEqual(['TP1', 'FP']);
        state.times.TP1 = { minutes: '10', seconds: '30' };
        const { payload, problems } = buildDeclarationPayload(TIMES, state);
        expect(problems).toEqual([]);
        expect(payload).toEqual({ known_time_gate_predictions: { TP1: 630 }, time_reference: 'start_point' });
    });
    it('is filled from a stored declaration in seconds', () => {
        const state = initialFormState(declaration(TIMES, { time_reference: 'start_point', relative_times: { TP1: 750 }, known_time_gate_predictions: { TP1: 'x' } }));
        expect(state.times.TP1).toEqual({ minutes: '12', seconds: '30' });
    });
    it('is filled from a stored declaration in clock times by their distance from the start point', () => {
        const state = initialFormState(declaration(TIMES, { known_time_gate_predictions: { FP: '2026-08-01T08:20:00+00:00' } }));
        expect(state.times.FP).toEqual({ minutes: '20', seconds: '0' });
    });
    it('refuses seconds over 59 and sends nothing for it', () => {
        const state = initialFormState(declaration(TIMES));
        state.times.TP1 = { minutes: '1', seconds: '75' };
        expect(buildDeclarationPayload(TIMES, state).problems).toHaveLength(1);
    });
    it('sends an empty declaration as an empty payload (saved as nothing declared)', () => {
        expect(buildDeclarationPayload(TIMES, initialFormState(declaration(TIMES))).payload).toEqual({});
    });
});

describe('sequences between fixed points', () => {
    const shape = { anchors: ['SP', 'MP', 'FP'], openEnds: false };
    it('have a list for each gap between the fixed points', () => {
        expect(laneCount(shape)).toBe(2);
        expect(laneLabel(shape, 0)).toBe('Before MP');
        expect(laneLabel(shape, 1)).toBe('Between MP and FP');
        expect(buildSequence(shape, [['A'], ['B', 'C']])).toEqual(['SP', 'A', 'MP', 'B', 'C', 'FP']);
        expect(splitSequence(['SP', 'A', 'MP', 'B', 'C', 'FP'], shape, ['A', 'B', 'C'])).toEqual([['A'], ['B', 'C']]);
    });
    it('can be built by tapping and reordered with up and down', () => {
        let lanes: string[][] = [[], []];
        lanes = addToLane(lanes, 0, 'A');
        lanes = addToLane(lanes, 0, 'B');
        lanes = addToLane(lanes, 1, 'A'); // a point is chosen once
        expect(lanes).toEqual([['A', 'B'], []]);
        lanes = moveInLane(lanes, 0, 1, -1);
        expect(lanes[0]).toEqual(['B', 'A']);
        expect(moveInLane(lanes, 0, 0, -1)).toBe(lanes);
        expect(moveInLane(lanes, 0, 1, 1)).toBe(lanes);
        expect(removeFromLane(lanes, 0, 'B')).toEqual([['A'], []]);
    });
    it('of a hunt follow the compulsory points in the order of their times, with room around them', () => {
        const state = initialFormState(declaration(HUNT));
        state.times.CP1 = { minutes: '30', seconds: '0' };
        state.times.CP2 = { minutes: '10', seconds: '0' };
        const huntShape = sequenceShape(HUNT, state.times);
        expect(huntShape).toEqual({ anchors: ['CP2', 'CP1'], openEnds: true });
        expect(laneCount(huntShape)).toBe(3);
        expect(laneLabel(huntShape, 0)).toBe('Before CP2');
        expect(laneLabel(huntShape, 1)).toBe('Between CP2 and CP1');
        expect(laneLabel(huntShape, 2)).toBe('After CP1');
        expect(buildSequence(huntShape, [['T1'], [], ['T2']])).toEqual(['T1', 'CP2', 'CP1', 'T2']);
    });
});

describe('the declaration of each form shape', () => {
    it('2.A3: the sequence with SP, MP and FP always, and the period T', () => {
        const state = initialFormState(declaration(CONTRACT));
        expect(state.lanes).toEqual([[], []]);
        state.lanes = [['A'], ['C']];
        state.period = { minutes: '1', seconds: '22' };
        expect(buildDeclarationPayload(CONTRACT, state).payload).toEqual({
            declared_sequence: ['SP', 'A', 'MP', 'C', 'FP'],
            declared_t_seconds: 82,
        });
    });
    it('2.A3: is read back from a stored declaration', () => {
        const state = initialFormState(declaration(CONTRACT, { declared_sequence: ['SP', 'B', 'MP', 'A', 'FP'], declared_t_seconds: 82 }));
        expect(state.lanes).toEqual([['B'], ['A']]);
        expect(state.period).toEqual({ minutes: '1', seconds: '22' });
    });
    it('hunt: times, targets between the compulsory points and an optional fuel endurance', () => {
        const state = initialFormState(declaration(HUNT));
        state.times.CP1 = { minutes: '10', seconds: '0' };
        state.times.CP2 = { minutes: '30', seconds: '0' };
        state.lanes = [['T1'], [], ['T2']];
        state.fuelMinutes = '120';
        expect(buildDeclarationPayload(HUNT, state).payload).toEqual({
            compulsory_point_times: { CP1: 600, CP2: 1800 },
            time_reference: 'start_point',
            declared_sequence: ['T1', 'CP1', 'CP2', 'T2'],
            fuel_metadata: { declared_endurance_minutes: 120 },
        });
    });
    it('hunt: no targets means no sequence, and no fuel endurance is fine', () => {
        const state = initialFormState(declaration(HUNT));
        state.times.CP1 = { minutes: '10', seconds: '0' };
        const { payload } = buildDeclarationPayload(HUNT, state);
        expect(payload).not.toHaveProperty('declared_sequence');
        expect(payload).not.toHaveProperty('fuel_metadata');
    });
    it('hunt: refuses a fuel endurance that is not a number', () => {
        const state = initialFormState(declaration(HUNT));
        state.fuelMinutes = 'lots';
        expect(buildDeclarationPayload(HUNT, state).problems).toHaveLength(1);
    });
});

describe('the words for the status of a flight', () => {
    const base = { need: 'required' as const, state: 'missing' as const, can_edit: true };
    it('says needed, saved but not finished, complete and closed', () => {
        expect(declarationLabel(base)?.text).toBe('Declaration needed');
        expect(declarationLabel({ ...base, state: 'incomplete' })?.text).toBe('Declaration saved, not finished');
        expect(declarationLabel({ ...base, state: 'complete' })?.text).toBe('Declaration complete');
        expect(declarationLabel({ ...base, can_edit: false })?.text).toBe('Declaration closed');
        expect(declarationLabel({ ...base, need: 'optional' })?.text).toBe('Declaration optional');
    });
    it('says nothing where there is nothing to declare', () => {
        expect(declarationLabel({ ...base, need: 'not_needed' })).toBeNull();
        expect(declarationLabel(undefined)).toBeNull();
    });
    it('offers editing while it can be changed and viewing after', () => {
        expect(declarationActionText({ ...base, state: 'incomplete' })).toBe('Edit declaration');
        expect(declarationActionText(base)).toBe('Make declaration');
        expect(declarationActionText({ ...base, can_edit: false })).toBe('View declaration');
    });
});

describe('polling', () => {
    it('is only while the flight order is being made', () => {
        const status = (state: any) => ({ state, path: null, created_at: null, reason: null });
        expect(shouldPoll(status('being_made'))).toBe(true);
        for (const state of ['ready', 'failed', 'waiting_for_declaration', 'not_available']) expect(shouldPoll(status(state))).toBe(false);
        expect(shouldPoll(null)).toBe(false);
    });
});

describe('a flight that had a declaration', () => {
    it('is one that asked for a declaration and has something saved', () => {
        expect(hadDeclaration({ need: 'required', state: 'complete' })).toBe(true);
        expect(hadDeclaration({ need: 'optional', state: 'incomplete' })).toBe(true);
        expect(hadDeclaration({ need: 'required', state: 'missing' })).toBe(false);
        expect(hadDeclaration({ need: 'not_needed', state: 'complete' })).toBe(false);
        expect(hadDeclaration(undefined)).toBe(false);
    });
});
