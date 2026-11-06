import { Clock, FileEdit, Wrench, AlertCircle } from 'lucide-react'
import { formatDuration } from '@/lib/utils'
import type { RunMetrics } from '@/types'

interface MetricsPanelProps {
  metrics: RunMetrics
}

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  return (
    <div className="mb-6 bg-white rounded-lg shadow-md p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Run Metrics</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          icon={<Clock className="w-5 h-5 text-blue-600" />}
          label="Duration"
          value={formatDuration(metrics.duration_seconds)}
          color="blue"
        />

        <MetricCard
          icon={<FileEdit className="w-5 h-5 text-green-600" />}
          label="Files Changed"
          value={metrics.files_changed.toString()}
          color="green"
        />

        <MetricCard
          icon={<Wrench className="w-5 h-5 text-purple-600" />}
          label="Tools Used"
          value={metrics.tools_called.toString()}
          color="purple"
        />

        <MetricCard
          icon={<AlertCircle className="w-5 h-5 text-red-600" />}
          label="Errors"
          value={metrics.errors.toString()}
          color="red"
        />
      </div>
    </div>
  )
}

interface MetricCardProps {
  icon: React.ReactNode
  label: string
  value: string
  color: 'blue' | 'green' | 'purple' | 'red'
}

function MetricCard({ icon, label, value, color }: MetricCardProps) {
  const colorClasses = {
    blue: 'bg-blue-50 border-blue-200',
    green: 'bg-green-50 border-green-200',
    purple: 'bg-purple-50 border-purple-200',
    red: 'bg-red-50 border-red-200',
  }

  return (
    <div className={`border rounded-lg p-4 ${colorClasses[color]}`}>
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs font-medium text-gray-600">{label}</span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  )
}
