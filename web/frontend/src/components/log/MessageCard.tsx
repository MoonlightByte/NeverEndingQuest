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

export interface MessageCardProps {
  message: GameMessage
  /** Generated images attached to this narration (matched by prompt). */
  images?: GeneratedImage[] | undefined
}

function InlineImages({ images }: { images: GeneratedImage[] }) {
  if (images.length === 0) return null
  return (
    <div className="mt-3 flex flex-col gap-2">
      {images.map((image, index) => (
        <img
          key={`${image.image_url}-${index}`}
          src={image.image_url}
          alt={`Generated scene: ${image.prompt.slice(0, 80)}`}
          className="max-w-full rounded-lg border-2 border-card"
        />
      ))}
    </div>
  )
}

export function MessageCard({ message, images = [] }: MessageCardProps) {
  switch (message.type) {
    case 'narration':
      return (
        <div className="my-5 flex items-start gap-3" data-message-type="narration">
          <div
            className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full font-display text-sm font-bold text-white"
            style={{ backgroundColor: '#8b4513' }}
            aria-hidden="true"
          >
            DM
          </div>
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex items-center gap-2">
              <span className="font-display text-base font-bold" style={{ color: '#ffb347' }}>
                Dungeon Master
              </span>
              <span
                className="inline-flex h-[22px] items-center rounded px-1.5 font-chrome text-[11px] font-bold text-white"
                style={{ backgroundColor: '#4a90e2' }}
              >
                DM
              </span>
              <TtsButton content={message.content} />
              <GenerateImageButton content={message.content} />
            </div>
            <div
              className="whitespace-pre-wrap font-log text-[17px] leading-snug"
              style={{ color: '#ffa500' }}
            >
              {message.content}
            </div>
            <InlineImages images={images} />
          </div>
        </div>
      )

    case 'user-input':
      return (
        <div
          className="my-5 flex flex-row-reverse items-start gap-3"
          data-message-type="user-input"
        >
          <div
            className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full font-log text-xl text-white"
            style={{ backgroundColor: '#4a90e2' }}
            aria-hidden="true"
          >
            {'>'}
          </div>
          <div className="flex min-w-0 flex-1 flex-col items-end">
            <div className="mb-1">
              <span className="font-chrome text-base font-bold" style={{ color: '#4a90e2' }}>
                You
              </span>
            </div>
            <div
              className="whitespace-pre-wrap text-right font-log text-[17px] leading-snug"
              style={{ color: '#e8e8e8' }}
            >
              {message.content}
            </div>
          </div>
        </div>
      )

    case 'error':
      return (
        <div className="my-4 flex justify-center" data-message-type="error">
          <div
            className="max-w-[500px] rounded-lg border px-3 py-2 text-center"
            style={{ backgroundColor: '#5a2d2d', borderColor: '#8b3333' }}
          >
            <div
              className="whitespace-pre-wrap font-log text-[13px]"
              style={{ color: '#ffaaaa' }}
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
    case 'startup':
      return (
        <div className="my-4 flex justify-center" data-message-type={message.type}>
          <div
            className="max-w-[500px] rounded-lg border px-3 py-2 text-center"
            style={{ backgroundColor: '#2a2a2a', borderColor: '#444' }}
          >
            <div className="whitespace-pre-wrap font-log text-[13px] italic text-secondary">
              {message.content}
            </div>
          </div>
        </div>
      )
  }
}
