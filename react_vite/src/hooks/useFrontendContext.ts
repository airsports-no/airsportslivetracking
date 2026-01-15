import { useEffect, useState } from 'react';

interface FrontendContext {
  is_authenticated: boolean;
  is_superuser: boolean;
  is_staff: boolean;
  email: string | null;
  STATIC_FILE_LOCATION: string;
  loginLink: string;
  logoutLink: string;
  // Add other URLs as needed from django_js_reverse output
  urls: {
    [key: string]: string | ((...args: any[]) => string); // Dynamically typed URLs
  };
}

export const useFrontendContext = () => {
  const [context, setContext] = useState<FrontendContext | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchContext = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/v1/frontend-context/');
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const data: FrontendContext = await response.json();
        setContext(data);
      } catch (err) {
        setError('Failed to load frontend context.');
        console.error('Failed to load frontend context:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchContext();
  }, []);

  return { context, loading, error };
};
