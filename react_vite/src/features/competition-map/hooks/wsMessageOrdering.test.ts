import { describe, expect, it } from 'vitest';
import { evaluateIncomingMessage, mergeAcceptedVersions, takeHigherVersion } from './wsMessageOrdering';

describe('evaluateIncomingMessage', () => {
    it('accepts the first message for a contestant with no prior baseline', () => {
        const result = evaluateIncomingMessage(undefined, 0, { msgId: 100, trackVersion: 1, scoreVersion: 1 });
        expect(result).toEqual({ accept: true, nextLatestMsgId: 100 });
    });

    it('rejects a message whose track_version regresses relative to the baseline', () => {
        const versions = { track_version: 5, score_version: 2 };
        const result = evaluateIncomingMessage(versions, 0, { msgId: 200, trackVersion: 4, scoreVersion: 2 });
        expect(result.accept).toBe(false);
    });

    it('rejects a message whose score_version regresses relative to the baseline', () => {
        const versions = { track_version: 5, score_version: 3 };
        const result = evaluateIncomingMessage(versions, 0, { msgId: 200, trackVersion: 5, scoreVersion: 2 });
        expect(result.accept).toBe(false);
    });

    it('rejects an out-of-order msg_id within the same version epoch', () => {
        const versions = { track_version: 5, score_version: 2 };
        const result = evaluateIncomingMessage(versions, /* latestMsgId */ 500, {
            msgId: 300,
            trackVersion: 5,
            scoreVersion: 2,
        });
        expect(result.accept).toBe(false);
    });

    it('accepts a lower msg_id if it carries a HIGHER version (a reset, e.g. recalculation)', () => {
        const versions = { track_version: 5, score_version: 2 };
        const result = evaluateIncomingMessage(versions, /* latestMsgId */ 500, {
            msgId: 300,
            trackVersion: 6,
            scoreVersion: 2,
        });
        expect(result).toEqual({ accept: true, nextLatestMsgId: 300 });
    });

    // Regression test for the frontend race during recalculation: a burst of many messages for
    // the same contestant can be processed back-to-back, synchronously, before React has re-
    // rendered. The stale-message guard's baseline MUST be updated the instant each message is
    // accepted (mergeAcceptedVersions, called eagerly) - not only after a render has committed
    // and a ref-sync effect has run.
    //
    // The two messages below are of DIFFERENT ws message types (e.g. position_data vs
    // score_log), so they track msg_id ordering independently (their own msgTypeKey/
    // latestMsgId) - msg_id ordering alone can't catch the second message being stale, only the
    // version-regression check can. This models the actual bug: the newer position_data message
    // bumps the true version to 6, but a late score_log message left over from before the
    // recalculation still carries the old version (5).
    it('would wrongly accept a stale message from another stream if the baseline is not updated eagerly between messages in a burst', () => {
        const initialVersions = { track_version: 5, score_version: 2 };
        const newerPositionMessage = { msgId: 1000, trackVersion: 6, scoreVersion: 2 };
        const staleScoreLogMessage = { msgId: 51, trackVersion: 5, scoreVersion: 2 }; // leftover from before the recalculation bumped the version
        const staleMessageOwnStreamLatestMsgId = 50; // score_log's own msgTypeKey counter, unrelated to position_data's

        // Correct usage (what the hook does): merge the accepted baseline after EACH message.
        const first = evaluateIncomingMessage(initialVersions, 0, newerPositionMessage);
        expect(first.accept).toBe(true);
        const versionsAfterFirst = mergeAcceptedVersions(initialVersions, newerPositionMessage.trackVersion, newerPositionMessage.scoreVersion);

        const second = evaluateIncomingMessage(versionsAfterFirst, staleMessageOwnStreamLatestMsgId, staleScoreLogMessage);
        expect(second.accept).toBe(false); // correctly rejected: stale relative to the just-accepted newer message

        // Buggy usage (the pre-fix bug): evaluate the second message against the SAME stale
        // baseline used for the first, because the baseline hadn't been refreshed yet (it only
        // updated once React re-rendered and a useEffect copied the new state into a ref).
        const secondAgainstStaleBaseline = evaluateIncomingMessage(initialVersions, staleMessageOwnStreamLatestMsgId, staleScoreLogMessage);
        expect(secondAgainstStaleBaseline.accept).toBe(true); // demonstrates the bug: a stale message slips through
    });
});

describe('mergeAcceptedVersions', () => {
    it('keeps the prior score_version when only track_version is present on the new message', () => {
        const result = mergeAcceptedVersions({ track_version: 1, score_version: 4 }, 2, undefined);
        expect(result).toEqual({ track_version: 2, score_version: 4 });
    });

    it('returns the existing versions unchanged when the message carries neither field', () => {
        const versions = { track_version: 1, score_version: 4 };
        expect(mergeAcceptedVersions(versions, undefined, undefined)).toBe(versions);
    });

    it('starts a fresh baseline when there was none before', () => {
        expect(mergeAcceptedVersions(undefined, 3, 7)).toEqual({ track_version: 3, score_version: 7 });
    });
});

describe('takeHigherVersion', () => {
    it('returns the higher of two defined numbers', () => {
        expect(takeHigherVersion(3, 7)).toBe(7);
        expect(takeHigherVersion(7, 3)).toBe(7);
    });

    it('falls back to whichever side is defined', () => {
        expect(takeHigherVersion(undefined, 5)).toBe(5);
        expect(takeHigherVersion(5, undefined)).toBe(5);
        expect(takeHigherVersion(undefined, undefined)).toBeUndefined();
    });
});
