import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import StandingsTable from './StandingsTable';
import { Standings } from './api';

const standings = (overrides: Partial<Standings> = {}): Standings => ({
    id: 1,
    name: 'Cup',
    scoring_method: 'placements',
    entrant_identity: 'pilot',
    best_results_counted: null,
    legs: [
        { contest_id: 10, name: 'Leg one', weight: 1 },
        { contest_id: 11, name: 'Leg two', weight: 2 },
    ],
    rows: [
        {
            rank: 1,
            total: 5,
            entrant: { key: '1', name: 'Anna Pilot', country: '', club: 'Kjeller Flyklubb' },
            legs: [
                { contest_id: 10, status: 'ranked', placement: 1, score: 10, points: 1, counted: true },
                { contest_id: 11, status: 'no_result', placement: null, score: null, points: 4, counted: false },
            ],
        },
        {
            rank: 2,
            total: 7,
            entrant: { key: '2', name: 'Carl Pilot', country: '', club: '' },
            legs: [
                { contest_id: 10, status: 'absent', placement: null, score: null, points: 3, counted: true },
                { contest_id: 11, status: 'ranked', placement: 2, score: 5, points: 4, counted: true },
            ],
        },
    ],
    ...overrides,
});

const render = (data: Standings) =>
    renderToStaticMarkup(
        <MemoryRouter>
            <StandingsTable standings={data} />
        </MemoryRouter>,
    );

describe('StandingsTable', () => {
    it('shows the entrants with rank, club, a column per leg and the total', () => {
        const html = render(standings());
        expect(html).toContain('Anna Pilot');
        expect(html).toContain('Kjeller Flyklubb');
        expect(html).toContain('Leg one');
        expect(html).toContain('Leg two');
        expect(html).toContain('× 2');
        expect(html).toContain('>Pilot<');
    });

    it('says why a leg has no place, and what it gave', () => {
        const html = render(standings());
        expect(html).toContain('no result');
        expect(html).toContain('not in it');
        expect(html).toContain('4 p');
    });

    it('dims the legs that do not count towards the total', () => {
        const html = render(standings());
        expect(html.match(/line-through/g)).toHaveLength(1);
    });

    it('names the column crew when crews are ranked and shows points for a points table', () => {
        const html = render(standings({ entrant_identity: 'crew', scoring_method: 'points_table' }));
        expect(html).toContain('>Crew<');
        expect(html).toContain('1 p');
    });

    it('says so when there are no results', () => {
        expect(render(standings({ rows: [] }))).toContain('no results yet');
    });
});
