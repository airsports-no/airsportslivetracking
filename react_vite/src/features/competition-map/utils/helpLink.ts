/** The guide to the live map on the documentation site (airsports_static, docs/15_Live_Map.md). */
const GUIDE = 'https://airsports.no/docs/15_Live_Map';

/** The parts of the guide, as the headings' anchors: where the viewer is decides where the help button goes. */
export type GuideSection = 'spectators' | 'following' | 'screen' | 'broadcast' | 'debrief' | 'settings';

const ANCHORS: Record<GuideSection, string> = {
    spectators: 'spectators-the-whole-field',
    following: 'following-a-contestant-live',
    screen: 'airfield-screens',
    broadcast: 'broadcast',
    debrief: 'pilot-debrief',
    settings: 'every-button-and-setting',
};

export function guideUrl(section?: GuideSection): string {
    return section ? `${GUIDE}#${ANCHORS[section]}` : GUIDE;
}
