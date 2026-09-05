// Pure ordering/versioning logic pulled out of useCompetitionData's processWsMessage so the
// stale-message guard can be unit tested without mocking a WebSocket or a React render cycle.
//
// The guard has two layers, both keyed per contestant (and, for msg_id, per message type - see
// evaluateIncomingMessage's msgTypeKey caller in useCompetitionData.ts):
//   1. track_version/score_version must never go backwards relative to the latest ACCEPTED
//      values for that contestant - this is what protects against a stale message (still in
//      flight from before a recalculation bumped the version) overwriting fresher data.
//   2. Within one version "epoch", msg_id (time_ns()-based, monotonic only within its own
//      backend stream) must also not go backwards for that contestant+type.
//
// Critically, the baseline for both checks must be updated the instant a message is accepted,
// not only once React has re-rendered and a useEffect has copied the new state into a ref -
// during a burst of many messages processed back-to-back (typical of a recalculation replay),
// several messages can be handled before any render happens. A baseline sourced from
// post-render state would then judge every message in the burst against the SAME pre-burst
// snapshot, letting a genuinely stale message slip through after a newer one for the same
// contestant was already accepted moments earlier in the same burst.

export interface VersionState {
    track_version?: number;
    score_version?: number;
}

export interface IncomingMessageVersions {
    msgId?: number;
    trackVersion?: number;
    scoreVersion?: number;
}

export interface MessageEvaluation {
    accept: boolean;
    nextLatestMsgId: number;
}

/**
 * Decides whether an incoming message should be accepted, given the latest accepted
 * versions and msg_id for this contestant (+ message type, for msg_id).
 */
export function evaluateIncomingMessage(
    versions: VersionState | undefined,
    latestMsgId: number,
    incoming: IncomingMessageVersions,
): MessageEvaluation {
    const { msgId, trackVersion, scoreVersion } = incoming;

    if (versions) {
        if (trackVersion !== undefined && versions.track_version !== undefined && trackVersion < versions.track_version) {
            return { accept: false, nextLatestMsgId: latestMsgId };
        }
        if (scoreVersion !== undefined && versions.score_version !== undefined && scoreVersion < versions.score_version) {
            return { accept: false, nextLatestMsgId: latestMsgId };
        }
    }

    if (msgId) {
        if (msgId < latestMsgId) {
            // Only reject based on msgId if the versions are the SAME. If the message has a
            // HIGHER version, it overrides msgId (a version bump, e.g. a recalculation, resets
            // the meaningfulness of msg_id ordering relative to what came before it).
            const sameTrackVersion = trackVersion === undefined || (versions !== undefined && trackVersion === versions.track_version);
            const sameScoreVersion = scoreVersion === undefined || (versions !== undefined && scoreVersion === versions.score_version);
            if (sameTrackVersion && sameScoreVersion) {
                return { accept: false, nextLatestMsgId: latestMsgId };
            }
        }
        return { accept: true, nextLatestMsgId: msgId };
    }

    return { accept: true, nextLatestMsgId: latestMsgId };
}

/** Merges an accepted message's versions into the running per-contestant baseline. */
export function mergeAcceptedVersions(
    versions: VersionState | undefined,
    trackVersion?: number,
    scoreVersion?: number,
): VersionState | undefined {
    if (trackVersion === undefined && scoreVersion === undefined) {
        return versions;
    }
    return {
        track_version: trackVersion !== undefined ? trackVersion : versions?.track_version,
        score_version: scoreVersion !== undefined ? scoreVersion : versions?.score_version,
    };
}

/** The higher of two possibly-undefined version numbers - used to seed a baseline from REST data without ever moving it backwards. */
export function takeHigherVersion(a?: number, b?: number): number | undefined {
    return a === undefined ? b : b === undefined ? a : Math.max(a, b);
}
