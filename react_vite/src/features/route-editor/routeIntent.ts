// A route's intent (intended_task_types) is only what the author chose: the task chosen in the guide plus what they
// tick in the route settings. It is never filled with what the route happens to suit.

export interface RouteIntent {
  types: string[];
  // The type the guide added, when the author did not tick it by hand. Switching task replaces only this one.
  guideChosen: string | null;
}

export const emptyIntent = (types: string[] = []): RouteIntent => ({ types, guideChosen: null });

// The intent of a route that was loaded: the stored [types], and the task template the route's settings say was selected
// (null or unknown: none). A saved route carries no record of which type the guide added, so when the stored template's
// subtype is among the types it counts as the guide-chosen one, and switching task in the guide replaces it.
export const intentForLoadedRoute = (types: string[], templateSubtype: string | null | undefined): RouteIntent => ({
  types,
  guideChosen: templateSubtype && types.includes(templateSubtype) ? templateSubtype : null,
});

// The guide's task changed to [subtype] (null: the guide was left). The previously guide-chosen type goes; a type the
// author ticked by hand stays, and so does one that was already ticked when the guide chose it.
export const applyGuideChoice = (intent: RouteIntent, subtype: string | null | undefined): RouteIntent => {
  const types = intent.guideChosen ? intent.types.filter((key) => key !== intent.guideChosen) : [...intent.types];
  if (!subtype) return { types, guideChosen: null };
  if (types.includes(subtype)) return { types, guideChosen: null };
  return { types: [...types, subtype], guideChosen: subtype };
};

// The author ticked or unticked [key] in the route settings. Either way the type is theirs from then on.
export const applyManualTick = (intent: RouteIntent, key: string, checked: boolean): RouteIntent => {
  const guideChosen = intent.guideChosen === key ? null : intent.guideChosen;
  if (checked) return { types: intent.types.includes(key) ? intent.types : [...intent.types, key], guideChosen };
  return { types: intent.types.filter((existing) => existing !== key), guideChosen };
};
