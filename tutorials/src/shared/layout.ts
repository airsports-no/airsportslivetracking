// The video's frame: 1920x1080 at 30 fps. The recorded page is shown in a window on a background, under a header
// strip with the logo and the tutorial's title.
export const VIDEO = { width: 1920, height: 1080, fps: 30 };
export const INTRO_MS = 3600;
export const OUTRO_MS = 6500;
export const TRANSITION_MS = 600;
export const HEADER_HEIGHT = 78;
export const WINDOW_MARGIN = { x: 64, top: HEADER_HEIGHT, bottom: 34 };

export const compositionId = (name: string) => name.replace(/[^a-zA-Z0-9-]/g, "-");
