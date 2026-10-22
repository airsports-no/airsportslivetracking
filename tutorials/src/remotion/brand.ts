// The look every tutorial shares: title screen, logo, colours and the end screen's information. Change it here.

export const brand = {
  name: "Air Sports Live Tracking",
  // The white wordmark from the site's header (src/static/img/airsports_live_tracking_white.png), for dark backgrounds
  wordmark: "brand/wordmark.png",
  wordmarkAspect: 1600 / 288,
  colors: {
    // The logo's red
    red: "#e11d24",
    background: "#0a0c10",
    panel: "#12161d",
    text: "#f8fafc",
    muted: "#94a3b8",
    line: "rgba(255,255,255,0.08)",
  },
  // Background music for every video, unless a script says otherwise (music: false, or another file). The file is not
  // in git (the licence covers using it in the videos, not passing it on): npm run fetch-assets fetches it from the
  // team's private bucket into public/brand/music/.
  music: {
    // "New Morning" by TrackTribe, from the YouTube Audio Library, levelled with npm run music
    file: "brand/music/new-morning-tracktribe.levelled.mp3",
    credit: "Music: New Morning by TrackTribe",
    // Volume (1 = as levelled) on the title and end screens, between narration lines, and under the narration: about
    // 4, 14 and 22 dB down, which puts the music some 17 dB under the voice while it speaks
    levels: { full: 0.6, between: 0.2, underVoice: 0.08 },
    // Where in the track the video starts (ms)
    startAtMs: 0,
  },
  // The end screen: where to go from here
  endScreen: {
    links: [
      { label: "Get started", value: "app.airsports.no" },
      { label: "Organiser guide", value: "airsports.no/docs/03_Contest_Manager_Guide" },
      { label: "Pilot guide", value: "airsports.no/docs/02_Contestant_Guide" },
      { label: "More tutorials", value: "airsports.no/tutorials" },
      { label: "Questions", value: "airsports.no/faq" },
    ],
  },
};
