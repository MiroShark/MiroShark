/**
 * Chart export utility — rasterises an inline SVG element to a canvas with a
 * MiroShark watermark strip at the bottom, then offers download and clipboard
 * variants. Used by PolymarketChart, BeliefDriftChart, WhatIfPanel, and
 * InteractionNetwork so exported images share the same provenance footer.
 */

const FOOTER_HEIGHT = 86
const BACKGROUND = '#110a26'
const LOGO_URL = '/miroshark-nobg.png'

// Cache the loaded logo so exports after the first don't re-fetch.
let _logoImagePromise = null
function _loadLogo() {
  if (_logoImagePromise) return _logoImagePromise
  _logoImagePromise = new Promise((resolve) => {
    const img = new Image()
    // Same-origin asset; crossOrigin not required. If loading fails (e.g.,
    // served from a different host without CORS) we resolve with null and
    // fall back to the accent squares.
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = LOGO_URL
  })
  return _logoImagePromise
}

/**
 * Build a drawHeader callback that renders a Young Serif title (wrapped) and
 * an optional Space Mono subtitle underneath. Returns `{ drawHeader, headerHeight }`
 * — wire both into `renderSvgToCanvas` so the header auto-sizes to its content.
 */
export function buildTitledHeader({ title, subtitle = '', width }) {
  const PX = 32
  const TITLE_LH = 44
  const TITLE_FONT = '700 36px "Young Serif", Georgia, serif'
  const SUBTITLE_FONT = '400 13px "Space Mono", "JetBrains Mono", ui-monospace, monospace'

  // Pre-measure title to size the header
  const measureCanvas = document.createElement('canvas')
  const measureCtx = measureCanvas.getContext('2d')
  measureCtx.font = TITLE_FONT
  const titleLines = wrapText(measureCtx, title || '', width - PX * 2)
  const titleBlock = titleLines.length * TITLE_LH
  const headerHeight =
    32 /* top pad */ +
    titleBlock +
    (subtitle ? 8 + 20 : 0) /* subtitle gap + line */ +
    24 /* bottom pad */

  const drawHeader = (ctx) => {
    let y = 32
    ctx.fillStyle = '#f4f1ff'
    ctx.font = TITLE_FONT
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    for (const line of titleLines) {
      ctx.fillText(line, PX, y)
      y += TITLE_LH
    }
    if (subtitle) {
      y += 8
      ctx.fillStyle = 'rgba(244, 241, 255, 0.5)'
      ctx.font = SUBTITLE_FONT
      ctx.fillText(subtitle, PX, y)
    }
  }

  return { drawHeader, headerHeight }
}

/**
 * Word-wrap a string so each line fits within `maxWidth` at the ctx's
 * current font. Returns an array of lines.
 */
export function wrapText(ctx, text, maxWidth) {
  const words = String(text || '').split(/\s+/).filter(Boolean)
  const lines = []
  let current = ''
  for (const word of words) {
    const test = current ? `${current} ${word}` : word
    if (ctx.measureText(test).width > maxWidth && current) {
      lines.push(current)
      current = word
    } else {
      current = test
    }
  }
  if (current) lines.push(current)
  return lines
}

/**
 * Ensure web fonts are available to canvas text rendering before we draw.
 * Without this, the first export after page load will silently fall back to
 * the system default because the font face hasn't been parsed yet.
 */
async function _ensureFontsReady() {
  try {
    if (document.fonts?.ready) await document.fonts.ready
    if (document.fonts?.load) {
      await Promise.all([
        document.fonts.load('700 42px "Young Serif"'),
        document.fonts.load('700 24px "Space Mono"'),
        document.fonts.load('400 13px "Space Mono"'),
      ])
    }
  } catch (_) {
    // Non-fatal — the export will just use fallback fonts.
  }
}

/**
 * Render the given <svg> element (already mounted in the DOM) to a canvas at
 * the specified logical width/height, with an optional titled header above
 * the chart and a MiroShark provenance footer below.
 *
 * @param {SVGElement} svgEl
 * @param {object} options
 * @param {number} options.width  — logical width of the SVG viewBox (before scale)
 * @param {number} options.height — logical height of the SVG viewBox
 * @param {number} [options.scale=2] — HiDPI multiplier for the output canvas
 * @param {number} [options.headerHeight=0] — pixels reserved above the SVG
 * @param {(ctx:CanvasRenderingContext2D, meta:{width:number, headerHeight:number}) => void} [options.drawHeader]
 *        — callback that draws the titled header on the reserved zone
 * @param {string} [options.title] — fallback title shown inside the footer
 *        when no `drawHeader` is supplied
 * @param {string} [options.subtitle] — shown right-aligned in the footer
 *        (e.g. sim id + date)
 * @returns {Promise<HTMLCanvasElement>}
 */
export async function renderSvgToCanvas(svgEl, {
  width,
  height,
  scale = 2,
  headerHeight = 0,
  drawHeader = null,
  title = '',
  subtitle = '',
} = {}) {
  if (!svgEl) throw new Error('renderSvgToCanvas: svgEl is required')

  await _ensureFontsReady()

  // Clone so we can inline computed styles without mutating the live DOM.
  const clone = svgEl.cloneNode(true)
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  if (!clone.getAttribute('viewBox') && width && height) {
    clone.setAttribute('viewBox', `0 0 ${width} ${height}`)
  }
  clone.setAttribute('width', String(width))
  clone.setAttribute('height', String(height))

  const svgStr = new XMLSerializer().serializeToString(clone)
  const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' })
  const svgUrl = URL.createObjectURL(svgBlob)

  const totalH = headerHeight + height + FOOTER_HEIGHT
  const canvas = document.createElement('canvas')
  canvas.width = width * scale
  canvas.height = totalH * scale
  const ctx = canvas.getContext('2d')
  ctx.scale(scale, scale)
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'

  // Background
  ctx.fillStyle = BACKGROUND
  ctx.fillRect(0, 0, width, totalH)

  // ── Header zone ──
  if (headerHeight > 0 && typeof drawHeader === 'function') {
    ctx.save()
    drawHeader(ctx, { width, headerHeight })
    ctx.restore()
    // Thin divider between header and chart
    ctx.fillStyle = 'rgba(244, 241, 255, 0.08)'
    ctx.fillRect(0, headerHeight, width, 1)
  }

  // Draw the SVG onto the canvas
  await new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      ctx.drawImage(img, 0, headerHeight, width, height)
      URL.revokeObjectURL(svgUrl)
      resolve()
    }
    img.onerror = (err) => {
      URL.revokeObjectURL(svgUrl)
      reject(err instanceof Error ? err : new Error('SVG rasterisation failed'))
    }
    img.src = svgUrl
  })

  // ── Footer: MiroShark logo + wordmark + provenance ──
  const footerY = headerHeight + height
  const midY = footerY + FOOTER_HEIGHT / 2
  // Thin top divider
  ctx.fillStyle = 'rgba(244, 241, 255, 0.08)'
  ctx.fillRect(0, footerY, width, 1)

  // Logo — kept in the same spot the accent squares used, sized to fit the
  // footer height with comfortable padding. Falls through to the wordmark
  // alone if the image fails to load.
  const logoX = 26
  const logoSize = 46
  let textStartX = logoX
  const logoImg = await _loadLogo()
  if (logoImg) {
    ctx.drawImage(logoImg, logoX, midY - logoSize / 2, logoSize, logoSize)
    textStartX = logoX + logoSize + 16
  }

  // Big wordmark — "SIMULATED BY MIROSHARK"
  ctx.fillStyle = '#f4f1ff'
  ctx.font = '700 24px "Space Mono", "JetBrains Mono", ui-monospace, monospace'
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'left'
  // Letter spacing ~2px, implemented manually because canvas lacks the CSS
  // equivalent — keeps the type matching the rest of the design system.
  const brand = 'SIMULATED BY MIROSHARK'
  const letterSpacing = 2
  let cursor = textStartX
  for (const ch of brand) {
    ctx.fillText(ch, cursor, midY)
    cursor += ctx.measureText(ch).width + letterSpacing
  }

  // Fallback title in the footer (only if there's no dedicated header zone)
  if (!drawHeader && title) {
    ctx.fillStyle = 'rgba(244, 241, 255, 0.9)'
    ctx.font = '700 13px "Space Mono", "JetBrains Mono", ui-monospace, monospace'
    ctx.textAlign = 'center'
    const titleStr = title.length > 60 ? title.slice(0, 57) + '…' : title
    ctx.fillText(titleStr, width / 2, midY)
  }

  // Subtitle / provenance (right)
  if (subtitle) {
    ctx.fillStyle = 'rgba(244, 241, 255, 0.4)'
    ctx.font = '400 12px "Space Mono", "JetBrains Mono", ui-monospace, monospace'
    ctx.textAlign = 'right'
    const subStr = subtitle.length > 44 ? subtitle.slice(0, 41) + '…' : subtitle
    ctx.fillText(subStr, width - 24, midY)
  }

  return canvas
}

export function downloadCanvas(canvas, filename) {
  const a = document.createElement('a')
  a.download = filename
  a.href = canvas.toDataURL('image/png')
  a.click()
}

/**
 * Copy canvas contents to the clipboard as a PNG. Rejects if the browser does
 * not support the async Clipboard API with ClipboardItem (Safari ≤ 13, some
 * Firefox versions).
 */
export async function copyCanvasToClipboard(canvas) {
  if (!navigator.clipboard || typeof window.ClipboardItem !== 'function') {
    throw new Error('Clipboard image copy is not supported in this browser')
  }
  const blob = await new Promise((resolve, reject) => {
    canvas.toBlob((b) => {
      if (b) resolve(b)
      else reject(new Error('Canvas → blob failed'))
    }, 'image/png')
  })
  await navigator.clipboard.write([
    new window.ClipboardItem({ 'image/png': blob }),
  ])
}

export function canCopyImageToClipboard() {
  return Boolean(navigator.clipboard && typeof window.ClipboardItem === 'function')
}
