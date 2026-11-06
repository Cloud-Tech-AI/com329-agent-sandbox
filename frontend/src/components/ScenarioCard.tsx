import { Play, Shield, TestTube, Zap, FileCode, Clock, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DemoScenario } from '@/types'

interface ScenarioCardProps {
  scenario: DemoScenario
  isActive: boolean
  isDisabled: boolean
  onRun: (scenario: DemoScenario) => void
}

export function ScenarioCard({ scenario, isActive, isDisabled, onRun }: ScenarioCardProps) {
  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'security':
        return <Shield className="w-4 h-4" />
      case 'testing':
        return <TestTube className="w-4 h-4" />
      case 'performance':
        return <Zap className="w-4 h-4" />
      case 'refactoring':
        return <FileCode className="w-4 h-4" />
      default:
        return <FileCode className="w-4 h-4" />
    }
  }

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'security':
        return 'bg-red-100 text-red-700'
      case 'testing':
        return 'bg-green-100 text-green-700'
      case 'performance':
        return 'bg-yellow-100 text-yellow-700'
      case 'refactoring':
        return 'bg-blue-100 text-blue-700'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'easy':
        return 'text-green-600'
      case 'medium':
        return 'text-yellow-600'
      case 'hard':
        return 'text-red-600'
      default:
        return 'text-gray-600'
    }
  }

  return (
    <div
      className={cn(
        'border rounded-lg p-4 transition-all cursor-pointer hover:shadow-md',
        isActive ? 'bg-primary-50 border-primary-300 shadow-md' : 'bg-white border-gray-200',
        isDisabled && 'opacity-50 cursor-not-allowed'
      )}
      onClick={() => !isDisabled && onRun(scenario)}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-semibold text-sm text-gray-900">{scenario.name}</h3>
        <span
          className={cn(
            'inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium',
            getCategoryColor(scenario.category)
          )}
        >
          {getCategoryIcon(scenario.category)}
          {scenario.category}
        </span>
      </div>

      <p className="text-xs text-gray-600 mb-3">{scenario.description}</p>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {scenario.estimated_duration}
          </span>
          <span className={cn('flex items-center gap-1 font-medium', getDifficultyColor(scenario.difficulty))}>
            <TrendingUp className="w-3 h-3" />
            {scenario.difficulty}
          </span>
        </div>

        {!isDisabled && (
          <Play className="w-4 h-4 text-primary-600" />
        )}
      </div>
    </div>
  )
}
