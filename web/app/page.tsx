'use client'

import { useState, useEffect } from 'react'
import styles from './page.module.css'

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
      false_claim: boolean
      steps: number
      verification: any
    }>
  }>
  summary: Record<string, {
    total_tasks: number
    real_success_count: number
    real_success_rate: number
    false_claims: number
    unsafe_attempts: number
    unsafe_blocked: number
  }>
}

export default function Home() {
  const [results, setResults] = useState<AblationResults | null>(null)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    // Try to load results from file
    fetch('/ablation_results.json')
      .then(res => res.json())
      .then(data => setResults(data))
      .catch(err => {
        setError('No results found. Run `harnessdiff ablate` first to generate data.')
      })
  }, [])

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
                    ✗ {summary.false_claims} false claims
                  </span>
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
                      <span className={styles.metricLabel}>False Claims</span>
                      <span className={styles.metricValue}>
                        {baseline.false_claims}
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
                      <span className={styles.metricLabel}>False Claims</span>
                      <span className={styles.metricValue}>
                        {final.false_claims}
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
                <div key={task.task_id} className={styles.taskCard}>
                  <h4 className={styles.taskTitle}>{task.task_description}</h4>
                  <div className={styles.taskStatus}>
                    <span className={task.real_success ? styles.success : styles.failure}>
                      {task.real_success ? '✓' : '✗'} Real: {task.real_success ? 'Success' : 'Failed'}
                    </span>
                    <span className={task.agent_claimed_success ? styles.success : styles.failure}>
                      {task.agent_claimed_success ? '✓' : '✗'} Agent Claimed: {task.agent_claimed_success ? 'Success' : 'Failed'}
                    </span>
                    {task.false_claim && (
                      <span className={styles.warning}>
                        ⚠️ False Claim
                      </span>
                    )}
                  </div>
                  <p className={styles.taskEvidence}>
                    {task.verification.evidence}
                  </p>
                  <p className={styles.taskMeta}>
                    {task.steps} steps
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
    </main>
  )
}
