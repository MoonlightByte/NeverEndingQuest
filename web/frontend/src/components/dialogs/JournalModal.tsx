import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useWorld } from '../../stores'
import type { PlotData } from '../../stores'
import { DialogShell } from './DialogShell'

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
    <article className={`mt-4 ${completed ? 'opacity-70' : ''}`}>
      <h3 className="font-display text-base text-primary">{quest.title}</h3>
      <p className="mt-1 font-body text-sm text-secondary">{quest.description}</p>
      {sideQuests.map((sq) => (
        <div
          key={sq.title}
          className={`mt-2 border-l-2 border-card pl-3 ${sq.status === 'completed' ? 'opacity-70' : ''}`}
        >
          <h4 className="font-display text-sm text-primary">{sq.title}</h4>
          <p className="mt-0.5 font-body text-sm text-secondary">{sq.description}</p>
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
    <section aria-label={heading} className="min-h-0 overflow-y-auto p-4">
      <h2 className="border-b-2 border-card pb-2 font-display text-xl text-accent">{heading}</h2>
      {quests.length === 0 ? (
        <p className="mt-4 font-body text-sm italic text-secondary">{emptyText}</p>
      ) : (
        quests.map((quest) => <QuestItem key={quest.id} quest={quest} />)
      )}
    </section>
  )
}

function JournalModalBody() {
  const closeDialog = useDialogs((s) => s.closeDialog)
  const plot = useWorld((s) => s.plot)
  const plotError = useWorld((s) => s.plotError)

  // Ask for the latest quest data every time the journal opens.
  useEffect(() => {
    emitC('request_plot_data', undefined)
  }, [])

  // The player only sees quests they have discovered.
  const discovered = (plot?.plotPoints ?? []).filter((q) => q.status !== 'not started')
  const activeQuests = discovered.filter((q) => q.status !== 'completed')
  const completedQuests = discovered.filter((q) => q.status === 'completed')

  return (
    <DialogShell title="Adventure Journal" onClose={closeDialog} maxWidth="64rem">
      {plotError ? (
        <p className="p-6 text-center font-body text-secondary">Could not load quest data.</p>
      ) : plot === null ? (
        <p className="p-6 text-center font-body italic text-secondary">
          Consulting the chronicle...
        </p>
      ) : (
        <div className="grid max-h-[65vh] grid-rows-2 md:grid-rows-1 md:grid-cols-2">
          <div className="border-b-2 border-card md:border-b-0 md:border-r-2">
            <JournalPage
              heading="Current Objectives"
              quests={activeQuests}
              emptyText="No active quests. Explore the world to discover new objectives."
            />
          </div>
          <JournalPage
            heading="A Chronicle of Deeds"
            quests={completedQuests}
            emptyText="No completed quests yet. Your deeds await their telling."
          />
        </div>
      )}
    </DialogShell>
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
