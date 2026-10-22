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
