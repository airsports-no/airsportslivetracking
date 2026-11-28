import { describe, expect, it } from 'vitest';
import { applyGuideChoice, applyManualTick, emptyIntent } from './routeIntent';

describe('route intent', () => {
  it('starts empty and gets the guide task added', () => {
    expect(applyGuideChoice(emptyIntent(), 'precision')).toEqual({ types: ['precision'], guideChosen: 'precision' });
  });

  it('replaces the previous guide choice when the task changes', () => {
    const first = applyGuideChoice(emptyIntent(), 'precision');
    expect(applyGuideChoice(first, 'anr')).toEqual({ types: ['anr'], guideChosen: 'anr' });
  });

  it('keeps what the author ticked by hand when the guide task changes', () => {
    let intent = applyGuideChoice(emptyIntent(), 'precision');
    intent = applyManualTick(intent, 'landing', true);
    intent = applyGuideChoice(intent, 'anr');
    expect(intent.types.sort()).toEqual(['anr', 'landing']);
  });

  it('keeps a guide choice the author then ticked by hand', () => {
    let intent = applyGuideChoice(emptyIntent(), 'precision');
    intent = applyManualTick(intent, 'precision', true);
    intent = applyGuideChoice(intent, 'anr');
    expect(intent.types.sort()).toEqual(['anr', 'precision']);
  });

  it('does not take over a type that was already ticked', () => {
    let intent = applyManualTick(emptyIntent(), 'precision', true);
    intent = applyGuideChoice(intent, 'precision');
    expect(intent.guideChosen).toBeNull();
    expect(applyGuideChoice(intent, 'anr').types.sort()).toEqual(['anr', 'precision']);
  });

  it('removes the guide choice when the guide is left, and an unticked type stays gone', () => {
    let intent = applyGuideChoice(emptyIntent(), 'precision');
    expect(applyGuideChoice(intent, null)).toEqual(emptyIntent());
    intent = applyManualTick(intent, 'precision', false);
    expect(intent.types).toEqual([]);
    expect(applyGuideChoice(intent, 'anr').types).toEqual(['anr']);
  });
});
