// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { RouteRequirementResult, RouteRequirementTool, TaskCompatibilityResult } from '../api';
import { buildWizardChecklist, type CompatibilityStatus } from '../taskRequirements';
import { getTaskTemplateById } from '../taskTemplates';
import TaskWizardPanel from './TaskWizardPanel';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const requirement = (key: string, tool: RouteRequirementTool | null, overrides: Partial<RouteRequirementResult> = {}): RouteRequirementResult => ({
  key,
  label: `Label of ${key}`,
  minimum: 1,
  maximum: null,
  found: 0,
  satisfied: false,
  message: `Message of ${key}`,
  required: true,
  help: `Help of ${key}`,
  tool,
  other_tools: [],
  ...overrides,
});

const compatibility = (key: string, requirements: RouteRequirementResult[]): TaskCompatibilityResult => ({
  compatible_task_types: [],
  subtypes: [{ key, display_name: key, group: 'CIMA', coarse_family: 'precision', compatible: false, missing_reasons: [], requirements }],
});

describe('TaskWizardPanel', () => {
  let container: HTMLDivElement;
  let root: Root;
  const startWizardStep = vi.fn();
  const onDone = vi.fn();
  const onClose = vi.fn();
  const onChooseTask = vi.fn();
  const onBackToTaskList = vi.fn();

  const render = (
    templateId: string | null,
    requirements: RouteRequirementResult[],
    options: { activeTool?: RouteRequirementTool | null; status?: CompatibilityStatus; local?: (tool: RouteRequirementTool) => number } = {},
  ) => {
    const template = templateId ? getTaskTemplateById(templateId) : undefined;
    const status = options.status ?? 'ready';
    const checklist = template
      ? buildWizardChecklist(template, compatibility(template.backendKey, requirements), null, status, options.local ?? (() => 0))
      : null;
    act(() => {
      root.render(
        <TaskWizardPanel
          selectedTaskTemplateId={templateId}
          onChooseTask={onChooseTask}
          onBackToTaskList={onBackToTaskList}
          visibleTaskTypeGroups={['legacy', 'cima']}
          checklist={checklist}
          compatibilityStatus={status}
          activeTool={options.activeTool ?? null}
          startWizardStep={startWizardStep}
          onDone={onDone}
          onClose={onClose}
        />,
      );
    });
  };
  const stepElement = (key: string) => container.querySelector(`[data-step="${key}"]`) as HTMLElement;
  const buttonsIn = (element: Element) => [...element.querySelectorAll('button')].map((item) => item.textContent);

  beforeEach(() => {
    [startWizardStep, onDone, onClose, onChooseTask, onBackToTaskList].forEach((mock) => mock.mockClear());
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('lists the visible tasks when none is chosen, and chooses one', () => {
    render(null, []);
    const choice = [...container.querySelectorAll('button')].find((item) => item.textContent?.includes('2.A7 Circle'))!;
    act(() => choice.click());
    expect(onChooseTask).toHaveBeenCalledWith('cima_a7');
  });

  it('gives every unmet step a button that starts its tool, and shows the registry help text', () => {
    render('cima_a2', [
      requirement('route_waypoints', 'route_waypoint', { minimum: 3, found: 1, help: 'Place SP, a turn point and FP.' }),
      requirement('hidden_gate', 'hidden_gate', { help: 'Click a leg.' }),
    ]);
    expect(stepElement('route_waypoint').textContent).toContain('Place SP, a turn point and FP.');
    expect(stepElement('route_waypoint').textContent).toContain('Label of route_waypoints');
    expect(buildButtons('route_waypoint')).toEqual(['Place waypoints']);
    expect(buildButtons('hidden_gate')).toEqual(['Place hidden gates']);
    act(() => (stepElement('hidden_gate').querySelector('button') as HTMLButtonElement).click());
    expect(startWizardStep).toHaveBeenCalledWith('hidden_gate');
  });

  function buildButtons(key: string) {
    return buttonsIn(stepElement(key));
  }

  it('gives the any-of requirement one button per tool', () => {
    render('cima_a4', [
      requirement('route_waypoint', 'route_waypoint', { found: 3, satisfied: true }),
      requirement('known_circuit_evidence', 'hidden_gate', { other_tools: ['known_time_gate', 'photo'], help: 'Add one of them.' }),
    ]);
    const evidence = stepElement('hidden_gate');
    // The circuit's turn points are its known time gates: no free-standing time gate is offered
    expect(buttonsIn(evidence)).toEqual(['Hidden gate', 'Photo']);
    expect(evidence.textContent).toContain('turn points of the circuit are its known time gates');
    act(() => (evidence.querySelectorAll('button')[1] as HTMLButtonElement).click());
    expect(startWizardStep).toHaveBeenCalledWith('photo');
  });

  it('shows "How" for the curved leg and starts it like any other step', () => {
    render('cima_a1', [requirement('curved_leg', 'curved_leg', { help: 'Make a leg curved.' })]);
    expect(buildButtons('curved_leg')).toEqual(['How']);
    expect(stepElement('curved_leg').textContent).toContain('Make a leg curved.');
    act(() => (stepElement('curved_leg').querySelector('button') as HTMLButtonElement).click());
    expect(startWizardStep).toHaveBeenCalledWith('curved_leg');
  });

  it('marks the current step and gives it "Done, next step" instead of a start button', () => {
    render('cima_a2', [
      requirement('route_waypoints', 'route_waypoint', { minimum: 3, found: 1 }),
      requirement('hidden_gate', 'hidden_gate'),
    ], { activeTool: 'route_waypoint' });
    const active = stepElement('route_waypoint');
    expect(active.getAttribute('data-active')).toBe('true');
    expect(active.textContent).toContain('Current step');
    expect(buttonsIn(active)).toEqual(['Done, next step']);
    expect(stepElement('hidden_gate').getAttribute('data-active')).toBeNull();
    act(() => (active.querySelector('button') as HTMLButtonElement).click());
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it('gives a fixed-count step "Stop" while it is active, and nothing once it is complete', () => {
    const requirements = [
      requirement('circle_start_marker', 'circle_start', { minimum: 1, maximum: 1, found: 0 }),
      requirement('circle_center_marker', 'circle_center', { minimum: 1, maximum: 1, found: 1, satisfied: true }),
    ];
    render('cima_a7', requirements, { activeTool: 'circle_start' });
    expect(buttonsIn(stepElement('circle_start'))).toEqual(['Stop']);
    expect(buttonsIn(stepElement('circle_center'))).toEqual([]);
  });

  it('says all required steps are done and lists the optional steps below, started only from the list', () => {
    render('cima_a2', [
      requirement('route_waypoints', 'route_waypoint', { minimum: 3, found: 3, satisfied: true }),
      requirement('hidden_gate', 'hidden_gate', { found: 1, satisfied: true }),
      requirement('observation_photo', 'photo', { minimum: 0, maximum: null, required: false, satisfied: true, help: 'Optional. Use the Photo tool.' }),
    ]);
    expect(container.querySelector('[role="status"]')?.textContent).toContain('All required steps are done');
    expect(container.textContent).toContain('Optional steps');
    expect(buttonsIn(stepElement('photo'))).toEqual(['Place photos']);
    expect(stepElement('photo').textContent).toContain('Optional');
    // The met required steps offer a quiet "Add more".
    expect(buttonsIn(stepElement('route_waypoint'))).toEqual(['Add more']);
  });

  it('does not say all done while a required step is unmet or a step is active', () => {
    render('cima_a2', [requirement('route_waypoints', 'route_waypoint', { minimum: 3, found: 1 })]);
    expect(container.querySelector('[role="status"]')).toBeNull();
  });

  it('falls back to the catalogue steps with local counts while the backend has not answered', () => {
    const template = getTaskTemplateById('cima_a7')!;
    const catalogue = compatibility('circle', [requirement('circle_start_marker', 'circle_start', { minimum: 1, maximum: 1 })]).subtypes;
    const checklist = buildWizardChecklist(template, null, catalogue, 'pending', () => 1);
    act(() => {
      root.render(
        <TaskWizardPanel
          selectedTaskTemplateId="cima_a7"
          onChooseTask={onChooseTask}
          onBackToTaskList={onBackToTaskList}
          visibleTaskTypeGroups={['legacy', 'cima']}
          checklist={checklist}
          compatibilityStatus="pending"
          activeTool={null}
          startWizardStep={startWizardStep}
          onDone={onDone}
          onClose={onClose}
        />,
      );
    });
    expect(container.textContent).toContain('Checking the route against the task requirements');
    expect(stepElement('circle_start').textContent).toContain('1 placed');
    expect(stepElement('circle_start').textContent).toContain('Help of circle_start_marker');
  });

  it('closes and goes back to the task list', () => {
    render('cima_a7', [requirement('circle_start_marker', 'circle_start', { minimum: 1, maximum: 1 })]);
    act(() => (container.querySelector('button[aria-label="Close the guide"]') as HTMLButtonElement).click());
    expect(onClose).toHaveBeenCalledTimes(1);
    act(() => ([...container.querySelectorAll('button')].find((item) => item.textContent?.includes('Back to task list')) as HTMLButtonElement).click());
    expect(onBackToTaskList).toHaveBeenCalledTimes(1);
  });
});
