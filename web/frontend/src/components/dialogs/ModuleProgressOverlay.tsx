import { useEffect, useState } from 'react'
import { useDialogs } from '../../stores'

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
  return <div className="fixed inset-0 z-[1000] bg-black/70 font-chrome leading-[normal]" role="status" aria-live="polite">
    <div className="relative mx-auto mt-[10%] min-h-[500px] w-4/5 max-w-[800px] overflow-hidden rounded-lg border-2 border-accent bg-[#2c2c2c] p-5">
      <video className="absolute inset-0 z-0 h-full w-full object-cover opacity-25" autoPlay loop muted playsInline><source src="/static/media/videos/dwarf_smith_compressed.mp4" type="video/mp4" /></video>
      <div className="relative z-[1] p-[15px] text-center"><div className="inline-block rounded-lg bg-[rgba(44,44,44,.85)] px-[25px] py-3"><div className="text-[22px] font-bold text-accent">Aye! Forgin&apos; Yer Adventure - Won&apos;t Be But a Moment...</div></div></div>
      <div className="relative z-[1] flex min-h-[400px] flex-col justify-end p-[30px] text-center">
        <div className="mb-[15px]"><div className="mb-2 inline-block rounded bg-[rgba(28,28,28,.75)] px-[15px] py-2 text-lg text-[#ffa500] [text-shadow:2px_2px_4px_rgba(0,0,0,.9)]">Stage {operation.stage} of {operation.totalStages}</div><br /><div className="inline-block rounded bg-[rgba(28,28,28,.75)] px-3 py-1.5 text-base font-bold text-primary [text-shadow:2px_2px_4px_rgba(0,0,0,.9)]">{operation.stageName}</div></div>
        <div className="mx-auto my-5 h-[25px] w-4/5 overflow-hidden rounded border-2 border-accent bg-[rgba(44,44,44,.6)] shadow-[0_2px_10px_rgba(0,0,0,.5)]"><div className="h-full bg-gradient-to-r from-[#4CAF50] to-[#66BB6A] shadow-[0_0_10px_rgba(76,175,80,.5)] transition-[width] duration-500" style={{ width: `${Math.max(0, Math.min(100, operation.percentage))}%` }} /></div>
        <div><div className="mb-[10px] inline-block rounded bg-[rgba(28,28,28,.75)] px-5 py-2 text-[28px] font-bold text-accent [text-shadow:2px_2px_4px_rgba(0,0,0,.9)]">{operation.percentage}%</div><br /><div className="inline-block rounded bg-[rgba(28,28,28,.7)] px-[15px] py-[5px] text-sm italic text-[#a0a0a0] [text-shadow:1px_1px_2px_rgba(0,0,0,.9)]">{operation.message}</div></div>
      </div>
    </div>
  </div>
}
