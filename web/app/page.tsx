'use client'

import { useState, useEffect } from 'react'
import styles from './page.module.css'
import TraceViewer from './components/TraceViewer'

interface AblationResults {
  timestamp: string
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
      verification: any
    }>
  }>
  summary: Record<string, {
    total_tasks: number
    real_success_count: number
    real_success_rate: number
    false_claims_made: number
    false_claims_caught: number
    unsafe_attempts: number
    unsafe_blocked: number
  }>
}

export default function Home() {
  const [results, setResults] = useState<AblationResults | null>(null)
  const [error, setError] = useState<string>('')
  const [selectedTask, setSelectedTask] = useState<string | null>(null)
  const [traces, setTraces] = useState<Record<string, any>>({})

  useEffect(() => {
    // Load results
    fetch('/ablation_results.json')
      .then(res => res.json())
      .then(data => {
        setResults(data)
        // Load traces for all tasks
        loadTraces(data)
      })
      .catch(err => {
        setError('No results found. Run `harnessdiff ablate` first to generate data.')
      })
  }, [])

  const loadTraces = async (data: AblationResults) => {
    const baselineRun = data.runs.find(r => r.run_id === 'baseline')
    const fullRun = data.runs[data.runs.length - 1]
    
    if (!baselineRun || !fullRun) return
    
    const newTraces: Record<string, any> = {}
    
    for (const task of baselineRun.tasks) {
      try {
        const baselineTrace = await fetch(`/baseline_${task.task_id}_trace.jsonl`)
          .then(res => res.text())
          .then(text => text.trim().split('\n').map(line => JSON.parse(line)))
        
        const fullTraceRun = data.runs[data.runs.length - 1].run_id
        const fullTrace = await fetch(`/${fullTraceRun}_${task.task_id}_trace.jsonl`)
          .then(res => res.text())
          .then(text => text.trim().split('\n').map(line => JSON.parse(line)))
        
        newTraces[task.task_id] = {
          baseline: baselineTrace,
          full: fullTrace,
          description: task.task_description
        }
      } catch (e) {
        // Trace file not found, skip
      }
    }
    
    setTraces(newTraces)
  }

  if (error) {
    return (
      <main className={styles.main}>
        <h1 className={styles.title}>HarnessDiff</h1>
        <p className={styles.error}>{error}</p>
        <p className={styles.instruction}>
          Run <code>harnessdiff ablate</code> to generate results, then copy results/ablation_results.json to web/public/
        </p>
      </main>
    )
  }

  if (!results) {
    return (
      <main className={styles.main}>
        <h1 className={styles.title}>Loading...</h1>
      </main>
    )
  }

  return (
    <main className={styles.main}>
      {selectedTask && traces[selectedTask] && (
        <div className={styles.backButton}>
          <button onClick={() => setSelectedTask(null)}>← Back to Results</button>
        </div>
      )}
      
      {selectedTask && traces[selectedTask] ? (
        <TraceViewer
          taskId={selectedTask}
          baselineTrace={traces[selectedTask].baseline}
          fullTrace={traces[selectedTask].full}
          taskDescription={traces[selectedTask].description}
        />
      ) : (
        <>
          <header className={styles.header}>
            <h1 className={styles.title}>HarnessDiff</h1>
            <p className={styles.subtitle}>
              See exactly what each agent harness layer fixes
            </p>
            <p className={styles.credit}>
              Based on "Understanding Harness Engineering" by @techNmak
            </p>
          </header>

          <section className={styles.section}>
        <h2 className={styles.sectionTitle}>📊 Ablation Results</h2>
        <p className={styles.sectionDesc}>
          Adding harness layers one at a time, measuring impact
        </p>
        
        <div className={styles.chart}>
          {results.runs.map((run, idx) => {
            const summary = results.summary[run.run_id]
            const successRate = (summary.real_success_rate * 100).toFixed(0)
            
            return (
              <div key={run.run_id} className={styles.chartRow}>
                <div className={styles.chartLabel}>
                  {run.run_id === 'baseline' 
                    ? 'Baseline (no harness)'
                    : `+ ${run.layer_added?.replace('_', ' ')}`
                  }
                </div>
                <div className={styles.chartBar}>
                  <div 
                    className={styles.chartFill}
                    style={{ width: `${successRate}%` }}
                  >
                    {successRate}%
                  </div>
                </div>
                <div className={styles.chartStats}>
                  <span className={styles.stat}>
                    ✓ {summary.real_success_count}/{summary.total_tasks}
                  </span>
                  <span className={styles.stat}>
                    ✗ {summary.false_claims_made} false claims
                  </span>
                  {summary.false_claims_caught > 0 && (
                    <span className={styles.stat}>
                      🔍 {summary.false_claims_caught} caught
                    </span>
                  )}
                  {summary.unsafe_blocked > 0 && (
                    <span className={styles.stat}>
                      🛡️ {summary.unsafe_blocked} blocked
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>🔍 Before vs After</h2>
        
        <div className={styles.comparison}>
          <div className={styles.comparisonCard}>
            <h3 className={styles.cardTitle}>Before (No Harness)</h3>
            <div className={styles.metrics}>
              {(() => {
                const baseline = results.summary['baseline']
                return (
                  <>
                    <div className={styles.metric}>
                      <span className={styles.metricLabel}>Success Rate</span>
                      <span className={styles.metricValue}>
                        {(baseline.real_success_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className={styles.metric}>
                      <span className={styles.metricLabel}>False Claims Made</span>
                      <span className={styles.metricValue}>
                        {baseline.false_claims_made}
                      </span>
                    </div>
                    <div className={styles.metric}>
                      <span className={styles.metricLabel}>False Claims Caught</span>
                      <span className={styles.metricValue}>
                        0
                      </span>
                    </div>
                    <div className={styles.metric}>
                      <span className={styles.metricLabel}>Unsafe Attempts</span>
                      <span className={styles.metricValue}>
                        {baseline.unsafe_attempts}
                      </span>
                    </div>
                  </>
                )
              })()}
            </div>
          </div>

          <div className={styles.comparisonCard}>
            <h3 className={styles.cardTitle}>After (Full Harness)</h3>
            <div className={styles.metrics}>
              {(() => {
                const final = results.summary[results.runs[results.runs.length - 1].run_id]
                return (
                  <>
                    <div className={styles.metric}>
                      <span className={styles.metricLabel}>Success Rate</span>
                      <span className={styles.metricValue}>
                        {(final.real_success_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className={styles.metric}>
                      <span className={styles.metricLabel}>False Claims Made</span>
                      <span className={styles.metricValue}>
                        {final.false_claims_made}
                      </span>
                    </div>
                    <div className={styles.metric}>
                      <span className={styles.metricLabel}>False Claims Caught</span>
                      <span className={styles.metricValue}>
                        {final.false_claims_caught}
                      </span>
                    </div>
                    <div className={styles.metric}>
                      <span className={styles.metricLabel}>Protected</span>
                      <span className={styles.metricValue}>
                        {final.unsafe_blocked} / {final.unsafe_attempts}
                      </span>
                    </div>
                  </>
                )
              })()}
            </div>
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>📋 Task Details</h2>
        
        {results.runs.map((run) => (
          <details key={run.run_id} className={styles.details}>
            <summary className={styles.detailsSummary}>
              {run.run_id === 'baseline' 
                ? 'Baseline'
                : run.layer_added?.replace('_', ' ').toUpperCase()
              }
            </summary>
            
            <div className={styles.taskGrid}>
              {run.tasks.map(task => (
                <div 
                  key={task.task_id} 
                  className={styles.taskCard}
                  onClick={() => setSelectedTask(task.task_id)}
                  style={{cursor: 'pointer'}}
                >
                  <h4 className={styles.taskTitle}>{task.task_description}</h4>
                  <div className={styles.taskStatus}>
                  <span className={task.real_success ? styles.success : styles.failure}>
                    {task.real_success ? '✓' : '✗'} Real: {task.real_success ? 'Success' : 'Failed'}
                  </span>
                  <span className={task.agent_claimed_success ? styles.success : styles.failure}>
                    {task.agent_claimed_success ? '✓' : '✗'} Agent Claimed: {task.agent_claimed_success ? 'Success' : 'Failed'}
                  </span>
                  {task.false_claim_made && (
                    <span className={styles.warning}>
                      ⚠️ False Claim {task.false_claim_caught ? '(Caught by Verifier)' : '(Uncaught)'}
                    </span>
                  )}
                  </div>
                  <p className={styles.taskEvidence}>
                    {task.verification.evidence}
                  </p>
                  <p className={styles.taskMeta}>
                    {task.steps} steps | 🔍 Click to view trace
                  </p>
                </div>
              ))}
            </div>
          </details>
        ))}
      </section>

      <footer className={styles.footer}>
        <p>
          Generated {new Date(results.timestamp).toLocaleString()}
        </p>
      </footer>
    </>
  )}
  </main>
  )
}
