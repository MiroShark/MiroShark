<template>
  <Teleport to="body">
    <Transition name="embed-dialog">
      <div v-if="open" class="embed-dialog-overlay" @click.self="$emit('close')">
        <div class="embed-dialog">
          <!-- Header -->
          <div class="embed-dialog-header">
            <div class="embed-dialog-title">
              <span class="title-icon">⌘</span>
              <span>{{ $tr('Embed simulation', '嵌入模拟') }}</span>
              <span class="title-sub">{{ formatSimulationId(simulationId) }}</span>
            </div>
            <button class="embed-dialog-close" @click="$emit('close')">×</button>
          </div>

          <!-- Description -->
          <p class="embed-dialog-desc">
            {{ $tr('Paste the iframe below into Notion, Substack, Medium, a GitHub README, or any HTML page. The widget loads live from this MiroShark instance and updates automatically as the simulation changes.', '将下面的 iframe 粘贴到 Notion、Substack、Medium、GitHub README 或任何 HTML 页面中。组件从当前 MiroShark 实例实时加载,并随模拟变化自动更新。') }}
          </p>

          <!-- Public toggle -->
          <div class="embed-public-row">
            <label class="embed-public-toggle">
              <input type="checkbox" :checked="isPublic" @change="togglePublic" :disabled="publishing" />
              <span class="embed-public-label">
                {{ isPublic ? $tr('Public — embeddable by anyone with the URL', '公开 — 任何获得 URL 的人都可嵌入') : $tr('Private — embed URL returns 403', '私有 — 嵌入 URL 返回 403') }}
              </span>
            </label>
            <span v-if="publishError" class="embed-public-error">{{ publishError }}</span>
          </div>

          <!-- Size presets -->
          <div class="embed-size-row">
            <span class="embed-size-label">{{ $tr('Size', '尺寸') }}</span>
            <div class="embed-size-buttons">
              <button
                v-for="preset in sizePresets"
                :key="preset.name"
                class="embed-size-btn"
                :class="{ active: activePreset === preset.name }"
                @click="activePreset = preset.name"
              >
                {{ translatePresetName(preset.name) }}
                <span class="embed-size-dim">{{ preset.width }}×{{ preset.height }}</span>
              </button>
            </div>
            <label class="embed-theme-toggle">
              <span>{{ $tr('Theme', '主题') }}</span>
              <select v-model="theme" class="embed-theme-select">
                <option value="light">{{ $tr('Light', '浅色') }}</option>
                <option value="dark">{{ $tr('Dark', '深色') }}</option>
              </select>
            </label>
          </div>

          <!-- Preview -->
          <div class="embed-preview-wrap" :class="`preview-${activePreset.toLowerCase()}`">
            <div class="embed-preview-frame" :style="previewStyle">
              <iframe
                v-if="embedUrl"
                :src="embedUrl"
                :style="iframeStyle"
                frameborder="0"
                loading="lazy"
                title="MiroShark simulation embed preview"
              ></iframe>
            </div>
          </div>

          <!-- Copyable snippets -->
          <div class="embed-snippets">
            <div class="snippet-block">
              <div class="snippet-head">
                <span class="snippet-label">{{ $tr('HTML iframe', 'HTML iframe') }}</span>
                <button class="snippet-copy-btn" @click="copy('iframe')">
                  {{ copied === 'iframe' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy', '复制') }}
                </button>
              </div>
              <pre class="snippet-code"><code>{{ iframeSnippet }}</code></pre>
            </div>

            <div class="snippet-block">
              <div class="snippet-head">
                <span class="snippet-label">{{ $tr('Markdown (Notion / Substack auto-embed)', 'Markdown(Notion / Substack 自动嵌入)') }}</span>
                <button class="snippet-copy-btn" @click="copy('markdown')">
                  {{ copied === 'markdown' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy', '复制') }}
                </button>
              </div>
              <pre class="snippet-code"><code>{{ markdownSnippet }}</code></pre>
            </div>

            <div class="snippet-block">
              <div class="snippet-head">
                <span class="snippet-label">{{ $tr('Direct URL', '直接 URL') }}</span>
                <button class="snippet-copy-btn" @click="copy('url')">
                  {{ copied === 'url' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy', '复制') }}
                </button>
              </div>
              <pre class="snippet-code"><code>{{ embedUrl }}</code></pre>
            </div>
          </div>

          <!-- Social share card -->
          <div class="share-card-section">
            <div class="share-card-divider">
              <span class="divider-line"></span>
              <span class="divider-text">{{ $tr('Social card', '社交卡片') }}</span>
              <span class="divider-line"></span>
            </div>

            <p class="share-card-desc">
              {{ $tr('A 1200×630 PNG with the scenario headline, status, quality, and belief split — the same image Twitter/X, Discord, Slack, and LinkedIn unfurl automatically when someone pastes the share link.', '一张 1200×630 的 PNG,包含情景标题、状态、质量和信念分布 — Twitter/X、Discord、Slack 和 LinkedIn 在有人粘贴分享链接时会自动展开此图。') }}
            </p>

            <div class="share-card-preview-wrap">
              <img
                v-if="isPublic && shareCardUrl"
                :src="shareCardUrl"
                :key="shareCardCacheBust"
                class="share-card-preview"
                alt="MiroShark share card preview"
                @error="onShareCardError"
              />
              <div v-else class="share-card-empty">
                {{ isPublic ? $tr('Loading preview…', '加载预览中…') : $tr('Publish the simulation to enable the share card.', '发布模拟以启用分享卡片。') }}
              </div>
            </div>

            <div class="share-card-actions">
              <div class="snippet-block share-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Share link (auto-unfurls with card)', '分享链接(随卡片自动展开)') }}</span>
                  <button class="snippet-copy-btn" @click="copy('share')" :disabled="!isPublic">
                    {{ copied === 'share' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy link', '复制链接') }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ shareLandingUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block share-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Card image URL (for manual paste)', '卡片图片 URL(供手动粘贴)') }}</span>
                  <button class="snippet-copy-btn" @click="copy('card')" :disabled="!isPublic">
                    {{ copied === 'card' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy URL', '复制 URL') }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ shareCardUrl || '—' }}</code></pre>
              </div>

              <a
                v-if="isPublic && shareCardUrl"
                class="share-download-btn"
                :href="shareCardUrl"
                :download="`miroshark-${simulationId.slice(0, 12)}.png`"
              >
                ↓ {{ $tr('Download PNG', '下载 PNG') }}
              </a>
            </div>

            <!-- Live spectator-watch link — distinct format from the
                 finished-result card above. The /watch/<id> URL is the
                 "tweet a sim mid-run" share: a minimal full-viewport
                 broadcast page that auto-unfurls as a 1200×630 image
                 card and updates the belief bar / round counter every
                 15 s while the simulation runs. -->
            <div class="watch-section">
              <div class="watch-head">
                <span class="watch-icon">📡</span>
                <div class="watch-head-body">
                  <div class="watch-title">{{ $tr('Watch live (broadcast page)', '实时观看(直播页面)') }}</div>
                  <div class="watch-sub">
                    {{ $tr('A minimal full-viewport page built for live spectating — the belief bar, round counter, and progress bar update every 15 s while the simulation runs. Auto-unfurls as a card on Twitter / X, Discord, Slack, LinkedIn. Different format from the finished-result share above; tweet this URL mid-run to broadcast as it happens.', '专为实时观看打造的极简全屏页面 — 信念条、轮次计数器和进度条在模拟运行时每 15 秒更新一次。在 Twitter / X、Discord、Slack、LinkedIn 上自动展开为卡片。与上方的完成结果分享不同;在运行过程中发推此 URL 即可实时广播。') }}
                  </div>
                </div>
              </div>

              <div class="watch-actions">
                <a
                  v-if="isPublic && watchUrl"
                  class="watch-open-btn"
                  :href="watchUrl"
                  target="_blank"
                  rel="noopener"
                >
                  👀 {{ $tr('Open watch page ↗', '打开观看页面 ↗') }}
                </a>
                <span v-if="!isPublic" class="watch-empty">
                  {{ $tr('Publish the simulation to enable the live watch page.', '发布模拟以启用实时观看页面。') }}
                </span>
              </div>

              <div class="snippet-block watch-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Watch URL (auto-unfurls with card on tweet)', '观看 URL(发推时随卡片自动展开)') }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('watch')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'watch' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy URL', '复制 URL') }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ watchUrl || '—' }}</code></pre>
              </div>
            </div>

            <!-- Animated belief replay — same 1200×630 frame as the share
                 card but one frame per round, so X / Discord / Slack
                 auto-play the belief drift inline. -->
            <div class="replay-section">
              <div class="replay-head">
                <span class="replay-icon">▶</span>
                <div class="replay-head-body">
                  <div class="replay-title">{{ $tr('Belief replay (animated)', '信念回放(动画)') }}</div>
                  <div class="replay-sub">
                    {{ $tr('Same canvas as the share card, one frame per round. Discord and Slack auto-play GIFs from the direct URL — drop the link in a channel and it plays inline.', '与分享卡片相同的画布,每轮一帧。Discord 和 Slack 会从直接 URL 自动播放 GIF — 在频道里贴上链接即可内联播放。') }}
                  </div>
                </div>
              </div>

              <div
                v-if="isPublic && replayGifUrl"
                class="replay-preview-wrap"
                :class="{ 'replay-preview-paused': !replayPlay }"
                @click="startReplay"
              >
                <img
                  v-if="replayPlay"
                  :src="replayGifUrl"
                  class="replay-preview"
                  :class="{ 'replay-preview-loaded': replayLoaded }"
                  alt="MiroShark belief replay GIF"
                  @load="onReplayLoad"
                  @error="onReplayError"
                />
                <div v-if="!replayPlay" class="replay-overlay">
                  <span class="replay-overlay-icon">▶</span>
                  <span class="replay-overlay-text">{{ $tr('Tap to play', '点击播放') }}</span>
                </div>
              </div>
              <div v-else class="replay-empty">
                {{ $tr('Publish the simulation to enable the belief replay GIF.', '发布模拟以启用信念回放 GIF。') }}
              </div>

              <div class="replay-actions">
                <div class="snippet-block share-snippet">
                  <div class="snippet-head">
                    <span class="snippet-label">{{ $tr('Replay GIF URL (auto-plays in Discord / Slack)', '回放 GIF URL(在 Discord / Slack 中自动播放)') }}</span>
                    <button
                      class="snippet-copy-btn"
                      @click="copy('replay')"
                      :disabled="!isPublic"
                    >
                      {{ copied === 'replay' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy URL', '复制 URL') }}
                    </button>
                  </div>
                  <pre class="snippet-code"><code>{{ replayGifUrl || '—' }}</code></pre>
                </div>

                <a
                  v-if="isPublic && replayGifUrl"
                  class="share-download-btn"
                  :href="replayGifUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-replay.gif`"
                >
                  ↓ {{ $tr('Download GIF', '下载 GIF') }}
                </a>
              </div>
            </div>

            <!-- Text transcript — pairs with the share card (preview)
                 and replay GIF (motion) as the third quote-friendly
                 share format. The Markdown form has YAML front matter
                 so Notion / Obsidian / Bear / Substack pick it up as
                 page metadata; the JSON form is for SDK consumers. -->
            <div class="transcript-section">
              <div class="transcript-head">
                <span class="transcript-icon">📄</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">{{ $tr('Export transcript', '导出对话记录') }}</div>
                  <div class="transcript-sub">
                    {{ $tr('Per-round agent posts + stance labels + final consensus. Cite the simulation in a research paper or a Substack post without screenshotting.', '逐轮智能体帖子 + 立场标签 + 最终共识。在研究论文或 Substack 文章中引用该模拟,无需截屏。') }}
                  </div>
                </div>
              </div>

              <div class="transcript-actions">
                <a
                  v-if="isPublic && transcriptMarkdownUrl"
                  class="transcript-download-btn"
                  :href="transcriptMarkdownUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-transcript.md`"
                >
                  ↓ {{ $tr('Download .md', '下载 .md') }}
                </a>
                <a
                  v-if="isPublic && transcriptJsonUrl"
                  class="transcript-download-btn transcript-download-btn-secondary"
                  :href="transcriptJsonUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-transcript.json`"
                >
                  ↓ {{ $tr('Download .json', '下载 .json') }}
                </a>
                <span v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to enable the transcript export.', '发布模拟以启用对话记录导出。') }}
                </span>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr(`Markdown URL (Notion / Obsidian "Import from URL")`, 'Markdown URL(Notion / Obsidian「从 URL 导入」)') }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('transcriptMd')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'transcriptMd' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy URL', '复制 URL') }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ transcriptMarkdownUrl || '—' }}</code></pre>
              </div>
            </div>

            <!-- Belief trajectory data export — pairs with the share
                 card / replay GIF / transcript as the fifth share
                 surface. The previous four cover the qualitative read
                 of a simulation; this one gives Pandas / Excel /
                 Tableau / R / Observable users the raw numbers. -->
            <div class="transcript-section trajectory-section">
              <div class="transcript-head">
                <span class="transcript-icon">📊</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">{{ $tr('Export trajectory data', '导出轨迹数据') }}</div>
                  <div class="transcript-sub">
                    {{ $tr('One row per round — bullish / neutral / bearish %, participating agents, post + engagement counts. Pandas, Excel, Tableau, R, and Observable consume CSV natively.', '每轮一行 — 看涨 / 中性 / 看跌 %、参与的智能体、帖子和互动数。Pandas、Excel、Tableau、R 和 Observable 原生消费 CSV。') }}
                  </div>
                </div>
              </div>

              <div class="transcript-actions">
                <a
                  v-if="isPublic && trajectoryCsvUrl"
                  class="transcript-download-btn"
                  :href="trajectoryCsvUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-trajectory.csv`"
                >
                  ↓ {{ $tr('Download .csv', '下载 .csv') }}
                </a>
                <a
                  v-if="isPublic && trajectoryJsonlUrl"
                  class="transcript-download-btn transcript-download-btn-secondary"
                  :href="trajectoryJsonlUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-trajectory.jsonl`"
                >
                  ↓ {{ $tr('Download .jsonl', '下载 .jsonl') }}
                </a>
                <span v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to enable the trajectory export.', '发布模拟以启用轨迹数据导出。') }}
                </span>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('CSV URL (paste into pandas.read_csv())', 'CSV URL(粘贴至 pandas.read_csv())') }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('trajectoryCsv')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'trajectoryCsv' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy URL', '复制 URL') }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ trajectoryCsvUrl || '—' }}</code></pre>
              </div>

              <p class="trajectory-quickstart">
                <code>pd.read_csv("{{ trajectoryCsvUrl || 'https://your-host/api/simulation/&lt;id&gt;/trajectory.csv' }}")</code>
              </p>
            </div>

            <!-- Verified-prediction annotation — lets operators turn a
                 published simulation into a "called it" record on the
                 /verified gallery page. Only meaningful once the run is
                 public, so the inputs are disabled until then. -->
            <div class="outcome-section" :class="{ 'outcome-section-live': isPublic }">
              <div class="outcome-head">
                <span class="outcome-icon">📍</span>
                <div class="outcome-head-body">
                  <div class="outcome-title">
                    {{ $tr('Mark outcome', '标记结果') }}
                    <span v-if="outcome && outcome.label" class="outcome-saved-tag">
                      ✓ {{ outcomeLabelText(outcome.label) }}
                    </span>
                  </div>
                  <div class="outcome-sub">
                    {{ $tr('Did this simulation predict a real event? Annotate it and your run lands on', '此模拟预测到了真实事件吗?为它做标注,你的运行将出现在') }}
                    <a href="/verified" target="_blank" rel="noopener">/verified</a>
                    {{ $tr('— the public hall of calls that landed.', ' — 已落地预测的公开展示厅。') }}
                  </div>
                </div>
              </div>

              <div class="outcome-fields" :class="{ 'outcome-fields-disabled': !isPublic }">
                <fieldset class="outcome-radio-group" :disabled="!isPublic">
                  <label
                    v-for="opt in outcomeOptions"
                    :key="opt.value"
                    class="outcome-radio"
                    :class="{ 'outcome-radio-active': outcomeForm.label === opt.value }"
                  >
                    <input
                      type="radio"
                      :value="opt.value"
                      v-model="outcomeForm.label"
                    />
                    <span class="outcome-radio-icon">{{ opt.icon }}</span>
                    <span class="outcome-radio-label">{{ opt.label }}</span>
                  </label>
                </fieldset>

                <input
                  v-model="outcomeForm.outcome_url"
                  type="url"
                  :placeholder="$tr('Outcome URL (article, tweet, dashboard) — optional', '结果 URL(文章、推文、仪表板)— 可选')"
                  class="outcome-input"
                  :disabled="!isPublic"
                  maxlength="500"
                />
                <textarea
                  v-model="outcomeForm.outcome_summary"
                  :placeholder="$tr('What happened, in one or two sentences (max 280 chars)', '用一两句话描述发生了什么(最多 280 字符)')"
                  class="outcome-textarea"
                  :disabled="!isPublic"
                  maxlength="280"
                  rows="2"
                ></textarea>
                <div class="outcome-summary-counter">
                  {{ outcomeForm.outcome_summary.length }}/280
                </div>

                <div class="outcome-actions">
                  <button
                    class="outcome-submit"
                    @click="submitOutcome"
                    :disabled="!isPublic || !outcomeForm.label || outcomeSubmitting"
                  >
                    <span v-if="outcomeSubmitting">{{ $tr('Saving…', '保存中…') }}</span>
                    <span v-else-if="outcome">{{ $tr('Update outcome', '更新结果') }}</span>
                    <span v-else>{{ $tr('Save outcome', '保存结果') }}</span>
                  </button>
                  <a
                    v-if="outcome"
                    href="/verified"
                    target="_blank"
                    rel="noopener"
                    class="outcome-link"
                  >
                    {{ $tr('View on /verified ↗', '在 /verified 查看 ↗') }}
                  </a>
                </div>

                <div v-if="outcomeMessage" class="outcome-message" :class="outcomeMessageClass">
                  {{ outcomeMessage }}
                </div>
              </div>
            </div>

            <!-- Gallery callout — appears once the simulation is public so the
                 operator knows their run is visible on /explore, and offers a
                 one-click jump to see it in situ alongside other public runs. -->
            <div class="gallery-callout" :class="{ 'gallery-callout-live': isPublic }">
              <div class="gallery-callout-icon">◎</div>
              <div class="gallery-callout-body">
                <div class="gallery-callout-title">
                  {{ isPublic ? $tr('Live on the public gallery', '已发布到公开画廊') : $tr('Submit to the public gallery', '提交到公开画廊') }}
                </div>
                <div class="gallery-callout-desc">
                  <template v-if="isPublic">
                    {{ $tr('This simulation is now visible on', '此模拟现可在以下页面查看') }}
                    <a href="/explore" target="_blank" rel="noopener">/explore</a> —
                    {{ $tr('the public gallery where anyone can browse published runs and fork them into their own simulations.', '公开画廊,任何人都可浏览已发布运行并派生为自己的模拟。') }}
                  </template>
                  <template v-else>
                    {{ $tr(`Toggle "Public" above and this run joins the community gallery at`, '将上方切换为「公开」,该运行将加入社区画廊') }}
                    <a href="/explore" target="_blank" rel="noopener">/explore</a>.
                    {{ $tr('Others can browse it, view the full belief drift, and fork your agents into their own scenarios.', '其他人可以浏览、查看完整的信念漂移,并将你的智能体派生到他们自己的情景中。') }}
                  </template>
                </div>
              </div>
              <a
                v-if="isPublic"
                href="/explore"
                target="_blank"
                rel="noopener"
                class="gallery-callout-link"
              >
                {{ $tr('Open gallery ↗', '打开画廊 ↗') }}
              </a>
            </div>

            <!-- RSS / Atom syndication — passive subscription channel
                 for researchers and tooling that already read AI/DeFi
                 content via Feedly / Readwise / Inoreader / Obsidian
                 RSS. Every newly published MiroShark simulation lands
                 in their reader without anyone curating it. -->
            <div class="feed-callout">
              <div class="feed-callout-head">
                <span class="feed-callout-icon">📡</span>
                <div class="feed-callout-body">
                  <div class="feed-callout-title">
                    {{ $tr('Follow the gallery via RSS', '通过 RSS 关注画廊') }}
                  </div>
                  <div class="feed-callout-desc">
                    {{ $tr('Every newly published MiroShark simulation appears in your reader (Feedly, Readwise, Inoreader, Obsidian RSS, NetNewsWire, …). No login, no account.', '每个新发布的 MiroShark 模拟都会出现在你的阅读器中(Feedly、Readwise、Inoreader、Obsidian RSS、NetNewsWire 等)。无需登录,无需账户。') }}
                  </div>
                </div>
              </div>
              <div class="feed-callout-actions">
                <a
                  class="feed-callout-link"
                  :href="feedAtomUrl"
                  target="_blank"
                  rel="noopener"
                  :title="$tr('Atom 1.0 feed of the public gallery', '公开画廊的 Atom 1.0 源')"
                >
                  {{ $tr('Atom feed ↗', 'Atom 源 ↗') }}
                </a>
                <a
                  class="feed-callout-link feed-callout-link-secondary"
                  :href="feedRssUrl"
                  target="_blank"
                  rel="noopener"
                  :title="$tr('RSS 2.0 feed of the public gallery', '公开画廊的 RSS 2.0 源')"
                >
                  RSS 2.0 ↗
                </a>
                <a
                  class="feed-callout-link feed-callout-link-secondary"
                  :href="feedVerifiedAtomUrl"
                  target="_blank"
                  rel="noopener"
                  :title="$tr('Atom feed restricted to verified predictions only', '仅限已验证预测的 Atom 源')"
                >
                  {{ $tr('Verified only ↗', '仅已验证 ↗') }}
                </a>
              </div>
            </div>
          </div>

          <!-- Hint -->
          <div class="embed-dialog-hint">
            <span class="hint-icon">ⓘ</span>
            {{ $tr(`The widget reads from this instance's API, so viewers must be able to reach`, '组件读取自当前实例的 API,因此查看者必须能访问') }}
            <code>{{ origin }}</code>. {{ $tr('For public embeds, deploy MiroShark somewhere reachable from the internet.', '若要进行公开嵌入,请将 MiroShark 部署到互联网可访问的位置。') }}
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import {
  publishSimulation,
  getEmbedSummary,
  getShareCardUrl,
  getReplayGifUrl,
  getShareLandingUrl,
  getWatchUrl,
  getTranscriptMarkdownUrl,
  getTranscriptJsonUrl,
  getTrajectoryCsvUrl,
  getTrajectoryJsonlUrl,
  getFeedUrl,
  getSimulationOutcome,
  submitSimulationOutcome,
} from '../api/simulation'
import { tr } from '../i18n'

const translatePresetName = (name) => {
  const map = {
    'Compact': tr('Compact', '紧凑'),
    'Standard': tr('Standard', '标准'),
    'Wide': tr('Wide', '宽屏'),
  }
  return map[name] || name
}

const props = defineProps({
  open: { type: Boolean, default: false },
  simulationId: { type: String, required: true },
  initialPublic: { type: Boolean, default: false }
})

defineEmits(['close'])

const isPublic = ref(props.initialPublic)
const publishing = ref(false)
const publishError = ref('')

const togglePublic = async () => {
  const next = !isPublic.value
  publishing.value = true
  publishError.value = ''
  try {
    const res = await publishSimulation(props.simulationId, next)
    isPublic.value = res?.data?.is_public ?? next
  } catch (err) {
    publishError.value = err?.response?.data?.error || err?.message || tr('Publish failed', '发布失败')
  } finally {
    publishing.value = false
  }
}

const sizePresets = [
  { name: 'Compact', width: 480, height: 260 },
  { name: 'Standard', width: 640, height: 340 },
  { name: 'Wide', width: 800, height: 420 },
]

const activePreset = ref('Standard')
const theme = ref('light')
const copied = ref('')

const origin = computed(() => {
  if (typeof window === 'undefined') return ''
  return window.location.origin
})

const currentSize = computed(() => {
  return sizePresets.find(p => p.name === activePreset.value) || sizePresets[1]
})

const embedUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  const base = `${origin.value}/embed/${props.simulationId}`
  const params = new URLSearchParams()
  if (theme.value !== 'light') params.set('theme', theme.value)
  const query = params.toString()
  return query ? `${base}?${query}` : base
})

const iframeSnippet = computed(() => {
  const { width, height } = currentSize.value
  return `<iframe src="${embedUrl.value}" width="${width}" height="${height}" frameborder="0" loading="lazy" title="MiroShark simulation"></iframe>`
})

const markdownSnippet = computed(() => {
  if (!embedUrl.value) return ''
  return `[MiroShark simulation ↗](${embedUrl.value})`
})

const shareCardCacheBust = ref(0)

const shareCardUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  // Append a cache-bust token so re-opening the dialog after a state change
  // (e.g. resolution recorded) shows the freshly rendered card.
  const base = getShareCardUrl(props.simulationId, origin.value)
  return shareCardCacheBust.value
    ? `${base}?v=${shareCardCacheBust.value}`
    : base
})

const shareLandingUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getShareLandingUrl(props.simulationId, origin.value)
})

const watchUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getWatchUrl(props.simulationId, origin.value)
})

const replayGifUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  // Same cache-bust token as the share card so re-opens after a state
  // change pull the freshly rendered GIF instead of the stale cache.
  const base = getReplayGifUrl(props.simulationId, origin.value)
  return shareCardCacheBust.value
    ? `${base}?v=${shareCardCacheBust.value}`
    : base
})

const transcriptMarkdownUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getTranscriptMarkdownUrl(props.simulationId, origin.value)
})

const transcriptJsonUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getTranscriptJsonUrl(props.simulationId, origin.value)
})

const trajectoryCsvUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getTrajectoryCsvUrl(props.simulationId, origin.value)
})

const trajectoryJsonlUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getTrajectoryJsonlUrl(props.simulationId, origin.value)
})

// Public-gallery syndication URLs — independent of `simulationId` (the
// feed lists everyone's published runs), but kept on the embed dialog
// so an operator who just toggled their sim public can subscribe to the
// stream they're now part of in one click.
const feedAtomUrl = computed(() =>
  getFeedUrl({ format: 'atom', verified: false, origin: origin.value }),
)
const feedRssUrl = computed(() =>
  getFeedUrl({ format: 'rss', verified: false, origin: origin.value }),
)
const feedVerifiedAtomUrl = computed(() =>
  getFeedUrl({ format: 'atom', verified: true, origin: origin.value }),
)

const replayLoaded = ref(false)
const replayPlay = ref(false)
const onReplayLoad = () => {
  replayLoaded.value = true
}
const onReplayError = () => {
  // Image fails until the simulation publishes — the watch on isPublic
  // busts the cache once the operator toggles public on.
  replayLoaded.value = false
}
const startReplay = () => {
  replayPlay.value = true
}

const onShareCardError = () => {
  // The image fails until the simulation is published; once the operator
  // toggles public on, watch(isPublic) below busts the cache.
}

const previewStyle = computed(() => {
  const { width, height } = currentSize.value
  return {
    maxWidth: `${width}px`,
    aspectRatio: `${width} / ${height}`
  }
})

const iframeStyle = computed(() => ({
  width: '100%',
  height: '100%',
  border: 'none',
  borderRadius: '8px'
}))

const formatSimulationId = (id) => {
  if (!id) return ''
  const prefix = id.replace(/^sim_/, '').slice(0, 6)
  return `SIM_${prefix.toUpperCase()}`
}

const copy = async (which) => {
  let text = ''
  if (which === 'iframe') text = iframeSnippet.value
  else if (which === 'markdown') text = markdownSnippet.value
  else if (which === 'url') text = embedUrl.value
  else if (which === 'share') text = shareLandingUrl.value
  else if (which === 'card') text = shareCardUrl.value
  else if (which === 'replay') text = replayGifUrl.value
  else if (which === 'watch') text = watchUrl.value
  else if (which === 'transcriptMd') text = transcriptMarkdownUrl.value
  else if (which === 'trajectoryCsv') text = trajectoryCsvUrl.value
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copied.value = which
    setTimeout(() => {
      if (copied.value === which) copied.value = ''
    }, 1800)
  } catch (err) {
    // Fallback: select-able textarea
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch (_) {}
    document.body.removeChild(ta)
    copied.value = which
    setTimeout(() => {
      if (copied.value === which) copied.value = ''
    }, 1800)
  }
}

// ── Verified-prediction outcome submission ─────────────────────────────
const outcomeOptions = [
  { value: 'correct', label: tr('Called it', '命中'), icon: '📍' },
  { value: 'partial', label: tr('Partial', '部分命中'), icon: '◑' },
  { value: 'incorrect', label: tr('Called wrong', '判断错误'), icon: '⚠' },
]

const outcomeForm = reactive({
  label: '',
  outcome_url: '',
  outcome_summary: '',
})

const outcome = ref(null)
const outcomeSubmitting = ref(false)
const outcomeMessage = ref('')
const outcomeMessageClass = ref('')

const outcomeLabelText = (label) => {
  const opt = outcomeOptions.find((o) => o.value === label)
  return opt ? opt.label : label || ''
}

const _applyOutcomeToForm = (data) => {
  outcome.value = data || null
  if (data && data.label) {
    outcomeForm.label = data.label
    outcomeForm.outcome_url = data.outcome_url || ''
    outcomeForm.outcome_summary = data.outcome_summary || ''
  }
}

const _resetOutcomeForm = () => {
  outcomeForm.label = ''
  outcomeForm.outcome_url = ''
  outcomeForm.outcome_summary = ''
  outcome.value = null
  outcomeMessage.value = ''
  outcomeMessageClass.value = ''
}

const loadOutcome = async () => {
  try {
    const res = await getSimulationOutcome(props.simulationId)
    _applyOutcomeToForm(res?.data || null)
  } catch (err) {
    // 404 here means the simulation doesn't exist yet — surface nothing.
    outcome.value = null
  }
}

const submitOutcome = async () => {
  if (!isPublic.value || !outcomeForm.label) return
  outcomeSubmitting.value = true
  outcomeMessage.value = ''
  try {
    const res = await submitSimulationOutcome(props.simulationId, {
      label: outcomeForm.label,
      outcome_url: outcomeForm.outcome_url.trim(),
      outcome_summary: outcomeForm.outcome_summary.trim(),
    })
    if (res?.success && res.data) {
      _applyOutcomeToForm(res.data)
      outcomeMessage.value =
        tr('Outcome saved — your simulation is visible in the Verified filter.', '结果已保存 — 你的模拟现在「已验证」筛选中可见。')
      outcomeMessageClass.value = 'outcome-message-success'
    } else {
      outcomeMessage.value = res?.error || tr('Could not save outcome.', '无法保存结果。')
      outcomeMessageClass.value = 'outcome-message-error'
    }
  } catch (err) {
    outcomeMessage.value =
      err?.response?.data?.error || err?.message || tr('Could not save outcome.', '无法保存结果。')
    outcomeMessageClass.value = 'outcome-message-error'
  } finally {
    outcomeSubmitting.value = false
  }
}

watch(() => props.open, async (val) => {
  if (!val) return
  copied.value = ''
  // Reset the replay back to its paused poster state so each open
  // starts with a click-to-play affordance instead of immediately
  // pulling the GIF (which can be a few hundred KB).
  replayPlay.value = false
  replayLoaded.value = false
  _resetOutcomeForm()
  // Refresh public state when reopened — reflects external flips.
  try {
    const res = await getEmbedSummary(props.simulationId)
    if (typeof res?.data?.is_public === 'boolean') isPublic.value = res.data.is_public
  } catch (err) {
    if (err?.response?.status === 403) isPublic.value = false
  }
  // Always pull the saved outcome — the GET endpoint is publish-gate-free
  // so even private sims will reflect a previously recorded annotation.
  await loadOutcome()
  // Bust the share-card image cache so the preview reloads with whatever
  // state the simulation is in right now (resolution may have landed
  // since the dialog was last opened).
  shareCardCacheBust.value = Date.now()
})

// When the operator toggles public on, the share-card endpoint flips from
// 403 → 200. Bust the cache so the <img> retries instead of staying broken.
watch(isPublic, () => {
  shareCardCacheBust.value = Date.now()
})
</script>

<style scoped>
.embed-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.55);
  backdrop-filter: blur(4px);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  overflow-y: auto;
}

.embed-dialog {
  background: #ffffff;
  color: #0a0a0a;
  width: min(720px, 100%);
  max-height: calc(100vh - 40px);
  overflow-y: auto;
  border-radius: 14px;
  border: 1px solid rgba(10, 10, 10, 0.08);
  box-shadow: 0 24px 56px rgba(0, 0, 0, 0.25);
  padding: 22px 24px 20px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.embed-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.embed-dialog-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.005em;
}

.title-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: rgba(234, 88, 12, 0.12);
  color: #ea580c;
  font-size: 13px;
}

.title-sub {
  font-size: 11px;
  font-weight: 500;
  color: #6b6b6b;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  background: rgba(10, 10, 10, 0.04);
  border-radius: 999px;
}

.embed-dialog-close {
  background: transparent;
  border: none;
  font-size: 24px;
  line-height: 1;
  color: #6b6b6b;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}

.embed-dialog-close:hover {
  background: rgba(10, 10, 10, 0.05);
  color: #0a0a0a;
}

.embed-dialog-desc {
  font-size: 13px;
  color: #4b4b4b;
  margin: 6px 0 14px;
  line-height: 1.5;
}

.embed-size-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.embed-size-label {
  font-size: 12px;
  color: #6b6b6b;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.embed-size-buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.embed-size-btn {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 6px 12px;
  border: 1px solid rgba(10, 10, 10, 0.12);
  background: #ffffff;
  color: #0a0a0a;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s;
}

.embed-size-btn:hover {
  border-color: rgba(10, 10, 10, 0.3);
}

.embed-size-btn.active {
  background: #0a0a0a;
  color: #ffffff;
  border-color: #0a0a0a;
}

.embed-size-dim {
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.04em;
  opacity: 0.7;
}

.embed-theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 12px;
  color: #6b6b6b;
  font-weight: 500;
}

.embed-theme-select {
  background: #ffffff;
  color: #0a0a0a;
  border: 1px solid rgba(10, 10, 10, 0.12);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.embed-preview-wrap {
  background: repeating-linear-gradient(
    45deg,
    rgba(10, 10, 10, 0.03),
    rgba(10, 10, 10, 0.03) 10px,
    rgba(10, 10, 10, 0.06) 10px,
    rgba(10, 10, 10, 0.06) 20px
  );
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 10px;
  padding: 14px;
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.embed-preview-frame {
  width: 100%;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
}

.embed-snippets {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.snippet-block {
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 10px;
  overflow: hidden;
  background: rgba(10, 10, 10, 0.02);
}

.snippet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(10, 10, 10, 0.04);
  font-size: 11px;
  font-weight: 600;
  color: #6b6b6b;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.snippet-copy-btn {
  background: #0a0a0a;
  color: #ffffff;
  border: none;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: opacity 0.15s;
}

.snippet-copy-btn:hover { opacity: 0.85; }

.snippet-code {
  margin: 0;
  padding: 10px 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  line-height: 1.55;
  color: #1f1f1f;
  white-space: pre-wrap;
  word-break: break-all;
  background: transparent;
  max-height: 120px;
  overflow-y: auto;
}

.embed-dialog-hint {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(234, 88, 12, 0.06);
  border: 1px solid rgba(234, 88, 12, 0.2);
  border-radius: 8px;
  font-size: 12px;
  color: #4b4b4b;
  line-height: 1.5;
}

.hint-icon {
  flex-shrink: 0;
  color: #ea580c;
  font-weight: 700;
}

.embed-dialog-hint code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  padding: 1px 6px;
  background: rgba(10, 10, 10, 0.06);
  border-radius: 4px;
  font-size: 11px;
}

.share-card-section {
  margin-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.share-card-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #6b6b6b;
}

.share-card-divider .divider-line {
  flex: 1;
  height: 1px;
  background: rgba(10, 10, 10, 0.08);
}

.share-card-divider .divider-text {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.share-card-desc {
  font-size: 12.5px;
  color: #4b4b4b;
  margin: 0;
  line-height: 1.55;
}

.share-card-preview-wrap {
  background: repeating-linear-gradient(
    45deg,
    rgba(10, 10, 10, 0.03),
    rgba(10, 10, 10, 0.03) 10px,
    rgba(10, 10, 10, 0.06) 10px,
    rgba(10, 10, 10, 0.06) 20px
  );
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 10px;
  padding: 14px;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 140px;
}

.share-card-preview {
  width: 100%;
  max-width: 560px;
  aspect-ratio: 1200 / 630;
  border-radius: 8px;
  background: #fafafa;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
  object-fit: contain;
  display: block;
}

.share-card-empty {
  color: #6b6b6b;
  font-size: 13px;
  text-align: center;
  padding: 24px 18px;
  line-height: 1.55;
}

.share-card-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.share-snippet {
  margin: 0;
}

.share-download-btn {
  display: inline-flex;
  align-self: flex-start;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #0a0a0a;
  color: #ffffff;
  text-decoration: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background 0.15s;
}

.share-download-btn:hover {
  background: #2a2a2a;
}

.replay-section {
  margin-top: 18px;
  padding: 14px 16px;
  background: #0a0a0a;
  color: #fafafa;
  border-radius: 10px;
  border: 1px solid rgba(250, 250, 250, 0.08);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.replay-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.replay-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(234, 88, 12, 0.18);
  color: #ea580c;
  font-size: 11px;
  flex-shrink: 0;
  margin-top: 2px;
}

.replay-head-body {
  flex: 1;
  min-width: 0;
}

.replay-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #fafafa;
  margin-bottom: 4px;
}

.replay-sub {
  font-size: 12px;
  line-height: 1.5;
  color: rgba(250, 250, 250, 0.65);
}

.replay-preview-wrap {
  position: relative;
  width: 100%;
  max-width: 560px;
  align-self: center;
  aspect-ratio: 1200 / 630;
  border-radius: 8px;
  overflow: hidden;
  background: #18181a;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
  cursor: pointer;
}

.replay-preview {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.replay-preview-loaded { opacity: 1; }

.replay-preview-paused .replay-preview {
  filter: brightness(0.55);
}

.replay-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fafafa;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: linear-gradient(180deg, rgba(10, 10, 10, 0.15), rgba(10, 10, 10, 0.4));
  pointer-events: none;
}

.replay-overlay-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(234, 88, 12, 0.92);
  color: #fff;
  font-size: 22px;
  box-shadow: 0 6px 18px rgba(234, 88, 12, 0.4);
}

.replay-empty {
  color: rgba(250, 250, 250, 0.55);
  font-size: 13px;
  text-align: center;
  padding: 28px 18px;
  line-height: 1.55;
  border: 1px dashed rgba(250, 250, 250, 0.18);
  border-radius: 8px;
}

.replay-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.replay-section .snippet-block {
  background: rgba(250, 250, 250, 0.04);
  border-color: rgba(250, 250, 250, 0.08);
}

.replay-section .snippet-head {
  background: rgba(250, 250, 250, 0.06);
  color: rgba(250, 250, 250, 0.7);
}

.replay-section .snippet-code {
  color: rgba(250, 250, 250, 0.85);
}

.replay-section .snippet-copy-btn {
  background: #ea580c;
}

.transcript-section {
  margin-top: 18px;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.transcript-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.transcript-icon {
  font-size: 18px;
  line-height: 1;
  padding-top: 2px;
}

.transcript-head-body {
  flex: 1;
  min-width: 0;
}

.transcript-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0a0a0a;
  margin-bottom: 4px;
}

.transcript-sub {
  font-size: 12px;
  line-height: 1.5;
  color: #4a4a4a;
}

.transcript-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.transcript-download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #0a0a0a;
  color: #ffffff;
  text-decoration: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background 0.15s;
}

.transcript-download-btn:hover { background: #2a2a2a; }

.transcript-download-btn-secondary {
  background: #fff;
  color: #0a0a0a;
  border: 1px solid rgba(10, 10, 10, 0.18);
}

.transcript-download-btn-secondary:hover {
  background: rgba(10, 10, 10, 0.04);
}

.transcript-empty {
  font-size: 12px;
  color: #6b6b6b;
  font-style: italic;
}

.transcript-snippet {
  margin: 0;
}

.trajectory-section {
  margin-top: 14px;
}

.trajectory-quickstart {
  margin: 8px 0 0;
  font-size: 12px;
  color: #555;
  background: #f5f5f5;
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 6px;
  padding: 8px 10px;
  overflow-x: auto;
  white-space: nowrap;
}

.trajectory-quickstart code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: #2a2a2a;
}

/* Live watch page — distinct visual treatment (warm orange tint)
   to signal the broadcast/live framing vs. the finished-result
   share card above. Reuses the structural rules from the transcript
   section so the dialog feels consistent. */
.watch-section {
  margin-top: 18px;
  padding: 14px 16px;
  background: linear-gradient(180deg, rgba(234, 88, 12, 0.05) 0%, rgba(234, 88, 12, 0.02) 100%);
  border: 1px solid rgba(234, 88, 12, 0.18);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.watch-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.watch-icon {
  font-size: 18px;
  line-height: 1;
  padding-top: 2px;
}

.watch-head-body {
  flex: 1;
  min-width: 0;
}

.watch-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0a0a0a;
  margin-bottom: 4px;
}

.watch-sub {
  font-size: 12px;
  line-height: 1.5;
  color: #4a4a4a;
}

.watch-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.watch-open-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #ea580c;
  color: #ffffff;
  text-decoration: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background 0.15s;
}

.watch-open-btn:hover { background: #c2410c; }

.watch-empty {
  font-size: 12px;
  color: #6b6b6b;
  font-style: italic;
}

.watch-snippet {
  margin: 0;
}

.outcome-section {
  margin-top: 18px;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px dashed rgba(10, 10, 10, 0.18);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.outcome-section-live {
  background: rgba(255, 107, 26, 0.04);
  border-color: rgba(255, 107, 26, 0.3);
  border-style: solid;
}

.outcome-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.outcome-icon {
  font-size: 18px;
  line-height: 1;
  padding-top: 2px;
}

.outcome-head-body {
  flex: 1;
  min-width: 0;
}

.outcome-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0a0a0a;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.outcome-saved-tag {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: none;
  color: var(--color-orange, #ff6b1a);
  background: rgba(255, 107, 26, 0.1);
  padding: 2px 8px;
  border-radius: 999px;
}

.outcome-sub {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #4a4a4a;
}

.outcome-sub a {
  color: var(--color-orange, #ff6b1a);
  text-decoration: none;
  font-weight: 600;
}

.outcome-sub a:hover { text-decoration: underline; }

.outcome-fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.outcome-fields-disabled { opacity: 0.55; }

.outcome-radio-group {
  display: flex;
  gap: 6px;
  border: none;
  margin: 0;
  padding: 0;
  flex-wrap: wrap;
}

.outcome-radio {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid rgba(10, 10, 10, 0.16);
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  background: #fff;
  transition: border-color 0.15s, background 0.15s;
}

.outcome-radio input {
  appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1.5px solid rgba(10, 10, 10, 0.35);
  position: relative;
}

.outcome-radio input:checked {
  border-color: var(--color-orange, #ff6b1a);
  background: var(--color-orange, #ff6b1a);
  box-shadow: inset 0 0 0 2px #fff;
}

.outcome-radio-active {
  border-color: var(--color-orange, #ff6b1a);
  background: rgba(255, 107, 26, 0.08);
}

.outcome-radio-icon { font-family: sans-serif; }

.outcome-input,
.outcome-textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid rgba(10, 10, 10, 0.14);
  border-radius: 8px;
  font-size: 12.5px;
  font-family: inherit;
  background: #fff;
  color: #0a0a0a;
  resize: vertical;
}

.outcome-input:focus,
.outcome-textarea:focus {
  outline: none;
  border-color: var(--color-orange, #ff6b1a);
  box-shadow: 0 0 0 3px rgba(255, 107, 26, 0.12);
}

.outcome-input:disabled,
.outcome-textarea:disabled {
  background: rgba(10, 10, 10, 0.03);
  color: #6b6b6b;
  cursor: not-allowed;
}

.outcome-summary-counter {
  align-self: flex-end;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10.5px;
  color: #6b6b6b;
  margin-top: -4px;
}

.outcome-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.outcome-submit {
  padding: 8px 16px;
  background: var(--color-orange, #ff6b1a);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  cursor: pointer;
  transition: background 0.15s;
}

.outcome-submit:hover:not(:disabled) {
  background: #0a0a0a;
}

.outcome-submit:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.outcome-link {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  color: var(--color-orange, #ff6b1a);
  text-decoration: none;
  font-weight: 600;
}

.outcome-link:hover { text-decoration: underline; }

.outcome-message {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
  padding: 8px 10px;
  border-radius: 6px;
}

.outcome-message-success {
  background: rgba(67, 193, 101, 0.12);
  color: #1f6b35;
}

.outcome-message-error {
  background: rgba(255, 68, 68, 0.12);
  color: #b22020;
}

.gallery-callout {
  margin-top: 18px;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px dashed rgba(10, 10, 10, 0.18);
  border-radius: 10px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.gallery-callout-live {
  background: rgba(255, 107, 26, 0.06);
  border-color: rgba(255, 107, 26, 0.45);
  border-style: solid;
}

.gallery-callout-icon {
  font-size: 22px;
  line-height: 1;
  color: var(--color-orange, #ff6b1a);
  padding-top: 2px;
}

.gallery-callout-body {
  flex: 1;
  min-width: 0;
}

.gallery-callout-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0a0a0a;
  margin-bottom: 4px;
}

.gallery-callout-desc {
  font-size: 12.5px;
  line-height: 1.5;
  color: #4a4a4a;
}

.gallery-callout-desc a {
  color: var(--color-orange, #ff6b1a);
  text-decoration: none;
  font-weight: 600;
}

.gallery-callout-desc a:hover { text-decoration: underline; }

.gallery-callout-link {
  flex-shrink: 0;
  align-self: center;
  padding: 6px 12px;
  background: var(--color-orange, #ff6b1a);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  text-decoration: none;
  border-radius: 6px;
  white-space: nowrap;
  transition: background 0.15s ease;
}

.gallery-callout-link:hover {
  background: #0a0a0a;
}

/* RSS / Atom feed callout — same anatomy as the gallery callout but
   with a wraparound action row (three feed flavours). Reads as a
   secondary discovery affordance, not a primary action, so the chips
   are outline-styled rather than filled. */
.feed-callout {
  margin-top: 12px;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px dashed rgba(10, 10, 10, 0.18);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feed-callout-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.feed-callout-icon {
  font-size: 22px;
  line-height: 1;
  color: var(--color-orange, #ff6b1a);
  padding-top: 2px;
}

.feed-callout-body {
  flex: 1;
  min-width: 0;
}

.feed-callout-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0a0a0a;
  margin-bottom: 4px;
}

.feed-callout-desc {
  font-size: 12.5px;
  line-height: 1.5;
  color: #4a4a4a;
}

.feed-callout-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 34px;
}

.feed-callout-link {
  padding: 6px 12px;
  background: var(--color-orange, #ff6b1a);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  text-decoration: none;
  border-radius: 6px;
  white-space: nowrap;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.feed-callout-link:hover {
  background: #0a0a0a;
}

.feed-callout-link-secondary {
  background: transparent;
  color: var(--color-orange, #ff6b1a);
  border: 1px solid rgba(255, 107, 26, 0.45);
}

.feed-callout-link-secondary:hover {
  background: var(--color-orange, #ff6b1a);
  color: #fff;
  border-color: var(--color-orange, #ff6b1a);
}

.snippet-copy-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Transition */
.embed-dialog-enter-active,
.embed-dialog-leave-active {
  transition: opacity 0.2s ease;
}

.embed-dialog-enter-active .embed-dialog,
.embed-dialog-leave-active .embed-dialog {
  transition: transform 0.25s cubic-bezier(0.23, 1, 0.32, 1), opacity 0.25s ease;
}

.embed-dialog-enter-from,
.embed-dialog-leave-to { opacity: 0; }

.embed-dialog-enter-from .embed-dialog,
.embed-dialog-leave-to .embed-dialog {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}
</style>
