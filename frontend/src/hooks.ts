import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api/client";

export interface FetchState<T> {
  data: T | null; error: ApiError | null; loading: boolean;
  reload: () => void;          // shows the loading state
  refreshQuietly: () => void;  // updates data without a loading flash (for polling)
}

/** Loads data and tracks loading / error state so every page can show all three states. */
export function useFetch<T>(load: () => Promise<T>, deps: unknown[]): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const loadRef = useRef(load);
  loadRef.current = load;
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  const run = useCallback((quiet: boolean) => {
    if (!quiet) { setLoading(true); setError(null); }
    loadRef.current()
      .then((d) => { if (alive.current) { setData(d); setError(null); } })
      .catch((e) => { if (alive.current && !quiet) setError(e instanceof ApiError ? e : new ApiError(0, "error", "Something went wrong.")); })
      .finally(() => { if (alive.current && !quiet) setLoading(false); });
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { run(false); }, deps);
  return { data, error, loading, reload: () => run(false), refreshQuietly: () => run(true) };
}

export function useInterval(fn: () => void, ms: number, enabled = true) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => ref.current(), ms);
    return () => clearInterval(id);
  }, [ms, enabled]);
}

export const fieldError = (err: unknown, field: string): string | undefined =>
  err instanceof ApiError ? err.fields.find((f) => f.field === field)?.message : undefined;
