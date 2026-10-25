/**
 * src/hooks/useHealth.ts
 * Polls backend readiness and subsystem status periodically.
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchHealth } from '../services/api';
import { HealthResponse } from '../types/amcrag';

export function useHealth(pollIntervalMs: number = 20000) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isOffline, setIsOffline] = useState<boolean>(false);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const data = await fetchHealth();
      setHealth(data);
      setIsOffline(false);
      setLastChecked(new Date());
    } catch (err) {
      console.warn('AMCRAG: Backend health check unreachable', err);
      setIsOffline(true);
      setHealth(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, pollIntervalMs);
    return () => clearInterval(interval);
  }, [checkHealth, pollIntervalMs]);

  return {
    health,
    isLoading,
    isOffline,
    lastChecked,
    checkHealth,
  };
}
