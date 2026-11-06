import { useState, useCallback, useEffect } from 'react'
import type { AgentEvent, RunRequest, RunResponse, RunMetrics } from '@/types'
import { startRun, subscribeToRun } from '@/lib/api'
import { EventType } from '@/types'

export function useAgentRun() {
  const [isRunning, setIsRunning] = useState(false)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [metrics, setMetrics] = useState<RunMetrics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [runId, setRunId] = useState<string | null>(null)

  const run = useCallback(async (request: RunRequest) => {
    setIsRunning(true)
    setEvents([])
    setMetrics(null)
    setError(null)

    try {
      const response: RunResponse = await startRun(request)
      setRunId(response.id)

      const unsubscribe = subscribeToRun(
        response.id,
        (event: AgentEvent) => {
          setEvents((prev) => [...prev, event])

          if (event.type === EventType.METRICS && event.metadata?.metrics) {
            setMetrics(event.metadata.metrics)
          }
        },
        () => {
          setIsRunning(false)
        },
        (err: Error) => {
          setError(err.message)
          setIsRunning(false)
        }
      )

      return unsubscribe
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setIsRunning(false)
      throw err
    }
  }, [])

  const reset = useCallback(() => {
    setIsRunning(false)
    setEvents([])
    setMetrics(null)
    setError(null)
    setRunId(null)
  }, [])

  return {
    isRunning,
    events,
    metrics,
    error,
    runId,
    run,
    reset,
  }
}
