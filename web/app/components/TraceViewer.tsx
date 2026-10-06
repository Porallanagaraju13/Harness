'use client'

import { useState } from 'react'
import styles from './viewer.module.css'

interface Step {
  step_num: number
  timestamp: number
  messages: Array<{role: string, content: string}>
  action?: {type: string, calls?: any[], content?: string}
  observation?: string
}

interface TraceData {
  type: string
  task_id?: string
  step_num?: number
  timestamp?: number
  messages?: any[]
  action?: any
  observation?: string
  result?: any
}

interface TraceViewerProps {
  taskId: string
  baselineTrace: TraceData[]
  fullTrace: TraceData[]
  taskDescription: string
}

export default function TraceViewer({ taskId, baselineTrace, fullTrace, taskDescription }: TraceViewerProps) {
  const [selectedStep, setSelectedStep] = useState<number | null>(null)
  
  // Parse traces
  const baselineSteps = baselineTrace.filter(t => t.type === 'step') as Step[]
  const fullSteps = fullTrace.filter(t => t.type === 'step') as Step[]
  
  const baselineResult = baselineTrace.find(t => t.type === 'trace_end')?.result
  const fullResult = fullTrace.find(t => t.type === 'trace_end')?.result
  
  // Find failure point in baseline
  const failureStep = baselineSteps.length - 1 // Usually the last step shows the issue
  
  return (
    <div className={styles.viewer}>
      <div className={styles.header}>
        <h3 className={styles.title}>📊 Trace Comparison: {taskId}</h3>
        <p className={styles.desc}>{taskDescription}</p>
      </div>
      
      <div className={styles.results}>
        <div className={styles.resultBox}>
          <h4>❌ Baseline (No Harness)</h4>
          <p>Status: {baselineResult?.status}</p>
          <p>Steps: {baselineResult?.steps}</p>
          <p>Tool Calls: {baselineResult?.tool_calls}</p>
        </div>
        <div className={styles.resultBox}>
          <h4>✅ Full Harness</h4>
          <p>Status: {fullResult?.status}</p>
          <p>Steps: {fullResult?.steps}</p>
          <p>Tool Calls: {fullResult?.tool_calls}</p>
        </div>
      </div>
      
      <div className={styles.traces}>
        <div className={styles.traceColumn}>
          <h4 className={styles.columnTitle}>Baseline Trace</h4>
          {baselineSteps.map((step, idx) => (
            <div 
              key={idx}
              className={`${styles.step} ${idx === failureStep ? styles.failure : ''}`}
              onClick={() => setSelectedStep(idx)}
            >
              <div className={styles.stepHeader}>
                <span className={styles.stepNum}>Step {step.step_num}</span>
                {idx === failureStep && <span className={styles.badge}>⚠️ Issue Here</span>}
              </div>
              
              {step.action?.type === 'tool_calls' && step.action.calls && (
                <div className={styles.action}>
                  <strong>Tool:</strong> {step.action.calls[0]?.function?.name || 'unknown'}
                </div>
              )}
              
              {step.action?.type === 'final_answer' && (
                <div className={styles.action}>
                  <strong>Final:</strong> {step.action.content?.substring(0, 50)}...
                </div>
              )}
              
              {step.observation && (
                <div className={styles.observation}>
                  <strong>Result:</strong> {step.observation.substring(0, 60)}...
                </div>
              )}
            </div>
          ))}
        </div>
        
        <div className={styles.traceColumn}>
          <h4 className={styles.columnTitle}>With Full Harness</h4>
          {fullSteps.map((step, idx) => {
            const hasIntervention = step.observation?.includes('Permission denied') || 
                                   step.observation?.includes('retries') ||
                                   step.observation?.includes('Skipped') ||
                                   step.observation?.includes('verification')
            
            return (
              <div 
                key={idx}
                className={`${styles.step} ${hasIntervention ? styles.intervention : ''}`}
                onClick={() => setSelectedStep(idx)}
              >
                <div className={styles.stepHeader}>
                  <span className={styles.stepNum}>Step {step.step_num}</span>
                  {hasIntervention && (
                    <span className={styles.badge}>
                      🛡️ Layer Active
                    </span>
                  )}
                </div>
                
                {step.action?.type === 'tool_calls' && step.action.calls && (
                  <div className={styles.action}>
                    <strong>Tool:</strong> {step.action.calls[0]?.function?.name || 'unknown'}
                  </div>
                )}
                
                {step.action?.type === 'final_answer' && (
                  <div className={styles.action}>
                    <strong>Final:</strong> {step.action.content?.substring(0, 50)}...
                  </div>
                )}
                
                {step.observation && (
                  <div className={styles.observation}>
                    <strong>Result:</strong> {step.observation.substring(0, 80)}
                    {step.observation.length > 80 ? '...' : ''}
                  </div>
                )}
                
                {hasIntervention && (
                  <div className={styles.layerNote}>
                    {step.observation?.includes('Permission denied') && '🔒 Permissions Layer'}
                    {step.observation?.includes('retries') && '🔄 Retry Layer'}
                    {step.observation?.includes('Skipped') && '🔑 Idempotency'}
                    {step.observation?.includes('verification') && '✓ Verification'}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
