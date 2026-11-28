// How a route's task tags are shown: what the author made it for (intended_task_types), and what its content suits
// (compatible_task_types). Pure, so the route card and the list filter share one reading of them.

export interface RouteTagSource {
  intended_task_types?: string[];
  compatible_task_types?: string[];
}

export interface TagSubtype {
  coarse_family: string;
  display_name: string;
}

export interface RouteTagGroup {
  family: string;
  subtypeNames: string[];
  // The names in this chip that the route does not meet the requirements of yet.
  unmetNames: string[];
}

export interface RouteTags {
  // The families of the types the author made the route for.
  madeFor: RouteTagGroup[];
  // The other families the route's content suits. Empty when the route has no intent.
  alsoSuitable: RouteTagGroup[];
  // What the route suits when it has no intent (shown as "Suitable for"). Empty when it has one.
  suitable: RouteTagGroup[];
}

export type TaskFilterMode = 'suitable' | 'made_for';

export const unmetRequirementsTooltip = (name: string): string => `This route does not meet the requirements of ${name} yet`;

const groupByFamily = (
  keys: string[],
  subtypeByKey: Record<string, TagSubtype>,
  compatible: Set<string> | null,
): RouteTagGroup[] => {
  const groups = new Map<string, RouteTagGroup>();
  const order: string[] = [];
  for (const key of keys) {
    const subtype = subtypeByKey[key];
    if (!subtype) continue;
    let group = groups.get(subtype.coarse_family);
    if (!group) {
      group = { family: subtype.coarse_family, subtypeNames: [], unmetNames: [] };
      groups.set(subtype.coarse_family, group);
      order.push(subtype.coarse_family);
    }
    group.subtypeNames.push(subtype.display_name);
    if (compatible && !compatible.has(key)) group.unmetNames.push(subtype.display_name);
  }
  return order.map((family) => groups.get(family)!);
};

// [orderedFamilies] is the display order of the families; families outside it follow in first-seen order.
const sortFamilies = (groups: RouteTagGroup[], orderedFamilies: string[]): RouteTagGroup[] => {
  const rank = (family: string) => {
    const index = orderedFamilies.indexOf(family);
    return index === -1 ? orderedFamilies.length : index;
  };
  return groups.map((group, index) => ({ group, index })).sort((a, b) => rank(a.group.family) - rank(b.group.family) || a.index - b.index).map(({ group }) => group);
};

// A CIMA type the viewer may not see ([visibleKeys]) is never shown, whatever the route contains.
export const buildRouteTags = (
  route: RouteTagSource,
  subtypeByKey: Record<string, TagSubtype>,
  visibleKeys: Set<string>,
  orderedFamilies: string[] = [],
): RouteTags => {
  const compatible = (route.compatible_task_types ?? []).filter((key) => visibleKeys.has(key));
  const intended = (route.intended_task_types ?? []).filter((key) => visibleKeys.has(key));
  const compatibleSet = new Set(route.compatible_task_types ?? []);
  if (intended.length === 0) {
    return { madeFor: [], alsoSuitable: [], suitable: sortFamilies(groupByFamily(compatible, subtypeByKey, null), orderedFamilies) };
  }
  const madeFor = sortFamilies(groupByFamily(intended, subtypeByKey, compatibleSet), orderedFamilies);
  const madeForFamilies = new Set(madeFor.map((group) => group.family));
  const alsoSuitable = sortFamilies(groupByFamily(compatible, subtypeByKey, null), orderedFamilies).filter(
    (group) => !madeForFamilies.has(group.family),
  );
  return { madeFor, alsoSuitable, suitable: [] };
};

export const routeMatchesTaskFilter = (route: RouteTagSource, taskTypeKey: string, mode: TaskFilterMode): boolean => {
  if (!taskTypeKey) return true;
  const keys = mode === 'made_for' ? route.intended_task_types : route.compatible_task_types;
  return (keys ?? []).includes(taskTypeKey);
};

// The task types the filter offers: only those in use by at least one route, in the sense of the mode.
export const taskTypeKeysInUse = (routes: RouteTagSource[], mode: TaskFilterMode): Set<string> =>
  new Set(routes.flatMap((route) => (mode === 'made_for' ? route.intended_task_types : route.compatible_task_types) ?? []));

// Routes made for [taskTypeKey] first, otherwise in the order given (a stable sort).
export const routesMadeForFirst = <T extends RouteTagSource>(routes: T[], taskTypeKey: string): T[] => {
  const made = (route: T) => ((route.intended_task_types ?? []).includes(taskTypeKey) ? 0 : 1);
  return routes.map((route, index) => ({ route, index })).sort((a, b) => made(a.route) - made(b.route) || a.index - b.index).map(({ route }) => route);
};
