/**
 * MessageCard -- one typed entry in the game log (plan Task 4.4b).
 * Renders per game_output type: narration gets the DM treatment (avatar,
 * Cinzel author header, TTS + Generate Image controls, inline generated
 * images), user-input is right-aligned, info/startup and error render as
 * centered system cards. Content is plain text (pre-wrap) -- no HTML
 * injection. Legacy palette preserved: DM text #ffa500, author #ffb347,
 * player accent #4a90e2 (game_interface.html .message styles).
 */
import type { GameMessage } from '../../contract/events'
import type { GeneratedImage } from '../../stores'
import { TtsButton } from './TtsButton'
import { GenerateImageButton } from './GenerateImageButton'
import { useSettings } from '../../stores'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberIcon } from '../layout/EmberIcon'
import { useState } from 'react'

export interface MessageCardProps {
  message: GameMessage
  /** Generated images attached to this narration (matched by prompt). */
  images?: GeneratedImage[] | undefined
}

function EmberSceneImage({ image }: { image: GeneratedImage }) {
  const [failed, setFailed] = useState(false)
  return failed ? <div className="ember-image-error" role="status">Scene image unavailable. <button type="button" onClick={() => setFailed(false)}>Retry image</button></div> : <img src={image.image_url} alt={`Generated scene: ${image.prompt.slice(0, 80)}`} onError={() => setFailed(true)} />
}

function InlineImages({ images }: { images: GeneratedImage[] }) {
  const ember = useEmberDesktop()
  if (images.length === 0) return null
  return (
    <div className="neq-inline-images mt-3 flex flex-col gap-2">
      {images.map((image, index) => ember ? <EmberSceneImage key={`${image.image_url}-${index}`} image={image} /> : (
        <img
          key={`${image.image_url}-${index}`}
          src={image.image_url}
          alt={`Generated scene: ${image.prompt.slice(0, 80)}`}
          className="max-w-full rounded-lg border-2 border-card"
        />
      ))}
      {ember && <span className="ember-image-caption">Generated image · attached to this message</span>}
    </div>
  )
}

export function MessageCard({ message, images = [] }: MessageCardProps) {
  const ember = useEmberDesktop()
  const aiImages = useSettings((s) => s.aiImages)
  const autoplay = useSettings((s) => s.autoplay)
  // A presentation split only: the original complete text still goes to voice
  // and image generation. Mobile retains the existing append-only placement.
  const paragraphEnd = ember && images.length ? /\n\s*\n/.exec(message.content) : null
  const splitAt = paragraphEnd ? paragraphEnd.index + paragraphEnd[0].length : message.content.length
  switch (message.type) {
    case 'narration':
      return (
        <div className="neq-message neq-message-narration my-5 flex items-start gap-3" data-message-type="narration">
          <div className="neq-message-avatar h-10 w-10 flex-shrink-0 overflow-hidden rounded-full" aria-hidden="true">
            <img src="/static/dm_logo.png" alt="" className="h-full w-full object-cover" />
          </div>
          <div className="neq-message-content min-w-0 flex-1">
            <div className="neq-message-header mb-1 flex items-center gap-2">
              <span className="neq-message-author text-base font-bold" style={{ color: '#ffb347' }}>
                Dungeon Master
              </span>
              {!ember && <span
                className="inline-flex h-[22px] items-center rounded px-1.5 font-chrome text-[11px] font-bold text-white"
                style={{ backgroundColor: '#4a90e2' }}
              >
                DM
              </span>}
              <TtsButton content={message.content} autoplay={autoplay} />
              {aiImages && <GenerateImageButton content={message.content} messageId={message.message_id} />}
            </div>
            <div
              className="neq-message-text whitespace-pre-wrap font-log text-[17px] leading-snug"
              style={{ color: '#ffa500' }}
            >
              {message.content.slice(0, paragraphEnd?.index ?? splitAt)}
            </div>
            <InlineImages images={images} />
            {splitAt < message.content.length && <div className="neq-message-text ember-narration-continuation whitespace-pre-wrap">{message.content.slice(splitAt)}</div>}
          </div>
        </div>
      )

    case 'user-input':
      return (
        <div className="neq-message neq-message-user my-5 flex items-start gap-3" data-message-type="user-input">
          <div
            className="neq-message-avatar flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full font-log text-xl text-white"
            style={{ backgroundColor: '#4a90e2' }}
            aria-hidden="true"
          >
            {ember ? <EmberIcon name="person" /> : '⚔️'}
          </div>
          <div className="neq-message-content min-w-0 flex-1">
            <div className="neq-message-header mb-1">
              <span className="neq-message-author font-chrome text-base font-bold" style={{ color: '#4a90e2' }}>
                You
              </span>
            </div>
            <div
              className="neq-message-text whitespace-pre-wrap font-log text-[17px] leading-snug"
              style={{ color: '#e8e8e8' }}
            >
              {message.content}
            </div>
          </div>
        </div>
      )

    case 'error':
      return (
        <div className="my-[20px] flex justify-center" data-message-type="error">
          <div
            className="w-full min-w-0 max-w-[500px] flex-1 rounded-lg border px-3 py-2 text-center"
            style={{ backgroundColor: '#5a2d2d', borderColor: '#8b3333' }}
          >
            <div
              className="whitespace-pre-wrap font-log text-[13px]"
              style={{ color: '#ffaaaa', lineHeight: 1.4 }}
            >
              {message.content}
            </div>
          </div>
        </div>
      )

    case 'debug':
      return (
        <div className="my-1 font-log text-xs text-secondary" data-message-type="debug">
          {message.timestamp ? `[${message.timestamp}] ` : ''}
          {message.content}
        </div>
      )

    case 'info':
    case 'system':
    case 'startup':
      return (
        <div className="my-[20px] flex justify-center" data-message-type={message.type}>
          <div
            className="w-full min-w-0 max-w-[500px] flex-1 rounded-lg border px-3 py-2 text-center"
            style={{ backgroundColor: '#2a2a2a', borderColor: '#444' }}
          >
            <div className="whitespace-pre-wrap font-log text-[13px] italic text-secondary" style={{ lineHeight: 1.4 }}>
              {message.content}
            </div>
          </div>
        </div>
      )
  }
}
