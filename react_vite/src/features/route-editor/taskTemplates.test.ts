import { getVisibleTaskTemplates, getTaskTemplateById, groupTaskTypesByFamily, groupTemplates, isTaskSubtypeVisible, TASK_TEMPLATES } from './taskTemplates';

describe('task templates', () => {
  it('gives every template the registry key of its task type', () => {
    for (const template of TASK_TEMPLATES) {
      expect(template.backendKey).toBeTruthy();
      if (template.subtype) expect(template.backendKey).toBe(template.subtype);
    }
  });

  it('describes every template in one line and keeps no steps: those come from the registry', () => {
    for (const template of TASK_TEMPLATES) {
      expect(template.description).toMatch(/^[A-Z].*\.$/);
      expect(template.description).not.toContain('\n');
      expect(template).not.toHaveProperty('steps');
      expect(template).not.toHaveProperty('guideOnly');
    }
  });
});

describe('groupTemplates', () => {
  it('groups in the order the groups first appear, keeping the order of the templates', () => {
    const groups = groupTemplates(TASK_TEMPLATES);
    expect(groups.map(([group]) => group)).toEqual(['Legacy', 'CIMA']);
    expect(groups[0][1].map((template) => template.id)).toEqual(['precision', 'anr', 'airsports_challenge']);
    expect(groups[1][1][0].id).toBe('cima_a1');
  });

  it('is empty when no template is visible', () => {
    expect(groupTemplates([])).toEqual([]);
  });
});

describe('getVisibleTaskTemplates', () => {
  it('always includes Legacy templates, even with no groups granted', () => {
    const visible = getVisibleTaskTemplates(undefined);
    const legacyIds = visible.filter((t) => t.group === 'Legacy').map((t) => t.id);
    expect(legacyIds.sort()).toEqual(['airsports_challenge', 'anr', 'precision']);
    // No CIMA templates without any 'cima' or 'cima:<subtype>' grant.
    expect(visible.some((t) => t.group === 'CIMA')).toBe(false);
  });

  it('unlocks every CIMA template when the coarse "cima" group is granted', () => {
    const visible = getVisibleTaskTemplates(['legacy', 'cima']);
    const cimaIds = visible.filter((t) => t.group === 'CIMA').map((t) => t.id);
    const allCimaIds = TASK_TEMPLATES.filter((t) => t.group === 'CIMA').map((t) => t.id);
    expect(cimaIds.sort()).toEqual(allCimaIds.sort());
  });

  it('unlocks only the matching CIMA template for a fine-grained "cima:<subtype>" grant', () => {
    const visible = getVisibleTaskTemplates(['legacy', 'cima:circle']);
    const cimaIds = visible.filter((t) => t.group === 'CIMA').map((t) => t.id);
    expect(cimaIds).toEqual(['cima_a7']);
  });

  it('grants for one subtype do not leak into other CIMA templates', () => {
    const visible = getVisibleTaskTemplates(['cima:circle']);
    expect(visible.some((t) => t.id === 'cima_a3')).toBe(false);
    expect(visible.some((t) => t.id === 'cima_a7')).toBe(true);
  });
});

describe('isTaskSubtypeVisible', () => {
  it('always shows Legacy regardless of groups', () => {
    expect(isTaskSubtypeVisible('Legacy', undefined, [])).toBe(true);
    expect(isTaskSubtypeVisible('Legacy', 'legacy_precision', undefined)).toBe(true);
  });

  it('hides CIMA with no matching group', () => {
    expect(isTaskSubtypeVisible('CIMA', 'circle', [])).toBe(false);
    expect(isTaskSubtypeVisible('CIMA', 'circle', ['legacy'])).toBe(false);
  });

  it('shows every CIMA subtype with the coarse "cima" group', () => {
    expect(isTaskSubtypeVisible('CIMA', 'circle', ['cima'])).toBe(true);
    expect(isTaskSubtypeVisible('CIMA', 'unknown_legs', ['cima'])).toBe(true);
  });

  it('shows only the matching subtype for a fine-grained "cima:<subtype>" group', () => {
    expect(isTaskSubtypeVisible('CIMA', 'circle', ['cima:circle'])).toBe(true);
    expect(isTaskSubtypeVisible('CIMA', 'unknown_legs', ['cima:circle'])).toBe(false);
  });
});

describe('getTaskTemplateById', () => {
  it('finds a template by id', () => {
    expect(getTaskTemplateById('cima_a7')?.label).toBe('2.A7 Circle');
  });

  it('returns undefined for an unknown, null, or undefined id', () => {
    expect(getTaskTemplateById('not_a_real_id')).toBeUndefined();
    expect(getTaskTemplateById(null)).toBeUndefined();
    expect(getTaskTemplateById(undefined)).toBeUndefined();
  });
});

describe('groupTaskTypesByFamily', () => {
  const subtypeByKey = {
    cima_a2: { coarse_family: 'precision', display_name: '2.A2 Precision navigation' },
    cima_a8: { coarse_family: 'precision', display_name: '2.A8 Precision navigation Air Nav Race (ANR)' },
    legacy_precision: { coarse_family: 'precision', display_name: 'Legacy precision navigation' },
    legacy_anr_corridor: { coarse_family: 'anr_corridor', display_name: 'Legacy ANR corridor' },
  };

  it('collapses multiple subtypes from the same family into a single group', () => {
    const groups = groupTaskTypesByFamily(['cima_a2', 'cima_a8', 'legacy_precision'], subtypeByKey);

    expect(groups).toEqual([
      {
        family: 'precision',
        subtypeNames: ['2.A2 Precision navigation', '2.A8 Precision navigation Air Nav Race (ANR)', 'Legacy precision navigation'],
      },
    ]);
  });

  it('keeps distinct families separate and orders them by COARSE_FAMILY_ORDER regardless of input order', () => {
    const groups = groupTaskTypesByFamily(['legacy_anr_corridor', 'cima_a2'], subtypeByKey);

    expect(groups.map((group) => group.family)).toEqual(['precision', 'anr_corridor']);
  });

  it('appends a family outside the known COARSE_FAMILY_ORDER instead of dropping it', () => {
    const groups = groupTaskTypesByFamily(
      ['cima_a2', 'future_key'],
      { ...subtypeByKey, future_key: { coarse_family: 'future_family', display_name: 'Some future subtype' } },
    );

    expect(groups.map((group) => group.family)).toEqual(['precision', 'future_family']);
    expect(groups[1].subtypeNames).toEqual(['Some future subtype']);
  });

  it('ignores keys missing from subtypeByKey rather than throwing', () => {
    const groups = groupTaskTypesByFamily(['unknown_key'], subtypeByKey);

    expect(groups).toEqual([]);
  });
});