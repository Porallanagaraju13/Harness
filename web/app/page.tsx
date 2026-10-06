'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import styles from './page.module.css'
import TraceViewer from './components/TraceViewer'

interface DatasetInfo {
  id: string
  label: string
  is_mock?: boolean
  path: string
  timestamp?: string
  model?: {
    spec?: string
    provider?: string
    model_id?: string
    display_name?: string
  }
  final_success_rate?: number
}

interface AblationResults {
  timestamp: string
  dataset_id?: string
  model?: DatasetInfo['model']
  runs: Array<{
    run_id: string
    layer_added?: string
    tasks: Array<{
      task_id: string
      task_description: string
      real_success: boolean
      agent_claimed_success: boolean
      false_claim_made: boolean
      false_claim_caught: boolean
      steps: number
      verification: { evidence?: string }
    }>
  }>
  summary: Record<
    string,
    {
      total_tasks: number
      real_success_count: number
      real_success_rate: number
      false_claims_made: number
      false_claims_caught: number
      unsafe_attempts: number
      unsafe_blocked: number
      unsafe_executed?: number
    }
  >
  task_layer_matrix?: Record<string, Record<string, boolean>>
}

const LAYER_LABELS: Record<string, string> = {
  baseline: 'Baseline',
  tool_design: 'Tool Design',
  context: 'Context',
  sandbox: 'Sandbox',
  permissions: 'Permissions',
  retry: 'Retry',
  verification: 'Verification',
}

function runLabel(run: AblationResults['runs'][number]) {
  if (run.run_id === 'baseline') return 'Baseline (no harness)'
  const key = run.layer_added || run.run_id.replace('layer_', '')
  return `+ ${LAYER_LABELS[key] || key.replace(/_/g, ' ')}`
}

export default function Home() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([])
  const [activeId, setActiveId] = useState<string>('mock')
  const [results, setResults] = useState<AblationResults | null>(null)
  const [error, setError] = useState('')
  const [selectedTask, setSelectedTask] = useState<string | null>(null)
  const [traces, setTraces] = useState<Record<string, any>>({})

  const showToggle = useMemo(
    () => datasets.some((d) => !d.is_mock) && datasets.length > 1,
    [datasets]
  )

  const loadTraces = useCallback(async (data: AblationResults, basePath: string) => {
    const baselineRun = data.runs.find((r) => r.run_id === 'baseline')
    const fullRun = data.runs[data.runs.length - 1]
    if (!baselineRun || !fullRun) return

    const newTraces: Record<string, any> = {}
    for (const task of baselineRun.tasks) {
      try {
        const baselineTrace = await fetch(
          `${basePath}/baseline_${task.task_id}_trace.jsonl`
        )
          .then((res) => {
            if (!res.ok) throw new Error('missing')
            return res.text()
          })
          .then((text) =>
            text
              .trim()
              .split('\n')
              .filter(Boolean)
              .map((line) => JSON.parse(line))
          )

        const fullTrace = await fetch(
          `${basePath}/${fullRun.run_id}_${task.task_id}_trace.jsonl`
        )
          .then((res) => {
            if (!res.ok) throw new Error('missing')
            return res.text()
          })
          .then((text) =>
            text
              .trim()
              .split('\n')
              .filter(Boolean)
              .map((line) => JSON.parse(line))
          )

        newTraces[task.task_id] = {
          baseline: baselineTrace,
          full: fullTrace,
          description: task.task_description,
        }
      } catch {
        // Trace file missing — skip
      }
    }
    setTraces(newTraces)
  }, [])

  const loadDataset = useCallback(
    async (ds: DatasetInfo) => {
      setError('')
      setSelectedTask(null)
      setTraces({})
      setResults(null)
      try {
        const res = await fetch(`${ds.path}/ablation_results.json`)
        if (!res.ok) throw new Error('missing')
        const data = await res.json()
        setResults(data)
        await loadTraces(data, ds.path)
      } catch {
        setError(
          `No results for "${ds.label}". Run ablation and \`harnessdiff publish-results\`.`
        )
      }
    },
    [loadTraces]
  )

  useEffect(() => {
    fetch('/data/index.json')
      .then((res) => {
        if (!res.ok) throw new Error('missing index')
        return res.json()
      })
      .then((index) => {
        const list: DatasetInfo[] = index.datasets || []
        if (!list.length) throw new Error('empty')
        setDatasets(list)
        const preferred =
          list.find((d) => d.is_mock || d.id === 'mock') || list[0]
        setActiveId(preferred.id)
        return loadDataset(preferred)
      })
      .catch(() => {
        // Backward-compat: root-level ablation_results.json
        fetch('/ablation_results.json')
          .then((res) => {
            if (!res.ok) throw new Error('missing')
            return res.json()
          })
          .then(async (data) => {
            const fallback: DatasetInfo = {
              id: 'mock',
              label: 'Mock model',
              is_mock: true,
              path: '',
            }
            setDatasets([fallback])
            setActiveId('mock')
            setResults(data)
            await loadTraces(data, '')
          })
          .catch(() => {
            setError(
              'No results found. Run `harnessdiff ablate` then `harnessdiff publish-results`.'
            )
          })
      })
  }, [loadDataset, loadTraces])

  const onSelectDataset = (id: string) => {
    const ds = datasets.find((d) => d.id === id)
    if (!ds) return
    setActiveId(id)
    loadDataset(ds)
  }

  const headline = useMemo(() => {
    if (!results) return null
    const baseline = results.summary.baseline
    const final = results.summary[results.runs[results.runs.length - 1].run_id]
    return {
      before: Math.round(baseline.real_success_rate * 1000) / 10,
      after: Math.round(final.real_success_rate * 1000) / 10,
      falseReduced: baseline.false_claims_made - final.false_claims_made,
      caught: final.false_claims_caught,
      blocked: final.unsafe_blocked,
      executedBefore: baseline.unsafe_executed ?? 0,
    }
  }, [results])

  const matrix = useMemo(() => {
    if (!results) return null
    if (results.task_layer_matrix) return results.task_layer_matrix
    const built: Record<string, Record<string, boolean>> = {}
    for (const run of results.runs) {
      for (const task of run.tasks) {
        built[task.task_id] ??= {}
        built[task.task_id][run.run_id] = task.real_success
      }
    }
    return built
  }, [results])

  if (error && !results) {
    return (
      <main className={styles.main}>
        <p className={styles.brandMark}>HarnessDiff</p>
        <p className={styles.error}>{error}</p>
      </main>
    )
  }

  if (!results || !headline) {
    return (
      <main className={styles.main}>
        <p className={styles.brandMark}>HarnessDiff</p>
        <p className={styles.loading}>Loading ablation results…</p>
      </main>
    )
  }

  const runIds = results.runs.map((r) => r.run_id)
  const activeLabel =
    datasets.find((d) => d.id === activeId)?.label ||
    results.model?.display_name ||
    'Mock model'

  return (
    <main className={styles.main}>
      {selectedTask && traces[selectedTask] ? (
        <>
          <div className={styles.backRow}>
            <button type="button" onClick={() => setSelectedTask(null)}>
              ← Back to results
            </button>
          </div>
          <TraceViewer
            taskId={selectedTask}
            baselineTrace={traces[selectedTask].baseline}
            fullTrace={traces[selectedTask].full}
            taskDescription={traces[selectedTask].description}
          />
        </>
      ) : (
        <>
          <section className={styles.hero} aria-label="HarnessDiff overview">
            <div className={styles.heroCopy}>
              <p className={styles.brand}>HarnessDiff</p>
              <h1 className={styles.headline}>
                The same agent. Different scaffolding. Measurable outcomes.
              </h1>
              <p className={styles.lede}>
                Without a harness, agents claim success they did not earn and reach for
                unsafe actions. Layer by layer, HarnessDiff shows what actually changes.
              </p>
              <div className={styles.ctaRow}>
                <a className={styles.ctaPrimary} href="#ablation">
                  See the ablation
                </a>
                <a
                  className={styles.ctaSecondary}
                  href="https://github.com/Porallanagaraju13/Harness"
                  target="_blank"
                  rel="noreferrer"
                >
                  View on GitHub
                </a>
              </div>
            </div>

            <div className={styles.heroVisual} aria-hidden="false">
              <div className={styles.scoreBefore}>
                <span className={styles.scoreLabel}>Before</span>
                <strong className={styles.scoreValue}>{headline.before}%</strong>
                <span className={styles.scoreHint}>bare agent</span>
              </div>
              <div className={styles.scoreArrow}>→</div>
              <div className={styles.scoreAfter}>
                <span className={styles.scoreLabel}>After</span>
                <strong className={styles.scoreValue}>{headline.after}%</strong>
                <span className={styles.scoreHint}>full harness</span>
              </div>
            </div>
          </section>

          {showToggle && (
            <div className={styles.datasetToggle} role="tablist" aria-label="Result dataset">
              {datasets.map((ds) => (
                <button
                  key={ds.id}
                  type="button"
                  role="tab"
                  aria-selected={ds.id === activeId}
                  className={
                    ds.id === activeId ? styles.datasetActive : styles.datasetIdle
                  }
                  onClick={() => onSelectDataset(ds.id)}
                >
                  {ds.label}
                </button>
              ))}
            </div>
          )}

          <p className={styles.datasetCaption}>
            Showing results for <strong>{activeLabel}</strong>
            {results.timestamp
              ? ` · generated ${new Date(results.timestamp).toLocaleString()}`
              : ''}
          </p>

          <section className={styles.numbers} aria-label="Headline numbers">
            <div>
              <strong>
                {headline.before}% → {headline.after}%
              </strong>
              <span>real success rate</span>
            </div>
            <div>
              <strong>−{headline.falseReduced}</strong>
              <span>false claims reduced</span>
            </div>
            <div>
              <strong>{headline.caught}</strong>
              <span>false claims caught</span>
            </div>
            <div>
              <strong>
                {headline.executedBefore} → {headline.blocked}
              </strong>
              <span>unsafe executed → blocked</span>
            </div>
          </section>

          <section id="ablation" className={styles.section}>
            <h2>Layer-by-layer ablation</h2>
            <p className={styles.sectionLede}>
              One configuration at a time. Each bar is the success rate after that layer
              is added on top of everything before it.
            </p>
            <div className={styles.chart}>
              {results.runs.map((run) => {
                const summary = results.summary[run.run_id]
                const rate = Math.round(summary.real_success_rate * 1000) / 10
                return (
                  <div key={run.run_id} className={styles.chartRow}>
                    <div className={styles.chartLabel}>{runLabel(run)}</div>
                    <div className={styles.chartTrack}>
                      <div
                        className={styles.chartFill}
                        style={{ width: `${Math.max(rate, 4)}%` }}
                      >
                        {rate}%
                      </div>
                    </div>
                    <div className={styles.chartMeta}>
                      {summary.real_success_count}/{summary.total_tasks} pass
                      {summary.false_claims_caught > 0
                        ? ` · ${summary.false_claims_caught} caught`
                        : ''}
                      {summary.unsafe_blocked > 0
                        ? ` · ${summary.unsafe_blocked} blocked`
                        : ''}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <section className={styles.section}>
            <h2>Task × layer matrix</h2>
            <p className={styles.sectionLede}>
              Green means real success for that task under that cumulative configuration.
              Click a task name to open the side-by-side trace.
            </p>
            <div className={styles.matrixWrap}>
              <table className={styles.matrix}>
                <thead>
                  <tr>
                    <th>Task</th>
                    {runIds.map((id) => (
                      <th key={id}>
                        {id === 'baseline'
                          ? 'base'
                          : (LAYER_LABELS[id.replace('layer_', '')] || id).slice(0, 6)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrix &&
                    Object.entries(matrix).map(([taskId, row]) => (
                      <tr key={taskId}>
                        <th>
                          <button
                            type="button"
                            className={styles.taskLink}
                            onClick={() => setSelectedTask(taskId)}
                          >
                            {taskId}
                          </button>
                        </th>
                        {runIds.map((id) => (
                          <td key={id} className={row[id] ? styles.pass : styles.fail}>
                            {row[id] ? '✓' : '✗'}
                          </td>
                        ))}
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className={styles.section}>
            <h2>Inspect a trace</h2>
            <p className={styles.sectionLede}>
              Baseline on the left, full harness on the right. Pick any task to see where
              the harness intervened.
            </p>
            <div className={styles.taskPicker}>
              {results.runs[0].tasks.map((task) => (
                <button
                  key={task.task_id}
                  type="button"
                  className={styles.taskChip}
                  onClick={() => setSelectedTask(task.task_id)}
                >
                  <span>{task.task_id}</span>
                  <small>{task.task_description}</small>
                </button>
              ))}
            </div>
          </section>

          <footer className={styles.footer}>
            <p>
              Based on <em>Understanding Harness Engineering</em> by{' '}
              <a href="https://x.com/techNmak" target="_blank" rel="noreferrer">
                @techNmak
              </a>
              . Built by{' '}
              <a
                href="https://github.com/Porallanagaraju13"
                target="_blank"
                rel="noreferrer"
              >
                Nagaraju Poralla
              </a>
              .
            </p>
            <p>
              <a
                href="https://github.com/Porallanagaraju13/Harness"
                target="_blank"
                rel="noreferrer"
              >
                github.com/Porallanagaraju13/Harness
              </a>
              {' · '}
              Results generated {new Date(results.timestamp).toLocaleString()}
            </p>
          </footer>
        </>
      )}
    </main>
  )
}
