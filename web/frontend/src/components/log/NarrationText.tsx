/**
 * NarrationText -- minimal line-based layout for Dungeon Master text (#792).
 *
 * Plain prose (the usual narration) is returned as the original string, so
 * its rendering is unchanged. Only text that carries structure gets a light
 * layout: lines starting with "- ", "* ", "\u2022 " or "1." become hanging-indent
 * list items, a short "Label:" line or "## Label" line becomes a bold label,
 * and **bold** spans become <strong>. Everything is rendered as React text
 * children -- never as HTML -- so model text cannot inject markup.
 */
import type { ReactNode } from 'react'
import { HEADING_LINE, LABEL_LINE, hasNarrationStructure, listMatch } from './narrationLayout'

const BOLD = /\*\*([^*\n]+?)\*\*/g
const MARKER_WIDTH = '1.6em'

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let index = 0
  for (const match of text.matchAll(BOLD)) {
    const start = match.index ?? 0
    if (start > last) out.push(text.slice(last, start))
    out.push(<strong key={`b${index++}`}>{match[1]}</strong>)
    last = start + match[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

function renderLine(line: string, key: number): ReactNode {
  const list = listMatch(line)
  if (list) {
    const nested = (list[1] ?? '').replace(/\t/g, '  ').length >= 2
    const marker = /\d/.test(list[2] ?? '') ? list[2] : '\u2022'
    return (
      <span
        key={key}
        className="neq-narration-item"
        style={{
          display: 'block',
          paddingLeft: nested ? `calc(${MARKER_WIDTH} * 2)` : MARKER_WIDTH,
          textIndent: `-${MARKER_WIDTH}`,
        }}
      >
        <span style={{ display: 'inline-block', minWidth: MARKER_WIDTH, textIndent: 0 }}>{`${marker} `}</span>
        {inline(list[3] ?? '')}
      </span>
    )
  }
  const heading = HEADING_LINE.exec(line)
  if (heading || LABEL_LINE.test(line.trim())) {
    return (
      <span key={key} className="neq-narration-label" style={{ display: 'block' }}>
        <strong>{inline(heading ? heading[1] ?? '' : line.trim())}</strong>
      </span>
    )
  }
  return (
    <span key={key} style={{ display: 'block' }}>
      {line.trim() === '' ? '\u00a0' : inline(line)}
    </span>
  )
}

export function NarrationText({ text }: { text: string }): ReactNode {
  if (!hasNarrationStructure(text)) return text
  return text.split('\n').map(renderLine)
}
