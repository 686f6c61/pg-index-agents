/**
 * PG Index Agents - Hook useJobPolling
 * https://github.com/686f6c61/pg-index-agents
 *
 * Este modulo proporciona hooks especializados para monitorear trabajos
 * de agentes ejecutados en background. Los agentes pueden tardar varios
 * minutos en completarse, y estos hooks permiten seguir su progreso.
 *
 * Hooks disponibles:
 *
 *   useJobPolling:
 *     Monitorea un unico job por su ID. Realiza polling cada 2 segundos
 *     (configurable) y detiene automaticamente cuando el job termina.
 *     Proporciona callbacks para completado y error.
 *
 *   useMultipleJobs:
 *     Permite consultar el estado de multiples jobs simultaneamente.
 *     util para dashboards que muestran varios agentes en ejecucion.
 *
 * Estados de job monitoreados:
 *   - pending: En cola, esperando ejecucion
 *   - running: En proceso de ejecucion
 *   - completed: Finalizado con exito
 *   - failed: Finalizado con error
 *   - cancelled: Cancelado por el usuario
 *
 * @author 686f6c61
 * @license MIT
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api, Job } from '@/lib/api';

/** Opciones de configuracion para el polling de jobs */
interface UseJobPollingOptions {
  onComplete?: (job: Job) => void;
  onError?: (error: string) => void;
  pollInterval?: number;
}

export function useJobPolling(
  jobId: string | null,
  options: UseJobPollingOptions = {}
) {
  const { onComplete, onError, pollInterval = 2000 } = options;

  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const fetchJob = useCallback(async () => {
    if (!jobId || !mountedRef.current) return;

    try {
      const jobData = await api.getJob(jobId);

      if (!mountedRef.current) return;

      setJob(jobData);
      setError(null);

      // Check if job is complete
      if (jobData.status === 'completed' || jobData.status === 'failed' || jobData.status === 'cancelled') {
        stopPolling();

        if (jobData.status === 'completed') {
          onComplete?.(jobData);
        } else if (jobData.status === 'failed') {
          onError?.(jobData.error || 'Job failed');
        }
      }
    } catch (err) {
      if (!mountedRef.current) return;

      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch job status';
      setError(errorMsg);
      onError?.(errorMsg);
      stopPolling();
    }
  }, [jobId, onComplete, onError, stopPolling]);

  const startPolling = useCallback(() => {
    if (!jobId) return;

    setLoading(true);
    fetchJob();

    intervalRef.current = setInterval(fetchJob, pollInterval);
  }, [jobId, fetchJob, pollInterval]);

  useEffect(() => {
    mountedRef.current = true;

    if (jobId) {
      startPolling();
    }

    return () => {
      mountedRef.current = false;
      stopPolling();
    };
  }, [jobId, startPolling, stopPolling]);

  useEffect(() => {
    if (job && (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled')) {
      setLoading(false);
    }
  }, [job]);

  return {
    job,
    loading,
    error,
    isRunning: job?.status === 'running' || job?.status === 'pending',
    isComplete: job?.status === 'completed',
    isFailed: job?.status === 'failed',
    stopPolling,
  };
}

// Hook for tracking multiple jobs
export function useMultipleJobs(jobIds: string[]) {
  const [jobs, setJobs] = useState<Map<string, Job>>(new Map());
  const [loading, setLoading] = useState(false);

  const fetchJobs = useCallback(async () => {
    if (jobIds.length === 0) return;

    setLoading(true);
    const jobPromises = jobIds.map(id => api.getJob(id).catch(() => null));
    const results = await Promise.all(jobPromises);

    const newJobs = new Map<string, Job>();
    results.forEach((job, index) => {
      if (job) {
        newJobs.set(jobIds[index], job);
      }
    });

    setJobs(newJobs);
    setLoading(false);
  }, [jobIds]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  return {
    jobs,
    loading,
    refresh: fetchJobs,
    getJob: (id: string) => jobs.get(id),
  };
}
