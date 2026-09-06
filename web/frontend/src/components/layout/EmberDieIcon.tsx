const paths: Record<number, string> = {
  20: 'M12 2 22 8v10l-10 5L2 18V8Zm0 0L7 15l5 8 5-8ZM2 8l5 7h10l5-7M2 18l5-3m10 0 5 3',
  12: 'm12 2 9 6v10l-9 5-9-5V8Zm0 5 6 4-2 7H8l-2-7ZM12 2v5M3 8l3 3m15-3-3 3M3 18l5 0m13 0h-5m-4 5v-5',
  10: 'm12 2 10 11-10 10L2 13Zm0 0 3 11-3 10-3-10ZM2 13h20',
  8: 'm12 2 10 10-10 11L2 12Zm0 0v21M2 12l10-3 10 3',
  6: 'M4 3h16v18H4ZM8 7h.01M16 7h.01M8 12h.01M16 12h.01M8 17h.01M16 17h.01',
  4: 'm12 2 10 20H2Zm0 0v14M2 22l10-6 10 6',
}
export function EmberDieIcon({ sides, rolling }: { sides: number; rolling?: boolean }) {
  return <svg className={`ember-icon${rolling ? ' ember-die-rolling' : ''}`} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[sides]} /></svg>
}
