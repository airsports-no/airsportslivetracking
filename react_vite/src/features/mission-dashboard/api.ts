// import { reverse } from '../../urls';
import { OngoingNavigation } from './types';

export const fetchOngoingNavigation = async (): Promise<OngoingNavigation[]> => {
    // const url = reverse('ongoing_navigation');
    const url = '/api/v1/contests/ongoing_navigation/';
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error('Failed to fetch ongoing navigation tasks');
    }
    return response.json();
};
