import { loadFont } from "@remotion/google-fonts/Inter";
import { Easing } from "remotion";
import { brand } from "./brand";

// Bundled with the video, so it looks the same on every machine
const { fontFamily } = loadFont("normal", { weights: ["400", "500", "600", "700", "800"], subsets: ["latin"] });

export const theme = {
  background: `radial-gradient(ellipse at 18% 0%, rgba(225,29,36,0.22) 0%, rgba(225,29,36,0) 45%), ${brand.colors.background}`,
  accent: brand.colors.red,
  highlight: brand.colors.red,
  highlightGlow: "rgba(225,29,36,0.45)",
  text: brand.colors.text,
  muted: brand.colors.muted,
  font: fontFamily,
  ease: Easing.bezier(0.33, 1, 0.68, 1),
};
