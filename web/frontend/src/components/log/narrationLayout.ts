/** Line patterns NarrationText lays out (#792). Plain prose matches none. */
const LIST_LINE = /^([ \t]*)([-*\u2022]|\d{1,2}[.)])[ \t]+(.*)$/
export const HEADING_LINE = /^#{1,6}[ \t]+(.+?)[ \t#]*$/
export const LABEL_LINE = /^[A-Z][A-Za-z0-9 &/,'()-]{0,40}:$/
const HAS_WORD = /[\p{L}\p{N}]/u

/** [indent, marker, item text] of a list line, or null. */
export function listMatch(line: string): RegExpExecArray | null {
  const match = LIST_LINE.exec(line)
  // "* * *" scene breaks and bare dashes are prose, not list items.
  return match && HAS_WORD.test(match[3] ?? '') ? match : null
}

/** True when the text uses list lines, headings or **bold**. */
export function hasNarrationStructure(text: string): boolean {
  if (/\*\*[^*\n]+?\*\*/.test(text)) return true
  return text.split('\n').some((line) => listMatch(line) !== null || HEADING_LINE.test(line))
}
