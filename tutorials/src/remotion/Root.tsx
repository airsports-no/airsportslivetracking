import { Composition, getStaticFiles, staticFile, type CalculateMetadataFunction } from "remotion";
import { computeEdit } from "../shared/edit";
import { compositionId, INTRO_MS, OUTRO_MS, TRANSITION_MS, VIDEO } from "../shared/layout";
import type { Timeline } from "../shared/timeline";
import { TutorialVideo, type TutorialProps } from "./TutorialVideo";

// One composition per recorded tutorial (public/recordings/<name>/timeline.json)
const recorded = getStaticFiles()
  .map((file) => file.name.match(/^recordings\/([^/]+)\/timeline\.json$/)?.[1])
  .filter((name): name is string => Boolean(name));

const calculateMetadata: CalculateMetadataFunction<TutorialProps> = async ({ props }) => {
  const timeline: Timeline = await (await fetch(staticFile(`recordings/${props.name}/timeline.json`))).json();
  const totalMs = INTRO_MS + computeEdit(timeline).durationMs + OUTRO_MS - 2 * TRANSITION_MS;
  return { durationInFrames: Math.ceil((totalMs / 1000) * VIDEO.fps), props: { ...props, timeline } };
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
