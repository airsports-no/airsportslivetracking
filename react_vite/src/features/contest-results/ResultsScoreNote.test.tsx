import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ResultCell, ScoreColumnNote } from './ResultsScoreNote';

const quality = { scoring_model: 'quality', task_value: 1000, scores_provisional: true, not_flown_team_ids: [7], provisional_explanation: 'Written by the server.' };

describe('ScoreColumnNote', () => {
  it('says what the scores are out of and that they are provisional, with the explanation behind the badge', () => {
    const html = renderToStaticMarkup(<ScoreColumnNote scoring={quality} />);
    expect(html).toContain('Score (of 1000)');
    expect(html).toContain('Provisional');
    expect(html).toContain('title="Written by the server."');
  });

  it('drops the badge when every flight is finished', () => {
    const html = renderToStaticMarkup(<ScoreColumnNote scoring={{ ...quality, scores_provisional: false }} />);
    expect(html).toContain('Score (of 1000)');
    expect(html).not.toContain('Provisional');
  });

  it('can show the badge alone, for a task that adds up several tests', () => {
    const html = renderToStaticMarkup(<ScoreColumnNote scoring={quality} showScale={false} />);
    expect(html).not.toContain('of 1000');
    expect(html).toContain('Provisional');
  });

  it('shows nothing for a task of the penalty model or a test that is not linked', () => {
    expect(renderToStaticMarkup(<ScoreColumnNote scoring={{ scoring_model: 'penalties', scores_provisional: true }} />)).toBe('');
    expect(renderToStaticMarkup(<ScoreColumnNote scoring={null} />)).toBe('');
  });
});

describe('ResultCell', () => {
  it('shows DNF with its meaning, a whole number, and anything else as it was', () => {
    expect(renderToStaticMarkup(<ResultCell value={0} scoring={quality} teamId={7} />)).toContain('>DNF<');
    expect(renderToStaticMarkup(<ResultCell value={0} scoring={quality} teamId={7} />)).toContain('Did Not Fly');
    expect(renderToStaticMarkup(<ResultCell value={874.4} scoring={quality} teamId={1} />)).toBe('874');
    expect(renderToStaticMarkup(<ResultCell value="-" scoring={quality} teamId={1} />)).toBe('-');
    expect(renderToStaticMarkup(<ResultCell value={12.5} scoring={{ scoring_model: 'penalties' }} teamId={7} />)).toBe('12.5');
    expect(renderToStaticMarkup(<ResultCell value={12.5} scoring={null} teamId={7} />)).toBe('12.5');
  });
});
