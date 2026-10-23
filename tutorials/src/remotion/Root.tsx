import { Composition, getStaticFiles, staticFile, type CalculateMetadataFunction } from "remotion";
import { computeEdit } from "../shared/edit";
import { compositionId, INTRO_MS, OUTRO_MS, TRANSITION_MS, VIDEO } from "../shared/layout";
import type { Timeline } from "../shared/timeline";
import type { Timing, Voice } from "../shared/timing";
import { TutorialVideo, type TutorialProps } from "./TutorialVideo";

// One composition per recorded tutorial (public/recordings/<name>/timeline.json)
const recorded = getStaticFiles()
  .map((file) => file.name.match(/^recordings\/([^/]+)\/timeline\.json$/)?.[1])
  .filter((name): name is string => Boolean(name));

// The timing files (scripts/<name>.timing.ts) are part of the bundle: Studio shows a change as soon as it is saved
const timingFiles = (
  require as unknown as {
    context: (directory: string, subdirectories: boolean, pattern: RegExp) => {
      keys: () => string[];
      (key: string): { default: Timing };
    };
  }
).context("../../scripts", false, /\.timing\.ts$/);
const timingOf = (name: string): Timing => {
  const key = timingFiles.keys().find((file) => file === `./${name}.timing.ts`);
  return key ? timingFiles(key).default : {};
};

const calculateMetadata: CalculateMetadataFunction<TutorialProps> = async ({ props }) => {
  const timeline: Timeline = await (await fetch(staticFile(`recordings/${props.name}/timeline.json`))).json();
  // Missing until npm run narrate has made it: the narration is then shown as captions only, with estimated lengths
  const response = await fetch(staticFile(`recordings/${props.name}/voice.json`));
  const voice: Voice = response.ok ? await response.json() : { lines: {} };
  const timing = timingOf(props.name);
  const totalMs = INTRO_MS + computeEdit(timeline, voice, timing).durationMs + OUTRO_MS - 2 * TRANSITION_MS;
  return { durationInFrames: Math.ceil((totalMs / 1000) * VIDEO.fps), props: { ...props, timeline, voice, timing } };
};

export const RemotionRoot = () => (
  <>
    {recorded.map((name) => (
      <Composition
        key={name}
        id={compositionId(name)}
        component={TutorialVideo}
        width={VIDEO.width}
        height={VIDEO.height}
        fps={VIDEO.fps}
        durationInFrames={1}
        defaultProps={{ name } as TutorialProps}
        calculateMetadata={calculateMetadata}
      />
    ))}
  </>
);
