import djangoJsReverse from 'django-js-reverse';

let _urls: any = null;

export const initUrls = async () => {
    try {
        const response = await fetch('/api/v1/reverse-urls/');
        if (!response.ok) {
            throw new Error(`Failed to fetch reverse URLs: ${response.statusText}`);
        }
        const data = await response.json();
        _urls = djangoJsReverse(data);
        console.log("URLs initialized successfully.");
    } catch (error) {
        console.error("Could not initialize URLs:", error);
        // Handle error appropriately in a real app, maybe retry or show an error state
    }
};

export const reverse = (name: string, ...args: (string | number)[]) => {
    if (!_urls) {
        // This could happen if reverse is called before initUrls is complete.
        // In a real app, you'd want a more robust way to handle this,
        // like a state to prevent API calls before urls are ready.
        console.error("URLs not initialized! Make sure to call initUrls() on app startup.");
        // We can't throw an error as it would crash the app,
        // so we return a placeholder that will likely fail the network request,
        // which is a detectable side-effect.
        return `/url-initialization-failed/${name}/`;
    }
    // @ts-ignore
    return _urls[name](...args);
};
