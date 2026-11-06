import type { DemoScenario, RunRequest, RunResponse, AgentEvent } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function startRun(request: RunRequest): Promise<RunResponse> {
  const response = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(`Failed to start run: ${response.statusText}`)
  }

  return response.json()
}

export function subscribeToRun(
  runId: string,
  onEvent: (event: AgentEvent) => void,
  onComplete: () => void,
  onError: (error: Error) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/runs/${runId}/events`)

  eventSource.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data) as AgentEvent
      onEvent(event)

      if (event.type === 'done' || event.type === 'error') {
        eventSource.close()
        onComplete()
      }
    } catch (error) {
      onError(error as Error)
    }
  }

  eventSource.onerror = (error) => {
    eventSource.close()
    onError(new Error('EventSource failed'))
  }

  return () => eventSource.close()
}

export async function fetchScenarios(): Promise<{
  scenarios: DemoScenario[]
  categories: string[]
}> {
  const response = await fetch(`${API_BASE}/scenarios`)
  if (!response.ok) {
    throw new Error(`Failed to fetch scenarios: ${response.statusText}`)
  }
  return response.json()
}

export async function fetchScenario(id: string): Promise<DemoScenario> {
  const response = await fetch(`${API_BASE}/scenarios/${id}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch scenario: ${response.statusText}`)
  }
  return response.json()
}
