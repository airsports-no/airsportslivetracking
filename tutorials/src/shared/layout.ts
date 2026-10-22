// The video's frame: 1920x1080 at 30 fps, the recorded page shown in a window on a background
export const VIDEO = { width: 1920, height: 1080, fps: 30 };
export const INTRO_MS = 2800;
export const OUTRO_MS = 2600;
export const TRANSITION_MS = 500;
export const WINDOW_MARGIN = { x: 64, y: 44 };

export const compositionId = (name: string) => name.replace(/[^a-zA-Z0-9-]/g, "-");
