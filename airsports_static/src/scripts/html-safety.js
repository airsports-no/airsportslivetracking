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

// Shared scheme validation for both helpers below: only http(s) (or relative, resolved
// against `base`) URLs are allowed, blocking javascript:/data: URLs. Returns the resolved
// href, or null if the value is missing/malformed/an unsafe scheme.
function validatedHref(value, base) {
    if (!value) return null;
    try {
        const parsed = new URL(String(value), base);
        if (parsed.protocol === "http:" || parsed.protocol === "https:") {
            return parsed.href;
        }
    } catch (e) {
        // Malformed URL - fall through to null below.
    }
    return null;
}

// For values placed inside a src="" or href="" attribute *as part of an HTML string*
// (i.e. interpolated into a template string that then gets assigned to .innerHTML): rejects
// any scheme other than http(s)/relative, and HTML-escapes the result so a "-containing
// value can't break out of the attribute. The browser's HTML parser decodes the escaped
// entities back when it parses that markup, so the resulting attribute value is correct.
export function safeUrl(value, base = window.location.origin) {
    const href = validatedHref(value, base);
    return href === null ? "#" : escapeHtml(href);
}

// For assigning directly to a DOM property (e.g. anchor.href = ...) rather than interpolating
// into an HTML string: DOM property assignment does not run the HTML parser, so - unlike
// safeUrl above - the value must NOT be HTML-escaped, or the literal escaped entities (e.g.
// "&amp;" instead of "&") end up in the URL the browser actually navigates to.
export function safeUrlForProperty(value, base = window.location.origin) {
    const href = validatedHref(value, base);
    return href === null ? "#" : href;
}
