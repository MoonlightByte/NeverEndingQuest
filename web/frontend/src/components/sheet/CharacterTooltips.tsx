import { useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import './character-tooltips.css'

export interface SkillTooltipRow {
  name: string
  proficient: boolean
  bonus: number
}

export interface SkillTooltipProps {
  anchor: HTMLElement | null
  ability: string
  rows: SkillTooltipRow[]
}

function signed(value: number): string {
  return value >= 0 ? `+${value}` : String(value)
}

/** Legacy ability tooltip: vertically centered to the right, flipping left. */
export function SkillTooltip({ anchor, ability, rows }: SkillTooltipProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null)

  useLayoutEffect(() => {
    const tooltip = ref.current
    if (!anchor || !tooltip) return
    const target = anchor.getBoundingClientRect()
    const tip = tooltip.getBoundingClientRect()
    let top = target.top + target.height / 2 - tip.height / 2
    let left = target.right + 10
    if (left + tip.width > window.innerWidth) left = target.left - tip.width - 10
    if (top < 0) top = 10
    else if (top + tip.height > window.innerHeight) top = window.innerHeight - tip.height - 10
    setPosition({ top, left })
  }, [anchor, ability, rows])

  if (rows.length === 0) return null
  return createPortal(
    <div
      ref={ref}
      role="tooltip"
      className={`neq-skill-tooltip-parity${position ? ' visible' : ''}`}
      style={{ top: position?.top ?? 0, left: position?.left ?? 0 }}
    >
      <div className="neq-skill-tooltip-header-parity">{ability} Skills</div>
      {rows.map((row) => (
        <div key={row.name} className="neq-skill-tooltip-item-parity">
          <span className="neq-skill-tooltip-name-parity">
            {row.proficient ? '\u25CF' : '\u25CB'} {row.name}
          </span>
          <span className="neq-skill-tooltip-value-parity">{signed(row.bonus)}</span>
        </div>
      ))}
    </div>,
    document.body,
  )
}

export interface GenericFeatureTooltipProps {
  anchor: HTMLElement | null
  title: string
  content: string
}

/** Legacy generic feature tooltip: the spell-tooltip shell without metadata. */
export function GenericFeatureTooltip({ anchor, title, content }: GenericFeatureTooltipProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null)

  useLayoutEffect(() => {
    const tooltip = ref.current
    if (!anchor || !tooltip) return
    const target = anchor.getBoundingClientRect()
    const tip = tooltip.getBoundingClientRect()
    let top = target.top - tip.height - 8
    if (top < 8) top = target.bottom + 8
    let left = target.left + target.width / 2 - tip.width / 2
    if (left < 8) left = 8
    else if (left + tip.width > window.innerWidth - 8) left = window.innerWidth - tip.width - 8
    setPosition({ top, left })
  }, [anchor, title, content])

  return createPortal(
    <div
      ref={ref}
      role="tooltip"
      className={`neq-generic-tooltip-parity${position ? ' visible' : ''}`}
      style={{ top: position?.top ?? 0, left: position?.left ?? 0 }}
    >
      <div className="neq-generic-tooltip-header-parity">{title}</div>
      <div className="neq-generic-tooltip-description-parity">{content}</div>
    </div>,
    document.body,
  )
}
