// @vitest-environment node
//
// Regression test for ContestantTimetable.tsx reassigning a render-scope variable
// (`lastDate`) from inside the sortedContestants.map() callback used to build each row's
// date-header grouping. React's newer render-purity lint rules (react-hooks/immutability)
// flag this as unsafe - render must be a pure function of props/state, and mutating a local
// variable while mapping breaks that even though, in the classic (non-compiled) runtime,
// this specific mutation was actually harmless (recomputed fresh every render, no
// cross-render leakage).
//
// Following the same approach as Timeline.rulesOfHooks.test.ts: run ESLint programmatically
// against the file and assert no react-hooks/immutability violations, rather than rendering
// the component (no @testing-library/react dependency in this repo).

import path from 'path';
import { fileURLToPath } from 'url';
import { describe, expect, it } from 'vitest';
import { ESLint } from 'eslint';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

describe('ContestantTimetable.tsx date-header grouping', () => {
    it('never reassigns a render-scope variable while mapping over contestants', async () => {
        const eslint = new ESLint({ cwd: path.resolve(__dirname, '../../..') });
        const [result] = await eslint.lintFiles([path.resolve(__dirname, 'ContestantTimetable.tsx')]);

        const violations = result.messages.filter((message) => message.ruleId === 'react-hooks/immutability');

        expect(violations).toEqual([]);
    });
});
