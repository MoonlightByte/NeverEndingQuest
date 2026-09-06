type IconName = 'person' | 'people' | 'menu' | 'exit' | 'book' | 'bug' | 'dice' | 'image' | 'sound' | 'send' | 'clear' | 'shield' | 'heart' | 'boot'

const paths: Record<IconName, string> = {
  person: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM3 22v-3c0-4 4-6 9-6s9 2 9 6v3',
  people: 'M14 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM3 21v-5c0-3 3-5 8-5s8 2 8 5v5M18 3a3 3 0 0 1 0 6m2 3c2 1 3 2 3 5v4',
  menu: 'M3 4h3v3H3ZM10 5h11M3 11h3v3H3ZM10 12h11M3 18h3v3H3ZM10 19h11',
  exit: 'M14 4H4v16h10M11 12h11m-4-4 4 4-4 4',
  book: 'M12 5C8 2 3 3 1 4v16c4-2 8-1 11 1 3-2 7-3 11-1V4c-3-1-7-2-11 1Zm0 0v16',
  bug: 'M8 7h8v10a4 4 0 0 1-8 0ZM9 7V4h6v3M3 9l5 2m8 0 5-2M2 15h6m8 0h6M4 22l5-3m6 0 5 3M12 8v12',
  dice: 'M12 2 22 8v10l-10 5L2 18V8Zm0 0L7 15l5 8 5-8ZM2 8l5 7h10l5-7M2 18l5-3m10 0 5 3',
  image: 'M3 3h18v18H3ZM3 17l6-7 5 5 3-4 4 6M17 7h.01',
  sound: 'M3 9h5l6-5v16l-6-5H3Zm14-2c3 3 3 7 0 10m3-13c5 5 5 11 0 16',
  send: 'M4 3h16v15H9l-5 4ZM8 8h1m3 0h1m3 0h1M8 12h8',
  clear: 'M4 9a9 9 0 1 1 0 7M4 3v6h6',
  shield: 'M12 2 21 6v7c0 5-5 8-9 10-4-2-9-5-9-10V6ZM9 9h6v7H9Z',
  heart: 'M12 21 3 12C-3 5 6-1 12 6c6-7 15-1 9 6Z',
  boot: 'M9 2h8v11l4 4v4H3v-5l6-3ZM9 6h8',
}

export function EmberIcon({ name, className = '' }: { name: IconName; className?: string }) {
  return <svg className={`ember-icon ${className}`} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
