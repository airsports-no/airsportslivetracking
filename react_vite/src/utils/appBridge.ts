/**
 * Pages are shown inside the mobile apps' web view (?embed=app). The apps intercept navigations to the private
 * `airsportsapp://` scheme and never load them, so this is how a page tells the app that something happened (for
 * example that a flight was registered) without any native bridge code on either platform.
 */
export const APP_SCHEME = 'airsportsapp';

export const isEmbeddedInApp = (): boolean => Boolean(document.configuration?.embeddedInApp);

/** airsportsapp://registered?contestId=1&navigationTaskId=2 */
export const appEventUrl = (event: string, params: Record<string, string | number> = {}): string => {
    const query = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();
    return `${APP_SCHEME}://${event}${query ? `?${query}` : ''}`;
};

export const signalApp = (event: string, params: Record<string, string | number> = {}): void => {
    window.location.href = appEventUrl(event, params);
};
