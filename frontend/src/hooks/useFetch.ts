import { useState, useEffect, useRef } from 'react';

/**
 * `intervalMs`, when set, re-runs fetchFn on that cadence for as long as
 * the component is mounted -- this is what makes the dashboard pick up a
 * new situation/alert on its own instead of only on first page load.
 * Poll ticks never flip `loading` back to true, so the UI doesn't flicker.
 */
export function useFetch<T>(fetchFn: () => Promise<T>, deps: any[] = [], intervalMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const fetchFnRef = useRef(fetchFn);
  fetchFnRef.current = fetchFn;
  const runRef = useRef<(isInitial: boolean) => void>(() => {});

  useEffect(() => {
    let mounted = true;

    const run = (isInitial: boolean) => {
      if (isInitial) setLoading(true);
      fetchFnRef.current()
        .then(res => { if (mounted) { setData(res); setError(null); } })
        .catch(err => { if (mounted) { setError(err); } })
        .finally(() => { if (mounted && isInitial) setLoading(false); });
    };
    runRef.current = run;

    run(true);

    if (!intervalMs) return () => { mounted = false; };

    const id = setInterval(() => run(false), intervalMs);
    return () => { mounted = false; clearInterval(id); };
  }, deps);

  const refetch = () => runRef.current(false);

  return { data, loading, error, refetch };
}
