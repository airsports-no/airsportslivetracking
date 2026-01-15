import { useEffect, useCallback } from 'react';
import axios from 'axios';
import { useContestResultsStore } from '../store/contestResultsStore';
import { useFrontendContext } from './useFrontendContext';

export const useContestResults = (contestId: number | null) => {
  const { context, loading: contextLoading, error: contextError } = useFrontendContext();
  const { setResults, setLoading, setError, results } = useContestResultsStore();

  const fetchResults = useCallback(async () => {
    if (!contestId || !context || !context.urls.contestResultsDetailsUrl) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // contestResultsDetailsUrl is a function in django_js_reverse, so it will be in context.urls.contestResultsDetailsUrl.
      // We need to call it with contestId.
      const url = context.urls.contestResultsDetailsUrl(contestId);
      const response = await axios.get(url);
      setResults(response.data);
    } catch (err) {
      setError('Failed to fetch contest results.');
      console.error('Failed to fetch contest results:', err);
    } finally {
      setLoading(false);
    }
  }, [contestId, context, setResults, setLoading, setError]);

  useEffect(() => {
    if (!contextLoading && !contextError && contestId) {
      fetchResults();
    }
  }, [contestId, contextLoading, contextError, fetchResults]);

  return { results, loading: useContestResultsStore().loading, error: useContestResultsStore().error, fetchResults };
};
