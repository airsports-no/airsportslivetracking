import { create } from 'zustand';
import * as api from './api';
import type { Club, Aircraft, Copilot, Contest, OngoingNavigation, Contestant, MyContestTeam, ContestResults } from './types';

interface MissionDashboardState {
    contests: Contest[];
    contestsById: Record<number, Contest>;
    myEditorContests: Contest[];
    ongoingNavigations: OngoingNavigation[];
    myFutureFlights: Contestant[];
    myPreviousFlights: Contestant[];
    myContestTeams: MyContestTeam[];
    results: Record<number, ContestResults>;
    clubs: Club[];
    aircrafts: Aircraft[];
    pilots: Copilot[];
    
    fetchContests: (filters?: api.ContestFilters) => Promise<void>;
    fetchContest: (contestId: number, force?: boolean) => Promise<void>;
    fetchMyEditorContests: (force?: boolean) => Promise<void>;
    fetchOngoingNavigation: (force?: boolean) => Promise<void>;
    fetchMyFutureFlights: (force?: boolean) => Promise<void>;
    fetchMyPreviousFlights: (force?: boolean) => Promise<void>;
    fetchMyContestTeams: (force?: boolean) => Promise<void>;
    fetchContestResults: (contestId: number, force?: boolean) => Promise<void>;
    fetchClubs: () => Promise<void>;
    fetchAircrafts: () => Promise<void>;
    fetchPilots: () => Promise<void>;

    // Actions that modify state locally or call API and then modify
    cancelFlight: (contestId: number, navigationTaskId: number, futureContestantId: number) => Promise<void>;
    withdraw: (contestId: number) => Promise<void>;
}

export const useMissionDashboardStore = create<MissionDashboardState>((set, get) => ({
    contests: [],
    contestsById: {},
    myEditorContests: [],
    ongoingNavigations: [],
    myFutureFlights: [],
    myPreviousFlights: [],
    myContestTeams: [],
    results: {},
    clubs: [],
    aircrafts: [],
    pilots: [],

    fetchContests: async (filters) => {
        const contests = await api.fetchContests(filters);
        set(state => ({ contests: [...state.contests, ...contests.filter(c => !state.contests.find(sc => sc.id === c.id))] }));
    },
    fetchContest: async (contestId, force) => {
        if (!force && get().contestsById[contestId]) {
            return;
        }
        const contest = await api.fetchContest(contestId);
        set(state => ({
            contestsById: {
                ...state.contestsById,
                [contestId]: contest
            }
        }));
    },
    fetchMyEditorContests: async (force) => {
        if (!force && get().myEditorContests.length > 0) {
            return;
        }
        const myEditorContests = await api.fetchContests({ isEditor: true });
        set({ myEditorContests });
    },
    fetchOngoingNavigation: async (force) => {
        if (!force && get().ongoingNavigations.length > 0) {
            return;
        }
        const ongoingNavigations = await api.fetchOngoingNavigation();
        set({ ongoingNavigations });
    },
    fetchMyFutureFlights: async (force) => {
        if (!force && get().myFutureFlights.length > 0) {
            return;
        }
        const myFutureFlights = await api.fetchMyFutureFlights();
        set({ myFutureFlights });
    },
    fetchMyPreviousFlights: async (force) => {
        if (!force && get().myPreviousFlights.length > 0) {
            return;
        }
        const myPreviousFlights = await api.fetchMyPreviousFlights();
        set({ myPreviousFlights });
    },
    fetchMyContestTeams: async (force) => {
        if (!force && get().myContestTeams.length > 0) {
            return;
        }
        const myContestTeams = await api.fetchMyContestTeams();
        set({ myContestTeams });
    },
    fetchContestResults: async (contestId, force) => {
        if (!force && get().results[contestId]) {
            return;
        }
        const results = await api.fetchContestResults(contestId);
        set(state => ({
            results: {
                ...state.results,
                [contestId]: results,
            }
        }));
    },
    fetchClubs: async () => {
        const clubs = await api.fetchClubs();
        set({ clubs });
    },
    fetchAircrafts: async () => {
        const aircrafts = await api.fetchAircrafts();
        set({ aircrafts });
    },
    fetchPilots: async () => {
        const pilots = await api.fetchPilots();
        set({ pilots });
    },
    cancelFlight: async (contestId, navigationTaskId, futureContestantId) => {
        await api.cancelFlight(contestId, navigationTaskId, futureContestantId);
        await get().fetchMyFutureFlights(true);
    },
    withdraw: async (contestId: number) => {
        await api.withdraw(contestId);
        // After withdrawing, we might need to refetch contest teams or other user-specific data.
        // For now, let's refetch my contest teams
        await get().fetchMyContestTeams(true);
    },
}));
