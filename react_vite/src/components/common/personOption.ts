export interface PersonOption {
    /** Person id for kind="person", user id for kind="user" */
    value: number;
    name: string;
    country: string;
    picture: string | null;
    /** Heavily masked email, only present when the name alone is ambiguous */
    emailHint: string;
}

export interface PersonSearchResult {
    id: number;
    name: string;
    country: string;
    picture: string | null;
    email_hint: string;
}

export const personOptionFromSearchResult = (result: PersonSearchResult): PersonOption => ({
    value: result.id,
    name: result.name,
    country: result.country,
    picture: result.picture,
    emailHint: result.email_hint,
});

/** Builds an option for someone we already know (e.g. the current co-pilot of a team being edited). */
export const personOptionFromPerson = (person: {
    id: number;
    first_name: string;
    last_name: string;
    picture?: string | null;
}): PersonOption => ({
    value: person.id,
    name: `${person.first_name} ${person.last_name}`.trim(),
    country: '',
    picture: person.picture ?? null,
    emailHint: '',
});
