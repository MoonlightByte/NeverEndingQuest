import type { MenuPrompt } from '../../contract/events'
import { emitC } from '../../services/socket'
import { useComposerGating } from '../../modes/useComposerGating'
import { useMenuPrompt } from '../../stores/menuPrompt'
import './rules-roll.css'
import './menu-panel.css'

/** #1129: a closed menu's options above the input, which stays: typing answers the menu as before. */
export function MenuPanel({ prompt }: { prompt: MenuPrompt }) {
  const gating = useComposerGating()
  const locked = !gating.canSend || prompt.submitted
  const choose = (number: number) => {
    useMenuPrompt.getState().markAnswered()
    emitC('submit_menu_choice', { id: prompt.id, number })
  }
  return <section className="neq-rules-roll neq-menu-panel" aria-label={prompt.title}>
    <div className="neq-rules-roll-title"><strong>{prompt.title}</strong></div>
    <div className="neq-menu-options">
      {prompt.options.map((option) => <button key={option.number} type="button" disabled={locked || option.disabled} onClick={() => choose(option.number)}>
        <span>{option.number}. {option.label}</span>
        {option.detail && <small>{option.detail}</small>}
      </button>)}
    </div>
  </section>
}
