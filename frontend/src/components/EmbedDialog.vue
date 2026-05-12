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

            <!-- Twitter / X tweet thread — pairs with the share card
                 (visual), replay GIF (motion), transcript (prose), and
                 trajectory CSV (data) as the sixth share format. The
                 short-form text channel X/Twitter speaks natively. -->
            <div class="transcript-section thread-section">
              <div class="transcript-head">
                <span class="transcript-icon">🧵</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Tweet thread (X / Twitter)', '推文串(X / Twitter)') }}
                    <span v-if="threadTotal" class="thread-count-badge">{{ threadTotal }}</span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Auto-formatted thread — intro tweet, one tweet per belief inflection point (when the dominant stance flips), and a closing tweet with the watch + share URLs. Each tweet ≤280 characters; copy the whole thread or individual tweets.', '自动生成的推文串 — 介绍推文、每个信念转折点一条推文(主导立场翻转时)、末尾推文附带观看 + 分享 URL。每条推文 ≤280 字符;可复制整串或单条推文。') }}
                  </div>
                </div>
              </div>

              <div class="transcript-actions">
                <button
                  class="transcript-download-btn"
                  :disabled="!isPublic || threadLoading || !threadTweets.length"
                  @click="copy('threadFull')"
                >
                  <span v-if="threadLoading">{{ $tr('Loading…', '加载中…') }}</span>
                  <span v-else-if="copied === 'threadFull'">✓ {{ $tr('Copied', '已复制') }}</span>
                  <span v-else>📋 {{ $tr('Copy full thread', '复制整串') }}</span>
                </button>
                <a
                  v-if="isPublic && threadTxtUrl"
                  class="transcript-download-btn transcript-download-btn-secondary"
                  :href="threadTxtUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-thread.txt`"
                >
                  ↓ {{ $tr('Download .txt', '下载 .txt') }}
                </a>
                <a
                  v-if="isPublic && threadJsonUrl"
                  class="transcript-download-btn transcript-download-btn-secondary"
                  :href="threadJsonUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-thread.json`"
                >
                  ↓ .json
                </a>
                <span v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to enable the tweet thread.', '发布模拟以启用推文串。') }}
                </span>
              </div>

              <div v-if="isPublic && threadError" class="transcript-empty thread-error">
                {{ threadError }}
              </div>

              <div v-if="isPublic && threadTweets.length" class="thread-tweets-list">
                <div
                  v-for="(tweet, idx) in threadTweets"
                  :key="`thread-tweet-${idx}`"
                  class="thread-tweet"
                >
                  <button
                    class="thread-tweet-copy"
                    @click="copyOneTweet(idx)"
                    :title="$tr('Copy this tweet', '复制此推文')"
                  >
                    {{ copied === `threadOne-${idx}` ? '✓' : '⧉' }}
                  </button>
                  <span class="thread-tweet-num">{{ idx + 1 }} / {{ threadTweets.length }}</span>
                  <pre class="thread-tweet-body">{{ tweet }}</pre>
                  <span class="thread-tweet-len">{{ tweet.length }}/280</span>
                </div>
                <p v-if="threadTruncated" class="thread-truncated-note">
                  {{ $tr('Thread shortened — many inflections were folded into a single bridge tweet to keep the thread under 15 tweets.', '推文串已缩短 — 多个转折点被合并为一条桥接推文,以使整串保持在 15 条以内。') }}
                </p>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Thread .txt URL (paste into a tweet scheduler)', '推文串 .txt URL(粘贴至推文排程工具)') }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('threadTxt')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'threadTxt' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy URL', '复制 URL') }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ threadTxtUrl || '—' }}</code></pre>
              </div>
            </div>

            <!-- Inbound observability — per-share-surface request
                 counters. Pairs with the outbound webhook delivery log
                 so an operator running MiroShark for a DeFi fund or
                 research group has both directions of the distribution
                 loop visible from the same dialog. Collapsed by default
                 to keep the panel compact for users who only care about
                 the share / publish / outcome flow. -->
            <div class="transcript-section surface-stats-section">
              <div class="transcript-head surface-stats-head" @click="toggleSurfaceStats">
                <span class="transcript-icon">📊</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Distribution', '分发统计') }}
                    <span v-if="isPublic && surfaceStatsTotal > 0" class="surface-stats-total-badge">
                      {{ surfaceStatsTotal }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('How many times each share surface has been served — the inbound side of the distribution loop the webhook log tracks on the outbound side.', '每个分享面已被服务的次数 — 分发回路的入站侧,webhook 日志跟踪的是出站侧。') }}
                  </div>
                </div>
                <button
                  class="surface-stats-chevron"
                  :class="{ 'surface-stats-chevron-open': surfaceStatsExpanded }"
                  :aria-expanded="surfaceStatsExpanded"
                  type="button"
                >
                  ▾
                </button>
              </div>

              <div v-if="surfaceStatsExpanded" class="surface-stats-body">
                <div v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to see distribution stats.', '发布模拟以查看分发统计。') }}
                </div>
                <div v-else-if="surfaceStatsLoading" class="surface-stats-loading">
                  {{ $tr('Loading distribution data…', '加载分发数据…') }}
                </div>
                <div v-else-if="surfaceStatsError" class="transcript-empty surface-stats-error">
                  {{ surfaceStatsError }}
                </div>
                <div v-else-if="surfaceStatsAllZero" class="transcript-empty">
                  {{ $tr('No surface serves recorded yet — share this simulation to see distribution data appear here.', '尚未记录任何分享面服务 — 分享此模拟即可在此查看分发数据。') }}
                </div>
                <div v-else class="surface-stats-table">
                  <div
                    v-for="row in surfaceStatsRows"
                    :key="`stats-row-${row.key}`"
                    class="surface-stats-row"
                    :class="{ 'surface-stats-row-zero': row.count === 0 }"
                  >
                    <span class="surface-stats-label">{{ row.label }}</span>
                    <span class="surface-stats-count">{{ row.count }}</span>
                  </div>
                  <div class="surface-stats-row surface-stats-row-total">
                    <span class="surface-stats-label">{{ $tr('Total serves', '总服务数') }}</span>
                    <span class="surface-stats-count">{{ surfaceStatsTotal }}</span>
                  </div>
                </div>

                <div v-if="!surfaceStatsAllZero" class="surface-stats-caveat">
                  {{ $tr('Counts origin hits only — CDN and browser caches are not counted, so true audience reach is higher.', '仅统计源服务器命中 — 不计入 CDN 与浏览器缓存,实际受众覆盖更高。') }}
                </div>

                <div v-if="isPublic" class="surface-stats-actions">
                  <button
                    class="surface-stats-refresh"
                    type="button"
                    :disabled="surfaceStatsLoading"
                    @click="loadSurfaceStats"
                  >
                    <span v-if="surfaceStatsLoading">{{ $tr('Refreshing…', '刷新中…') }}</span>
                    <span v-else>↻ {{ $tr('Refresh', '刷新') }}</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Reproducibility config — citation primitive behind every
                 other share surface. Six surfaces (transcript, trajectory,
                 thread, watch, GIF, share card) make a finished sim
                 citable; this one carries the *parameters* a second
                 operator needs to re-run it. Lineage badge surfaces
                 fork / counterfactual parentage (when present) so a
                 reader knows "this run is a counterfactual branch of
                 sim_X at round 12" without reading the diff. Collapsed
                 by default to keep the dialog compact. -->
            <div class="transcript-section repro-section">
              <div class="transcript-head repro-head" @click="toggleRepro">
                <span class="transcript-icon">🔬</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Reproducibility config', '可复现配置') }}
                    <span
                      v-if="reproLineageBadge"
                      class="repro-lineage-badge"
                      :title="reproLineageTitle"
                    >
                      {{ reproLineageBadge }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Every parameter another researcher needs to reproduce this exact run — scenario, agents, rounds, platforms, time-config, director events, fork lineage. Citation-friendly JSON.', '另一位研究者复现此运行所需的全部参数 — 情景、智能体、轮次、平台、时序配置、导演事件、派生谱系。便于引用的 JSON。') }}
                  </div>
                </div>
                <button
                  class="repro-chevron"
                  :class="{ 'repro-chevron-open': reproExpanded }"
                  :aria-expanded="reproExpanded"
                  type="button"
                >
                  ▾
                </button>
              </div>

              <div v-if="reproExpanded" class="repro-body">
                <div v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to expose the reproducibility config.', '发布模拟以公开可复现配置。') }}
                </div>
                <div v-else-if="reproLoading" class="repro-loading">
                  {{ $tr('Loading reproduction blob…', '加载复现配置…') }}
                </div>
                <div v-else-if="reproError" class="transcript-empty repro-error">
                  {{ reproError }}
                </div>
                <div v-else-if="reproBlob" class="repro-detail">
                  <div class="repro-summary-grid">
                    <div class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Schema', 'Schema') }}</span>
                      <span class="repro-summary-value">v{{ reproBlob.schema_version }}</span>
                    </div>
                    <div class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Agents', '智能体数') }}</span>
                      <span class="repro-summary-value">{{ reproBlob.agent_count }}</span>
                    </div>
                    <div class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Rounds', '轮次') }}</span>
                      <span class="repro-summary-value">{{ reproBlob.total_rounds }}</span>
                    </div>
                    <div class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Platforms', '平台') }}</span>
                      <span class="repro-summary-value">{{ reproPlatformsLabel }}</span>
                    </div>
                    <div v-if="reproDirectorEventCount > 0" class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Director events', '导演事件') }}</span>
                      <span class="repro-summary-value">{{ reproDirectorEventCount }}</span>
                    </div>
                    <div v-if="reproBlob.lineage && reproBlob.lineage.kind !== 'original'" class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Lineage', '谱系') }}</span>
                      <span class="repro-summary-value">{{ reproLineageDescription }}</span>
                    </div>
                  </div>

                  <div class="repro-curl-block">
                    <div class="repro-curl-head">
                      <span class="repro-curl-label">{{ $tr('Reproduce via curl', '使用 curl 复现') }}</span>
                      <button class="snippet-copy-btn" @click="copy('reproCurl')">
                        {{ copied === 'reproCurl' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy', '复制') }}
                      </button>
                    </div>
                    <pre class="snippet-code"><code>{{ reproCurlSnippet }}</code></pre>
                  </div>

                  <div class="repro-note">
                    {{ $tr('Anyone with this config has every parameter that shapes the run — same scenario, same agent count, same rounds, same platform mix. Identical exports of a finished sim are bytewise-identical, so the file hash is a stable citation key.', '获得此配置的任何人都拥有决定该运行的所有参数 — 相同情景、相同智能体数、相同轮次、相同平台组合。已完成模拟的多次导出在字节级别完全一致,因此文件哈希可作为稳定的引用键。') }}
                  </div>
                </div>

                <div v-if="isPublic" class="repro-actions">
                  <a
                    v-if="reproDownloadUrl"
                    class="repro-download"
                    :href="reproDownloadUrl"
                    :download="reproDownloadFilename"
                    target="_blank"
                    rel="noopener"
                  >
                    {{ $tr('Download reproduce.json', '下载 reproduce.json') }}
                  </a>
                  <button
                    class="snippet-copy-btn repro-copy-url"
                    type="button"
                    @click="copy('reproUrl')"
                    :disabled="!reproDownloadUrl"
                  >
                    {{ copied === 'reproUrl' ? '✓ ' + $tr('URL copied', '已复制 URL') : $tr('Copy URL', '复制 URL') }}
                  </button>
                  <button
                    class="surface-stats-refresh repro-refresh"
                    type="button"
                    :disabled="reproLoading"
                    @click="loadRepro"
                  >
                    <span v-if="reproLoading">{{ $tr('Refreshing…', '刷新中…') }}</span>
                    <span v-else>↻ {{ $tr('Refresh', '刷新') }}</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Jupyter notebook export — analysis-ready surface paired
                 with the reproducibility config. The repro blob is
                 "here is the data"; this notebook is "here is the
                 analysis, ready to run". Trajectory CSV is embedded
                 directly so the notebook runs air-gapped (no network
                 call back to the MiroShark host). Same publish gate as
                 every other share surface. The body is a pure download
                 surface — there's no inline preview because the .ipynb
                 is a 30+ KB JSON document the SPA shouldn't pull just
                 to render a button. -->
            <div class="transcript-section notebook-section">
              <div class="transcript-head notebook-head">
                <span class="transcript-icon">📓</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Jupyter notebook', 'Jupyter 笔记本') }}
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Pre-populated analysis notebook — trajectory data embedded, belief evolution + final consensus charts scaffolded, ready to run in JupyterLab, VS Code, or Colab. No network call back required.', '预填的分析笔记本 — 嵌入轨迹数据,已搭建信念演化与最终共识图表,可在 JupyterLab、VS Code 或 Colab 中直接运行,无需联网。') }}
                  </div>
                </div>
              </div>

              <div class="notebook-body">
                <div v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to enable the Jupyter notebook export.', '发布模拟以启用 Jupyter 笔记本导出。') }}
                </div>
                <template v-else>
                  <div class="repro-curl-block">
                    <div class="repro-curl-head">
                      <span class="repro-curl-label">{{ $tr('Download via curl', '使用 curl 下载') }}</span>
                      <button class="snippet-copy-btn" @click="copy('notebookCurl')">
                        {{ copied === 'notebookCurl' ? '✓ ' + $tr('Copied', '已复制') : $tr('Copy', '复制') }}
                      </button>
                    </div>
                    <pre class="snippet-code"><code>{{ notebookCurlSnippet }}</code></pre>
                  </div>
                  <div class="repro-note">
                    {{ $tr('Identical exports of a finished simulation produce bytewise-identical notebooks — the file hash is a stable citation key, same property the reproduce.json blob has. Opens directly in JupyterLab, VS Code, and Google Colab.', '已完成模拟的多次导出在字节级别完全一致 — 文件哈希可作为稳定的引用键,与 reproduce.json 一致。可直接在 JupyterLab、VS Code 与 Google Colab 中打开。') }}
                  </div>
                  <div class="repro-actions">
                    <a
                      v-if="notebookDownloadUrl"
                      class="repro-download"
                      :href="notebookDownloadUrl"
                      :download="notebookDownloadFilename"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ $tr('Download notebook.ipynb', '下载 notebook.ipynb') }}
                    </a>
                    <button
                      class="snippet-copy-btn repro-copy-url"
                      type="button"
                      @click="copy('notebookUrl')"
                      :disabled="!notebookDownloadUrl"
                    >
                      {{ copied === 'notebookUrl' ? '✓ ' + $tr('URL copied', '已复制 URL') : $tr('Copy URL', '复制 URL') }}
                    </button>
                  </div>
                </template>
              </div>
            </div>

            <!-- Lineage navigator — closes the navigation gap PR #75
                 (reproducibility config) left behind. The
                 `parent_simulation_id` pointer existed on disk but was
                 one-directional (a child knew its parent, the parent
                 had no visibility into its children). This section
                 surfaces both directions: a Parent row when the sim
                 was forked / branched, and a Children list of every
                 public simulation whose parent points back at this
                 one. Hidden entirely for original sims with no forks
                 (the common case) so the dialog stays compact. -->
            <div
              v-if="hasLineageGraph"
              class="transcript-section lineage-section"
            >
              <div class="transcript-head lineage-head" @click="toggleLineage">
                <span class="transcript-icon">🌳</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Lineage', '谱系') }}
                    <span class="lineage-count-chip" v-if="lineageTotalChildren > 0">
                      {{ lineageTotalChildren }}
                      {{ lineageTotalChildren === 1
                          ? $tr('branch', '分支')
                          : $tr('branches', '分支') }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Navigate the fork / counterfactual graph this simulation belongs to. Click a row to open that sim in a new tab.', '浏览此模拟所属的派生 / 反事实分支图。点击任意行可在新标签页中打开对应模拟。') }}
                  </div>
                </div>
                <button
                  class="repro-chevron lineage-chevron"
                  :class="{ 'repro-chevron-open': lineageExpanded }"
                  :aria-expanded="lineageExpanded"
                  type="button"
                >
                  ▾
                </button>
              </div>

              <div v-if="lineageExpanded" class="lineage-body">
                <div v-if="lineageLoading" class="repro-loading">
                  {{ $tr('Loading lineage…', '加载谱系中…') }}
                </div>
                <div v-else-if="lineageError" class="transcript-empty repro-error">
                  {{ lineageError }}
                </div>
                <div v-else>
                  <!-- Parent row — shown when this sim was forked or
                       branched from another sim. Public parents render
                       as a click-through; unpublished parents render
                       the bare id without the link. -->
                  <div v-if="lineageParent" class="lineage-parent-row">
                    <div class="lineage-row-arrow">↑</div>
                    <div class="lineage-row-body">
                      <div class="lineage-row-head">
                        <span class="lineage-row-tag">{{ $tr('Parent', '父级') }}</span>
                        <span
                          class="lineage-row-id"
                          :title="lineageParent.simulation_id"
                        >
                          {{ truncateSimId(lineageParent.simulation_id) }}
                        </span>
                      </div>
                      <div
                        v-if="lineageParent.scenario_preview"
                        class="lineage-row-scenario"
                      >
                        {{ lineageParent.scenario_preview }}
                      </div>
                      <div v-else class="lineage-row-private">
                        {{ $tr('Parent simulation is unpublished.', '父级模拟未发布。') }}
                      </div>
                      <a
                        v-if="parentWatchUrl"
                        :href="parentWatchUrl"
                        target="_blank"
                        rel="noopener"
                        class="lineage-row-link"
                      >
                        {{ $tr('Open parent ↗', '打开父级 ↗') }}
                      </a>
                    </div>
                  </div>

                  <!-- Children list — every public sim whose
                       parent_simulation_id points at this one. Sorted
                       oldest fork first (natural narrative order). -->
                  <div v-if="lineageChildren.length > 0" class="lineage-children">
                    <div class="lineage-children-head">
                      <span class="lineage-row-arrow">↓</span>
                      <span class="lineage-row-tag">
                        {{ lineageTotalChildren === 1
                            ? $tr('Child', '子级')
                            : $tr('Children', '子级') }}
                      </span>
                      <span
                        v-if="lineageChildren.length < lineageTotalChildren"
                        class="lineage-truncated-note"
                      >
                        {{ $tr('Showing first', '显示前') }}
                        {{ lineageChildren.length }}
                        {{ $tr('of', '/共') }}
                        {{ lineageTotalChildren }}
                      </span>
                    </div>
                    <a
                      v-for="child in lineageChildren"
                      :key="child.simulation_id"
                      class="lineage-child-row"
                      :href="childWatchUrl(child)"
                      target="_blank"
                      rel="noopener"
                    >
                      <span
                        class="lineage-child-badge"
                        :class="{
                          'lineage-child-badge-fork': child.kind === 'fork',
                          'lineage-child-badge-cf': child.kind === 'counterfactual',
                        }"
                      >
                        {{ formatChildKindBadge(child) }}
                      </span>
                      <span class="lineage-child-body">
                        <span
                          class="lineage-row-id"
                          :title="child.simulation_id"
                        >
                          {{ truncateSimId(child.simulation_id) }}
                        </span>
                        <span class="lineage-row-scenario">
                          {{ formatChildScenarioPreview(child) }}
                        </span>
                      </span>
                      <span class="lineage-child-cta">↗</span>
                    </a>
                  </div>

                  <div class="lineage-actions">
                    <button
                      class="surface-stats-refresh lineage-refresh"
                      type="button"
                      :disabled="lineageLoading"
                      @click="loadLineage"
                    >
                      <span v-if="lineageLoading">{{ $tr('Refreshing…', '刷新中…') }}</span>
                      <span v-else>↻ {{ $tr('Refresh', '刷新') }}</span>
                    </button>
                  </div>
                </div>
              </div>
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

            <!-- Webhook delivery history — every Zapier / Make / n8n /
                 Slack / Discord integration built on top of the outbound
                 completion webhook (PR #46) needs a feedback loop so the
                 operator can verify it fired. Reads the last 10 entries
                 from <sim_dir>/webhook-log.jsonl. Admin-token gated
                 server-side; the panel shows a "configure first" hint
                 instead of a hard error when the token is unset. -->
            <div class="webhook-log-section">
              <div class="webhook-log-head">
                <span class="webhook-log-icon">📡</span>
                <div class="webhook-log-head-body">
                  <div class="webhook-log-title">
                    {{ $tr('Webhook delivery history', 'Webhook 投递历史') }}
                    <span v-if="webhookLogTotal > 0" class="webhook-log-count">
                      {{ webhookLogTotal }} {{ webhookLogTotal === 1 ? $tr('attempt', '次') : $tr('attempts', '次') }}
                    </span>
                  </div>
                  <div class="webhook-log-sub">
                    {{ $tr('Auto-fires on simulation completion. Records the last 50 attempts on disk so a delivery failure is visible without checking server logs.', '在模拟完成时自动触发。最多在磁盘上保留 50 次投递记录,无需查看服务器日志即可发现失败。') }}
                  </div>
                </div>
                <button
                  class="webhook-log-toggle"
                  @click="toggleWebhookLog"
                  :title="webhookLogExpanded ? $tr('Hide history', '隐藏历史') : $tr('Show history', '显示历史')"
                >
                  {{ webhookLogExpanded ? '▾' : '▸' }}
                </button>
              </div>

              <div v-if="webhookLogExpanded" class="webhook-log-body">
                <div v-if="webhookLogLoading" class="webhook-log-loading">
                  {{ $tr('Loading delivery history…', '正在加载投递历史…') }}
                </div>

                <div v-else-if="webhookLogConfigError" class="webhook-log-config-hint">
                  {{ $tr('Admin authentication is not configured on this deployment. Set MIROSHARK_ADMIN_TOKEN to enable the delivery log.', '此部署未配置管理员身份验证。设置 MIROSHARK_ADMIN_TOKEN 以启用投递日志。') }}
                </div>

                <div v-else-if="webhookLogError" class="webhook-log-error">
                  {{ webhookLogError }}
                </div>

                <div v-else-if="webhookLogEntries.length === 0" class="webhook-log-empty">
                  {{ $tr('No deliveries recorded yet. The webhook fires automatically on simulation completion.', '暂无投递记录。Webhook 会在模拟完成时自动触发。') }}
                </div>

                <ul v-else class="webhook-log-list">
                  <li
                    v-for="entry in webhookLogEntries"
                    :key="entry.attempt"
                    class="webhook-log-row"
                    :class="webhookEntryClass(entry)"
                  >
                    <span class="webhook-log-row-icon">{{ webhookEntryIcon(entry) }}</span>
                    <span class="webhook-log-row-attempt">#{{ entry.attempt }}</span>
                    <span class="webhook-log-row-code">{{ webhookEntryCode(entry) }}</span>
                    <span class="webhook-log-row-latency">{{ formatLatency(entry.latency_ms) }}</span>
                    <span class="webhook-log-row-trigger">{{ entry.trigger || '—' }}</span>
                    <span class="webhook-log-row-time" :title="entry.timestamp || ''">
                      {{ formatLogTime(entry.timestamp) }}
                    </span>
                  </li>
                </ul>

                <div class="webhook-log-actions">
                  <button
                    class="webhook-log-refresh"
                    @click="loadWebhookLog"
                    :disabled="webhookLogLoading"
                  >
                    {{ $tr('Refresh', '刷新') }}
                  </button>
                  <button
                    class="webhook-log-retry"
                    @click="retryWebhook"
                    :disabled="webhookRetrying || !canRetryWebhook"
                    :title="canRetryWebhook ? $tr('Re-fire the webhook with the same payload', '使用相同 payload 重发 webhook') : $tr('Retry available after the simulation reaches a terminal state', '模拟到达终止状态后可重试')"
                  >
                    <span v-if="webhookRetrying">{{ $tr('Queueing…', '排队中…') }}</span>
                    <span v-else>{{ $tr('Retry delivery', '重试投递') }}</span>
                  </button>
                </div>

                <div v-if="webhookRetryMessage" class="webhook-log-message" :class="webhookRetryMessageClass">
                  {{ webhookRetryMessage }}
                </div>

                <!-- Signature verification hint — appears once a delivery has
                     succeeded so the operator has proof the basic wire works
                     before being asked to layer signing on top. Shows the
                     env var NAME only (`WEBHOOK_SECRET`); the actual secret
                     value is never echoed by the frontend, the API, or the
                     delivery log. Collapsed by default to keep the dialog
                     compact for users on the unsigned default path. -->
                <div
                  v-if="hasSuccessfulWebhookDelivery"
                  class="signature-hint"
                  :class="{ 'signature-hint-open': signatureHintExpanded }"
                >
                  <button
                    class="signature-hint-toggle"
                    @click="toggleSignatureHint"
                    :title="signatureHintExpanded ? $tr('Hide signature verification hint', '隐藏签名验证提示') : $tr('Show signature verification hint', '显示签名验证提示')"
                  >
                    <span class="signature-hint-icon">🔐</span>
                    <span class="signature-hint-title">
                      {{ $tr('Verify webhook signatures', '验证 webhook 签名') }}
                    </span>
                    <span class="signature-hint-chevron">{{ signatureHintExpanded ? '▾' : '▸' }}</span>
                  </button>
                  <div v-if="signatureHintExpanded" class="signature-hint-body">
                    <p class="signature-hint-line">
                      {{ $tr(
                        'Set the WEBHOOK_SECRET environment variable on this MiroShark instance and MiroShark will HMAC-sign every dispatch with an X-MiroShark-Signature header. Recipients verify with three lines of stdlib hmac — same scheme Stripe and GitHub use.',
                        '在这台 MiroShark 实例上设置 WEBHOOK_SECRET 环境变量,MiroShark 就会用 HMAC 对每一次投递签名,并通过 X-MiroShark-Signature 头部送出。消费方用三行 stdlib hmac 即可校验 — Stripe 和 GitHub 用的就是同一套。'
                      ) }}
                    </p>
                    <code class="signature-hint-code">WEBHOOK_SECRET=&lt;your 32+ char secret&gt;</code>
                    <p class="signature-hint-line">
                      <a
                        href="https://github.com/aaronjmars/MiroShark/blob/main/docs/WEBHOOKS.md#verifying-webhook-signatures"
                        target="_blank"
                        rel="noopener"
                      >{{ $tr('Verification snippets (Python / Node.js / curl)', '验证示例(Python / Node.js / curl)') }} ↗</a>
                    </p>
                  </div>
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
  getThreadTxtUrl,
  getThreadJsonUrl,
  getSurfaceStats,
  getReproductionUrl,
  getReproduction,
  getNotebookUrl,
  getSimulationLineage,
  getFeedUrl,
  getSimulationOutcome,
  submitSimulationOutcome,
  getWebhookLog,
  retryWebhookDelivery,
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

const threadTxtUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getThreadTxtUrl(props.simulationId, origin.value)
})

const threadJsonUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getThreadJsonUrl(props.simulationId, origin.value)
})

// ── Tweet thread state ──────────────────────────────────────────────────
// We fetch the structured (JSON) form on first reveal so per-tweet copy
// buttons have the exact text without re-splitting the .txt body — the
// .txt URL is still exposed in the snippet block for users who want to
// paste it into a Twitter scheduling tool.
const threadTweets = ref([])
const threadTotal = ref(0)
const threadTruncated = ref(false)
const threadLoading = ref(false)
const threadError = ref('')

const loadThread = async () => {
  if (!props.simulationId || !isPublic.value) {
    threadTweets.value = []
    threadTotal.value = 0
    threadTruncated.value = false
    return
  }
  threadLoading.value = true
  threadError.value = ''
  try {
    const url = threadJsonUrl.value
    if (!url) return
    const res = await fetch(url, { credentials: 'omit', cache: 'no-store' })
    if (!res.ok) {
      threadError.value =
        res.status === 403
          ? tr('Publish the simulation to enable the tweet thread.', '发布模拟以启用推文串。')
          : `${tr('Could not load thread', '无法加载推文串')} (HTTP ${res.status})`
      threadTweets.value = []
      threadTotal.value = 0
      threadTruncated.value = false
      return
    }
    const data = await res.json()
    threadTweets.value = Array.isArray(data?.tweets) ? data.tweets : []
    threadTotal.value = Number(data?.total || threadTweets.value.length)
    threadTruncated.value = !!data?.truncated
  } catch (err) {
    threadError.value =
      err?.message || tr('Could not load thread', '无法加载推文串')
    threadTweets.value = []
    threadTotal.value = 0
    threadTruncated.value = false
  } finally {
    threadLoading.value = false
  }
}

// ── Surface-stats state ────────────────────────────────────────────────
// The first inbound observability surface — pairs with the outbound
// webhook delivery log. Counters live in `<sim_dir>/surface-stats.json`
// and are incremented by every successful `_serve_X` handler. The
// panel is collapsed by default to keep the dialog compact for users
// who only care about the share / publish / outcome flow.
const surfaceStatsExpanded = ref(false)
const surfaceStatsLoading = ref(false)
const surfaceStatsError = ref('')
const surfaceStats = ref(null)

const SURFACE_STAT_LABELS = [
  { key: 'share_card', label: tr('Share card · PNG', '分享卡片 · PNG') },
  { key: 'replay_gif', label: tr('Replay GIF', '回放 GIF') },
  { key: 'transcript_md', label: tr('Transcript · Markdown', '记录 · Markdown') },
  { key: 'transcript_json', label: tr('Transcript · JSON', '记录 · JSON') },
  { key: 'trajectory_csv', label: tr('Trajectory · CSV', '轨迹 · CSV') },
  { key: 'trajectory_jsonl', label: tr('Trajectory · JSONL', '轨迹 · JSONL') },
  { key: 'thread_txt', label: tr('Tweet thread · TXT', '推文串 · TXT') },
  { key: 'thread_json', label: tr('Tweet thread · JSON', '推文串 · JSON') },
  { key: 'watch_page', label: tr('Watch page', '观看页面') },
  { key: 'feed_atom', label: tr('Atom feed', 'Atom 源') },
  { key: 'feed_rss', label: tr('RSS feed', 'RSS 源') },
  { key: 'reproduce_json', label: tr('Reproduce config · JSON', '可复现配置 · JSON') },
  { key: 'lineage', label: tr('Lineage graph', '谱系图') },
  { key: 'notebook_ipynb', label: tr('Jupyter notebook · IPYNB', 'Jupyter 笔记本 · IPYNB') },
]

const surfaceStatsRows = computed(() => {
  const stats = surfaceStats.value || {}
  return SURFACE_STAT_LABELS
    .map((row) => ({ ...row, count: Number(stats[row.key] || 0) }))
    .sort((a, b) => b.count - a.count || a.key.localeCompare(b.key))
})

const surfaceStatsTotal = computed(() => {
  if (!surfaceStats.value) return 0
  return Number(surfaceStats.value.total || 0)
})

const surfaceStatsAllZero = computed(() => {
  if (!surfaceStats.value) return true
  return surfaceStatsTotal.value === 0
})

const loadSurfaceStats = async () => {
  if (!props.simulationId || !isPublic.value) {
    surfaceStats.value = null
    return
  }
  surfaceStatsLoading.value = true
  surfaceStatsError.value = ''
  try {
    const res = await getSurfaceStats(props.simulationId)
    if (res?.success && res.stats) {
      surfaceStats.value = res.stats
    } else if (res?.data?.stats) {
      surfaceStats.value = res.data.stats
    } else {
      surfaceStats.value = null
      surfaceStatsError.value = res?.error
        || tr('Could not load distribution stats.', '无法加载分发统计。')
    }
  } catch (err) {
    if (err?.response?.status === 403) {
      surfaceStatsError.value = tr(
        'Publish the simulation to see distribution stats.',
        '发布模拟以查看分发统计。',
      )
    } else {
      surfaceStatsError.value = err?.response?.data?.error
        || err?.message
        || tr('Could not load distribution stats.', '无法加载分发统计。')
    }
    surfaceStats.value = null
  } finally {
    surfaceStatsLoading.value = false
  }
}

const toggleSurfaceStats = () => {
  surfaceStatsExpanded.value = !surfaceStatsExpanded.value
  if (surfaceStatsExpanded.value && !surfaceStats.value) {
    loadSurfaceStats()
  }
}

// ── Reproducibility config state ───────────────────────────────────────
// The citation primitive behind every other share surface. The blob
// is a v1-schema JSON document carrying every parameter another
// operator would need to re-run the same simulation (scenario, agent
// count, rounds, platforms, time-config, director events, lineage).
// Same publish gate as the other share surfaces. Collapsed by default
// so a viewer who only cares about share / publish / outcome doesn't
// pay the network round-trip on every dialog open.
const reproExpanded = ref(false)
const reproLoading = ref(false)
const reproError = ref('')
const reproBlob = ref(null)

const reproDownloadUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getReproductionUrl(props.simulationId, origin.value)
})

const reproDownloadFilename = computed(() => {
  if (!props.simulationId) return 'reproduce.json'
  return `miroshark-${props.simulationId.slice(0, 12)}-reproduce.json`
})

const reproPlatformsLabel = computed(() => {
  const p = reproBlob.value?.platforms
  if (!p) return ''
  const parts = []
  if (p.twitter) parts.push(tr('Twitter', 'Twitter'))
  if (p.reddit) parts.push(tr('Reddit', 'Reddit'))
  if (p.polymarket) {
    const count = Number(p.polymarket_market_count || 1)
    parts.push(`${tr('Polymarket', 'Polymarket')} ×${count}`)
  }
  return parts.length
    ? parts.join(' · ')
    : tr('No platforms enabled', '未启用平台')
})

const reproDirectorEventCount = computed(() => {
  const events = reproBlob.value?.director_events
  return Array.isArray(events) ? events.length : 0
})

const reproLineageBadge = computed(() => {
  const lineage = reproBlob.value?.lineage
  if (!lineage) return ''
  if (lineage.kind === 'fork') return tr('🪐 Forked', '🪐 派生')
  if (lineage.kind === 'counterfactual') return tr('🔀 Counterfactual', '🔀 反事实')
  return ''
})

const reproLineageDescription = computed(() => {
  const lineage = reproBlob.value?.lineage
  if (!lineage || lineage.kind === 'original') return ''
  const parent = lineage.parent_simulation_id
    ? lineage.parent_simulation_id.slice(0, 12)
    : ''
  if (lineage.kind === 'fork') {
    return tr('Forked from ', '派生自 ') + parent
  }
  // Counterfactual — surface the trigger round and label so the
  // reader sees "Counterfactual branch of sim_X at round 12 (ceo_resigns)"
  // without opening the parent.
  const cf = lineage.counterfactual || {}
  const round = Number.isInteger(cf.trigger_round) ? cf.trigger_round : '?'
  const label = cf.label
    ? ` (${cf.label})`
    : ''
  return tr('Counterfactual of ', '反事实分支自 ')
    + parent
    + tr(' at round ', ' · 第 ')
    + round
    + tr('', ' 轮')
    + label
})

const reproLineageTitle = computed(() => {
  // Tooltip seen on hover — full parent ID, not the truncated 12-char
  // version, so the operator can grab the canonical sim id for
  // /share/<id> or /watch/<id>.
  const lineage = reproBlob.value?.lineage
  if (!lineage || lineage.kind === 'original') {
    return tr(
      'Original simulation — no parent run.',
      '原始模拟 — 无父运行。',
    )
  }
  const parent = lineage.parent_simulation_id || '?'
  if (lineage.kind === 'fork') {
    return tr('Fork of ', '派生自 ') + parent
  }
  return tr('Counterfactual branch of ', '反事实分支自 ') + parent
})

const reproCurlSnippet = computed(() => {
  if (!reproDownloadUrl.value) return ''
  // Plain curl that produces the same blob the Download button does —
  // suitable for paper-appendix screenshots and Jupyter notebook
  // quickstarts. ``-fsSL`` keeps the snippet quiet on success and
  // forwards redirects (the production deploy may sit behind a CDN
  // that issues a 308 to the canonical host).
  return `curl -fsSL '${reproDownloadUrl.value}' -o reproduce.json`
})

// ── Notebook export state ──────────────────────────────────────────────
// Pre-populated Jupyter notebook download — sits beneath the
// reproducibility config because both are institution-targeted: the
// repro blob is "here is the data", the notebook is "here is the
// analysis, ready to run". Pure download surface — there is no parsed
// preview because the .ipynb body is a 30 KB+ JSON document the SPA
// shouldn't pull just to render a button.
const notebookDownloadUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getNotebookUrl(props.simulationId, origin.value)
})

const notebookDownloadFilename = computed(() => {
  if (!props.simulationId) return 'notebook.ipynb'
  return `miroshark-${props.simulationId.slice(0, 12)}-notebook.ipynb`
})

const notebookCurlSnippet = computed(() => {
  if (!notebookDownloadUrl.value) return ''
  return `curl -fsSL '${notebookDownloadUrl.value}' -o ${notebookDownloadFilename.value}`
})

const loadRepro = async () => {
  if (!props.simulationId || !isPublic.value) {
    reproBlob.value = null
    return
  }
  reproLoading.value = true
  reproError.value = ''
  try {
    const res = await getReproduction(props.simulationId)
    // The endpoint returns the blob directly (no {success, data}
    // wrapper) — the axios client already unwraps the JSON body.
    if (res && typeof res === 'object' && res.schema_version) {
      reproBlob.value = res
    } else if (res && res.data && typeof res.data === 'object') {
      // Defensive — handle a future enveloping change without
      // breaking the panel.
      reproBlob.value = res.data
    } else {
      reproBlob.value = null
      reproError.value = tr(
        'Could not parse the reproduction config.',
        '无法解析复现配置。',
      )
    }
  } catch (err) {
    if (err?.response?.status === 403) {
      reproError.value = tr(
        'Publish the simulation to expose the reproducibility config.',
        '发布模拟以公开可复现配置。',
      )
    } else if (err?.response?.status === 404) {
      reproError.value = tr(
        'Simulation not found.',
        '未找到模拟。',
      )
    } else {
      reproError.value = err?.response?.data?.error
        || err?.message
        || tr('Could not load the reproduction config.', '无法加载复现配置。')
    }
    reproBlob.value = null
  } finally {
    reproLoading.value = false
  }
}

const toggleRepro = () => {
  reproExpanded.value = !reproExpanded.value
  if (reproExpanded.value && !reproBlob.value && !reproError.value) {
    loadRepro()
  }
}

// ── Lineage navigator state ────────────────────────────────────────────
// Reverse pointer over the same `parent_simulation_id` data the
// reproducibility blob carries. The reproduce.json export tells a
// reader where this sim came from; the lineage panel tells them where
// it went — every public child whose `parent_simulation_id` matches.
// Same publish gate as the share / repro endpoints. Collapsed by
// default to keep the dialog compact for the common original-with-no-
// children case (where the panel hides itself entirely).
const lineageExpanded = ref(false)
const lineageLoading = ref(false)
const lineageError = ref('')
const lineagePayload = ref(null)

// Surface visibility — the lineage section disappears entirely when
// there's nothing to navigate to (no parent + no children). For
// originals with no forks the dialog stays as compact as it was
// before this section shipped.
const hasLineageGraph = computed(() => {
  const p = lineagePayload.value
  if (!p) return false
  if (p.parent) return true
  if (Array.isArray(p.children) && p.children.length > 0) return true
  return false
})

const lineageChildren = computed(() => {
  const p = lineagePayload.value
  if (!p || !Array.isArray(p.children)) return []
  return p.children
})

const lineageTotalChildren = computed(() => {
  const p = lineagePayload.value
  return Number.isFinite(p?.total_children) ? p.total_children : 0
})

const lineageParent = computed(() => lineagePayload.value?.parent || null)

const formatChildKindBadge = (child) => {
  if (!child) return ''
  if (child.kind === 'counterfactual') return tr('🔀 Counterfactual', '🔀 反事实')
  if (child.kind === 'fork') return tr('🪐 Forked', '🪐 派生')
  return ''
}

const formatChildScenarioPreview = (child) => {
  if (!child) return ''
  // Counterfactuals carry their own headline (trigger round + label);
  // surface that ahead of the scenario text so the row reads as the
  // narrative event, not a slightly different scenario.
  const cf = child.counterfactual
  if (child.kind === 'counterfactual' && cf) {
    const round = Number.isInteger(cf.trigger_round) ? cf.trigger_round : '?'
    const label = cf.label
      ? ` (${cf.label})`
      : ''
    const head = tr('At round ', '第 ') + round + tr('', ' 轮') + label
    if (child.scenario_preview) {
      return head + ' · ' + child.scenario_preview
    }
    return head
  }
  return child.scenario_preview || ''
}

const childWatchUrl = (child) => {
  if (!child || !child.simulation_id) return ''
  return getWatchUrl(child.simulation_id, origin.value)
}

const parentWatchUrl = computed(() => {
  if (!lineageParent.value || !lineageParent.value.is_public) return ''
  return getWatchUrl(lineageParent.value.simulation_id, origin.value)
})

const truncateSimId = (id) => {
  if (!id) return ''
  return id.length > 14 ? id.slice(0, 14) + '…' : id
}

const loadLineage = async () => {
  if (!props.simulationId || !isPublic.value) {
    lineagePayload.value = null
    return
  }
  lineageLoading.value = true
  lineageError.value = ''
  try {
    const res = await getSimulationLineage(props.simulationId)
    if (res && res.success && res.data) {
      lineagePayload.value = res.data
    } else {
      lineagePayload.value = null
      lineageError.value = tr(
        'Could not parse the lineage payload.',
        '无法解析谱系数据。',
      )
    }
  } catch (err) {
    if (err?.response?.status === 403) {
      lineageError.value = tr(
        'Publish the simulation to see its lineage.',
        '发布模拟以查看谱系。',
      )
    } else if (err?.response?.status === 404) {
      lineageError.value = tr(
        'Simulation not found.',
        '未找到模拟。',
      )
    } else {
      lineageError.value = err?.response?.data?.error
        || err?.message
        || tr('Could not load the lineage.', '无法加载谱系。')
    }
    lineagePayload.value = null
  } finally {
    lineageLoading.value = false
  }
}

const toggleLineage = () => {
  lineageExpanded.value = !lineageExpanded.value
  if (lineageExpanded.value && !lineagePayload.value && !lineageError.value) {
    loadLineage()
  }
}

const _writeClipboard = async (text) => {
  if (!text) return false
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (err) {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch (_) { /* noop */ }
    document.body.removeChild(ta)
    return true
  }
}

const copyOneTweet = async (idx) => {
  const tweet = threadTweets.value[idx]
  if (!tweet) return
  const ok = await _writeClipboard(tweet)
  if (!ok) return
  const key = `threadOne-${idx}`
  copied.value = key
  setTimeout(() => {
    if (copied.value === key) copied.value = ''
  }, 1800)
}

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
  else if (which === 'threadTxt') text = threadTxtUrl.value
  else if (which === 'threadFull') {
    // The full thread copy joins the per-tweet array with the same
    // ``\n---\n`` separator the .txt endpoint emits. Doing the join
    // here (rather than fetching the .txt body) lets the operator
    // paste-and-edit immediately without a network round-trip.
    text = threadTweets.value.length ? threadTweets.value.join('\n---\n') : ''
  }
  else if (which === 'reproUrl') text = reproDownloadUrl.value
  else if (which === 'reproCurl') text = reproCurlSnippet.value
  else if (which === 'notebookUrl') text = notebookDownloadUrl.value
  else if (which === 'notebookCurl') text = notebookCurlSnippet.value
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

// ── Webhook delivery log ───────────────────────────────────────────────
// Operators get no feedback today on whether the outbound completion
// webhook actually fired — this panel reads ``<sim_dir>/webhook-log.jsonl``
// (admin-token gated server-side) so a 5xx from Zapier / n8n / Slack /
// Discord doesn't disappear into server logs.
const webhookLogExpanded = ref(false)
const webhookLogLoading = ref(false)
const webhookLogEntries = ref([])
const webhookLogTotal = ref(0)
const webhookLogError = ref('')
const webhookLogConfigError = ref(false)
const webhookRetrying = ref(false)
const webhookRetryMessage = ref('')
const webhookRetryMessageClass = ref('')
const runnerStatus = ref('')

const canRetryWebhook = computed(() => {
  // Retry only meaningful once the run has reached a terminal state —
  // before then there's no completion event to replay.
  const s = (runnerStatus.value || '').toLowerCase()
  return s === 'completed' || s === 'failed'
})

const formatLatency = (ms) => {
  if (typeof ms !== 'number' || Number.isNaN(ms)) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

const formatLogTime = (iso) => {
  if (!iso || typeof iso !== 'string') return '—'
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    // Compact time-only label so the row stays one line on narrow screens.
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

const webhookEntryClass = (entry) => {
  if (!entry) return ''
  if (entry.ok) return 'webhook-row-ok'
  if (entry.status_code === null && (entry.error || '').toLowerCase().includes('timeout')) {
    return 'webhook-row-timeout'
  }
  return 'webhook-row-fail'
}

// Show the "Verify webhook signatures" hint once the operator has
// confirmed their webhook is wired up (at least one 2xx delivery
// on disk). Earlier than that, the hint would be talking about
// signing a connection that hasn't proven it works — bad time to
// recommend an additional moving part.
const hasSuccessfulWebhookDelivery = computed(() =>
  webhookLogEntries.value.some((e) => e && e.ok === true),
)

const signatureHintExpanded = ref(false)
const toggleSignatureHint = () => {
  signatureHintExpanded.value = !signatureHintExpanded.value
}

const webhookEntryIcon = (entry) => {
  if (!entry) return ''
  if (entry.ok) return '✓'
  if (entry.status_code === null && (entry.error || '').toLowerCase().includes('timeout')) {
    return '⏱'
  }
  return '✗'
}

const webhookEntryCode = (entry) => {
  if (!entry) return '—'
  if (typeof entry.status_code === 'number') return `HTTP ${entry.status_code}`
  if (entry.error) {
    const text = String(entry.error)
    return text.length > 40 ? `${text.slice(0, 39)}…` : text
  }
  return '—'
}

const loadWebhookLog = async () => {
  if (!props.simulationId) return
  webhookLogLoading.value = true
  webhookLogError.value = ''
  webhookLogConfigError.value = false
  try {
    const res = await getWebhookLog(props.simulationId)
    const data = res?.data || {}
    webhookLogEntries.value = Array.isArray(data.entries) ? data.entries : []
    webhookLogTotal.value = Number(data.total_attempts || 0)
  } catch (err) {
    const status = err?.response?.status
    if (status === 503) {
      webhookLogConfigError.value = true
    } else if (status === 401) {
      webhookLogError.value = tr(
        'Admin token does not match — set Authorization: Bearer $MIROSHARK_ADMIN_TOKEN at your reverse proxy to view the log.',
        '管理员 token 不匹配 — 请在反向代理处设置 Authorization: Bearer $MIROSHARK_ADMIN_TOKEN 以查看日志。',
      )
    } else {
      webhookLogError.value =
        err?.response?.data?.error || err?.message || tr('Could not load delivery history.', '无法加载投递历史。')
    }
    webhookLogEntries.value = []
    webhookLogTotal.value = 0
  } finally {
    webhookLogLoading.value = false
  }
}

const toggleWebhookLog = () => {
  webhookLogExpanded.value = !webhookLogExpanded.value
  if (webhookLogExpanded.value && webhookLogEntries.value.length === 0 && !webhookLogError.value) {
    loadWebhookLog()
  }
}

const retryWebhook = async () => {
  if (!canRetryWebhook.value || webhookRetrying.value) return
  webhookRetrying.value = true
  webhookRetryMessage.value = ''
  webhookRetryMessageClass.value = ''
  try {
    const res = await retryWebhookDelivery(props.simulationId, {})
    if (res?.success && res.data?.queued) {
      webhookRetryMessage.value = tr(
        'Queued — refresh in a moment to see the new attempt.',
        '已排队 — 稍后刷新查看新一次投递。',
      )
      webhookRetryMessageClass.value = 'webhook-log-message-ok'
      // Pull fresh entries after a short delay so the daemon thread has
      // time to log its result. 1.2s comfortably covers a healthy
      // round-trip; a slow downstream still surfaces on the next manual
      // Refresh click.
      setTimeout(() => loadWebhookLog(), 1200)
    } else {
      webhookRetryMessage.value =
        res?.error || tr('Could not queue retry.', '无法排队重试。')
      webhookRetryMessageClass.value = 'webhook-log-message-error'
    }
  } catch (err) {
    const status = err?.response?.status
    if (status === 400) {
      webhookRetryMessage.value = err?.response?.data?.error
        || tr('No webhook URL configured.', '未配置 webhook URL。')
    } else if (status === 409) {
      webhookRetryMessage.value = err?.response?.data?.error
        || tr('Simulation has not finished yet.', '模拟尚未完成。')
    } else if (status === 503) {
      webhookRetryMessage.value = tr(
        'Admin authentication not configured.',
        '未配置管理员身份验证。',
      )
    } else {
      webhookRetryMessage.value =
        err?.response?.data?.error || err?.message || tr('Could not queue retry.', '无法排队重试。')
    }
    webhookRetryMessageClass.value = 'webhook-log-message-error'
  } finally {
    webhookRetrying.value = false
  }
}

const _resetWebhookLogState = () => {
  webhookLogExpanded.value = false
  webhookLogEntries.value = []
  webhookLogTotal.value = 0
  webhookLogError.value = ''
  webhookLogConfigError.value = false
  webhookRetryMessage.value = ''
  webhookRetryMessageClass.value = ''
  runnerStatus.value = ''
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
  _resetWebhookLogState()
  // Refresh public state when reopened — reflects external flips.
  try {
    const res = await getEmbedSummary(props.simulationId)
    if (typeof res?.data?.is_public === 'boolean') isPublic.value = res.data.is_public
    // Capture the runner status so the Retry button knows whether the
    // sim has reached a terminal state — auto-fire only triggers on
    // completed/failed, so retry semantics need the same gate.
    runnerStatus.value = res?.data?.runner_status || res?.data?.status || ''
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
  // Pull the tweet thread alongside the share-card preview — same publish
  // gate, so a private sim resolves cleanly to the empty state without
  // an extra round-trip on every dialog open.
  loadThread()
  // Reset surface-stats state on each open so a previously expanded
  // panel doesn't show stale numbers from a different sim. The
  // counters are only fetched on demand (when the operator expands
  // the panel) so a viewer who only cares about the share flow
  // doesn't pay the network round-trip.
  surfaceStatsExpanded.value = false
  surfaceStats.value = null
  surfaceStatsError.value = ''
  // Same reset for the reproducibility panel — collapsed on open,
  // blob cleared so the next expand fetches fresh against this sim.
  reproExpanded.value = false
  reproBlob.value = null
  reproError.value = ''
  // Eager-fetch the lineage payload on dialog open so the panel can
  // auto-show when there are children to navigate. Fetching cheaply
  // upfront beats the alternative (collapsed-by-default with no
  // visual hint there's a lineage to explore) for the navigation
  // use case the panel exists to enable.
  lineageExpanded.value = false
  lineagePayload.value = null
  lineageError.value = ''
  if (isPublic.value) {
    loadLineage()
  }
})

// When the operator toggles public on, the share-card endpoint flips from
// 403 → 200. Bust the cache so the <img> retries instead of staying broken.
watch(isPublic, () => {
  shareCardCacheBust.value = Date.now()
  // Re-fetch the thread when the publish flag flips — going public means
  // the gate now passes, so the previously-403 fetch should retry.
  loadThread()
  // Same publish-gate flip applies to the surface-stats panel — pull
  // fresh counters if the user has the panel expanded.
  if (surfaceStatsExpanded.value) {
    loadSurfaceStats()
  } else {
    surfaceStats.value = null
  }
  // Reproducibility panel follows the same flip semantics — visible
  // and expanded means we re-fetch the now-200 blob; collapsed means
  // we just clear the cached value so the next expand fetches fresh.
  if (reproExpanded.value) {
    loadRepro()
  } else {
    reproBlob.value = null
  }
  // Lineage panel mirrors the same lifecycle. Critically, we always
  // reload (not just when expanded) the first time the sim is
  // published — the panel auto-shows when there are children to
  // navigate, and that decision needs the payload, not just the
  // expand-on-click trigger.
  if (lineageExpanded.value || lineagePayload.value) {
    loadLineage()
  } else {
    lineagePayload.value = null
  }
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

/* Tweet thread — short-form text companion to the transcript / share
   card / replay GIF / trajectory CSV / watch page. Carries a small
   tweet-count badge so an operator can scan how long the thread is
   without scrolling, and a per-tweet character counter so paste-and-
   add-emoji edits don't blow the 280-char limit. */
.thread-section {
  margin-top: 14px;
}

.thread-count-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 7px;
  background: rgba(10, 10, 10, 0.08);
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #2a2a2a;
  vertical-align: middle;
  text-transform: none;
}

.thread-error {
  color: #b91c1c;
  font-style: normal;
}

.thread-tweets-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px 2px 2px 2px;
}

.thread-tweet {
  position: relative;
  padding: 10px 12px 10px 44px;
  background: #ffffff;
  border: 1px solid rgba(10, 10, 10, 0.1);
  border-radius: 8px;
}

.thread-tweet-num {
  position: absolute;
  top: 10px;
  left: 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #6b6b6b;
}

.thread-tweet-copy {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid rgba(10, 10, 10, 0.12);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  color: #2a2a2a;
  transition: background 0.15s, border-color 0.15s;
}

.thread-tweet-copy:hover {
  background: rgba(10, 10, 10, 0.04);
  border-color: rgba(10, 10, 10, 0.24);
}

.thread-tweet-body {
  margin: 0;
  padding: 0;
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
  font-size: 13px;
  line-height: 1.5;
  color: #0a0a0a;
  white-space: pre-wrap;
  word-break: break-word;
}

.thread-tweet-len {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: #8a8a8a;
  letter-spacing: 0.02em;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.thread-truncated-note {
  margin: 6px 2px 0;
  font-size: 11px;
  color: #6b6b6b;
  font-style: italic;
}

/* Surface usage analytics — pairs visually with the transcript /
   trajectory / thread sections (same shell, same head shape) so the
   dialog reads as one continuous Publish & Embed flow. The head is
   the click target that toggles the body open / closed; body uses a
   compact two-column grid (label / count) sorted by count desc so
   the operator's most-used surface lands at the top of the table. */
.surface-stats-section {
  cursor: default;
}

.surface-stats-head {
  cursor: pointer;
  user-select: none;
  align-items: center;
}

.surface-stats-head:hover .surface-stats-chevron {
  color: #0a0a0a;
}

.surface-stats-total-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 8px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #0a0a0a;
  background: #f4ecd8;
  border-radius: 999px;
  vertical-align: middle;
}

.surface-stats-chevron {
  border: 0;
  background: transparent;
  font-size: 16px;
  line-height: 1;
  color: #6b6b6b;
  cursor: pointer;
  padding: 4px 6px;
  transition: transform 0.15s, color 0.15s;
}

.surface-stats-chevron-open {
  transform: rotate(180deg);
  color: #0a0a0a;
}

.surface-stats-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.surface-stats-loading {
  font-size: 12px;
  color: #6b6b6b;
  font-style: italic;
}

.surface-stats-error {
  color: #b91c1c;
}

.surface-stats-table {
  display: grid;
  grid-template-columns: 1fr auto;
  row-gap: 4px;
  column-gap: 14px;
  padding: 10px 12px;
  background: #fafaf7;
  border: 1px solid #ececec;
  border-radius: 8px;
  font-size: 12px;
}

.surface-stats-row {
  display: contents;
  color: #1a1a1a;
}

.surface-stats-row > .surface-stats-label {
  padding: 3px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.surface-stats-row > .surface-stats-count {
  padding: 3px 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.surface-stats-row-zero > .surface-stats-label,
.surface-stats-row-zero > .surface-stats-count {
  color: #9b9b9b;
  font-weight: 400;
}

.surface-stats-row-total {
  border-top: 1px solid #ececec;
  margin-top: 2px;
  padding-top: 2px;
}

.surface-stats-row-total > .surface-stats-label {
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  font-size: 11px;
}

.surface-stats-row-total > .surface-stats-count {
  font-weight: 700;
}

.surface-stats-caveat {
  margin-top: 8px;
  padding: 6px 8px;
  font-size: 11px;
  line-height: 1.4;
  color: #6b6b6b;
  background: #f7f7f7;
  border-radius: 4px;
}

.surface-stats-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.surface-stats-refresh {
  border: 1px solid #d4d4d4;
  background: #ffffff;
  color: #1a1a1a;
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.surface-stats-refresh:hover:not(:disabled) {
  background: #f4ecd8;
  border-color: #c2a76b;
}

.surface-stats-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 600px) {
  .surface-stats-table {
    font-size: 11px;
  }
}

/* Reproducibility config — citation primitive behind every other
   share surface. Visual treatment matches the surface-stats panel
   (collapsed by default, chevron rotates on open) but adds a small
   blueish lineage badge inline with the title when the sim was
   forked or branched, plus a download / copy / refresh button row
   so the operator can grab the JSON without reading the curl snippet
   first. */
.repro-section {
  margin-top: 14px;
}

.repro-head {
  cursor: pointer;
  user-select: none;
}

.repro-lineage-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #4338ca;
  vertical-align: middle;
  text-transform: none;
  cursor: help;
}

.repro-chevron {
  align-self: center;
  border: none;
  background: transparent;
  font-size: 14px;
  color: #6b6b6b;
  transition: transform 0.18s ease;
  line-height: 1;
  padding: 4px;
  cursor: pointer;
}

.repro-chevron-open {
  transform: rotate(180deg);
}

.repro-body {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.repro-loading,
.repro-error {
  font-size: 12px;
  color: #6b6b6b;
  font-style: italic;
}

.repro-error {
  color: #b91c1c;
  font-style: normal;
}

.repro-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.repro-summary-grid {
  display: grid;
  grid-template-columns: max-content 1fr;
  column-gap: 16px;
  row-gap: 6px;
  font-size: 12px;
  background: #fafafa;
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 8px;
  padding: 10px 12px;
}

.repro-summary-row {
  display: contents;
}

.repro-summary-key {
  color: #6b6b6b;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.repro-summary-value {
  color: #1a1a1a;
  font-variant-numeric: tabular-nums;
  word-break: break-word;
}

.repro-curl-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.repro-curl-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.repro-curl-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #6b6b6b;
}

.repro-note {
  font-size: 11px;
  line-height: 1.5;
  color: #6b6b6b;
  background: #f5f5f5;
  border-left: 3px solid rgba(99, 102, 241, 0.4);
  padding: 8px 10px;
  border-radius: 4px;
}

.repro-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.repro-download {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  border-radius: 6px;
  background: linear-gradient(180deg, #1a1a1a 0%, #2a2a2a 100%);
  color: #ffffff;
  text-decoration: none;
  border: 1px solid #1a1a1a;
  transition: background 0.15s;
}

.repro-download:hover {
  background: linear-gradient(180deg, #2a2a2a 0%, #1a1a1a 100%);
}

.repro-copy-url {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.repro-refresh {
  margin-left: auto;
}

@media (max-width: 600px) {
  .repro-summary-grid {
    grid-template-columns: 1fr;
    row-gap: 2px;
  }
  .repro-summary-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }
  .repro-actions {
    flex-direction: column;
    align-items: stretch;
  }
  .repro-refresh {
    margin-left: 0;
  }
}

/* Lineage navigator — fork / counterfactual graph slice. Visually
   sits beneath the reproducibility config (the reproduce.json blob
   tells a reader where this sim came from; this section tells them
   where it went). Uses a green tint to distinguish from the indigo
   reproducibility block above and the orange watch-page block below. */
.lineage-section {
  border: 1px solid rgba(34, 139, 34, 0.16);
  background: rgba(34, 139, 34, 0.03);
}

.lineage-head {
  cursor: pointer;
}

.lineage-count-chip {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  border-radius: 999px;
  background: rgba(34, 139, 34, 0.12);
  color: #1f7a1f;
  vertical-align: middle;
}

.lineage-chevron {
  margin-left: auto;
}

.lineage-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 10px;
}

.lineage-parent-row,
.lineage-child-row {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(10, 10, 10, 0.07);
  background: #ffffff;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s, background 0.15s;
  align-items: flex-start;
}

.lineage-child-row:hover {
  border-color: rgba(34, 139, 34, 0.4);
  background: rgba(34, 139, 34, 0.04);
}

.lineage-row-arrow {
  font-size: 14px;
  font-weight: 700;
  color: #1f7a1f;
  flex: 0 0 auto;
  width: 16px;
  text-align: center;
}

.lineage-row-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1 1 auto;
  min-width: 0;
}

.lineage-row-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.lineage-row-tag {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6b6b6b;
}

.lineage-row-id {
  font-family: var(--font-mono, "SFMono-Regular", "Menlo", monospace);
  font-size: 11px;
  font-weight: 600;
  color: #4a4a4a;
}

.lineage-row-scenario {
  font-size: 12px;
  line-height: 1.4;
  color: #2a2a2a;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.lineage-row-private {
  font-size: 11px;
  color: #9a9a9a;
  font-style: italic;
}

.lineage-row-link {
  font-size: 11px;
  font-weight: 600;
  color: #1f7a1f;
  text-decoration: none;
  letter-spacing: 0.02em;
  margin-top: 2px;
}

.lineage-row-link:hover {
  text-decoration: underline;
}

.lineage-children {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.lineage-children-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.lineage-truncated-note {
  margin-left: auto;
  font-size: 10px;
  color: #9a9a9a;
  letter-spacing: 0.02em;
}

.lineage-child-badge {
  display: inline-block;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  border-radius: 6px;
  flex: 0 0 auto;
  white-space: nowrap;
  align-self: flex-start;
}

.lineage-child-badge-fork {
  background: rgba(99, 102, 241, 0.12);
  color: #4f46e5;
}

.lineage-child-badge-cf {
  background: rgba(234, 88, 12, 0.1);
  color: #c2410c;
}

.lineage-child-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1 1 auto;
  min-width: 0;
}

.lineage-child-cta {
  font-size: 14px;
  color: #6b6b6b;
  flex: 0 0 auto;
  align-self: center;
}

.lineage-actions {
  display: flex;
  justify-content: flex-end;
}

.lineage-refresh {
  margin-left: auto;
}

@media (max-width: 600px) {
  .lineage-child-row,
  .lineage-parent-row {
    flex-wrap: wrap;
  }
  .lineage-truncated-note {
    margin-left: 0;
    width: 100%;
  }
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

/* Webhook delivery history — collapsed by default to keep the dialog
   compact for users who don't have a webhook configured. Expands to a
   compact tabular row layout that reads like a tail of a delivery log
   (one row per attempt, status colour, latency, trigger, time). */
.webhook-log-section {
  margin-top: 12px;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px solid rgba(10, 10, 10, 0.08);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.webhook-log-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.webhook-log-icon {
  font-size: 20px;
  line-height: 1;
  padding-top: 2px;
}

.webhook-log-head-body {
  flex: 1;
  min-width: 0;
}

.webhook-log-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #0a0a0a;
  display: flex;
  align-items: center;
  gap: 8px;
}

.webhook-log-count {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: none;
  color: #4a4a4a;
  padding: 2px 7px;
  background: rgba(10, 10, 10, 0.06);
  border-radius: 999px;
}

.webhook-log-sub {
  font-size: 12px;
  line-height: 1.5;
  color: #4a4a4a;
  margin-top: 4px;
}

.webhook-log-toggle {
  flex-shrink: 0;
  background: transparent;
  border: 1px solid rgba(10, 10, 10, 0.18);
  color: #0a0a0a;
  font-size: 13px;
  font-weight: 600;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.webhook-log-toggle:hover {
  background: rgba(10, 10, 10, 0.05);
}

.webhook-log-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.webhook-log-loading,
.webhook-log-empty,
.webhook-log-config-hint,
.webhook-log-error {
  font-size: 12.5px;
  line-height: 1.5;
  color: #4a4a4a;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(10, 10, 10, 0.04);
}

.webhook-log-config-hint {
  background: rgba(255, 178, 0, 0.12);
  color: #7a4a00;
}

.webhook-log-error {
  background: rgba(255, 68, 68, 0.10);
  color: #b22020;
}

.webhook-log-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
  font-variant-numeric: tabular-nums;
}

.webhook-log-row {
  display: grid;
  grid-template-columns: auto auto auto 1fr auto auto;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.4;
  background: #fff;
  border: 1px solid rgba(10, 10, 10, 0.06);
}

.webhook-log-row-icon {
  font-weight: 700;
  font-size: 13px;
}

.webhook-log-row-attempt {
  color: #4a4a4a;
  font-size: 11px;
}

.webhook-log-row-code {
  font-weight: 600;
  color: #0a0a0a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.webhook-log-row-latency {
  color: #4a4a4a;
}

.webhook-log-row-trigger {
  color: #6a6a6a;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.webhook-log-row-time {
  color: #6a6a6a;
  font-size: 11px;
  white-space: nowrap;
}

.webhook-row-ok .webhook-log-row-icon { color: #2e7d32; }
.webhook-row-fail .webhook-log-row-icon { color: #b22020; }
.webhook-row-timeout .webhook-log-row-icon { color: #b97000; }

.webhook-row-ok { border-left: 3px solid #2e7d32; }
.webhook-row-fail { border-left: 3px solid #b22020; }
.webhook-row-timeout { border-left: 3px solid #b97000; }

.webhook-log-actions {
  display: flex;
  gap: 8px;
}

.webhook-log-refresh,
.webhook-log-retry {
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-radius: 6px;
  border: 1px solid rgba(10, 10, 10, 0.18);
  background: #fff;
  color: #0a0a0a;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.webhook-log-refresh:hover,
.webhook-log-retry:hover {
  background: #0a0a0a;
  color: #fff;
  border-color: #0a0a0a;
}

.webhook-log-refresh:disabled,
.webhook-log-retry:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.webhook-log-message {
  font-size: 12px;
  line-height: 1.4;
  padding: 8px 10px;
  border-radius: 6px;
}

.webhook-log-message-ok {
  background: rgba(67, 193, 101, 0.12);
  color: #1f6b35;
}

.webhook-log-message-error {
  background: rgba(255, 68, 68, 0.12);
  color: #b22020;
}

.signature-hint {
  margin-top: 4px;
  border: 1px solid rgba(10, 10, 10, 0.10);
  border-radius: 6px;
  background: rgba(10, 10, 10, 0.025);
}

.signature-hint-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: 0;
  font-size: 12px;
  font-weight: 600;
  color: #0a0a0a;
  cursor: pointer;
  text-align: left;
}

.signature-hint-icon {
  font-size: 14px;
}

.signature-hint-title {
  flex: 1;
}

.signature-hint-chevron {
  color: rgba(10, 10, 10, 0.5);
  font-size: 12px;
}

.signature-hint-body {
  padding: 0 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.signature-hint-line {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.5;
  color: rgba(10, 10, 10, 0.78);
}

.signature-hint-line a {
  color: #0a0a0a;
  text-decoration: underline;
}

.signature-hint-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  background: rgba(10, 10, 10, 0.06);
  padding: 6px 8px;
  border-radius: 4px;
  color: #0a0a0a;
  user-select: all;
}

@media (max-width: 600px) {
  .webhook-log-row {
    grid-template-columns: auto auto 1fr;
    grid-template-rows: auto auto;
    grid-row-gap: 2px;
  }
  .webhook-log-row-trigger,
  .webhook-log-row-time { grid-column: 1 / -1; }
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
