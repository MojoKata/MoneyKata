// Loading data for a screen: fetch on mount, again when its inputs change or the live stream
// says its data changed, and keep the last good answer while reloading.
import { useCallback, useEffect, useRef, useState } from 'preact/hooks';
import { api } from '../api/client.js';
import { changes } from './stream.js';

/**
 * @template T
 * @param {string | null} path  null waits (nothing to load yet)
 * @param {Record<string, any>} [params]
 * @param {string[]} [reloadOn]  the live stream's kinds that make it load again
 * @returns {{ data: T | null, error: any, loading: boolean, reload: () => void }}
 */
export function useApi(path, params = {}, reloadOn = []) {
  const [state, setState] = useState(
    /** @type {{ data: T | null, error: any, loading: boolean }} */ ({
      data: null,
      error: null,
      loading: !!path,
    }),
  );
  const key = path + JSON.stringify(params);
  const seen = reloadOn.map((k) => changes.value[k] || 0).join(',');
  const [tick, setTick] = useState(0);
  const current = useRef(key);
  current.current = key;

  useEffect(() => {
    if (!path) return;
    let live = true;
    setState((s) => ({ ...s, loading: true }));
    api.get(path, params).then(
      (data) => live && current.current === key && setState({ data, error: null, loading: false }),
      (error) => live && setState((s) => ({ data: s.data, error, loading: false })),
    );
    return () => {
      live = false;
    };
  }, [key, seen, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}

/**
 * A form's submission: busy while it runs, the server's refusal kept for the fields.
 * @param {(...args: any[]) => Promise<any>} fn
 */
export function useSubmit(fn) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(/** @type {any} */ (null));
  const run = async (/** @type {any[]} */ ...args) => {
    setBusy(true);
    setError(null);
    try {
      return await fn(...args);
    } catch (e) {
      setError(e);
      throw e;
    } finally {
      setBusy(false);
    }
  };
  return { run, busy, error, setError };
}
