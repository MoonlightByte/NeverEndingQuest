/** Serialize one image URL as a CSS string, never as additional CSS syntax.
 * React escapes HTML attributes, but backgroundImage is parsed as CSS too.
 * Hex escapes with a terminating space preserve quotes, slashes and controls
 * without letting filenames close url() or append another image layer.
 */
export function cssImageUrl(url: string): string {
  return `url("${url.replace(/["\\\u0000-\u001f\u007f]/g,
    char => `\\${char.charCodeAt(0).toString(16)} `)}")`
}
