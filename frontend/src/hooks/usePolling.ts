/**
 * Generic polling hook.
 * Fetches data immediately, then every `intervalMs` milliseconds.
 */

import { useCallback, useEffect, useState } from 'react'

interface UsePollingResult<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs = 5000
): UsePollingResult<T> {
  const [data, setData]     = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState<string | null>(null)

  const refetch = useCallback(async () => {
    try {
      const result = await fetcher()
      setData(result)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [fetcher])

  useEffect(() => {
    refetch()
    const id = setInterval(refetch, intervalMs)
    return () => clearInterval(id)
  }, [refetch, intervalMs])

  return { data, loading, error, refetch }
}
