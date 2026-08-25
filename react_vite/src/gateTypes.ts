// Legacy CIMA alias: a RoutePoint.type of 'hidden_gate' is a secret point that predates
// canonicalization onto 'secret'. New authoring never writes 'hidden_gate' as a pointType;
// this helper exists so every read path treats both spellings identically.
export const SECRET_POINT_TYPES = ['secret', 'hidden_gate'] as const;

export function isSecretPointType(type?: string | null): boolean {
  return type === 'secret' || type === 'hidden_gate';
}
