import { countWizardStepMatches, TASK_TEMPLATES } from './taskTemplates';
import type { RoutePoint } from '../../types';

describe('countWizardStepMatches', () => {
  it('counts 2.A5 route-insert steps by point type, not generic route_waypoint feature type', () => {
    const a5 = TASK_TEMPLATES.find((item) => item.id === 'cima_a5');
    expect(a5).toBeTruthy();

    const routeStep = a5!.steps.find((step) => step.key === 'route_waypoint');
    const triggerStep = a5!.steps.find((step) => step.key === 'unknown_leg');
    const dummyStep = a5!.steps.find((step) => step.key === 'dummy');
    const hiddenGateStep = a5!.steps.find((step) => step.key === 'hidden_gate');

    const routePoints: RoutePoint[] = [
      { id: '1', name: 'SP', type: 'sp', featureType: 'route_waypoint', lat: 60, lng: 11, width: 1852, isTiming: true, isPassing: true, segmentType: 'straight' },
      { id: '2', name: 'A', type: 'tp', featureType: 'route_waypoint', lat: 60.1, lng: 11.1, width: 1852, isTiming: false, isPassing: true, segmentType: 'straight' },
      { id: '3', name: 'TRG1', type: 'ul', featureType: 'route_waypoint', lat: 60.2, lng: 11.2, width: 1852, isTiming: false, isPassing: true, segmentType: 'straight' },
      { id: '4', name: 'D1', type: 'dummy', featureType: 'route_waypoint', lat: 60.3, lng: 11.3, width: 1852, isTiming: false, isPassing: true, segmentType: 'straight' },
      { id: '5', name: 'HG1', type: 'hidden_gate', featureType: 'route_waypoint', lat: 60.4, lng: 11.4, width: 1852, isTiming: false, isPassing: true, segmentType: 'straight' },
      { id: '6', name: 'FP', type: 'fp', featureType: 'route_waypoint', lat: 60.5, lng: 11.5, width: 1852, isTiming: true, isPassing: true, segmentType: 'straight' },
    ];

    expect(countWizardStepMatches(routeStep!, routePoints, [], [], [], [])).toBe(6);
    expect(countWizardStepMatches(triggerStep!, routePoints, [], [], [], [])).toBe(1);
    expect(countWizardStepMatches(dummyStep!, routePoints, [], [], [], [])).toBe(1);
    expect(countWizardStepMatches(hiddenGateStep!, routePoints, [], [], [], [])).toBe(1);
  });
});