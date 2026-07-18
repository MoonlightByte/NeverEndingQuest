import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useWorld } from '../../stores'
import type { PlotData } from '../../stores'
import { useId, useRef } from 'react'

type PlotPoint = PlotData['plotPoints'][number]

interface SideQuest {
  title: string
  description: string
  status: string
}

function toSideQuests(raw: unknown[] | undefined): SideQuest[] {
  if (!raw) return []
  return raw.flatMap((sq) => {
    if (typeof sq !== 'object' || sq === null) return []
    const r = sq as Record<string, unknown>
    return [
      {
        title: typeof r['title'] === 'string' ? r['title'] : 'Unknown quest',
        description: typeof r['description'] === 'string' ? r['description'] : '',
        status: typeof r['status'] === 'string' ? r['status'] : 'unknown',
      },
    ]
  })
}

function QuestItem({ quest }: { quest: PlotPoint }) {
  const completed = quest.status === 'completed'
  // Only show side quests the player has discovered.
  const sideQuests = toSideQuests(quest.sideQuests).filter((sq) => sq.status !== 'not started')
  return (
    <article className={`neq-journal-quest ${completed ? 'completed' : ''}`}>
      <h3 className="neq-journal-quest-title">{quest.title}</h3>
      <p className="neq-journal-description">{quest.description}</p>
      {sideQuests.map((sq) => (
        <div
          key={sq.title}
          className={`neq-journal-quest neq-journal-side-quest ${sq.status === 'completed' ? 'completed' : ''}`}
        >
          <h4 className="neq-journal-quest-title">{sq.title}</h4>
          <p className="neq-journal-description">{sq.description}</p>
        </div>
      ))}
    </article>
  )
}

function JournalPage({
  heading,
  quests,
  emptyText,
}: {
  heading: string
  quests: PlotPoint[]
  emptyText: string
}) {
  return (
    <section aria-label={heading} className="neq-journal-page">
      <div className="neq-journal-page-content">
      <h2>{heading}</h2>
      {quests.length === 0 ? (
        <p className="neq-journal-empty">{emptyText}</p>
      ) : (
        quests.map((quest) => <QuestItem key={quest.id} quest={quest} />)
      )}
      </div>
    </section>
  )
}

function JournalModalBody() {
  const closeDialog = useDialogs((s) => s.closeDialog)
  const plot = useWorld((s) => s.plot)
  const plotError = useWorld((s) => s.plotError)
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)

  // Ask for the latest quest data every time the journal opens.
  useEffect(() => {
    emitC('request_plot_data', undefined)
  }, [])

  // The player only sees quests they have discovered.
  const discovered = (plot?.plotPoints ?? []).filter((q) => q.status !== 'not started')
  const activeQuests = discovered.filter((q) => q.status !== 'completed')
  const completedQuests = discovered.filter((q) => q.status === 'completed')

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    dialogRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeDialog()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      previousFocus?.focus()
    }
  }, [closeDialog])

  return (
    <div
      className="neq-journal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) closeDialog()
      }}
    >
      <h1 id={titleId} className="sr-only">Adventure Journal</h1>
      <button type="button" className="neq-journal-close" onClick={closeDialog} aria-label="Close">×</button>
      <div ref={dialogRef} className="neq-journal-book" tabIndex={-1}>
      {plotError ? (
        <div className="neq-journal-page"><p className="neq-journal-empty">Could not load quest data.</p></div>
      ) : plot === null ? (
        <div className="neq-journal-page"><p className="neq-journal-empty">
          Consulting the chronicle...
        </p></div>
      ) : (
        <>
          <JournalPage
            heading="Current Objectives"
            quests={activeQuests}
            emptyText="No active quests. Explore the world to discover new objectives."
          />
          <JournalPage
            heading="A Chronicle of Deeds"
            quests={completedQuests}
            emptyText="No completed quests yet. Your deeds await their telling."
          />
        </>
      )}
      </div>
    </div>
  )
}

/**
 * Quest journal: two-page book layout fed by plot_data_response -- left page
 * lists active quests, right page the completed ones (plan 4.4e).
 */
export function JournalModal() {
  const open = useDialogs((s) => s.open)
  if (open !== 'journal') return null
  return <JournalModalBody />
}
