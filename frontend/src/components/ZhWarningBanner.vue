<template>
  <Teleport to="body">
    <Transition name="zh-warning-fade">
      <div
        v-if="showZhWarning"
        class="zh-warning-overlay"
        role="dialog"
        aria-modal="true"
        :aria-label="tr('Chinese mode notice', '中文模式提示')"
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
              :title="tr('Dismiss', '关闭')"
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
  padding: var(--space-md, 22px);
  background: rgba(10, 10, 10, 0.55);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.zh-warning-modal {
  position: relative;
  width: 100%;
  max-width: 520px;
  background: var(--color-white, #FAFAFA);
  border: 3px solid var(--color-orange, #FF6B1A);
  box-shadow: 0 18px 48px rgba(10, 10, 10, 0.35);
  overflow: hidden;
  animation: zh-warning-pop 0.25s ease-out;
}

@keyframes zh-warning-pop {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.zh-warning-stripes {
  height: 7px;
  background: repeating-linear-gradient(
    -45deg,
    var(--color-orange, #FF6B1A),
    var(--color-orange, #FF6B1A) 11px,
    var(--color-amber, #FFB347) 11px,
    var(--color-amber, #FFB347) 22px
  );
}

.zh-warning-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 22px 12px 22px;
  border-bottom: 1px solid rgba(10, 10, 10, 0.08);
}

.zh-warning-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  font-size: 18px;
  color: var(--color-orange, #FF6B1A);
  background: rgba(255, 107, 26, 0.12);
  border: 2px solid var(--color-orange, #FF6B1A);
  border-radius: 0;
  flex-shrink: 0;
}

.zh-warning-title {
  flex: 1;
  margin: 0;
  font-family: var(--font-display, 'Young Serif', Georgia, serif);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-black, #0A0A0A);
  letter-spacing: 0.3px;
}

.zh-warning-close {
  appearance: none;
  background: transparent;
  border: 1px solid rgba(10, 10, 10, 0.15);
  color: rgba(10, 10, 10, 0.55);
  width: 28px;
  height: 28px;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  font-family: var(--font-mono, 'Space Mono', 'Courier New', monospace);
  transition: var(--transition-fast, all 0.1s ease);
}

.zh-warning-close:hover {
  color: var(--color-orange, #FF6B1A);
  border-color: var(--color-orange, #FF6B1A);
}

.zh-warning-body {
  padding: 18px 22px;
  font-family: var(--font-display, 'Young Serif', Georgia, serif);
  font-size: 14.5px;
  line-height: 1.65;
  color: rgba(10, 10, 10, 0.82);
}

.zh-warning-body p {
  margin: 0 0 12px 0;
}

.zh-warning-body p:last-child {
  margin-bottom: 0;
}

.zh-warning-body strong {
  color: var(--color-orange, #FF6B1A);
  font-weight: 600;
}

.zh-warning-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 22px 20px 22px;
  border-top: 1px solid rgba(10, 10, 10, 0.06);
}

.zh-warning-confirm {
  appearance: none;
  padding: 9px 22px;
  font-family: var(--font-mono, 'Space Mono', 'Courier New', monospace);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: var(--color-white, #FAFAFA);
  background: var(--color-orange, #FF6B1A);
  border: 2px solid var(--color-orange, #FF6B1A);
  border-radius: 0;
  cursor: pointer;
  transition: var(--transition-fast, all 0.1s ease);
}

.zh-warning-confirm:hover {
  background: var(--color-black, #0A0A0A);
  border-color: var(--color-black, #0A0A0A);
}

.zh-warning-confirm:focus-visible {
  outline: 2px solid var(--color-green, #43C165);
  outline-offset: 2px;
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
