/**
 * PG Index Agents - Hook useApi
 * https://github.com/686f6c61/pg-index-agents
 *
 * Este modulo proporciona hooks de React para gestionar llamadas a la API
 * con soporte para cache en memoria, estados de carga, y manejo de errores.
 *
 * Hooks disponibles:
 *
 *   useApi<T>:
 *     Hook principal para ejecutar llamadas API con estados reactivos.
 *     Soporta ejecucion inmediata, callbacks de exito/error, y cache TTL.
 *
 *   usePolling<T>:
 *     Extension de useApi con polling automatico a intervalos configurables.
 *     util para monitorear jobs en background o refrescar datos periodicamente.
 *
 *   clearApiCache:
 *     Funcion utilitaria para invalidar cache manualmente, ya sea una clave
 *     especifica o todo el cache.
 *
 * El cache en memoria tiene un TTL por defecto de 30 segundos para evitar
 * llamadas redundantes durante navegacion rapida.
 *
 * @author 686f6c61
 * @license MIT
 */

import { useState, useCallback, useRef, useEffect } from 'react';

/** Estado interno del hook useApi */
interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface UseApiOptions {
  immediate?: boolean;
  onSuccess?: (data: any) => void;
  onError?: (error: string) => void;
  cacheKey?: string;
  cacheTTL?: number; // in milliseconds
}

// Simple in-memory cache
const cache = new Map<string, { data: any; timestamp: number }>();
const DEFAULT_CACHE_TTL = 30000; // 30 seconds

export function useApi<T>(
  apiCall: () => Promise<T>,
  options: UseApiOptions = {}
) {
  const { immediate = false, onSuccess, onError, cacheKey, cacheTTL = DEFAULT_CACHE_TTL } = options;

  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: immediate,
    error: null,
  });

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const execute = useCallback(async () => {
    // Check cache first
    if (cacheKey) {
      const cached = cache.get(cacheKey);
      if (cached && Date.now() - cached.timestamp < cacheTTL) {
        setState({ data: cached.data, loading: false, error: null });
        return cached.data;
      }
    }

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const data = await apiCall();

      if (!mountedRef.current) return;

      // Update cache
      if (cacheKey) {
        cache.set(cacheKey, { data, timestamp: Date.now() });
      }

      setState({ data, loading: false, error: null });
      onSuccess?.(data);
      return data;
    } catch (err) {
      if (!mountedRef.current) return;

      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      setState(prev => ({ ...prev, loading: false, error: errorMessage }));
      onError?.(errorMessage);
      throw err;
    }
  }, [apiCall, cacheKey, cacheTTL, onSuccess, onError]);

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null });
  }, []);

  // Execute immediately if requested
  useEffect(() => {
    if (immediate) {
      execute();
    }
  }, [immediate, execute]);

  return {
    ...state,
    execute,
    reset,
    isIdle: !state.loading && !state.data && !state.error,
  };
}

// Hook for polling data
export function usePolling<T>(
  apiCall: () => Promise<T>,
  interval: number,
  options: UseApiOptions & { enabled?: boolean } = {}
) {
  const { enabled = true, ...apiOptions } = options;
  const api = useApi(apiCall, apiOptions);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Initial fetch
    api.execute();

    // Set up polling
    intervalRef.current = setInterval(() => {
      api.execute();
    }, interval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enabled, interval]);

  return api;
}

// Clear cache utility
export function clearApiCache(key?: string) {
  if (key) {
    cache.delete(key);
  } else {
    cache.clear();
  }
}
