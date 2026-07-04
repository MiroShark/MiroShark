<template>
  <Teleport to="body">
    <Transition name="zh-warning-fade">
      <div
        v-if="showZhWarning"
        class="zh-warning-overlay"
        role="dialog"
        aria-modal="true"
        :aria-label="tr('Chinese mode notice', '中文模式提示', { de: 'Hinweis zum chinesischen Modus' , fr: 'Avis mode chinois'})"
        @click.self="dismissZhWarning"
      >
        <div class="zh-warning-modal">
          <div class="zh-warning-stripes" aria-hidden="true"></div>

          <div class="zh-warning-header">
            <span class="zh-warning-icon" aria-hidden="true">⚠</span>
            <h2 class="zh-warning-title">中文模式 · 实验性功能</h2>
            <button
              class="zh-warning-close"
              type="button"
              aria-label="关闭"
              :title="tr('Dismiss', '关闭', { de: 'Schließen', fr: 'Ignorer' })"
              @click="dismissZhWarning"
            >
              ✕
            </button>
          </div>

          <div class="zh-warning-body">
            <p>
              界面已完全切换为中文。除了 UI 翻译,<strong>模拟智能体</strong>也将以中文运行
              (此功能尚处于<strong>实验阶段</strong>)。
            </p>
            <p>
              请注意:某些<strong>结构化输出</strong>(自动报告、本体生成、人物画像)
              的质量可能因您配置的 LLM 模型而有所不同。
              您可随时通过右上角的语言切换按钮返回英文。
            </p>
          </div>

          <div class="zh-warning-actions">
            <button
              type="button"
              class="zh-warning-confirm"
              @click="dismissZhWarning"
            >
              我知道了
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { useI18n } from '../i18n'

const { showZhWarning, dismissZhWarning, tr } = useI18n()
</script>

<style scoped>
.zh-warning-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  background: rgba(5, 3, 10, 0.7);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.zh-warning-modal {
  position: relative;
  width: 100%;
  max-width: 540px;
  border-radius: 1.25rem;
  background: linear-gradient(180deg, rgba(40, 30, 70, 0.92) 0%, rgba(18, 12, 38, 0.96) 100%);
  border: 1px solid rgba(167, 139, 250, 0.45);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    0 30px 80px -20px rgba(0, 0, 0, 0.9),
    0 0 80px -20px rgba(139, 92, 246, 0.5);
  color: #f4f1ff;
  font-family: 'Geist', system-ui, -apple-system, sans-serif;
  overflow: hidden;
  animation: zh-warning-pop 0.25s ease-out;
}

@keyframes zh-warning-pop {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* The old orange diagonal stripes become a calm metal rule. */
.zh-warning-stripes {
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(167, 139, 250, 0.4) 20%,
    rgba(255, 255, 255, 0.5) 50%,
    rgba(167, 139, 250, 0.4) 80%,
    transparent 100%
  );
  box-shadow: 0 0 16px rgba(167, 139, 250, 0.4);
}

.zh-warning-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 24px 14px 24px;
  border-bottom: 1px solid rgba(167, 139, 250, 0.18);
}

.zh-warning-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  font-size: 18px;
  color: #ffffff;
  background: linear-gradient(180deg, rgba(167, 139, 250, 0.35) 0%, rgba(76, 29, 149, 0.55) 100%);
  border: 1px solid rgba(167, 139, 250, 0.5);
  border-radius: 9999px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.25);
  flex-shrink: 0;
}

.zh-warning-title {
  flex: 1;
  margin: 0;
  font-family: inherit;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.005em;
  background: linear-gradient(180deg, #ffffff 0%, #e2dcf6 60%, #b9b0d8 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.zh-warning-close {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(70, 55, 120, 0.45) 0%, rgba(20, 14, 42, 0.7) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(244, 241, 255, 0.7);
  width: 32px;
  height: 32px;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  border-radius: 9999px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2);
  font-family: 'Geist Mono', ui-monospace, monospace;
  transition: color 180ms ease, border-color 180ms ease, transform 180ms ease;
}

.zh-warning-close:hover {
  color: #ffffff;
  border-color: rgba(167, 139, 250, 0.55);
  transform: translateY(-1px);
}

.zh-warning-body {
  padding: 20px 24px;
  font-family: inherit;
  font-size: 14.5px;
  line-height: 1.65;
  color: rgba(244, 241, 255, 0.82);
}

.zh-warning-body p { margin: 0 0 12px 0; }
.zh-warning-body p:last-child { margin-bottom: 0; }
.zh-warning-body strong {
  color: #c4b5fd;
  font-weight: 600;
}

.zh-warning-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px 22px 24px;
  border-top: 1px solid rgba(167, 139, 250, 0.12);
}

/* Purple metal CTA, same family as the Launch button on Home. */
.zh-warning-confirm {
  position: relative;
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 26px;
  height: 44px;
  font-family: inherit;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #f8f5ff;
  background: linear-gradient(180deg, #6a4ad6 0%, #4922b8 45%, #2a118a 55%, #4f2dc4 100%);
  border: none;
  border-radius: 9999px;
  cursor: pointer;
  text-shadow: 0 1px 0 rgba(0, 0, 0, 0.4);
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.5),
    inset 0 -1px 0 rgba(0, 0, 0, 0.5),
    0 14px 28px -8px rgba(139, 92, 246, 0.55);
  transition: transform 200ms ease, box-shadow 200ms ease, background 200ms ease;
  overflow: hidden;
  isolation: isolate;
}

.zh-warning-confirm::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.4) 0%, rgba(255, 255, 255, 0.08) 40%, transparent 55%);
  pointer-events: none;
}

.zh-warning-confirm:hover {
  transform: translateY(-2px);
  background: linear-gradient(180deg, #7d5ee8 0%, #5728d4 45%, #3414a3 55%, #5e3bde 100%);
}

.zh-warning-confirm:focus-visible {
  outline: 2px solid rgba(196, 181, 253, 0.85);
  outline-offset: 3px;
}

/* Transition wrappers */
.zh-warning-fade-enter-active,
.zh-warning-fade-leave-active {
  transition: opacity 0.2s ease;
}

.zh-warning-fade-enter-from,
.zh-warning-fade-leave-to {
  opacity: 0;
}

@media (max-width: 520px) {
  .zh-warning-modal {
    max-width: 100%;
  }
  .zh-warning-title {
    font-size: 16px;
  }
  .zh-warning-body {
    font-size: 14px;
  }
}
</style>
