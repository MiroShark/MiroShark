<template>
  <router-view />
  <DebugPanel />
  <ZhWarningBanner />
</template>

<script setup>
import DebugPanel from './components/DebugPanel.vue'
import ZhWarningBanner from './components/ZhWarningBanner.vue'
</script>

<style>
/* ═══════════════════════════════════════════════════════════
   MIROSHARK DESIGN SYSTEM — Space Purple
   Mirrors miroshark.xyz: deep-space radial gradients, chrome
   shimmer text, glossy violet panels. Legacy --color-* token
   names kept so scoped styles in every component inherit the
   new palette automatically.
   ═══════════════════════════════════════════════════════════ */

:root {
  /* ── Space-purple palette ── */
  --background: #05030a;
  --foreground: #f4f1ff;
  --accent: #8b5cf6;
  --accent-bright: #a78bfa;
  --accent-deep: #4c1d95;
  --signal-up: #c4b5fd;
  --signal-down: #f0abfc;

  /* ── Legacy tokens, remapped onto the new palette ──
     Components reference these directly in scoped <style> blocks,
     so changing the values here repaints them without per-file edits.
       --color-orange  →  bright violet accent
       --color-green   →  soft violet (used for "yes" / positive)
       --color-white   →  glossy-panel base (deep panel surface)
       --color-black   →  light foreground (text on dark)
       --color-gray    →  panel-on-panel surface
   */
  --color-orange: #a78bfa;
  --color-green:  #c4b5fd;
  --color-white:  #110a26;
  --color-black:  #f4f1ff;
  --color-gray:   #1a0f3a;
  --color-amber:  #fcd34d;
  --color-red:    #f0abfc;

  --space-xs: 6px;
  --space-sm: 11px;
  --space-md: 22px;
  --space-lg: 34px;
  --space-xl: 56px;
  --space-2xl: 84px;

  --border-light: 1px solid rgba(255, 255, 255, 0.08);
  --border-medium: 1px solid rgba(167, 139, 250, 0.22);
  --border-orange: 1px solid var(--accent-bright);
  --border-green: 1px solid var(--signal-up);

  --transition-fast: all 0.1s ease;
  --transition-medium: all 0.2s ease;

  --font-display: 'Geist', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  font-family: var(--font-display);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--foreground);
  background: var(--background);
  min-height: 100%;
}

/* Deep-space radial gradient layer */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -2;
  pointer-events: none;
  background:
    radial-gradient(ellipse 55% 45% at 50% 30%, rgba(139, 92, 246, 0.45), transparent 65%),
    radial-gradient(ellipse 70% 50% at 50% 50%, rgba(76, 29, 149, 0.35), transparent 70%),
    radial-gradient(ellipse 40% 30% at 15% 75%, rgba(56, 30, 110, 0.45), transparent 70%),
    radial-gradient(ellipse 35% 30% at 85% 25%, rgba(150, 80, 230, 0.3), transparent 70%),
    linear-gradient(180deg, #050210 0%, #0a0420 45%, #06021a 80%, #02010a 100%);
}

/* Twinkling stars */
body::after {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background-image:
    radial-gradient(1px 1px at 12% 18%, rgba(255, 255, 255, 1), transparent 50%),
    radial-gradient(1px 1px at 78% 9%, rgba(255, 255, 255, 0.9), transparent 50%),
    radial-gradient(1.5px 1.5px at 33% 72%, rgba(255, 255, 255, 1), transparent 50%),
    radial-gradient(1px 1px at 62% 38%, rgba(220, 220, 255, 0.85), transparent 50%),
    radial-gradient(1px 1px at 88% 56%, rgba(255, 255, 255, 0.95), transparent 50%),
    radial-gradient(1.5px 1.5px at 22% 88%, rgba(255, 240, 255, 0.75), transparent 50%),
    radial-gradient(1px 1px at 7% 42%, rgba(255, 255, 255, 0.6), transparent 50%),
    radial-gradient(1px 1px at 49% 14%, rgba(255, 255, 255, 1), transparent 50%),
    radial-gradient(1px 1px at 92% 82%, rgba(255, 255, 255, 0.7), transparent 50%),
    radial-gradient(1.5px 1.5px at 41% 51%, rgba(255, 255, 255, 0.6), transparent 50%),
    radial-gradient(1px 1px at 67% 91%, rgba(220, 220, 255, 0.7), transparent 50%),
    radial-gradient(1px 1px at 17% 63%, rgba(255, 255, 255, 0.6), transparent 50%),
    radial-gradient(1px 1px at 55% 78%, rgba(255, 255, 255, 0.75), transparent 50%),
    radial-gradient(1px 1px at 73% 24%, rgba(255, 255, 255, 0.7), transparent 50%),
    radial-gradient(1px 1px at 38% 28%, rgba(255, 255, 255, 0.8), transparent 50%);
  animation: twinkle 6s ease-in-out infinite alternate;
}

@keyframes twinkle {
  from { opacity: 0.55; }
  to   { opacity: 1; }
}

/* Chrome text helper — for hero headlines */
.chrome-text {
  background: linear-gradient(
    180deg,
    #ffffff 0%, #e9e9f5 15%, #b9b9cc 32%, #6e6e85 50%,
    #c8c8dc 68%, #ffffff 85%, #d6d6e8 100%
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-stroke: 1px rgba(255, 255, 255, 0.15);
  filter:
    drop-shadow(0 1px 0 rgba(255, 255, 255, 0.4))
    drop-shadow(0 4px 12px rgba(167, 139, 250, 0.35))
    drop-shadow(0 16px 32px rgba(0, 0, 0, 0.6));
  letter-spacing: -0.04em;
  position: relative;
}

::selection {
  background: rgba(167, 139, 250, 0.45);
  color: #ffffff;
}
::-moz-selection {
  background: rgba(167, 139, 250, 0.45);
  color: #ffffff;
}

::-webkit-scrollbar { width: 11px; height: 11px; }
::-webkit-scrollbar-track { background: rgba(20, 12, 40, 0.5); }
::-webkit-scrollbar-thumb { background: rgba(167, 139, 250, 0.35); border-radius: 9999px; }
::-webkit-scrollbar-thumb:hover { background: rgba(167, 139, 250, 0.55); }

button {
  font-family: var(--font-mono);
  cursor: pointer;
}

/* Text opacity scale — inverted for the dark backdrop */
.text-primary-100 { color: #ffffff; }
.text-primary-70  { color: rgba(244, 241, 255, 0.85); }
.text-primary-50  { color: rgba(228, 222, 255, 0.7); }
.text-primary-40  { color: rgba(228, 222, 255, 0.6); }
.text-primary-35  { color: rgba(228, 222, 255, 0.5); }

/* Calm metal rule replaces the old warning stripes */
.warning-stripes {
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(167, 139, 250, 0.4) 20%,
    rgba(255, 255, 255, 0.5) 50%,
    rgba(167, 139, 250, 0.4) 80%,
    transparent 100%
  );
  box-shadow: 0 0 16px rgba(167, 139, 250, 0.3);
}

.bg-grid {
  background-image: none;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes shimmer {
  0%, 100% { opacity: 0.55; }
  50%      { opacity: 1; }
}

@keyframes pulse-border {
  0%, 100% { border-color: rgba(167, 139, 250, 0.4); }
  50%      { border-color: rgba(196, 181, 253, 0.85); }
}

@keyframes scan {
  0%, 100% { transform: translateY(-50px); opacity: 0; }
  10% { opacity: 0.6; }
  50% { transform: translateY(50px); opacity: 0.6; }
  90% { opacity: 0.6; }
}

@keyframes shimmer-gradient {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.animate-fade-in { animation: fade-in 0.5s ease-out; }
.animate-shimmer { animation: shimmer 2s ease-in-out infinite; }
.animate-pulse-border { animation: pulse-border 2s ease-in-out infinite; }
</style>
