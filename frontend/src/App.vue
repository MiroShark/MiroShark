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
   MIROSHARK DESIGN SYSTEM — Hyperstitions v2.0
   Evangelion-inspired. Orange + Green bicolor. 1.4x scale.
   ═══════════════════════════════════════════════════════════ */

:root {
  /* ── Primary Colors ──
     Legacy token NAMES kept (so every scoped <style> that already
     references them inherits the new palette automatically), but
     VALUES remapped to the MiroShark space-purple system.
       --color-orange  →  bright violet accent
       --color-green   →  soft violet (used for "yes" / positive)
       --color-white   →  deep glossy-panel base
       --color-black   →  light foreground text
       --color-gray    →  panel-on-panel surface
       --color-red     →  soft fuchsia for warnings
   */
  --color-orange: #a78bfa;
  --color-green:  #c4b5fd;
  --color-white:  #110a26;
  --color-black:  #f4f1ff;
  --color-gray:   #1a0f3a;
  --color-amber:  #fcd34d;
  --color-red:    #f0abfc;

  /* Page-level background — deep-space. */
  --background: #05030a;
  --foreground: #f4f1ff;

  /* ── 1.4x Modular Spacing Scale ── */
  --space-xs: 6px;
  --space-sm: 11px;
  --space-md: 22px;
  --space-lg: 34px;
  --space-xl: 56px;
  --space-2xl: 84px;

  /* ── Borders ── */
  --border-light: 2px solid rgba(10,10,10,0.08);
  --border-medium: 2px solid rgba(10,10,10,0.12);
  --border-orange: 3px solid var(--color-orange);
  --border-green: 3px solid var(--color-green);

  /* ── Transitions ── */
  --transition-fast: all 0.1s ease;
  --transition-medium: all 0.2s ease;

  /* ── Fonts ── */
  --font-display: 'Young Serif', Georgia, serif;
  --font-mono: 'Space Mono', 'Courier New', monospace;
}

/* ── Reset ── */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body, #app {
  font-family: var(--font-display);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--foreground);
  background-color: var(--background);
}

/* ── Text Selection ── */
::selection {
  background: var(--color-orange);
  color: var(--color-white);
}

::-moz-selection {
  background: var(--color-orange);
  color: var(--color-white);
}

/* ── Scrollbar (1.4x scale) ── */
::-webkit-scrollbar {
  width: 11px;
  height: 11px;
}

::-webkit-scrollbar-track {
  background: var(--color-gray);
}

::-webkit-scrollbar-thumb {
  background: rgba(10,10,10,0.2);
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(10,10,10,0.3);
}

/* ── Global Button Base ── */
button {
  font-family: var(--font-mono);
  cursor: pointer;
}

/* ── Text Opacity Scale (now light-on-dark) ── */
.text-primary-100 { color: #ffffff; }
.text-primary-70 { color: rgba(244, 241, 255, 0.85); }
.text-primary-50 { color: rgba(228, 222, 255, 0.7); }
.text-primary-40 { color: rgba(228, 222, 255, 0.6); }
.text-primary-35 { color: rgba(228, 222, 255, 0.5); }

/* ── Warning Stripes Divider ── */
.warning-stripes {
  height: 7px;
  background: repeating-linear-gradient(
    -45deg,
    var(--color-orange),
    var(--color-orange) 11px,
    var(--color-white) 11px,
    var(--color-white) 22px
  );
}

/* ── Background Grid ── */
.bg-grid {
  background-image:
    linear-gradient(rgba(67,193,101,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(67,193,101,0.04) 1px, transparent 1px);
  background-size: 70px 70px;
}

/* ── Animations ── */
@keyframes fade-in {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes shimmer {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

@keyframes pulse-border {
  0%, 100% { border-color: var(--color-orange); }
  50% { border-color: var(--color-green); }
}

@keyframes scan {
  0%, 100% { transform: translateY(-50px); opacity: 0; }
  10% { opacity: 0.6; }
  50% { transform: translateY(50px); opacity: 0.6; }
  90% { opacity: 0.6; }
}

.animate-fade-in { animation: fade-in 0.5s ease-out; }
.animate-shimmer { animation: shimmer 2s ease-in-out infinite; }
.animate-pulse-border { animation: pulse-border 2s ease-in-out infinite; }
</style>
