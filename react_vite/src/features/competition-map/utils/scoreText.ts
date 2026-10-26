/**
 * A score log message in a few words for the panel: "outside corridor (19 s). Leg scores: [WP 1: 42.0]. Total: 42.0"
 * reads "Outside corridor 19 s". The leg and total parts repeat what the score already says, durations read "19 s"
 * whichever way they were written ("(19 s)", "(19s)", "(19 seconds)"), and a message it does not recognise passes
 * through with only a capital letter. The full message stays available (title, the entry jumped to, the map's label).
 */
export function shortScoreText(message: string): string {
    let text = message
        .replace(/\.\s*Leg scores:\s*\[[^\]]*\]/i, '')
        .replace(/\.?\s*Total:\s*[-\d.]+\s*\.?/i, '')
        .trim();
    // "inside penalty zone P5 (12s)" -> "in penalty zone P5, 12 s"; without a zone name -> "in penalty zone, 34 s"
    text = text.replace(/^inside penalty zone\s*(.*?)\s*\((\d+)\s*s\)$/i, (_, name: string, seconds: string) =>
        name.trim() ? `in penalty zone ${name.trim()}, ${seconds} s` : `in penalty zone, ${seconds} s`);
    text = text.replace(/^inside penalty zone\b/i, 'in penalty zone');
    // A duration in brackets: "(19 s)", "(19s)", "(19 seconds)" -> "19 s"
    text = text.replace(/\s*\((\d+)\s*(?:s|seconds?)\)/gi, ' $1 s');
    // A signed offset in brackets: "(+21 s)" -> "+21 s"
    text = text.replace(/\s*\(([-+]\d+\s*s)\)/g, ' $1');
    text = text.replace(/\s*:\s*$/, '').replace(/\s{2,}/g, ' ').trim();
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : message;
}
