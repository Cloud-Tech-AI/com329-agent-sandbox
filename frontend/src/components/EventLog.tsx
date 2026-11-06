import { useEffect, useRef } from 'react'
import {
  CheckCircle,
  AlertCircle,
  Info,
  Wrench,
  FileEdit,
  Brain,
  BarChart3,
  GitDiff,
} from 'lucide-react'
import { cn, formatTimestamp } from '@/lib/utils'
import type { AgentEvent } from '@/types'
import { EventType } from '@/types'

interface EventLogProps {
  events: AgentEvent[]
}

export function EventLog({ events }: EventLogProps) {
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [events])

  const getEventIcon = (type: EventType) => {
    switch (type) {
      case EventType.TOOL:
        return <Wrench className="w-4 h-4" />
      case EventType.THINKING:
        return <Brain className="w-4 h-4" />
      case EventType.FILE_CHANGE:
        return <FileEdit className="w-4 h-4" />
      case EventType.DIFF:
        return <GitDiff className="w-4 h-4" />
      case EventType.DONE:
        return <CheckCircle className="w-4 h-4" />
      case EventType.ERROR:
        return <AlertCircle className="w-4 h-4" />
      case EventType.METRICS:
        return <BarChart3 className="w-4 h-4" />
      default:
        return <Info className="w-4 h-4" />
    }
  }

  const getEventColor = (type: EventType) => {
    switch (type) {
      case EventType.TOOL:
        return 'text-blue-600 bg-blue-50 border-blue-200'
      case EventType.THINKING:
        return 'text-purple-600 bg-purple-50 border-purple-200'
      case EventType.FILE_CHANGE:
        return 'text-green-600 bg-green-50 border-green-200'
      case EventType.DIFF:
        return 'text-orange-600 bg-orange-50 border-orange-200'
      case EventType.DONE:
        return 'text-green-700 bg-green-100 border-green-300'
      case EventType.ERROR:
        return 'text-red-600 bg-red-50 border-red-200'
      case EventType.METRICS:
        return 'text-indigo-600 bg-indigo-50 border-indigo-200'
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200'
    }
  }

  const formatText = (event: AgentEvent) => {
    switch (event.type) {
      case EventType.TOOL:
        return `Using ${event.text}`
      case EventType.FILE_CHANGE:
        if (event.metadata?.lines_added || event.metadata?.lines_removed) {
          const added = event.metadata.lines_added || 0
          const removed = event.metadata.lines_removed || 0
          return `${event.text} (+${added}/-${removed})`
        }
        return event.text
      default:
        return event.text
    }
  }

  return (
    <div
      ref={logRef}
      className="event-log space-y-2 max-h-[700px] overflow-y-auto pr-2"
    >
      {events.map((event, index) => (
        <div
          key={index}
          className={cn(
            'animate-slide-in border rounded-lg p-3 flex items-start gap-3',
            getEventColor(event.type)
          )}
        >
          <div className="mt-0.5">{getEventIcon(event.type)}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <p className={cn(
                'text-sm break-words',
                event.type === EventType.DONE || event.type === EventType.ERROR
                  ? 'font-semibold'
                  : 'font-medium'
              )}>
                {formatText(event)}
              </p>
              {event.metadata?.runtime && (
                <span className={cn(
                  'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap',
                  event.metadata.runtime === 'runc'
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-gvisor-100 text-gvisor-800'
                )}>
                  {event.metadata.runtime}
                </span>
              )}
            </div>

            {event.type === EventType.THINKING && (
              <pre className="mt-2 text-xs whitespace-pre-wrap bg-white/50 rounded p-2 border">
                {event.text}
              </pre>
            )}

            {event.type === EventType.DIFF && (
              <pre className="mt-2 text-xs whitespace-pre-wrap bg-white/50 rounded p-2 border overflow-x-auto">
                {event.text}
              </pre>
            )}

            <p className="text-xs opacity-75 mt-1">
              {formatTimestamp(event.timestamp)}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
