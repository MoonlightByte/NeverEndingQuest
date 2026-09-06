import { useEffect, useRef, useState } from 'react'
import { useDialogs } from '../../stores'
import { useModalLayer } from './useModalLayer'

function BlockingOperation({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  useModalLayer(ref)
  return <div ref={ref} tabIndex={-1} className="neq-module-progress-parity fixed inset-0 z-[1000] overflow-y-auto bg-black/70 leading-[normal]" role="status" aria-live="polite">{children}</div>
}

export function ModuleProgressOverlay() {
  const operation = useDialogs((s) => s.moduleOperation)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (!operation) { setVisible(false); return undefined }
    setVisible(true)
    if (!operation.terminal) return undefined
    const timer = window.setTimeout(() => setVisible(false), 3000)
    return () => window.clearTimeout(timer)
  }, [operation])
  if (!operation || !visible) return null
  const failed = operation.terminal && operation.success === false
  return <BlockingOperation>
    <div className="relative mx-auto mt-[10%] min-h-[500px] w-4/5 max-w-[800px] overflow-hidden rounded-lg border-2 border-accent bg-[#2c2c2c] p-5">
      <video className="absolute inset-0 z-0 h-full w-full object-cover opacity-25" autoPlay={!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches} loop muted playsInline><source src="/static/media/videos/dwarf_smith_compressed.mp4" type="video/mp4" /></video>
      <div className="relative z-[1] p-[15px] text-center"><div className="inline-block rounded-lg bg-[rgba(44,44,44,.85)] px-[25px] py-3"><div className="text-[22px] font-bold text-accent">Aye! Forgin&apos; Yer Adventure - Won&apos;t Be But a Moment...</div></div></div>
      <div className="relative z-[1] flex min-h-[400px] flex-col justify-end p-[30px] text-center">
        <div className="mb-[15px]"><div className="neq-module-stage-parity mb-2 inline-block rounded-[5px] bg-[rgba(28,28,28,.75)] px-[15px] py-2 text-[#ffa500] [text-shadow:2px_2px_4px_rgba(0,0,0,.9)]"><span>{`Stage ${operation.stage} of ${operation.totalStages}`}</span></div><br /><div className="neq-module-stage-name-parity inline-block rounded-[5px] bg-[rgba(28,28,28,.75)] px-3 py-1.5 text-primary [text-shadow:2px_2px_4px_rgba(0,0,0,.9)]"><span style={failed ? { color: '#ff8a80' } : undefined}>{operation.stageName}</span></div></div>
        <div className="mx-auto my-5 h-[25px] w-4/5 overflow-hidden rounded border-2 border-accent bg-[rgba(44,44,44,.6)] shadow-[0_2px_10px_rgba(0,0,0,.5)]"><div className="neq-module-progress-bar-parity h-full shadow-[0_0_10px_rgba(76,175,80,.5)] transition-[width] duration-500" style={{ width: `${Math.max(0, Math.min(100, operation.percentage))}%`, ...(failed ? { background: 'linear-gradient(90deg, #b71c1c, #ef5350)' } : {}) }} /></div>
        <div><div className="neq-module-percentage-parity mb-[10px] inline-block rounded-[5px] bg-[rgba(28,28,28,.75)] px-5 py-2 text-accent [text-shadow:2px_2px_4px_rgba(0,0,0,.9)]"><span>{`${operation.percentage}%`}</span></div><br /><div className="neq-module-message-parity inline-block rounded-[5px] bg-[rgba(28,28,28,.7)] px-[15px] py-[5px] italic text-[#a0a0a0] [text-shadow:1px_1px_2px_rgba(0,0,0,.9)]" style={failed ? { color: '#ff8a80' } : undefined}><span>{operation.message}</span></div></div>
      </div>
    </div>
  </BlockingOperation>
}
