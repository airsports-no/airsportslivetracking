// @vitest-environment node
//
// Regression test for two bugs in useContestResultsWebSocket.ts's reconnect handling:
//
// 1. react-hooks/immutability: `onclose` called `connectWebSocket` directly - a plain closure
//    over the outer const, not a ref - so a reconnect firing up to 3s after a contest switch
//    would reconnect using the *old* contestId's closure instead of the current one.
// 2. The cleanup function connectWebSocket() used to `return` was never actually wired up:
//    `useEffect(() => { connectWebSocket(); }, [...])` discards connectWebSocket()'s return
//    value, since the effect callback itself returns nothing - so the socket was never
//    explicitly closed on unmount, and (relatedly) no pending reconnect timeout was ever
//    cleared either.
//
// Following the same approach as Timeline.rulesOfHooks.test.ts: run ESLint programmatically
// against the file and assert no react-hooks/immutability or react-hooks/refs violations,
// rather than rendering the hook (no @testing-library/react dependency in this repo).

import path from 'path';
import { fileURLToPath } from 'url';
import { describe, expect, it } from 'vitest';
import { ESLint } from 'eslint';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

describe('useContestResultsWebSocket.ts reconnect handling', () => {
    it('never references connectWebSocket before it is declared, and never touches a ref during render', async () => {
        const eslint = new ESLint({ cwd: path.resolve(__dirname, '../..') });
        const [result] = await eslint.lintFiles([path.resolve(__dirname, 'useContestResultsWebSocket.ts')]);

        const violations = result.messages.filter(
            (message) => message.ruleId === 'react-hooks/immutability' || message.ruleId === 'react-hooks/refs'
        );

        expect(violations).toEqual([]);
    });
});
