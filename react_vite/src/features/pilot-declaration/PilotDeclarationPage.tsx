import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { CheckCircle2, Info, Loader2, Lock, TriangleAlert } from 'lucide-react';
import { DeclarationApiError, fetchDeclaration, saveDeclaration } from './api';
import {
    PilotFormState,
    asksForSequence,
    buildDeclarationPayload,
    cutoffSentence,
    fitLanes,
    initialFormState,
    laneCount,
    sequenceOptions,
    sequenceShape,
    timePointNames,
} from './declarationForm';
import { PilotDeclaration } from './types';
import FlightOrderPanel from './FlightOrderPanel';
import { useFlightOrderStatus } from './useFlightOrderStatus';
import { SequenceLanes, TimeRow } from './fields';
import { BookingIds, finishBooking, safeReturnTo } from './bookingFlow';
import { isEmbeddedInApp } from '../../utils/appBridge';
import { reverse } from '../../urls';

const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <div className="min-h-screen bg-base-200" data-theme="aviation">
        <div className="max-w-xl mx-auto px-4 py-4 pb-24 space-y-4">{children}</div>
    </div>
);

const PilotDeclarationPage: React.FC = () => {
    const { contestantId: contestantParam } = useParams();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const contestantId = Number(contestantParam);
    // Coming from the booking: the booking ends here, with the signal the app knows
    const booking = searchParams.get('booking') === '1';
    const bookingContestId = Number(searchParams.get('contestId'));
    const bookingTaskId = Number(searchParams.get('navigationTaskId'));
    const bookingReturnTo = safeReturnTo(searchParams.get('returnTo'));
    const bookingIds = useMemo<BookingIds | null>(
        () =>
            booking && bookingContestId && bookingTaskId
                ? { contestId: bookingContestId, navigationTaskId: bookingTaskId, returnTo: bookingReturnTo }
                : null,
        [booking, bookingContestId, bookingTaskId, bookingReturnTo],
    );

    const [declaration, setDeclaration] = useState<PilotDeclaration | null>(null);
    const [form, setForm] = useState<PilotFormState | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [problems, setProblems] = useState<string[]>([]);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [dirty, setDirty] = useState(false);

    useEffect(() => {
        let cancelled = false;
        fetchDeclaration(contestantId)
            .then((loaded) => {
                if (cancelled) return;
                setDeclaration(loaded);
                setForm(initialFormState(loaded));
            })
            .catch((error: unknown) => {
                if (cancelled) return;
                if (error instanceof DeclarationApiError && (error.status === 401 || error.status === 403)) {
                    // Not signed in: sign in and come back to this page
                    const next = encodeURIComponent(window.location.pathname + window.location.search);
                    const loginUrl = reverse('login');
                    window.location.href = `${loginUrl.includes('url-initialization-failed') ? '/accounts/login/' : loginUrl}?next=${next}`;
                    return;
                }
                setLoadError(error instanceof Error ? error.message : 'The declaration could not be loaded.');
            });
        return () => {
            cancelled = true;
        };
    }, [contestantId]);

    const refreshFlightOrder = useCallback(async () => (await fetchDeclaration(contestantId)).flight_order_status, [contestantId]);
    const flightOrder = useFlightOrderStatus(declaration?.flight_order_status ?? null, refreshFlightOrder);

    const leave = useCallback(() => {
        if (bookingIds) finishBooking(bookingIds, navigate);
        else navigate('/');
    }, [bookingIds, navigate]);

    const update = (change: (state: PilotFormState) => PilotFormState) => {
        setForm((current) => (current ? change(current) : current));
        setDirty(true);
        setSaved(false);
    };

    const shape = useMemo(() => (declaration && form ? sequenceShape(declaration.form, form.times) : null), [declaration, form]);

    if (loadError) {
        return (
            <Shell>
                <div className="alert alert-error" role="alert">{loadError}</div>
                {/* A booking must still be able to end when this page cannot be shown */}
                {bookingIds ? (
                    <button type="button" className="btn btn-primary min-h-11 w-full" onClick={leave}>Continue without declaring now</button>
                ) : null}
            </Shell>
        );
    }
    if (!declaration || !form || !shape) {
        return (
            <Shell>
                <div className="flex items-center gap-2" role="status"><Loader2 className="animate-spin" size={20} /> Loading your declaration...</div>
            </Shell>
        );
    }

    const { status, form: ask } = declaration;
    const readOnly = !status.can_edit;
    const optional = status.need === 'optional';
    const names = timePointNames(ask);
    const cutoff = cutoffSentence(status, declaration.time_zone);
    const lanes = fitLanes(form.lanes, laneCount(shape));
    const hasTimes = names.length > 0;

    const handleSave = async (event: React.FormEvent) => {
        event.preventDefault();
        const built = buildDeclarationPayload(ask, form);
        setProblems(built.problems);
        setSaveError(null);
        if (built.problems.length > 0) return;
        setSaving(true);
        try {
            const result = await saveDeclaration(contestantId, built.payload);
            setDeclaration(result);
            setForm(initialFormState(result));
            setDirty(false);
            setSaved(true);
        } catch (error: unknown) {
            // What the pilot typed stays where it is
            setSaveError(error instanceof Error ? error.message : 'The declaration could not be saved.');
        } finally {
            setSaving(false);
        }
    };

    const stateBanner = () => {
        if (status.state === 'complete') {
            return (
                <div className="alert alert-success" role="status">
                    <CheckCircle2 size={20} className="shrink-0" aria-hidden="true" />
                    <span>{saved ? 'Saved. Your declaration is complete.' : 'Your declaration is complete.'}</span>
                </div>
            );
        }
        if (status.state === 'incomplete' || (status.state === 'missing' && status.errors.length > 0 && !optional)) {
            const heading = status.state === 'incomplete' ? 'Saved, but not finished yet.' : 'Not done yet.';
            return (
                <div className="alert alert-warning items-start" role="status" data-testid="declaration-unfinished">
                    <TriangleAlert size={20} className="shrink-0 mt-0.5" aria-hidden="true" />
                    <div>
                        <p className="font-semibold">{heading}</p>
                        {status.errors.length > 0 && (
                            <>
                                <p className="text-sm">Still missing:</p>
                                <ul className="list-disc list-inside text-sm">{status.errors.map((error) => <li key={error}>{error}</li>)}</ul>
                            </>
                        )}
                    </div>
                </div>
            );
        }
        return null;
    };

    return (
        <Shell>
            <header>
                <p className="text-sm opacity-70">{declaration.contest_name}</p>
                <h1 className="text-2xl font-bold">Your declaration</h1>
                <p className="opacity-80">{declaration.navigation_task_name}</p>
            </header>

            {status.need === 'not_needed' && <div className="alert alert-info"><Info size={20} aria-hidden="true" /><span>This task has no declaration.</span></div>}

            {stateBanner()}

            {optional && status.state === 'missing' && !readOnly && (
                <div className="alert alert-info items-start" data-testid="optional-note">
                    <Info size={20} className="shrink-0 mt-0.5" aria-hidden="true" />
                    <span>This declaration is optional. If you skip it, you fly without declaring anything and the task&apos;s defaults apply.</span>
                </div>
            )}

            {readOnly && status.need !== 'not_needed' && (
                <div className="alert alert-info items-start" role="status" data-testid="declaration-read-only">
                    <Lock size={20} className="shrink-0 mt-0.5" aria-hidden="true" />
                    <div>
                        <p className="font-semibold">You can only read this declaration.</p>
                        {declaration.read_only_reason && <p className="text-sm">{declaration.read_only_reason}</p>}
                    </div>
                </div>
            )}

            {cutoff && <p className="text-sm" data-testid="declaration-cutoff">{cutoff}</p>}

            {status.need !== 'not_needed' && (
                <form onSubmit={handleSave} className="space-y-4" noValidate>
                    {hasTimes && (
                        <section className="card bg-base-100 shadow">
                            <div className="card-body p-4">
                                <h2 className="card-title text-lg">Times</h2>
                                <p className="text-sm opacity-80">
                                    Give each time as minutes and seconds after you cross the start point.
                                </p>
                                {ask.adaptive_start || !ask.start_point_time ? (
                                    <p className="text-sm font-medium" data-testid="adaptive-note">
                                        Your times count from when you cross the start, so there is no clock time to show yet.
                                    </p>
                                ) : null}
                                <div className="divide-y divide-base-200">
                                    {names.map((name) => (
                                        <TimeRow
                                            key={name}
                                            name={name}
                                            label={`Time at ${name}`}
                                            entry={form.times[name] ?? { minutes: '', seconds: '' }}
                                            startPointTime={ask.start_point_time}
                                            timeZone={declaration.time_zone}
                                            disabled={readOnly}
                                            onChange={(entry) => update((state) => ({ ...state, times: { ...state.times, [name]: entry } }))}
                                        />
                                    ))}
                                </div>
                            </div>
                        </section>
                    )}

                    {asksForSequence(ask) && (
                        <section className="card bg-base-100 shadow">
                            <div className="card-body p-4">
                                <h2 className="card-title text-lg">{ask.mandatory_points?.length ? 'Your turn points, in order' : 'Your targets, in order'}</h2>
                                <p className="text-sm opacity-80">
                                    {ask.mandatory_points?.length
                                        ? 'Tap a point to add it. Use the arrows to change the order.'
                                        : 'Tap a target to add it. Use the arrows to change the order. The compulsory points follow the times you gave.'}
                                </p>
                                <SequenceLanes
                                    shape={shape}
                                    lanes={lanes}
                                    options={sequenceOptions(ask)}
                                    disabled={readOnly}
                                    onChange={(next) => update((state) => ({ ...state, lanes: next }))}
                                />
                            </div>
                        </section>
                    )}

                    {ask.asks_for_period && (
                        <section className="card bg-base-100 shadow">
                            <div className="card-body p-4">
                                <h2 className="card-title text-lg">Your period T</h2>
                                <p className="text-sm opacity-80">The time you will use from SP to MP, and again from MP to FP.</p>
                                <TimeRow
                                    name="Period T"
                                    label="Period T"
                                    entry={form.period}
                                    startPointTime={null}
                                    timeZone={declaration.time_zone}
                                    disabled={readOnly}
                                    onChange={(entry) => update((state) => ({ ...state, period: entry }))}
                                />
                            </div>
                        </section>
                    )}

                    {ask.asks_for_fuel_endurance && (
                        <section className="card bg-base-100 shadow">
                            <div className="card-body p-4">
                                <label className="block">
                                    <span className="card-title text-lg">Fuel endurance (optional)</span>
                                    <span className="block text-sm opacity-80 mb-2">How many minutes you can fly on your fuel.</span>
                                    <input
                                        type="text"
                                        inputMode="numeric"
                                        pattern="[0-9]*"
                                        className="input input-bordered w-full min-h-11 text-lg"
                                        aria-label="Fuel endurance in minutes"
                                        value={form.fuelMinutes}
                                        disabled={readOnly}
                                        onChange={(event) => update((state) => ({ ...state, fuelMinutes: event.target.value }))}
                                    />
                                </label>
                            </div>
                        </section>
                    )}

                    {problems.length > 0 && (
                        <div className="alert alert-error items-start" role="alert" data-testid="declaration-problems">
                            <TriangleAlert size={20} className="shrink-0 mt-0.5" aria-hidden="true" />
                            <div>
                                <p className="font-semibold">Check what you typed. Nothing was saved.</p>
                                <ul className="list-disc list-inside text-sm">{problems.map((problem) => <li key={problem}>{problem}</li>)}</ul>
                            </div>
                        </div>
                    )}
                    {saveError && (
                        <div className="alert alert-error items-start" role="alert" data-testid="declaration-save-error">
                            <TriangleAlert size={20} className="shrink-0 mt-0.5" aria-hidden="true" />
                            <div>
                                <p className="font-semibold">Not saved.</p>
                                <p className="text-sm">{saveError}</p>
                                <p className="text-sm">What you typed is still here. Try again.</p>
                            </div>
                        </div>
                    )}

                    {!readOnly && (
                        <div className="space-y-2">
                            <button type="submit" className="btn btn-primary w-full min-h-12 text-base" disabled={saving}>
                                {saving ? <Loader2 className="animate-spin" size={18} aria-hidden="true" /> : null}
                                {saving ? 'Saving...' : 'Save declaration'}
                            </button>
                            {dirty && !saving && <p className="text-sm text-center opacity-70">You have changes that are not saved.</p>}
                        </div>
                    )}
                </form>
            )}

            {status.need !== 'not_needed' && (
                <FlightOrderPanel status={flightOrder} retryBySaving={status.can_edit} />
            )}

            <div className="space-y-2 pt-2">
                {booking && status.state === 'complete' && !dirty && (
                    <button type="button" className="btn btn-primary w-full min-h-12 text-base" onClick={leave}>Done</button>
                )}
                {booking && !(status.state === 'complete' && !dirty) && (
                    <button type="button" className="btn btn-outline w-full min-h-12" onClick={leave}>
                        {readOnly ? 'Continue' : 'Do this later'}
                    </button>
                )}
                {optional && status.state === 'missing' && !readOnly && (
                    <button type="button" className="btn btn-ghost w-full min-h-12" onClick={leave}>
                        Skip the declaration
                    </button>
                )}
                {!booking && !isEmbeddedInApp() && (
                    <Link to="/" className="btn btn-ghost w-full min-h-12">Back to my flights</Link>
                )}
            </div>
        </Shell>
    );
};

export default PilotDeclarationPage;
