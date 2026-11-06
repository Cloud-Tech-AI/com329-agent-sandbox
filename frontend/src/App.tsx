import { useState, useEffect } from 'react'
import { Play, AlertCircle, CheckCircle, Clock, FileCode, Shield } from 'lucide-react'
import { useAgentRun } from './hooks/useAgentRun'
import { fetchScenarios } from './lib/api'
import { cn, formatDuration } from './lib/utils'
import type { DemoScenario, Runtime } from './types'
import { EventLog } from './components/EventLog'
import { ScenarioCard } from './components/ScenarioCard'
import { MetricsPanel } from './components/MetricsPanel'

function App() {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedScenario, setSelectedScenario] = useState<DemoScenario | null>(null)
  const [customRepo, setCustomRepo] = useState('')
  const [customTask, setCustomTask] = useState('')
  const [selectedRuntime, setSelectedRuntime] = useState<Runtime | undefined>(undefined)

  const { isRunning, events, metrics, error, run, reset } = useAgentRun()

  useEffect(() => {
    fetchScenarios().then(({ scenarios }) => setScenarios(scenarios))
  }, [])

  const categories = ['all', ...Array.from(new Set(scenarios.map(s => s.category)))]
  const filteredScenarios = selectedCategory === 'all'
    ? scenarios
    : scenarios.filter(s => s.category === selectedCategory)

  const handleRunScenario = async (scenario: DemoScenario) => {
    setSelectedScenario(scenario)
    await run({
      github_repo: scenario.repo,
      task: scenario.task,
      runtime: selectedRuntime,
    })
  }

  const handleRunCustom = async () => {
    if (!customRepo || !customTask) return

    setSelectedScenario(null)
    await run({
      github_repo: customRepo,
      task: customTask,
      runtime: selectedRuntime,
    })
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                <Shield className="w-8 h-8 text-primary-600" />
                Code Change Agent
              </h1>
              <p className="mt-1 text-sm text-gray-600">
                AI-powered code analysis with gVisor sandbox isolation
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-xs text-gray-500">Runtime Selection</p>
                <div className="flex gap-2 mt-1">
                  <button
                    onClick={() => setSelectedRuntime(undefined)}
                    className={cn(
                      "px-3 py-1 text-sm font-medium rounded-md transition-colors",
                      selectedRuntime === undefined
                        ? "bg-primary-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    Both
                  </button>
                  <button
                    onClick={() => setSelectedRuntime('runc' as Runtime)}
                    className={cn(
                      "px-3 py-1 text-sm font-medium rounded-md transition-colors",
                      selectedRuntime === 'runc'
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    runc
                  </button>
                  <button
                    onClick={() => setSelectedRuntime('gvisor' as Runtime)}
                    className={cn(
                      "px-3 py-1 text-sm font-medium rounded-md transition-colors",
                      selectedRuntime === 'gvisor'
                        ? "bg-gvisor-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    gVisor
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Status Banner */}
        {isRunning && (
          <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center gap-3 animate-pulse-slow">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
            <span className="text-blue-900 font-medium">
              Agent is running... ({events.length} events)
            </span>
          </div>
        )}

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <span className="text-red-900">{error}</span>
          </div>
        )}

        {metrics && (
          <MetricsPanel metrics={metrics} />
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Sidebar: Scenarios & Custom Input */}
          <div className="lg:col-span-1 space-y-6">
            {/* Custom Input */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <FileCode className="w-5 h-5" />
                Custom Task
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Repository (owner/name)
                  </label>
                  <input
                    type="text"
                    value={customRepo}
                    onChange={(e) => setCustomRepo(e.target.value)}
                    placeholder="Cloud-Tech-AI/demo-app"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    disabled={isRunning}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Task Description
                  </label>
                  <textarea
                    value={customTask}
                    onChange={(e) => setCustomTask(e.target.value)}
                    placeholder="Fix the SQL injection in the login endpoint..."
                    rows={4}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    disabled={isRunning}
                  />
                </div>

                <button
                  onClick={handleRunCustom}
                  disabled={isRunning || !customRepo || !customTask}
                  className={cn(
                    "w-full py-2 px-4 rounded-md font-medium transition-colors flex items-center justify-center gap-2",
                    isRunning || !customRepo || !customTask
                      ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                      : "bg-primary-600 text-white hover:bg-primary-700"
                  )}
                >
                  <Play className="w-4 h-4" />
                  Run Custom Task
                </button>
              </div>
            </div>

            {/* Scenarios */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Demo Scenarios
              </h2>

              {/* Category Filter */}
              <div className="mb-4 flex flex-wrap gap-2">
                {categories.map(cat => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={cn(
                      "px-3 py-1 text-sm font-medium rounded-full transition-colors",
                      selectedCategory === cat
                        ? "bg-primary-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </button>
                ))}
              </div>

              {/* Scenario List */}
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {filteredScenarios.map(scenario => (
                  <ScenarioCard
                    key={scenario.id}
                    scenario={scenario}
                    isActive={selectedScenario?.id === scenario.id}
                    isDisabled={isRunning}
                    onRun={handleRunScenario}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Main Content: Event Log */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Execution Log
                </h2>
                {!isRunning && events.length > 0 && (
                  <button
                    onClick={reset}
                    className="text-sm text-gray-600 hover:text-gray-900"
                  >
                    Clear
                  </button>
                )}
              </div>

              {events.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <p>Select a scenario or enter a custom task to begin</p>
                </div>
              ) : (
                <EventLog events={events} />
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
