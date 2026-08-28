// Escaping helpers for server-sourced strings interpolated into innerHTML template strings.
// Any field ultimately backed by user-editable input (pilot/team names, contest/task names,
// aircraft registrations, free-text blurbs, or URLs an organiser configured) must be escaped
// here before being placed into markup - see the 2026-08-28 security review for the incident
// this fixes (unsanitised profile names reaching the public homepage via .innerHTML).

export function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

// For values placed inside a src="" or href="" attribute: rejects any scheme other than
// http(s)/relative (blocking javascript:/data: URLs), and HTML-escapes the result so a
// "-containing value can't break out of the attribute.
export function safeUrl(value, base = window.location.origin) {
    if (!value) return "#";
    try {
        const parsed = new URL(String(value), base);
        if (parsed.protocol === "http:" || parsed.protocol === "https:") {
            return escapeHtml(parsed.href);
        }
    } catch (e) {
        // Malformed URL - fall through to the safe default below.
    }
    return "#";
}
