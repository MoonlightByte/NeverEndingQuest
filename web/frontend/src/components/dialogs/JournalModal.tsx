import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useWorld } from '../../stores'
import type { PlotData } from '../../stores'
import { useId, useRef } from 'react'
import './dialog-parity.css'
import { DialogShell } from './DialogShell'
import { useEmberViewport } from '../layout/useEmberViewport'

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
}: {
  heading: string
  quests: PlotPoint[]
}) {
  return (
    <section aria-label={heading} className="neq-journal-page">
      <div className="neq-journal-page-content">
      <h2>{heading}</h2>
      {quests.map((quest) => <QuestItem key={quest.id} quest={quest} />)}
      </div>
    </section>
  )
}

function BlankJournalPages({ error = false }: { error?: boolean }) {
  return (
    <>
      <section className="neq-journal-page">
        <div className="neq-journal-page-content">
          {error && (
            <>
              <h2>Journal</h2>
              <p>Could not load quest data.</p>
            </>
          )}
        </div>
      </section>
      <section className="neq-journal-page">
        <div className="neq-journal-page-content" />
      </section>
    </>
  )
}

function JournalModalBody() {
  const ember = useEmberViewport()
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
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) closeDialog()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      previousFocus?.focus()
    }
  }, [closeDialog])

  const pages = plotError ? <p role="alert">Could not load quest data. Close and reopen the journal to retry.</p> : plot === null ? <p role="status">Fetching your journal…</p> : discovered.length === 0 ? <p>No discovered quests have been recorded yet.</p> : <><JournalPage heading="Current Objectives" quests={activeQuests} /><JournalPage heading="A Chronicle of Deeds" quests={completedQuests} /></>
  if (ember) return <DialogShell title="Adventure Journal" onClose={closeDialog} maxWidth="1100px"><div className="neq-journal-book">{pages}</div></DialogShell>
  return (
    <div
      className="neq-journal-overlay neq-journal-overlay-parity"
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
        <BlankJournalPages error />
      ) : plot === null ? (
        <BlankJournalPages />
      ) : (
        <>
          <JournalPage
            heading="Current Objectives"
            quests={activeQuests}
          />
          <JournalPage
            heading="A Chronicle of Deeds"
            quests={completedQuests}
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
