import { Player, type PlayerRef } from "@remotion/player";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { TutorialVideo } from "../remotion/TutorialVideo";
import { computeEdit, STEP_LEAD_MS, stepAnchor } from "../shared/edit";
import { INTRO_MS, OUTRO_MS, TRANSITION_MS, VIDEO } from "../shared/layout";
import { DEFAULT_EDIT, type EditSettings, type Step, type Timeline } from "../shared/timeline";
import { addedLineKeys, type AddedLine, type StepTiming, type Timing, type Voice } from "../shared/timing";

// The timing editor's page (served by server.ts): the video as render makes it, the steps beside it, and the
// timing file's changes for the chosen step. The edit is worked out here as render does (computeEdit), so a change
// plays at once.

type Data = { name: string; timeline: Timeline; voice: Voice; timing: Timing };
// A recording, a chapter's clicks recorded again, or putting them into the script (server.ts)
type Job = { kind: "record" | "clicks" | "replace"; chapter?: string; log: string[]; running: boolean; code: number | null };
const JOB_TITLES = {
  record: (chapter?: string) => (chapter ? `Recording from "${chapter}"` : "Recording all of it"),
  clicks: (chapter?: string) => `Recording the clicks of "${chapter}" on Windows: close the browser when done`,
  replace: (chapter?: string) => `Putting the new clicks of "${chapter}" into the script`,
};

// Where the tutorial starts in the video: after the title screen, less the crossfade
const OFFSET_MS = INTRO_MS - TRANSITION_MS;
const SPEEDS = [0.25, 0.5, 0.75, 1.5, 2, 3, 4];

const clock = (ms: number) => {
  const tenths = Math.max(0, Math.round(ms / 100));
  return `${Math.floor(tenths / 600)}:${String(Math.floor(tenths / 10) % 60).padStart(2, "0")}.${tenths % 10}`;
};

// Only what changes something, in the recording's order of steps, so the file stays short and readable
function tidy(timing: Timing, steps: Step[]): Timing {
  const result: Timing = {};
  const edit = Object.fromEntries(
    Object.entries(timing.edit ?? {}).filter(([, value]) => typeof value === "number" && Number.isFinite(value)),
  );
  if (Object.keys(edit).length > 0) result.edit = edit;
  const order = new Map(steps.map((step, index) => [step.id, index]));
  const entries = Object.entries(timing.steps ?? {})
    .map(([id, change]) => {
      const kept = Object.fromEntries(
        Object.entries(change).filter(([key, value]) => {
          if (value === undefined || value === null || value === "") return false;
          if ((key === "holdMs" || key === "delayMs") && value === 0) return false;
          return !(key === "speed" && value === 1);
        }),
      ) as StepTiming;
      if (kept.until && !kept.speed) delete kept.until;
      return [id, kept] as const;
    })
    .filter(([, change]) => Object.keys(change).length > 0)
    .sort(([a], [b]) => (order.get(a) ?? Infinity) - (order.get(b) ?? Infinity));
  if (entries.length > 0) result.steps = Object.fromEntries(entries);
  // Added chapters and lines in the order they were added: a line's name counts the lines before it at its step
  if (timing.chapters?.length) result.chapters = timing.chapters;
  if (timing.lines?.length) {
    result.lines = timing.lines.map((line) => {
      const kept: AddedLine = { at: line.at, text: line.text };
      if (line.wait === false) kept.wait = false;
      if (line.delayMs) kept.delayMs = line.delayMs;
      return kept;
    });
  }
  return result;
}

function App() {
  const [data, setData] = useState<Data | null>(null);
  const [timing, setTiming] = useState<Timing>({});
  const [saved, setSaved] = useState("{}");
  const [voice, setVoice] = useState<Voice>({ lines: {} });
  const [selected, setSelected] = useState<string | null>(null);
  const [frame, setFrame] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const player = useRef<PlayerRef>(null);
  const stepList = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/data")
      .then((response) => response.json())
      .then((loaded: Data) => {
        const tidied = tidy(loaded.timing, loaded.timeline.steps);
        setData(loaded);
        setTiming(tidied);
        setSaved(JSON.stringify(tidied));
        setVoice(loaded.voice);
      })
      .catch((error) => setMessage(`Could not load the recording: ${error}`));
  }, []);

  // A job's progress, while it runs; a recording that has finished is loaded again
  const reload = useCallback(async () => {
    const loaded: Data = await (await fetch("/api/data")).json();
    setData((before) => (before ? { ...before, timeline: loaded.timeline } : loaded));
    setVoice(loaded.voice);
  }, []);
  const startJob = async (kind: Job["kind"], chapter?: string) => {
    if (dirty && !window.confirm("The timing has unsaved changes. Start anyway? (They stay in the editor.)")) return;
    const response = await fetch(`/api/job/${kind}`, { method: "POST", body: JSON.stringify({ chapter }) });
    const result = await response.json();
    if (!response.ok) setMessage(result.error);
    else setJob(result);
  };
  useEffect(() => {
    if (!job?.running) return;
    const timer = setInterval(async () => {
      const now: Job | null = await (await fetch("/api/job")).json();
      setJob(now);
      if (now && !now.running) {
        clearInterval(timer);
        if (now.kind === "record") await reload();
        // The new clicks are in the script: record the chapter with them
        if (now.kind === "replace" && now.code === 0) void startJob("record", now.chapter);
      }
    }, 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.running]);

  const timeline = data?.timeline;
  const tidied = useMemo(() => (timeline ? tidy(timing, timeline.steps) : timing), [timing, timeline]);
  const dirty = JSON.stringify(tidied) !== saved;
  const edit = useMemo(() => (timeline ? computeEdit(timeline, voice, tidied) : null), [timeline, voice, tidied]);
  const durationInFrames = edit
    ? Math.ceil(((INTRO_MS + edit.durationMs + OUTRO_MS - 2 * TRANSITION_MS) / 1000) * VIDEO.fps)
    : 1;
  const inputProps = useMemo(
    () => (data && timeline ? { name: data.name, timeline, voice, timing: tidied } : null),
    [data, timeline, voice, tidied],
  );

  // Where each step is in the video: a narration line where it starts, anything else where it happens
  const stepTimes = useMemo(() => {
    const times = new Map<string, number>();
    if (!edit || !timeline) return times;
    const starts = new Map(edit.narration.map((line) => [line.step, line.start]));
    for (const step of timeline.steps) times.set(step.id, OFFSET_MS + (starts.get(step.id) ?? edit.toOut(step.t)));
    for (const key of addedLineKeys(tidied.lines ?? [])) {
      const start = starts.get(key);
      if (start !== undefined) times.set(key, OFFSET_MS + start);
    }
    return times;
  }, [edit, timeline, tidied]);

  // The step being shown, as Studio's badge finds it: the camera starts moving to a step STEP_LEAD_MS before it
  const current = useMemo(() => {
    if (!edit || !timeline) return undefined;
    const outMs = (frame / VIDEO.fps) * 1000 - OFFSET_MS;
    if (outMs < 0) return undefined;
    const srcMs = edit.toSrc(outMs);
    return [...timeline.steps].reverse().find((step) => step.t <= srcMs + STEP_LEAD_MS);
  }, [edit, timeline, frame]);

  useEffect(() => {
    const instance = player.current;
    if (!instance) return;
    const onFrame = (event: { detail: { frame: number } }) => setFrame(event.detail.frame);
    instance.addEventListener("frameupdate", onFrame);
    instance.addEventListener("seeked", onFrame);
    return () => {
      instance.removeEventListener("frameupdate", onFrame);
      instance.removeEventListener("seeked", onFrame);
    };
  }, [inputProps]);

  // The list follows the video while it plays
  useEffect(() => {
    if (!current || !player.current?.isPlaying()) return;
    stepList.current?.querySelector(`[data-step="${CSS.escape(current.id)}"]`)?.scrollIntoView({ block: "nearest" });
  }, [current]);

  const seekTo = (id: string) => {
    const step = timeline?.steps.find((item) => item.id === id);
    if (!step && stepTimes.has(id)) {
      // An added line: where it starts
      player.current?.seekTo(Math.max(0, Math.round(((stepTimes.get(id)! - 300) / 1000) * VIDEO.fps)));
      return;
    }
    if (!step || !edit) return;
    // Where the camera starts moving to the step, before the picture is held there (holdMs), so both show
    const hold = Math.max(0, tidied.steps?.[id]?.holdMs ?? 0);
    const lead = OFFSET_MS + edit.toOut(Math.max(0, step.t - STEP_LEAD_MS)) - hold;
    const ms = Math.min(stepTimes.get(id) ?? lead, lead);
    player.current?.seekTo(Math.max(0, Math.round((ms / 1000) * VIDEO.fps)));
  };

  const change = (id: string, patch: Partial<StepTiming>) =>
    setTiming((before) => ({ ...before, steps: { ...before.steps, [id]: { ...before.steps?.[id], ...patch } } }));
  const changeEdit = (patch: Partial<EditSettings>) =>
    setTiming((before) => ({ ...before, edit: { ...before.edit, ...patch } }));

  // Chapters and lines added before a step
  const addChapter = (at: string) => {
    const title = window.prompt("The new chapter's title (it starts as the camera moves to this step)")?.trim();
    if (title) setTiming((before) => ({ ...before, chapters: [...(before.chapters ?? []), { at, title }] }));
  };
  const renameChapter = (index: number) => {
    const title = window.prompt("The chapter's title", timing.chapters?.[index]?.title)?.trim();
    if (title) {
      setTiming((before) => ({
        ...before,
        chapters: before.chapters?.map((chapter, other) => (other === index ? { ...chapter, title } : chapter)),
      }));
    }
  };
  const deleteChapter = (index: number) =>
    setTiming((before) => ({ ...before, chapters: before.chapters?.filter((_, other) => other !== index) }));
  const addLine = (at: string) => {
    const text = window.prompt("What is said before this step (and shown as captions)")?.trim();
    if (!text) return;
    const lines = [...(timing.lines ?? []), { at, text }];
    setTiming((before) => ({ ...before, lines }));
    setSelected(addedLineKeys(lines)[lines.length - 1]);
  };
  const changeLine = (index: number, patch: Partial<AddedLine>) =>
    setTiming((before) => ({
      ...before,
      lines: before.lines?.map((line, other) => (other === index ? { ...line, ...patch } : line)),
    }));
  const deleteLine = (index: number) => {
    setTiming((before) => ({ ...before, lines: before.lines?.filter((_, other) => other !== index) }));
    setSelected(null);
  };

  const save = useCallback(async () => {
    setBusy("Saving");
    try {
      const response = await fetch("/api/timing", { method: "POST", body: JSON.stringify(tidied) });
      if (!response.ok) throw new Error((await response.json()).error);
      setSaved(JSON.stringify(tidied));
      setMessage(`Saved scripts/${data?.name}.timing.ts`);
    } catch (error) {
      setMessage(`Not saved: ${error}`);
    } finally {
      setBusy(null);
    }
  }, [tidied, data]);

  const makeVoice = async () => {
    await save();
    setBusy("Making the voice");
    try {
      const response = await fetch("/api/narrate", { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      setVoice(result.voice);
      setMessage("The voice is up to date");
    } catch (error) {
      setMessage(`No voice made: ${error}`);
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "s") {
        event.preventDefault();
        if (dirty) void save();
      }
    };
    const onLeave = (event: BeforeUnloadEvent) => {
      if (dirty) event.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("beforeunload", onLeave);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("beforeunload", onLeave);
    };
  }, [dirty, save]);

  if (!data || !timeline || !edit || !inputProps) {
    return <div className="loading">{message ?? "Loading the recording…"}</div>;
  }

  const editSettings = { ...DEFAULT_EDIT, ...timeline.edit };
  const missingVoice = edit.warnings.some((warning) => warning.includes("has no voice yet"));
  const selectedStep = timeline.steps.find((step) => step.id === selected);
  const lineKeys = addedLineKeys(tidied.lines ?? []);
  const selectedLine = lineKeys.indexOf(selected ?? "");
  // The chapters in the recording's time, recorded and added (with their index in the timing file), for the list
  const chapterStarts = [
    ...(timeline.chapters ?? []).map((chapter) => ({ t: chapter.t, title: chapter.title, added: -1 })),
    ...(tidied.chapters ?? []).flatMap((chapter, index) => {
      const t = stepAnchor(timeline, chapter.at);
      return t === undefined ? [] : [{ t, title: chapter.title, added: index }];
    }),
  ].sort((a, b) => a.t - b.t);
  let shownChapter = 0;

  return (
    <div className="app">
      <header>
        <h1>
          Timing <span>{data.name}</span>
        </h1>
        <div className="actions">
          {message && <span className="message">{message}</span>}
          {busy && <span className="message">{busy}…</span>}
          <button type="button" onClick={() => startJob("record")} disabled={job?.running}>
            Record all
          </button>
          <button type="button" onClick={() => setTiming(JSON.parse(saved))} disabled={!dirty || busy !== null}>
            Undo changes
          </button>
          <button type="button" onClick={makeVoice} disabled={!missingVoice || busy !== null}>
            Make voice
          </button>
          <button type="button" className="primary" onClick={save} disabled={!dirty || busy !== null}>
            {dirty ? "Save" : "Saved"}
          </button>
        </div>
      </header>
      <main>
        <section className="video">
          <Player
            ref={player}
            component={TutorialVideo}
            inputProps={inputProps}
            durationInFrames={durationInFrames}
            compositionWidth={VIDEO.width}
            compositionHeight={VIDEO.height}
            fps={VIDEO.fps}
            controls
            clickToPlay
            acknowledgeRemotionLicense
            style={{ width: "100%", aspectRatio: "16 / 9" }}
          />
          <div className="now">
            {clock((frame / VIDEO.fps) * 1000)} / {clock((durationInFrames / VIDEO.fps) * 1000)}
            {current ? <strong>{current.id}</strong> : <strong>title screen</strong>}
            {current && <span>{current.label}</span>}
          </div>
          {selectedLine >= 0 && tidied.lines ? (
            <LineInspector
              name={lineKeys[selectedLine]}
              line={tidied.lines[selectedLine]}
              onChange={(patch) => changeLine(selectedLine, patch)}
              onDelete={() => deleteLine(selectedLine)}
              onPlay={() => {
                seekTo(lineKeys[selectedLine]);
                player.current?.play();
              }}
            />
          ) : selectedStep ? (
            <Inspector
              step={selectedStep}
              steps={timeline.steps}
              timeline={timeline}
              change={tidied.steps?.[selectedStep.id] ?? {}}
              onChange={(patch) => change(selectedStep.id, patch)}
              onClear={() =>
                setTiming((before) => ({ ...before, steps: { ...before.steps, [selectedStep.id]: {} } }))
              }
              onPlay={() => {
                seekTo(selectedStep.id);
                player.current?.play();
              }}
              onAddChapter={() => addChapter(selectedStep.id)}
              onAddLine={() => addLine(selectedStep.id)}
            />
          ) : (
            <p className="hint">Choose a step in the list to change its timing. The video jumps to it.</p>
          )}
          <fieldset className="global">
            <legend>Cutting still stretches, for the whole video</legend>
            <label>
              Longer than
              <NumberInput
                value={tidied.edit?.minGapMs}
                placeholder={editSettings.minGapMs}
                step={100}
                onChange={(minGapMs) => changeEdit({ minGapMs })}
              />
              ms
            </label>
            <label>
              is shortened to
              <NumberInput
                value={tidied.edit?.keepGapMs}
                placeholder={editSettings.keepGapMs}
                step={50}
                onChange={(keepGapMs) => changeEdit({ keepGapMs })}
              />
              ms
            </label>
          </fieldset>
          {job && (
            <JobPanel
              job={job}
              onStop={() => fetch("/api/job/stop", { method: "POST", body: "{}" })}
              onUseClicks={() => startJob("replace", job.chapter)}
              onClose={() => setJob(null)}
            />
          )}
          {edit.warnings.length > 0 && (
            <ul className="warnings">
              {edit.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </section>
        <aside ref={stepList}>
          {timeline.steps.map((step) => {
            // The chapters that start before this step, and the lines added before it
            const headings = [];
            while (shownChapter < chapterStarts.length && chapterStarts[shownChapter].t <= step.t) {
              headings.push(chapterStarts[shownChapter++]);
            }
            const lines = (tidied.lines ?? []).flatMap((line, index) => (line.at === step.id ? [{ line, index }] : []));
            const stepChange = tidied.steps?.[step.id];
            return (
              <div key={step.id}>
                {headings.map((heading) => (
                  <h2 key={`${heading.title}-${heading.t}`} className={heading.added >= 0 ? "added" : undefined}>
                    {heading.title}
                    {heading.added < 0 && (
                      <>
                        <button
                          type="button"
                          disabled={job?.running}
                          title="Record the video again from this chapter, keeping what comes before it"
                          onClick={() => startJob("record", heading.title)}
                        >
                          record from here
                        </button>
                        <button
                          type="button"
                          disabled={job?.running}
                          title="Record this chapter's clicks again on Windows (the steps before it are replayed first)"
                          onClick={() => startJob("clicks", heading.title)}
                        >
                          redo clicks
                        </button>
                      </>
                    )}
                    {heading.added >= 0 && (
                      <>
                        <button type="button" onClick={() => renameChapter(heading.added)}>
                          rename
                        </button>
                        <button type="button" onClick={() => deleteChapter(heading.added)}>
                          delete
                        </button>
                      </>
                    )}
                  </h2>
                ))}
                {lines.map(({ line, index }) => (
                  <button
                    key={lineKeys[index]}
                    type="button"
                    className={`step added${lineKeys[index] === selected ? " selected" : ""}`}
                    onClick={() => {
                      setSelected(lineKeys[index]);
                      seekTo(lineKeys[index]);
                    }}
                  >
                    <span className="time">{clock(stepTimes.get(lineKeys[index]) ?? 0)}</span>
                    <span className="id">+</span>
                    <span className="label">say({JSON.stringify(line.text)})</span>
                  </button>
                ))}
                <button
                  type="button"
                  data-step={step.id}
                  className={`step${step.id === selected ? " selected" : ""}${step.id === current?.id ? " current" : ""}`}
                  onClick={() => {
                    setSelected(step.id);
                    seekTo(step.id);
                  }}
                >
                  <span className="time">{clock(stepTimes.get(step.id) ?? 0)}</span>
                  <span className="id">#{step.id.match(/#(\d+)$/)?.[1]}</span>
                  <span className="label">{step.label}</span>
                  {stepChange && <ChangeBadges change={stepChange} />}
                </button>
              </div>
            );
          })}
        </aside>
      </main>
    </div>
  );
}

function ChangeBadges({ change }: { change: StepTiming }) {
  const badges: string[] = [];
  if (change.holdMs) badges.push(`${change.holdMs > 0 ? "+" : ""}${(change.holdMs / 1000).toFixed(1)} s`);
  if (change.speed) badges.push(`×${change.speed}`);
  if (change.delayMs) badges.push(`line ${change.delayMs > 0 ? "+" : ""}${(change.delayMs / 1000).toFixed(1)} s`);
  if (change.wait !== undefined) badges.push(change.wait ? "waits" : "no wait");
  if (change.text) badges.push("text");
  return (
    <span className="badges">
      {badges.map((badge) => (
        <span key={badge}>{badge}</span>
      ))}
    </span>
  );
}

function NumberInput({
  value,
  placeholder,
  step,
  onChange,
}: {
  value: number | undefined;
  placeholder?: number;
  step: number;
  onChange: (value: number | undefined) => void;
}) {
  const current = value ?? 0;
  return (
    <span className="number">
      <button type="button" onClick={() => onChange((value ?? placeholder ?? 0) - step)}>
        −
      </button>
      <input
        type="number"
        step={step}
        value={value ?? ""}
        placeholder={placeholder !== undefined ? String(placeholder) : "0"}
        onChange={(event) => onChange(event.target.value === "" ? undefined : Number(event.target.value))}
      />
      <button type="button" onClick={() => onChange((value ?? placeholder ?? current) + step)}>
        +
      </button>
    </span>
  );
}

function Inspector({
  step,
  steps,
  timeline,
  change,
  onChange,
  onClear,
  onPlay,
  onAddChapter,
  onAddLine,
}: {
  step: Step;
  steps: Step[];
  timeline: Timeline;
  change: StepTiming;
  onChange: (patch: Partial<StepTiming>) => void;
  onClear: () => void;
  onPlay: () => void;
  onAddChapter: () => void;
  onAddLine: () => void;
}) {
  const say = timeline.says.find((item) => item.step === step.id);
  const later = steps.slice(steps.indexOf(step) + 1);
  return (
    <div className="inspector">
      <div className="title">
        <strong>{step.id}</strong>
        <span>{step.label}</span>
        <button type="button" onClick={onPlay}>
          Play from here
        </button>
        <button type="button" onClick={onClear} disabled={Object.keys(change).length === 0}>
          Clear changes
        </button>
      </div>
      <div className="add">
        Before this step:
        <button type="button" onClick={onAddChapter}>
          New chapter here
        </button>
        <button type="button" onClick={onAddLine}>
          New line here
        </button>
      </div>
      <label>
        Hold the picture before the step
        <NumberInput value={change.holdMs} step={250} onChange={(holdMs) => onChange({ holdMs })} />
        ms <small>(less than 0: shorter wait)</small>
      </label>
      <label>
        Speed
        <select
          value={change.speed ?? ""}
          onChange={(event) => onChange({ speed: event.target.value === "" ? undefined : Number(event.target.value) })}
        >
          <option value="">normal</option>
          {SPEEDS.map((speed) => (
            <option key={speed} value={speed}>
              ×{speed} {speed > 1 ? "faster" : "slower"}
            </option>
          ))}
        </select>
        until
        <select
          value={change.until ?? ""}
          disabled={!change.speed}
          onChange={(event) => onChange({ until: event.target.value || undefined })}
        >
          <option value="">the next step</option>
          {later.map((item) => (
            <option key={item.id} value={item.id}>
              {item.id}: {item.label.slice(0, 50)}
            </option>
          ))}
        </select>
      </label>
      {say && (
        <>
          <label>
            Start the line
            <NumberInput value={change.delayMs} step={250} onChange={(delayMs) => onChange({ delayMs })} />
            ms later <small>(less than 0: earlier)</small>
          </label>
          <label>
            The next step
            <select
              value={change.wait === undefined ? "" : String(change.wait)}
              onChange={(event) => onChange({ wait: event.target.value === "" ? undefined : event.target.value === "true" })}
            >
              <option value="">as the script says ({say.wait ? "waits" : "does not wait"})</option>
              <option value="true">waits until the line has been said</option>
              <option value="false">carries on while it is said</option>
            </select>
          </label>
          <label className="text">
            What is said (and shown as captions)
            <textarea
              rows={3}
              value={change.text ?? say.text}
              onChange={(event) => onChange({ text: event.target.value === say.text ? undefined : event.target.value })}
            />
            {change.text && <small>Changed from the script. Make voice to hear it.</small>}
          </label>
        </>
      )}
    </div>
  );
}

// What a job does, as it goes
function JobPanel({
  job,
  onStop,
  onUseClicks,
  onClose,
}: {
  job: Job;
  onStop: () => void;
  onUseClicks: () => void;
  onClose: () => void;
}) {
  const log = useRef<HTMLPreElement>(null);
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [job.log.length]);
  return (
    <div className="job">
      <div className="title">
        <strong>{JOB_TITLES[job.kind](job.chapter)}</strong>
        <span>{job.running ? "running…" : job.code === 0 ? "done" : "stopped"}</span>
        {job.running ? (
          <button type="button" onClick={onStop}>
            Stop
          </button>
        ) : (
          <>
            {job.kind === "clicks" && job.code === 0 && (
              <button
                type="button"
                className="primary"
                title="Replaces the chapter's steps in the script (the old script goes to .bak), then records from it"
                onClick={onUseClicks}
              >
                Use the new clicks
              </button>
            )}
            <button type="button" onClick={onClose}>
              Close
            </button>
          </>
        )}
      </div>
      <pre ref={log}>{job.log.join("\n")}</pre>
    </div>
  );
}

// A narration line added in the timing file, before the step `at`
function LineInspector({
  name,
  line,
  onChange,
  onDelete,
  onPlay,
}: {
  name: string;
  line: AddedLine;
  onChange: (patch: Partial<AddedLine>) => void;
  onDelete: () => void;
  onPlay: () => void;
}) {
  return (
    <div className="inspector">
      <div className="title">
        <strong>{name}</strong>
        <span>A line added before {line.at}</span>
        <button type="button" onClick={onPlay}>
          Play from here
        </button>
        <button type="button" onClick={onDelete}>
          Delete line
        </button>
      </div>
      <label>
        Start the line
        <NumberInput value={line.delayMs} step={250} onChange={(delayMs) => onChange({ delayMs })} />
        ms later <small>(less than 0: earlier)</small>
      </label>
      <label>
        The next step
        <select
          value={String(line.wait ?? true)}
          onChange={(event) => onChange({ wait: event.target.value === "true" })}
        >
          <option value="true">waits until the line has been said</option>
          <option value="false">carries on while it is said</option>
        </select>
      </label>
      <label className="text">
        What is said (and shown as captions)
        <textarea rows={3} value={line.text} onChange={(event) => onChange({ text: event.target.value })} />
        <small>Make voice to hear it.</small>
      </label>
    </div>
  );
}

const style = document.createElement("style");
style.textContent = `
  :root { color-scheme: dark; --bg: #0a0c10; --panel: #12161d; --line: #262c36; --text: #e8edf3; --muted: #94a3b8;
    --accent: #e11d24; --current: #1e3a5f; font: 14px/1.4 system-ui, sans-serif; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); }
  .loading { padding: 40px; color: var(--muted); }
  .app { display: flex; flex-direction: column; height: 100vh; }
  header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 16px;
    border-bottom: 1px solid var(--line); background: var(--panel); }
  h1 { margin: 0; font-size: 16px; } h1 span { color: var(--muted); font-weight: 500; margin-left: 6px; }
  .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .message { color: var(--muted); }
  button { font: inherit; color: var(--text); background: #1c222c; border: 1px solid var(--line); border-radius: 6px;
    padding: 5px 10px; cursor: pointer; }
  button:hover:not(:disabled) { border-color: var(--muted); }
  button:disabled { opacity: 0.45; cursor: default; }
  button.primary { background: var(--accent); border-color: var(--accent); }
  main { flex: 1; display: grid; grid-template-columns: minmax(0, 1fr) 420px; min-height: 0; }
  .video { overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
  .now { display: flex; gap: 12px; align-items: baseline; color: var(--muted); font-variant-numeric: tabular-nums; }
  .now strong { color: var(--text); }
  .now span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hint { color: var(--muted); margin: 0; }
  .inspector, .global { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px;
    display: flex; flex-direction: column; gap: 10px; margin: 0; }
  .global legend { color: var(--muted); padding: 0 4px; }
  .inspector .title { display: flex; gap: 10px; align-items: baseline; }
  .inspector .title span { flex: 1; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  label { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  label.text { align-items: stretch; flex-direction: column; }
  small { color: var(--muted); }
  .number { display: inline-flex; } .number button { border-radius: 0; padding: 4px 9px; }
  .number button:first-child { border-radius: 6px 0 0 6px; } .number button:last-child { border-radius: 0 6px 6px 0; }
  input, select, textarea { font: inherit; color: var(--text); background: #0d1117; border: 1px solid var(--line);
    padding: 4px 8px; }
  input[type=number] { width: 90px; text-align: right; border-left: 0; border-right: 0; }
  select { border-radius: 6px; max-width: 360px; } textarea { border-radius: 6px; resize: vertical; width: 100%; }
  .warnings { margin: 0; padding: 10px 10px 10px 28px; color: #fbbf24; background: var(--panel); border-radius: 8px; }
  aside { border-left: 1px solid var(--line); overflow-y: auto; padding: 8px; }
  aside h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: var(--accent); margin: 14px 6px 4px;
    display: flex; gap: 6px; align-items: center; }
  aside h2.added { color: #60a5fa; }
  aside h2 button { font-size: 11px; padding: 0 6px; text-transform: none; letter-spacing: 0; }
  .step.added .label { color: #93c5fd; }
  .inspector .add { display: flex; gap: 8px; align-items: center; color: var(--muted); }
  .job { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
  .job .title { display: flex; gap: 10px; align-items: baseline; margin-bottom: 8px; }
  .job .title span { flex: 1; color: var(--muted); }
  .job pre { margin: 0; max-height: 260px; overflow: auto; font-size: 12px; color: var(--muted); white-space: pre-wrap; }
  .step { display: grid; grid-template-columns: 52px 32px minmax(0, 1fr); gap: 2px 6px; width: 100%; text-align: left;
    background: none; border: 1px solid transparent; padding: 5px 6px; }
  .step.current { background: var(--current); }
  .step.selected { border-color: var(--accent); }
  .step .time { color: var(--muted); font-variant-numeric: tabular-nums; }
  .step .id { color: var(--muted); }
  .step .label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: ui-monospace, monospace;
    font-size: 12px; }
  .badges { grid-column: 3; display: flex; gap: 4px; flex-wrap: wrap; }
  .badges span { background: #3b1d1f; color: #fca5a5; border-radius: 4px; padding: 0 6px; font-size: 12px; }
`;
document.head.append(style);
createRoot(document.getElementById("root")!).render(<App />);
