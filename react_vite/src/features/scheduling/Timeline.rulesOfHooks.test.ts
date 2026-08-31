// @vitest-environment node
//
// Regression test for Timeline.tsx calling hooks conditionally after an early
// return: four `useRef`s ran unconditionally, but three `useMemo`s and three
// `useEffect`s ran only when navigationTask.contestant_set was non-empty. Since
// ContestantScheduling.tsx renders <Timeline> unconditionally and
// contestant_set commonly starts empty (open a task with no contestants yet,
// then run the scheduler), the hook count changed between renders and React
// threw "Rendered more hooks than during the previous render", killing the
// primary scheduling flow.
//
// ESLint's react-hooks/rules-of-hooks rule (already enabled repo-wide via
// eslint.config.js) is the precise, purpose-built detector for exactly this
// bug class - it flags every hook call reachable after a conditional return.
// Running it here pins the regression without needing to render vis-timeline
// (which has known jsdom incompatibilities unrelated to this bug) or adding a
// new testing-library dependency.

import path from 'path';
import { fileURLToPath } from 'url';
import { describe, expect, it } from 'vitest';
import { ESLint } from 'eslint';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

describe('Timeline.tsx hook ordering', () => {
    it('never calls a hook conditionally after an early return', async () => {
        const eslint = new ESLint({ cwd: path.resolve(__dirname, '../../..') });
        const [result] = await eslint.lintFiles([path.resolve(__dirname, 'Timeline.tsx')]);

        const rulesOfHooksViolations = result.messages.filter(
            (message) => message.ruleId === 'react-hooks/rules-of-hooks'
        );

        expect(rulesOfHooksViolations).toEqual([]);
    });
});
