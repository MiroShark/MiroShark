<template>
  <Teleport to="body">
    <Transition name="embed-dialog">
      <div v-if="open" class="embed-dialog-overlay" @click.self="$emit('close')">
        <div class="embed-dialog">
          <!-- Header -->
          <div class="embed-dialog-header">
            <div class="embed-dialog-title">
              <span class="title-icon">⌘</span>
              <span>{{ $tr('Embed simulation', '嵌入模拟', { de: 'Simulation einbetten', fr: 'Intégrer la simulation' }) }}</span>
              <span class="title-sub">{{ formatSimulationId(simulationId) }}</span>
            </div>
            <button class="embed-dialog-close" @click="$emit('close')">×</button>
          </div>

          <!-- Description -->
          <p class="embed-dialog-desc">
            {{ $tr('Paste the iframe below into Notion, Substack, Medium, a GitHub README, or any HTML page. The widget loads live from this MiroShark instance and updates automatically as the simulation changes.', '将下面的 iframe 粘贴到 Notion、Substack、Medium、GitHub README 或任何 HTML 页面中。组件从当前 MiroShark 实例实时加载,并随模拟变化自动更新。', { de: 'Füge den folgenden iframe in Notion, Substack, Medium, ein GitHub-README oder eine beliebige HTML-Seite ein. Das Widget lädt live von dieser MiroShark-Instanz und aktualisiert sich automatisch, wenn sich die Simulation ändert.', fr: `Collez l'iframe ci-dessous dans Notion, Substack, Medium, un README GitHub, ou toute page HTML. Le widget se charge en direct depuis cette instance MiroShark et se met à jour automatiquement au fil de la simulation.` }) }}
          </p>

          <!-- Public toggle -->
          <div class="embed-public-row">
            <label class="embed-public-toggle">
              <input type="checkbox" :checked="isPublic" @change="togglePublic" :disabled="publishing" />
              <span class="embed-public-label">
                {{ isPublic ? $tr('Public — embeddable by anyone with the URL', '公开 — 任何获得 URL 的人都可嵌入', { de: 'Öffentlich — von jedem mit der URL einbettbar', fr: `Public — intégrable par toute personne avec l'URL` }) : $tr('Private — embed URL returns 403', '私有 — 嵌入 URL 返回 403', { de: 'Privat — Einbettungs-URL gibt 403 zurück', fr: `Privé — l'URL d'intégration retourne 403` }) }}
              </span>
            </label>
            <span v-if="publishError" class="embed-public-error">{{ publishError }}</span>
          </div>

          <!-- Private share links -->
          <div class="share-link-section">
            <div class="share-link-header">
              <span class="share-link-title">🔗 {{ $tr('Private share links', '私享链接', { de: 'Private Freigabelinks', fr: 'Liens de partage privés' }) }}</span>
              <span class="share-link-sub">
                {{ $tr('Send a simulation to one person without publishing it. The preview link bypasses the public gate but is `noindex` and revocable.', '将模拟发送给特定人员而无需公开。预览链接绕过公开门控,但禁止索引且可随时撤销。', { de: 'Sende eine Simulation an eine Person, ohne sie zu veröffentlichen. Der Vorschau-Link umgeht die öffentliche Zugangskontrolle, ist aber als `noindex` markiert und kann widerrufen werden.', fr: 'Envoyez une simulation à une personne sans la publier. Le lien d\'aperçu contourne la porte publique mais est `noindex` et révocable.' }) }}
              </span>
            </div>
            <div class="share-link-mint-row">
              <label class="share-link-expiry">
                <span>{{ $tr('Expires in', '有效期', { de: 'Läuft ab in', fr: 'Expire dans' }) }}</span>
                <select v-model.number="shareLinkExpiresInDays" :disabled="shareLinkBusy">
                  <option :value="1">1 {{ $tr('day', '天', { de: 'Tag' , fr: 'jour'}) }}</option>
                  <option :value="7">7 {{ $tr('days', '天', { de: 'Tagen' , fr: 'jours'}) }}</option>
                  <option :value="30">30 {{ $tr('days', '天', { de: 'Tagen' }) }}</option>
                  <option :value="90">90 {{ $tr('days', '天', { de: 'Tagen' }) }}</option>
                  <option :value="365">365 {{ $tr('days', '天', { de: 'Tagen' }) }}</option>
                </select>
              </label>
              <button
                class="share-link-mint-btn"
                @click="mintShareLink"
                :disabled="shareLinkBusy || !simulationId"
              >
                {{ shareLinkBusy ? $tr('Working…', '处理中…', { de: 'Verarbeitung…' , fr: 'En cours…'}) : $tr('Generate link', '生成链接', { de: 'Link generieren' , fr: 'Générer le lien'}) }}
              </button>
            </div>
            <p v-if="shareLinkError" class="share-link-error">{{ shareLinkError }}</p>
            <ul v-if="shareLinks.length" class="share-link-list">
              <li v-for="entry in shareLinks" :key="entry.token" class="share-link-row">
                <div class="share-link-url">
                  <code>{{ entry.preview_url }}</code>
                </div>
                <div class="share-link-meta">
                  <span>
                    {{ $tr('Expires', '过期时间', { de: 'Läuft ab' , fr: 'Expire'}) }}: {{ entry.expires_at_iso || '—' }}
                    <template v-if="entry.expires_in_days_remaining != null">
                      ({{ entry.expires_in_days_remaining }} {{ $tr('days left', '天剩余', { de: 'Tage verbleibend' , fr: 'jours restants'}) }})
                    </template>
                  </span>
                </div>
                <div class="share-link-actions">
                  <button class="share-link-copy" @click="copyShareLink(entry.preview_url)">
                    {{ $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                  </button>
                  <button class="share-link-revoke" @click="revokeShareLinkEntry(entry.token)">
                    {{ $tr('Revoke', '撤销', { de: 'Widerrufen', fr: 'Révoquer' }) }}
                  </button>
                </div>
              </li>
            </ul>
            <p v-else-if="!shareLinkBusy && !shareLinkError" class="share-link-empty">
              {{ $tr('No private links issued. Generate one to share without publishing.', '尚未生成私享链接。生成一个即可在不公开的情况下分享。', { de: 'Keine privaten Links erstellt. Generiere einen, um ohne Veröffentlichung zu teilen.', fr: 'Aucun lien privé émis. Générez-en un pour partager sans publier.' }) }}
            </p>
          </div>

          <!-- Size presets -->
          <div class="embed-size-row">
            <span class="embed-size-label">{{ $tr('Size', '尺寸', { de: 'Größe', fr: 'Taille' }) }}</span>
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
              <span>{{ $tr('Theme', '主题', { de: 'Design', fr: 'Thème' }) }}</span>
              <select v-model="theme" class="embed-theme-select">
                <option value="light">{{ $tr('Light', '浅色', { de: 'Hell', fr: 'Clair' }) }}</option>
                <option value="dark">{{ $tr('Dark', '深色', { de: 'Dunkel', fr: 'Sombre' }) }}</option>
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
                <span class="snippet-label">{{ $tr('HTML iframe', 'HTML iframe', { de: 'HTML iframe', fr: 'iframe HTML' }) }}</span>
                <button class="snippet-copy-btn" @click="copy('iframe')">
                  {{ copied === 'iframe' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                </button>
              </div>
              <pre class="snippet-code"><code>{{ iframeSnippet }}</code></pre>
            </div>

            <div class="snippet-block">
              <div class="snippet-head">
                <span class="snippet-label">{{ $tr('Markdown (Notion / Substack auto-embed)', 'Markdown(Notion / Substack 自动嵌入)', { de: 'Markdown (Notion / Substack Auto-Einbettung)', fr: 'Markdown (Notion / Substack auto-intégration)' }) }}</span>
                <button class="snippet-copy-btn" @click="copy('markdown')">
                  {{ copied === 'markdown' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                </button>
              </div>
              <pre class="snippet-code"><code>{{ markdownSnippet }}</code></pre>
            </div>

            <div class="snippet-block">
              <div class="snippet-head">
                <span class="snippet-label">{{ $tr('Direct URL', '直接 URL', { de: 'Direkte URL', fr: 'URL directe' }) }}</span>
                <button class="snippet-copy-btn" @click="copy('url')">
                  {{ copied === 'url' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                </button>
              </div>
              <pre class="snippet-code"><code>{{ embedUrl }}</code></pre>
            </div>
          </div>

          <!-- Social share card -->
          <div class="share-card-section">
            <div class="share-card-divider">
              <span class="divider-line"></span>
              <span class="divider-text">{{ $tr('Social card', '社交卡片', { de: 'Social Card', fr: 'Carte sociale' }) }}</span>
              <span class="divider-line"></span>
            </div>

            <p class="share-card-desc">
              {{ $tr('A 1200×630 PNG with the scenario headline, status, quality, and belief split — the same image Twitter/X, Discord, Slack, and LinkedIn unfurl automatically when someone pastes the share link.', '一张 1200×630 的 PNG,包含情景标题、状态、质量和信念分布 — Twitter/X、Discord、Slack 和 LinkedIn 在有人粘贴分享链接时会自动展开此图。', { de: 'Ein 1200×630 PNG mit Szenario-Überschrift, Status, Qualität und Überzeugungsverteilung — dasselbe Bild, das Twitter/X, Discord, Slack und LinkedIn automatisch entfalten, wenn jemand den Freigabelink einfügt.', fr: `Un PNG 1200×630 avec le titre du scénario, le statut, la qualité et la répartition des croyances — la même image que Twitter/X, Discord, Slack et LinkedIn déroulent automatiquement quand quelqu'un colle le lien de partage.` }) }}
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
                {{ isPublic ? $tr('Loading preview…', '加载预览中…', { de: 'Vorschau wird geladen…' , fr: 'Chargement de l\'aperçu…'}) : $tr('Publish the simulation to enable the share card.', '发布模拟以启用分享卡片。', { de: 'Veröffentliche die Simulation, um die Share Card zu aktivieren.' , fr: 'Publiez la simulation pour activer la carte de partage.'}) }}
              </div>
            </div>

            <div class="share-card-actions">
              <div class="snippet-block share-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Share link (auto-unfurls with card)', '分享链接(随卡片自动展开)', { de: 'Freigabelink (entfaltet sich automatisch mit Card)' , fr: 'Lien de partage (dépliage auto avec carte)'}) }}</span>
                  <button class="snippet-copy-btn" @click="copy('share')" :disabled="!isPublic">
                    {{ copied === 'share' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy link', '复制链接', { de: 'Link kopieren', fr: 'Copier le lien' }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ shareLandingUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block share-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Card image URL (for manual paste)', '卡片图片 URL(供手动粘贴)', { de: 'Card-Bild-URL (zum manuellen Einfügen)', fr: `URL de l'image de la carte (pour collage manuel)` }) }}</span>
                  <button class="snippet-copy-btn" @click="copy('card')" :disabled="!isPublic">
                    {{ copied === 'card' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
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
                ↓ {{ $tr('Download PNG', '下载 PNG', { de: 'PNG herunterladen', fr: 'Télécharger PNG' }) }}
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
                  <div class="watch-title">{{ $tr('Watch live (broadcast page)', '实时观看(直播页面)', { de: 'Live zuschauen (Broadcast-Seite)' , fr: 'Voir en direct (page de diffusion)'}) }}</div>
                  <div class="watch-sub">
                    {{ $tr('A minimal full-viewport page built for live spectating — the belief bar, round counter, and progress bar update every 15 s while the simulation runs. Auto-unfurls as a card on Twitter / X, Discord, Slack, LinkedIn. Different format from the finished-result share above; tweet this URL mid-run to broadcast as it happens.', '专为实时观看打造的极简全屏页面 — 信念条、轮次计数器和进度条在模拟运行时每 15 秒更新一次。在 Twitter / X、Discord、Slack、LinkedIn 上自动展开为卡片。与上方的完成结果分享不同;在运行过程中发推此 URL 即可实时广播。', { de: 'Eine minimalistische Vollbild-Seite für Live-Zuschauer — der Überzeugungsbalken, Rundenanzahl und Fortschrittsbalken aktualisieren sich alle 15 Sekunden während die Simulation läuft. Entfaltet sich automatisch als Card auf Twitter/X, Discord, Slack, LinkedIn. Anderes Format als die oben stehende Ergebnis-Freigabe; tweete diese URL während der Laufzeit für Live-Übertragung.' , fr: 'Une page plein écran minimale pour le direct — la barre de croyance, le compteur de tours et la barre de progression se mettent à jour toutes les 15 secondes. Se déplie automatiquement en carte sur Twitter/X, Discord, Slack, LinkedIn. Format différent du partage ci-dessus ; tweetez cette URL en cours de route pour diffuser en direct.'}) }}
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
                  👀 {{ $tr('Open watch page ↗', '打开观看页面 ↗', { de: 'Watch-Seite öffnen ↗' , fr: 'Page de direct ↗'}) }}
                </a>
                <span v-if="!isPublic" class="watch-empty">
                  {{ $tr('Publish the simulation to enable the live watch page.', '发布模拟以启用实时观看页面。', { de: 'Veröffentliche die Simulation, um die Live-Watch-Seite zu aktivieren.' , fr: 'Publiez la simulation pour activer la page de direct.'}) }}
                </span>
              </div>

              <div class="snippet-block watch-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Watch URL (auto-unfurls with card on tweet)', '观看 URL(发推时随卡片自动展开)', { de: 'Watch-URL (entfaltet sich beim Tweet automatisch als Card)' , fr: 'URL du direct (dépliage auto sur tweet)'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('watch')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'watch' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
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
                  <div class="replay-title">{{ $tr('Belief replay (animated)', '信念回放(动画)', { de: 'Überzeugungswiedergabe (animiert)', fr: 'Rejeu des croyances (animé)' }) }}</div>
                  <div class="replay-sub">
                    {{ $tr('Same canvas as the share card, one frame per round. Discord and Slack auto-play GIFs from the direct URL — drop the link in a channel and it plays inline.', '与分享卡片相同的画布,每轮一帧。Discord 和 Slack 会从直接 URL 自动播放 GIF — 在频道里贴上链接即可内联播放。', { de: 'Gleiche Leinwand wie die Share Card, ein Frame pro Runde. Discord und Slack spielen GIFs von der direkten URL automatisch ab — Link in einen Kanal posten und er spielt direkt inline ab.', fr: `Même canvas que la carte de partage, une image par tour. Discord et Slack lisent automatiquement les GIFs depuis l'URL directe — collez le lien dans un canal et il joue en ligne.` }) }}
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
                  <span class="replay-overlay-text">{{ $tr('Tap to play', '点击播放', { de: 'Zum Abspielen tippen', fr: 'Toucher pour lire' }) }}</span>
                </div>
              </div>
              <div v-else class="replay-empty">
                {{ $tr('Publish the simulation to enable the belief replay GIF.', '发布模拟以启用信念回放 GIF。', { de: 'Veröffentliche die Simulation, um das Überzeugungswiedergabe-GIF zu aktivieren.' , fr: 'Publiez la simulation pour activer le GIF de rejeu.'}) }}
              </div>

              <div class="replay-actions">
                <div class="snippet-block share-snippet">
                  <div class="snippet-head">
                    <span class="snippet-label">{{ $tr('Replay GIF URL (auto-plays in Discord / Slack)', '回放 GIF URL(在 Discord / Slack 中自动播放)', { de: 'Wiedergabe-GIF-URL (automatische Wiedergabe in Discord / Slack)' , fr: 'URL du GIF de rejeu (lecture auto dans Discord/Slack)'}) }}</span>
                    <button
                      class="snippet-copy-btn"
                      @click="copy('replay')"
                      :disabled="!isPublic"
                    >
                      {{ copied === 'replay' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
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
                  ↓ {{ $tr('Download GIF', '下载 GIF', { de: 'GIF herunterladen', fr: 'Télécharger GIF' }) }}
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
                  <div class="transcript-title">{{ $tr('Export transcript', '导出对话记录', { de: 'Protokoll exportieren', fr: 'Exporter le transcript' }) }}</div>
                  <div class="transcript-sub">
                    {{ $tr('Per-round agent posts + stance labels + final consensus. Cite the simulation in a research paper or a Substack post without screenshotting.', '逐轮智能体帖子 + 立场标签 + 最终共识。在研究论文或 Substack 文章中引用该模拟,无需截屏。', { de: 'Beiträge der Agenten pro Runde + Haltungsbezeichnungen + Endkonsens. Zitiere die Simulation in einem Forschungspapier oder Substack-Beitrag ohne Screenshot.', fr: `Publications des agents par tour + labels de position + consensus final. Citez la simulation dans un article de recherche ou un post Substack sans capture d'écran.` }) }}
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
                  ↓ {{ $tr('Download .md', '下载 .md', { de: '.md herunterladen', fr: 'Télécharger .md' }) }}
                </a>
                <a
                  v-if="isPublic && transcriptJsonUrl"
                  class="transcript-download-btn transcript-download-btn-secondary"
                  :href="transcriptJsonUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-transcript.json`"
                >
                  ↓ {{ $tr('Download .json', '下载 .json', { de: '.json herunterladen', fr: 'Télécharger .json' }) }}
                </a>
                <span v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to enable the transcript export.', '发布模拟以启用对话记录导出。', { de: 'Veröffentliche die Simulation, um den Protokollexport zu aktivieren.', fr: `Publiez la simulation pour activer l'export de la transcription.` }) }}
                </span>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr(`Markdown URL (Notion / Obsidian "Import from URL")`, 'Markdown URL(Notion / Obsidian「从 URL 导入」)', { de: 'Markdown-URL (Notion / Obsidian „Von URL importieren")', fr: 'URL Markdown (Notion / Obsidian « Importer depuis une URL »)' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('transcriptMd')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'transcriptMd' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
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
                  <div class="transcript-title">{{ $tr('Export trajectory data', '导出轨迹数据', { de: 'Trajektoriendaten exportieren', fr: 'Exporter les données de trajectoire' }) }}</div>
                  <div class="transcript-sub">
                    {{ $tr('One row per round — bullish / neutral / bearish %, participating agents, post + engagement counts. Pandas, Excel, Tableau, R, and Observable consume CSV natively.', '每轮一行 — 看涨 / 中性 / 看跌 %、参与的智能体、帖子和互动数。Pandas、Excel、Tableau、R 和 Observable 原生消费 CSV。', { de: 'Eine Zeile pro Runde — Bullish/Neutral/Bearish %, teilnehmende Agenten, Beiträge und Interaktionszahlen. Pandas, Excel, Tableau, R und Observable konsumieren CSV nativ.', fr: `Une ligne par tour — % haussier / neutre / baissier, agents participants, publications + compteurs d'engagement. Pandas, Excel, Tableau, R et Observable consomment le CSV nativement.` }) }}
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
                  ↓ {{ $tr('Download .csv', '下载 .csv', { de: '.csv herunterladen', fr: 'Télécharger .csv' }) }}
                </a>
                <a
                  v-if="isPublic && trajectoryJsonlUrl"
                  class="transcript-download-btn transcript-download-btn-secondary"
                  :href="trajectoryJsonlUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-trajectory.jsonl`"
                >
                  ↓ {{ $tr('Download .jsonl', '下载 .jsonl', { de: '.jsonl herunterladen' , fr: 'Télécharger .jsonl'}) }}
                </a>
                <span v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to enable the trajectory export.', '发布模拟以启用轨迹数据导出。', { de: 'Veröffentliche die Simulation, um den Trajektorienexport zu aktivieren.' , fr: 'Publiez la simulation pour activer l\'export de trajectoire.'}) }}
                </span>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('CSV URL (paste into pandas.read_csv())', 'CSV URL(粘贴至 pandas.read_csv())', { de: 'CSV-URL (in pandas.read_csv() einfügen)' , fr: 'URL CSV (à coller dans pandas.read_csv())'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('trajectoryCsv')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'trajectoryCsv' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ trajectoryCsvUrl || '—' }}</code></pre>
              </div>

              <p class="trajectory-quickstart">
                <code>pd.read_csv("{{ trajectoryCsvUrl || 'https://your-host/api/simulation/&lt;id&gt;/trajectory.csv' }}")</code>
              </p>
            </div>

            <!-- Belief trajectory chart as a stdlib-pure SVG. Scalable
                 vector companion to the share card (PNG verdict),
                 replay GIF (motion), and Jupyter notebook (matplotlib).
                 Embeddable as <img> in Notion, Substack, Ghost, GitHub
                 READMEs, and LaTeX — vector means no resolution choice,
                 and <img> means no JS at the embed site. -->
            <div class="transcript-section trajectory-section chart-svg-section">
              <div class="transcript-head">
                <span class="transcript-icon">📈</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">{{ $tr('Trajectory chart (SVG)', '轨迹图(SVG)', { de: 'Trajektorienchart (SVG)', fr: 'Graphique de trajectoire (SVG)' }) }}</div>
                  <div class="transcript-sub">
                    {{ $tr('Vector belief chart — bullish / neutral / bearish curves across every round. Same ±0.2 stance threshold as every other surface. Embed as <img> in Notion, Substack, Ghost, GitHub READMEs, and LaTeX — scales to any size with no JavaScript.', '矢量信念图 — 每轮的看涨 / 中性 / 看跌曲线。与其他所有界面使用相同的 ±0.2 立场阈值。作为 <img> 嵌入 Notion、Substack、Ghost、GitHub README 和 LaTeX — 无需 JavaScript 即可缩放到任何尺寸。', { de: 'Vektorielles Überzeugungsdiagramm — Bullish/Neutral/Bearish-Kurven über alle Runden. Gleiche ±0,2 Haltungsschwelle wie alle anderen Ansichten. Als <img> in Notion, Substack, Ghost, GitHub-READMEs und LaTeX einbetten — skaliert auf jede Größe ohne JavaScript.', fr: `Graphique vectoriel des croyances — courbes haussier / neutre / baissier sur tous les tours. Même seuil de position ±0.2 que toutes les autres surfaces. Intégrez comme <img> dans Notion, Substack, Ghost, READMEs GitHub et LaTeX — s'adapte à toute taille sans JavaScript.` }) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && chartSvgUrl" class="chart-svg-preview">
                <img
                  :src="chartSvgUrl"
                  alt="MiroShark belief trajectory chart"
                  loading="lazy"
                  class="chart-svg-img"
                />
              </div>

              <div class="transcript-actions">
                <a
                  v-if="isPublic && chartSvgUrl"
                  class="transcript-download-btn"
                  :href="chartSvgUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-chart.svg`"
                >
                  ↓ {{ $tr('Download .svg', '下载 .svg', { de: '.svg herunterladen', fr: 'Télécharger .svg' }) }}
                </a>
                <span v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to enable the trajectory chart.', '发布模拟以启用轨迹图。', { de: 'Veröffentliche die Simulation, um den Trajektorienchart zu aktivieren.' , fr: 'Publiez la simulation pour activer le graphique de trajectoire.'}) }}
                </span>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Chart URL (paste into <img src="…">)', '图表 URL(粘贴至 <img src="…">)', { de: 'Chart-URL (in <img src="…"> einfügen)' , fr: 'URL du graphique (à coller dans <img src="…">)'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('chartSvg')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'chartSvg' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ chartSvgUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('HTML embed', 'HTML 嵌入', { de: 'HTML-Einbettung', fr: 'Intégration HTML' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('chartSvgEmbed')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'chartSvgEmbed' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ chartSvgEmbedSnippet }}</code></pre>
              </div>
            </div>

            <!-- Farcaster Frame v2 — the Base-chain audience surface.
                 $MIROSHARK lives on Base; the Base-native social
                 network is Farcaster / Warpcast. When the share URL
                 is pasted into a cast, the share-page <head> emits
                 fc:frame:* meta tags so the cast renders as an
                 interactive Frame card with the chart SVG as the
                 preview and a "View Simulation →" link button. This
                 section surfaces the Frame image + a Warpcast
                 composer link so the operator can preview the Frame
                 before casting. -->
            <div class="transcript-section trajectory-section farcaster-frame-section">
              <div class="transcript-head">
                <span class="transcript-icon">🟣</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">{{ $tr('Farcaster Frame', 'Farcaster Frame', { de: 'Farcaster Frame', fr: 'Farcaster Frame' }) }}</div>
                  <div class="transcript-sub">
                    {{ $tr('Paste the share link into any Farcaster client (Warpcast, Supercast, the in-wallet Frame in Coinbase Wallet) and the cast renders as an interactive belief-chart card with a one-tap link to the full simulation. Zero new dependencies — pure Frame v2 meta tags on the share page.', '在任何 Farcaster 客户端(Warpcast、Supercast、Coinbase Wallet 内置 Frame)中粘贴分享链接,Cast 会渲染为带一键链接到完整模拟的交互式信念图卡片。零新依赖 — 仅在分享页面添加 Frame v2 meta 标签。', { de: 'Füge den Freigabelink in einen beliebigen Farcaster-Client (Warpcast, Supercast, den In-Wallet-Frame in Coinbase Wallet) ein und der Cast wird als interaktive Überzeugungsdiagramm-Card mit einem Ein-Tipp-Link zur vollständigen Simulation gerendert. Keine neuen Abhängigkeiten — nur Frame-v2-Meta-Tags auf der Freigabeseite.', fr: `Collez le lien de partage dans n'importe quel client Farcaster (Warpcast, Supercast, le Frame in-wallet de Coinbase Wallet) et le cast s'affiche comme une carte de graphique de croyances interactive avec un lien en un clic vers la simulation complète. Zéro nouvelle dépendance — pures balises meta Frame v2 sur la page de partage.` }) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && farcasterFrameImage" class="chart-svg-preview farcaster-frame-preview">
                <img
                  :src="farcasterFrameImage"
                  :alt="$tr('Farcaster Frame preview', 'Farcaster Frame 预览', { de: 'Farcaster Frame Vorschau' , fr: 'Aperçu Farcaster Frame'})"
                  loading="lazy"
                  class="chart-svg-img"
                />
              </div>

              <div class="transcript-actions">
                <a
                  v-if="isPublic && farcasterComposeUrl"
                  class="transcript-download-btn"
                  :href="farcasterComposeUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  🟣 {{ $tr('Compose on Warpcast', '在 Warpcast 中撰写', { de: 'Auf Warpcast verfassen' , fr: 'Composer sur Warpcast'}) }}
                </a>
                <span v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to enable the Farcaster Frame.', '发布模拟以启用 Farcaster Frame。', { de: 'Veröffentliche die Simulation, um den Farcaster Frame zu aktivieren.' , fr: 'Publiez la simulation pour activer le Farcaster Frame.'}) }}
                </span>
                <span
                  v-else-if="farcasterHasTrajectory === false"
                  class="transcript-empty farcaster-frame-fallback"
                >
                  {{ $tr('No trajectory yet — the Frame will preview the share card until rounds are recorded.', '尚无轨迹数据 — 在记录回合之前,Frame 将预览分享卡片。', { de: 'Noch keine Trajektorie — der Frame zeigt die Share Card in der Vorschau, bis Runden aufgezeichnet wurden.' , fr: 'Pas encore de trajectoire — le Frame affichera la carte de partage.'}) }}
                </span>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Share URL (paste into a Farcaster cast)', '分享 URL(粘贴到 Farcaster Cast)', { de: 'Freigabe-URL (in einen Farcaster-Cast einfügen)' , fr: 'URL de partage (à coller dans un cast Farcaster)'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('farcasterShare')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'farcasterShare' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ farcasterShareUrl || '—' }}</code></pre>
              </div>
            </div>

            <!-- Status badge — the cheapest visible pointer back to
                 the simulation. A flat 20-pixel Shields.io-compatible
                 SVG that fits inside any GitHub README, Notion page,
                 Substack post, or personal site as a one-line
                 Markdown image embed. The live signal (direction +
                 confidence) travels with the badge, so a reader
                 seeing the badge in a README sees the current
                 consensus, not a stale screenshot. Same publish gate
                 as every other share surface; pure stdlib, zero new
                 deps. -->
            <div class="transcript-section badge-section">
              <div class="transcript-head">
                <span class="transcript-icon">🏷️</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Status badge (SVG)', '状态徽章(SVG)', { de: 'Statusabzeichen (SVG)', fr: 'Badge de statut (SVG)' }) }}
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('A flat Shields.io-compatible 20-pixel SVG showing the current belief direction + confidence. Embed in any GitHub README, Notion page, Substack post, or personal site with one line of Markdown — the badge updates as the simulation runs, so the embed never goes stale.', '一个扁平、与 Shields.io 兼容的 20 像素高 SVG,显示当前信念方向与置信度。在任何 GitHub README、Notion 页面、Substack 文章或个人网站中,用一行 Markdown 即可嵌入 — 徽章会随模拟运行而更新,嵌入永不过期。', { de: 'Ein flaches, Shields.io-kompatibles 20-Pixel-SVG, das die aktuelle Überzeugungsrichtung und Konfidenz anzeigt. Mit einer Zeile Markdown in jedes GitHub-README, jede Notion-Seite, jeden Substack-Beitrag oder jede persönliche Website einbetten — das Abzeichen aktualisiert sich mit der laufenden Simulation und wird nie veraltet.', fr: `Un SVG plat 20 pixels compatible Shields.io montrant la direction et la confiance actuelles des croyances. Intégrez dans tout README GitHub, page Notion, post Substack ou site personnel avec une ligne de Markdown — le badge se met à jour au fil de la simulation, pour que l'intégration ne devienne jamais obsolète.` }) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && badgeSvgUrl" class="badge-preview">
                <img
                  :src="badgeSvgUrl"
                  :alt="$tr('MiroShark consensus status badge', 'MiroShark 共识状态徽章', { de: 'MiroShark Konsensstatusabzeichen', fr: 'Badge de statut du consensus MiroShark' })"
                  class="badge-svg-img"
                />
              </div>
              <div v-else-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable the status badge.', '发布模拟以启用状态徽章。', { de: 'Veröffentliche die Simulation, um das Statusabzeichen zu aktivieren.' , fr: 'Publiez la simulation pour activer le badge de statut.'}) }}
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Badge URL', '徽章 URL', { de: 'Abzeichen-URL' , fr: 'URL du badge'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('badgeUrl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'badgeUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ badgeSvgUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Markdown', 'Markdown', { de: 'Markdown', fr: 'Markdown' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('badgeMd')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'badgeMd' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ badgeMarkdownSnippet }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('HTML', 'HTML', { de: 'HTML', fr: 'HTML' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('badgeHtml')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'badgeHtml' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ badgeHtmlSnippet }}</code></pre>
              </div>
            </div>

            <!-- Machine-readable trading signal — the action primitive
                 sitting on top of the data-export stack. Collapses the
                 final-round belief split + quality health into a single
                 line a quant tool, alert pipeline, or Zapier / Make /
                 n8n workflow can consume directly. Same publish gate as
                 every other share surface; pure stdlib, zero new deps. -->
            <div class="transcript-section signal-section">
              <div class="transcript-head">
                <span class="transcript-icon">📡</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Trading signal (JSON)', '交易信号(JSON)', { de: 'Handelssignal (JSON)', fr: 'Signal de trading (JSON)' }) }}
                    <span v-if="signalDirection" :class="['signal-direction-badge', `signal-direction-${signalDirection.toLowerCase()}`]">
                      {{ signalDirection }} · {{ signalConfidence }}%
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Machine-readable action primitive — direction (Bullish / Neutral / Bearish) + confidence (0 = pure three-way split, 100 = unanimous) + risk tier (low / medium / high, mapped from quality health). Consumable by quant tools, Zapier / Make / n8n workflows, and alert pipelines.', '机器可读的行动原语 — 方向(看涨 / 中性 / 看跌)+ 置信度(0 = 纯三向分裂,100 = 一致)+ 风险等级(低 / 中 / 高,源自质量健康度)。可被量化工具、Zapier / Make / n8n 工作流以及预警管道直接消费。', { de: 'Maschinenlesbares Handlungselement — Richtung (Bullish/Neutral/Bearish) + Konfidenz (0 = reine Dreiweg-Aufteilung, 100 = einstimmig) + Risikoklasse (niedrig/mittel/hoch, aus Qualitätszustand abgeleitet). Für Quant-Tools, Zapier/Make/n8n-Workflows und Alert-Pipelines nutzbar.', fr: `Primitive d'action lisible par machine — direction (Haussier / Neutre / Baissier) + confiance (0 = pur split à trois, 100 = unanime) + niveau de risque (faible / moyen / élevé, mappé depuis la qualité). Consommable par les outils quant, les workflows Zapier / Make / n8n et les pipelines d'alerte.` }) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && signalPayload" class="signal-preview">
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Direction', '方向', { de: 'Richtung' , fr: 'Direction'}) }}</span>
                  <span :class="['signal-value', `signal-direction-${signalPayload.direction.toLowerCase()}`]">
                    {{ signalPayload.direction }}
                  </span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Confidence', '置信度', { de: 'Konfidenz' , fr: 'Confiance'}) }}</span>
                  <span class="signal-value">{{ signalPayload.confidence_pct }}%</span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Risk tier', '风险等级', { de: 'Risikoklasse' , fr: 'Niveau de risque'}) }}</span>
                  <span :class="['signal-value', `signal-risk-${signalPayload.risk_tier}`]">
                    {{ signalPayload.risk_tier }}
                  </span>
                </div>
                <div class="signal-row signal-row-breakdown">
                  <span class="signal-label">{{ $tr('Breakdown', '分布', { de: 'Aufschlüsselung', fr: 'Répartition' }) }}</span>
                  <span class="signal-value">
                    🟢 {{ signalPayload.bullish_pct }}% · ⚪ {{ signalPayload.neutral_pct }}% · 🔴 {{ signalPayload.bearish_pct }}%
                  </span>
                </div>
              </div>
              <div v-else-if="isPublic && signalLoading" class="signal-loading">
                {{ $tr('Loading signal…', '加载信号中…', { de: 'Signal wird geladen…', fr: 'Chargement du signal…' }) }}
              </div>
              <div v-else-if="isPublic && signalError" class="signal-empty">
                {{ signalError }}
              </div>
              <div v-else-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable the trading signal.', '发布模拟以启用交易信号。', { de: 'Veröffentliche die Simulation, um das Handelssignal zu aktivieren.', fr: 'Publiez la simulation pour activer le signal de trading.' }) }}
              </div>

              <div class="transcript-actions">
                <a
                  v-if="isPublic && signalJsonUrl"
                  class="transcript-download-btn"
                  :href="signalJsonUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-signal.json`"
                >
                  ↓ {{ $tr('Download signal.json', '下载 signal.json', { de: 'signal.json herunterladen', fr: 'Télécharger signal.json' }) }}
                </a>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Signal URL', '信号 URL', { de: 'Signal-URL' , fr: 'URL du signal'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('signalUrl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'signalUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ signalJsonUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('curl snippet', 'curl 片段', { de: 'curl-Snippet', fr: 'extrait curl' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('signalCurl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'signalCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ signalCurlSnippet }}</code></pre>
              </div>
            </div>

            <!-- Peak-round belief analytics — the analytical counterpart
                 to trajectory.csv (raw per-round data) and chart.svg
                 (the visual). Collapses the whole trajectory into a
                 single O(n) inflection-point summary: when each stance
                 peaked + the most volatile round. Same publish gate as
                 every other surface; pure stdlib, zero new deps. -->
            <div class="transcript-section signal-section">
              <div class="transcript-head">
                <span class="transcript-icon">📊</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Peak beliefs (JSON)', '峰值信念(JSON)', { de: 'Spitzenüberzeugungen (JSON)', fr: 'Pics de croyances (JSON)' }) }}
                    <span v-if="peakPayload" class="signal-direction-badge signal-direction-bullish">
                      {{ $tr('Most volatile: round', '最波动:回合', { de: 'Volatilste Runde:', fr: 'Tour le plus volatil :' }) }} {{ peakPayload.most_volatile_round }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Machine-readable inflection points — the round each stance (bullish / neutral / bearish) peaked, the most volatile round, and the maximum round-over-round swing. The analytical summary quant tools need alongside trajectory.csv, in one O(n) pass.', '机器可读的拐点 — 每种立场(看涨 / 中性 / 看跌)达到峰值的回合、最波动的回合,以及最大的回合间摆动幅度。量化工具在 trajectory.csv 之外需要的分析摘要,一次 O(n) 遍历即可获得。', { de: 'Maschinenlesbare Wendepunkte — die Runde, in der jede Haltung (Bullish/Neutral/Bearish) ihren Höhepunkt erreichte, die volatilste Runde und der maximale Rundenübergang. Die analytische Zusammenfassung, die Quant-Tools neben trajectory.csv benötigen, in einem O(n)-Durchlauf.' , fr: 'Points d\'inflexion lisibles par machine — le tour de pic de chaque position, le tour le plus volatil, et le swing max entre deux tours. Le résumé analytique pour les outils quant, en un seul passage O(n).'}) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && peakPayload" class="signal-preview">
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Bullish peak', '看涨峰值', { de: 'Bullish-Höhepunkt' , fr: 'Pic haussier'}) }}</span>
                  <span class="signal-value signal-direction-bullish">
                    {{ peakPayload.bullish.pct }}% · {{ $tr('round', '回合', { de: 'Runde' , fr: 'tour'}) }} {{ peakPayload.bullish.round }}
                  </span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Bearish peak', '看跌峰值', { de: 'Bearish-Höhepunkt' , fr: 'Pic baissier'}) }}</span>
                  <span class="signal-value signal-direction-bearish">
                    {{ peakPayload.bearish.pct }}% · {{ $tr('round', '回合', { de: 'Runde' }) }} {{ peakPayload.bearish.round }}
                  </span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Most volatile', '最波动', { de: 'Volatilste' , fr: 'Plus volatil'}) }}</span>
                  <span class="signal-value">
                    {{ $tr('round', '回合', { de: 'Runde' }) }} {{ peakPayload.most_volatile_round }} (±{{ peakPayload.max_swing_pct }}%)
                  </span>
                </div>
                <div class="signal-row signal-row-breakdown">
                  <span class="signal-label">{{ $tr('Total rounds', '总回合数', { de: 'Gesamtrunden' , fr: 'Tours totaux'}) }}</span>
                  <span class="signal-value">{{ peakPayload.total_rounds }}</span>
                </div>
              </div>
              <div v-else-if="isPublic && peakLoading" class="signal-loading">
                {{ $tr('Loading peak beliefs…', '加载峰值信念中…', { de: 'Spitzenüberzeugungen werden geladen…' , fr: 'Chargement des croyances de pic…'}) }}
              </div>
              <div v-else-if="isPublic && peakError" class="signal-empty">
                {{ peakError }}
              </div>
              <div v-else-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable peak-round analytics.', '发布模拟以启用峰值回合分析。', { de: 'Veröffentliche die Simulation, um die Spitzenrunden-Analyse zu aktivieren.' , fr: 'Publiez la simulation pour activer l\'analyse des pics de tour.'}) }}
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Peak-round URL', '峰值回合 URL', { de: 'Spitzenrunden-URL' , fr: 'URL du pic de tour'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('peakUrl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'peakUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ peakRoundUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('curl snippet', 'curl 片段', { de: 'curl-Snippet', fr: 'extrait curl' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('peakCurl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'peakCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ peakCurlSnippet }}</code></pre>
              </div>
            </div>

            <!-- Belief volatility — the turbulence counterpart to
                 peak-round. peak-round picks the single most-volatile
                 round; volatility describes the *distribution* of
                 round-over-round swings (mean / std dev / max), a
                 normalized 0-100 index, and a converging / stable /
                 contested trend label. The third leg of the analytical
                 quadrant alongside signal.json (where) and peak-round
                 (when), so a quant tool can tell a high-volatility
                 Bullish result from a low-volatility one. Same publish
                 gate + pure-stdlib derivation; zero new deps. -->
            <div class="transcript-section signal-section volatility-section">
              <div class="transcript-head">
                <span class="transcript-icon">📈</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Belief volatility (JSON)', '信念波动率(JSON)', { de: 'Überzeugungsvolatilität (JSON)', fr: 'Volatilité des croyances (JSON)' }) }}
                    <span
                      v-if="volatilityPayload"
                      class="signal-direction-badge"
                      :class="volatilityTrendBadgeClass(volatilityPayload.trend)"
                    >
                      {{ volatilityTrendLabel(volatilityPayload.trend) }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('The turbulence layer alongside signal.json (direction) and peak-round (when). Mean + std dev + max of the round-over-round swing, a normalized 0-100 volatility index, and a stable / converging / contested trend label. High-volatility Bullish ≠ low-volatility Bullish for a position-sizing model.', '与 signal.json(方向)和 peak-round(时机)并列的动荡层。回合间摆动的均值 + 标准差 + 最大值,归一化的 0-100 波动指数,以及稳定 / 收敛 / 争议的趋势标签。对仓位模型而言,高波动看涨 ≠ 低波动看涨。', { de: 'Die Turbulenzsicht neben signal.json (Richtung) und peak-round (Zeitpunkt). Mittelwert + Std.-Abw. + Maximum des rundenübergreifenden Schwings, ein normierter 0-100-Volatilitätsindex und ein Stabilitäts-/Konvergenz-/Streit-Trendlabel. Hohe Volatilität Bullish ≠ niedrige Volatilität Bullish für ein Positionsgrößenmodell.', fr: 'La couche de turbulence aux côtés de signal.json (direction) et peak-round (quand). Moyenne + écart-type + max de la variation tour à tour, un indice de volatilité normalisé 0-100, et un label de tendance stable / convergent / contesté. Haussier haute volatilité ≠ Haussier basse volatilité pour un modèle de dimensionnement de position.' }) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && volatilityPayload" class="signal-preview">
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Volatility index', '波动指数', { de: 'Volatilitätsindex' , fr: 'Indice de volatilité'}) }}</span>
                  <span class="signal-value">
                    {{ volatilityPayload.volatility_index }} / 100
                  </span>
                </div>
                <div class="volatility-bar-wrap">
                  <div
                    class="volatility-bar"
                    :class="volatilityIndexBucket(volatilityPayload.volatility_index)"
                    :style="{ width: volatilityIndexBarWidth(volatilityPayload.volatility_index) }"
                  ></div>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Max swing', '最大摆动', { de: 'Maximaler Schwing' , fr: 'Swing max'}) }}</span>
                  <span class="signal-value">
                    ±{{ volatilityPayload.max_delta_pct }}% · {{ $tr('round', '回合', { de: 'Runde' }) }} {{ volatilityPayload.max_delta_round }}
                  </span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Mean swing', '平均摆动', { de: 'Mittlerer Schwing' , fr: 'Swing moyen'}) }}</span>
                  <span class="signal-value">±{{ volatilityPayload.mean_delta_pct }}%</span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Std dev', '标准差', { de: 'Std.-Abw.' , fr: 'Écart-type'}) }}</span>
                  <span class="signal-value">±{{ volatilityPayload.std_dev_delta_pct }}%</span>
                </div>
                <div class="signal-row signal-row-breakdown">
                  <span class="signal-label">{{ $tr('Path', '路径', { de: 'Verlauf' , fr: 'Chemin'}) }}</span>
                  <span class="signal-value">
                    {{ volatilityTrendLabel(volatilityPayload.trend) }}
                    · {{ volatilityPayload.delta_count }} {{ $tr('deltas', '差值', { de: 'Deltas' , fr: 'deltas'}) }}
                  </span>
                </div>
              </div>
              <div v-else-if="isPublic && volatilityLoading" class="signal-loading">
                {{ $tr('Loading volatility…', '加载波动率中…', { de: 'Volatilität wird geladen…' , fr: 'Chargement de la volatilité…'}) }}
              </div>
              <div v-else-if="isPublic && volatilityError" class="signal-empty">
                {{ volatilityError }}
              </div>
              <div v-else-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable volatility analytics.', '发布模拟以启用波动率分析。', { de: 'Veröffentliche die Simulation, um die Volatilitätsanalyse zu aktivieren.' , fr: 'Publiez la simulation pour activer l\'analyse de volatilité.'}) }}
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Volatility URL', '波动率 URL', { de: 'Volatilitäts-URL' , fr: 'URL de volatilité'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('volatilityUrl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'volatilityUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ volatilityUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('curl snippet', 'curl 片段', { de: 'curl-Snippet', fr: 'extrait curl' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('volatilityCurl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'volatilityCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ volatilityCurlSnippet }}</code></pre>
              </div>
            </div>

            <!-- Per-agent belief sparklines — the agent-level companion
                 to chart.svg (aggregate curve) and peak-round
                 (inflection points). Each agent's belief position over
                 rounds, drawn as a compact SVG polyline colored by final
                 stance. Answers the swarm-convergence question ("which
                 agent anchored the consensus? did one cohort align
                 first?") without parsing the transcript. Same publish
                 gate + pure-stdlib derivation as every other surface;
                 zero new deps. -->
            <div class="transcript-section signal-section sparklines-section">
              <div class="transcript-head">
                <span class="transcript-icon">🤖</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Agent trajectories (JSON)', '智能体轨迹(JSON)', { de: 'Agenten-Trajektorien (JSON)', fr: 'Trajectoires d\'agents (JSON)' }) }}
                    <span v-if="sparklinesPayload" class="signal-direction-badge signal-direction-bullish">
                      {{ sparklinesPayload.agent_count }} {{ $tr('agents', '个智能体', { de: 'Agenten', fr: 'agents' }) }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr(`Per-agent belief sparklines — each agent's position across rounds, colored by final stance (bullish / neutral / bearish). The agent-level layer under chart.svg's aggregate curve: which agent anchored the consensus, which cohort aligned first. Same ±0.2 threshold every surface uses.`, '单智能体信念迷你趋势图 — 每个智能体在各回合的立场,按最终立场着色(看涨 / 中性 / 看跌)。chart.svg 聚合曲线之下的智能体层:哪个智能体锚定了共识,哪个群体最先对齐。与所有界面一致的 ±0.2 阈值。', { de: `Überzeugungssparklines pro Agent — die Position jedes Agenten über die Runden, farblich nach Endstance (bullish/neutral/bearish). Die Agentenebene unter chart.svg's Aggregatkurve: welcher Agent den Konsens verankert hat, welche Gruppe sich zuerst ausgerichtet hat. Gleiche ±0,2-Schwelle wie alle anderen Ansichten.` , fr: `Sparklines par agent — position de chaque agent au fil des tours, colorée par position finale.`}) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && sparklinesPayload && sparklinesPayload.agents.length" class="sparklines-list">
                <div
                  v-for="agent in sparklinesPayload.agents"
                  :key="agent.agent_id"
                  class="sparkline-row"
                >
                  <span class="sparkline-name" :title="agent.name">{{ agent.name }}</span>
                  <svg
                    class="sparkline-svg"
                    :viewBox="`0 0 ${SPARK_W} ${SPARK_H}`"
                    :width="SPARK_W"
                    :height="SPARK_H"
                    preserveAspectRatio="none"
                    role="img"
                    :aria-label="`${agent.name}: ${agent.final_stance}`"
                  >
                    <line
                      :x1="0" :y1="SPARK_H / 2" :x2="SPARK_W" :y2="SPARK_H / 2"
                      class="sparkline-axis"
                    />
                    <polyline
                      :points="sparklinePoints(agent.trajectory)"
                      fill="none"
                      :stroke="agent.color"
                      stroke-width="1.3"
                      stroke-linejoin="round"
                      stroke-linecap="round"
                    />
                  </svg>
                  <span class="sparkline-stance" :style="{ color: agent.color }">
                    {{ agent.final_stance }}
                  </span>
                </div>
                <div v-if="!sparklinesPayload.has_per_agent_data" class="sparkline-note">
                  {{ $tr('Only one round of data — sparklines need ≥2 rounds to show a trend.', '只有一个回合的数据 — 迷你趋势图需要 ≥2 个回合才能显示趋势。', { de: 'Nur eine Runde Daten — Sparklines benötigen ≥2 Runden, um einen Trend anzuzeigen.', fr: `Une seule tour de données — les sparklines ont besoin d'au moins 2 tours pour montrer une tendance.` }) }}
                </div>
              </div>
              <div v-else-if="isPublic && sparklinesLoading" class="signal-loading">
                {{ $tr('Loading agent trajectories…', '加载智能体轨迹中…', { de: 'Agenten-Trajektorien werden geladen…' , fr: 'Chargement des trajectoires d\'agents…'}) }}
              </div>
              <div v-else-if="isPublic && sparklinesError" class="signal-empty">
                {{ sparklinesError }}
              </div>
              <div v-else-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable agent trajectories.', '发布模拟以启用智能体轨迹。', { de: 'Veröffentliche die Simulation, um Agenten-Trajektorien zu aktivieren.' , fr: 'Publiez la simulation pour activer les trajectoires d\'agents.'}) }}
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Sparklines URL', '迷你趋势图 URL', { de: 'Sparklines-URL' , fr: 'URL des sparklines'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('sparkUrl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'sparkUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ agentSparklinesUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('curl snippet', 'curl 片段', { de: 'curl-Snippet', fr: 'extrait curl' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('sparkCurl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'sparkCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ sparklinesCurlSnippet }}</code></pre>
              </div>
            </div>

            <!-- Agent roster (agents.json) — the participants surface.
                 Sparklines above show *how* each agent's belief moved;
                 this section shows *who they were*. Name + username +
                 bio + persona preview + demographics + final stance
                 derived from the same trajectory.json the sparklines
                 read, so the ±0.2 stance bucket here matches the
                 sparkline's color. Researchers comparing pool
                 composition across runs read this surface; AntFleet
                 benchmark jobs cross-reference agent personas with
                 outcome quality. Same publish gate + pure-stdlib
                 derivation as every other surface; zero new deps. -->
            <div class="transcript-section signal-section agents-section">
              <div class="transcript-head">
                <span class="transcript-icon">🧑‍🤝‍🧑</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Agent roster (JSON)', '智能体名册(JSON)', { de: 'Agentenliste (JSON)', fr: 'Liste des agents (JSON)' }) }}
                    <span v-if="agentsPayload" class="signal-direction-badge signal-direction-bullish">
                      {{ agentsPayload.agent_count }} {{ $tr('participants', '位参与者', { de: 'Teilnehmer', fr: 'participants' }) }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Per-agent identity export — name, username, bio, persona preview, demographics (age / country / profession / mbti / interested topics), karma, plus final stance and rounds participated. The participants companion to sparklines (which show belief trajectories): this surface answers who was in the debate. Persona is previewed to 280 chars; full text remains in transcript.md.', '单智能体身份导出 — 姓名、用户名、简介、persona 预览、人口属性(年龄 / 国家 / 职业 / mbti / 关注话题)、karma,加上最终立场与参与回合数。迷你趋势图的参与者侧补充(迷你趋势图展示信念轨迹):此界面回答”辩论中有谁”。Persona 预览截至 280 字符;完整文本保留在 transcript.md。', { de: 'Identitätsexport pro Agent — Name, Benutzername, Bio, Persona-Vorschau, Demografik (Alter/Land/Beruf/MBTI/Interessenthemen), Karma sowie Endstance und teilgenommene Runden. Die Teilnehmer-Ergänzung zu Sparklines (die die Überzeugungstrajektorien zeigen): diese Ansicht beantwortet, wer an der Debatte teilnahm. Persona wird auf 280 Zeichen gekürzt; vollständiger Text verbleibt in transcript.md.' , fr: 'Export d\'identité par agent — nom, bio, données démographiques, karma, position finale et tours participés.'}) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && agentsPayload && agentsPayload.agents.length" class="agents-list">
                <div
                  v-for="agent in agentsPayload.agents.slice(0, 12)"
                  :key="agent.agent_id"
                  class="agent-row"
                >
                  <div class="agent-row-head">
                    <span class="agent-name" :title="agent.name">{{ agent.name }}</span>
                    <span
                      v-if="agent.username"
                      class="agent-handle"
                    >@{{ agent.username }}</span>
                    <span
                      class="agent-stance-chip"
                      :style="{ color: agentStanceColor(agent.final_stance) }"
                    >{{ agent.final_stance }}</span>
                  </div>
                  <div v-if="agentDemographicTags(agent).length" class="agent-tags">
                    <span
                      v-for="(tag, i) in agentDemographicTags(agent)"
                      :key="i"
                      class="agent-tag"
                    >{{ tag }}</span>
                  </div>
                  <div v-if="agent.persona_preview" class="agent-persona">
                    {{ agent.persona_preview }}
                  </div>
                </div>
                <div v-if="agentsPayload.agents.length > 12" class="agents-overflow-note">
                  {{ $tr('Showing top 12 by final stance — full roster in the JSON payload.', '按最终立场显示前 12 位 — 完整名册见 JSON。', { de: 'Top 12 nach Endstance — vollständige Liste im JSON-Payload.' , fr: 'Top 12 par position finale — registre complet dans le JSON.'}) }}
                </div>
                <div v-if="!agentsPayload.has_trajectory_data" class="sparkline-note">
                  {{ $tr('No trajectory data yet — every agent shows the profile-only neutral default.', '尚无轨迹数据 — 每位智能体显示仅画像的中性默认值。', { de: 'Noch keine Trajektoriendaten — jeder Agent zeigt den profilbasierten neutralen Standardwert.' , fr: 'Pas encore de données de trajectoire — profil neutre par défaut.'}) }}
                </div>
              </div>
              <div v-else-if="isPublic && agentsLoading" class="signal-loading">
                {{ $tr('Loading agent roster…', '加载智能体名册中…', { de: 'Agentenliste wird geladen…' , fr: 'Chargement du registre des agents…'}) }}
              </div>
              <div v-else-if="isPublic && agentsError" class="signal-empty">
                {{ agentsError }}
              </div>
              <div v-else-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable the agent roster.', '发布模拟以启用智能体名册。', { de: 'Veröffentliche die Simulation, um die Agentenliste zu aktivieren.' , fr: 'Publiez la simulation pour activer le registre des agents.'}) }}
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Agents JSON URL', '智能体 JSON URL', { de: 'Agenten-JSON-URL' , fr: 'URL JSON des agents'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('agentsUrl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'agentsUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ agentsJsonUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('curl snippet', 'curl 片段', { de: 'curl-Snippet', fr: 'extrait curl' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('agentsCurl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'agentsCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ agentsCurlSnippet }}</code></pre>
              </div>
            </div>

            <!-- Polymarket-shaped prediction JSON — the first share
                 surface adapted for a specific external integrator
                 (a Polymarket trading bot). Reshapes the signal.json
                 primitive into the YES / NO binary-market envelope
                 a bot consumes between "simulation result" and
                 "actionable market signal". Stricter publish gate:
                 only completed sims emit a payload (a Polymarket
                 bot acting on a mid-run signal would chase numbers
                 that can still flip). Same publish gate + pure
                 stdlib posture as every other surface; zero new
                 deps. -->
            <div class="transcript-section signal-section polymarket-section">
              <div class="transcript-head">
                <span class="transcript-icon">🎯</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Polymarket prediction (JSON)', 'Polymarket 预测(JSON)', { de: 'Polymarket-Prognose (JSON)', fr: `Prédiction Polymarket (JSON)` }) }}
                    <span v-if="polymarketYesPct !== ''" class="signal-direction-badge polymarket-yes-badge">
                      {{ $tr('YES', 'YES', { de: 'JA', fr: 'OUI' }) }} · {{ polymarketYesPct }}%
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Binary YES / NO probability shape a Polymarket trading bot expects — one curl call between "simulation result" and "actionable market signal". Direction-aware: a Bullish swarm emits high yes_probability; Bearish swarm emits low; Neutral lands exactly at 0.5. Confidence tier (speculative / moderate / confident / high-conviction) for position-sizing logic.', '为 Polymarket 交易机器人量身的二元 YES / NO 概率结构 —「模拟结果」与「可执行市场信号」之间的一次 curl 调用。方向感知:看涨群体输出高 yes_probability;看跌输出低;中性恰好为 0.5。置信度等级(speculative / moderate / confident / high-conviction)用于仓位规模逻辑。', { de: 'Binäre JA/NEIN-Wahrscheinlichkeitsform, die ein Polymarket-Handelsbot erwartet — ein curl-Aufruf zwischen „Simulationsergebnis" und „handelbarem Marktsignal". Richtungsbewusst: ein Bullish-Schwarm gibt hohe yes_probability aus; Bearish niedrig; Neutral genau 0,5. Konfidenzklasse (spekulativ/moderat/zuversichtlich/high-conviction) für Positionsgrößenlogik.' , fr: 'Format binaire OUI/NON attendu par un bot Polymarket. Directionnel : haussier = OUI élevé ; baissier = faible ; neutre = 0.5.'}) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && polymarketPayload" class="signal-preview polymarket-preview">
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('YES probability', 'YES 概率', { de: 'JA-Wahrscheinlichkeit' , fr: 'Probabilité OUI'}) }}</span>
                  <span class="signal-value signal-direction-bullish">
                    {{ polymarketYesPct }}%
                  </span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('NO probability', 'NO 概率', { de: 'NEIN-Wahrscheinlichkeit' , fr: 'Probabilité NON'}) }}</span>
                  <span class="signal-value signal-direction-bearish">
                    {{ polymarketNoPct }}%
                  </span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Confidence tier', '置信度等级', { de: 'Konfidenzklasse' , fr: 'Niveau de confiance'}) }}</span>
                  <span :class="['signal-value', `polymarket-tier-${polymarketPayload.confidence_tier}`]">
                    {{ polymarketPayload.confidence_tier }}
                  </span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Risk tier', '风险等级', { de: 'Risikoklasse' }) }}</span>
                  <span :class="['signal-value', `signal-risk-${polymarketPayload.risk_tier}`]">
                    {{ polymarketPayload.risk_tier }}
                  </span>
                </div>
                <div class="signal-row signal-row-breakdown">
                  <span class="signal-label">{{ $tr('Suggested title', '建议标题', { de: 'Vorgeschlagener Titel' , fr: 'Titre suggéré'}) }}</span>
                  <span class="signal-value polymarket-title-value">
                    {{ polymarketPayload.suggested_market_title }}
                  </span>
                </div>
              </div>
              <div v-else-if="isPublic && polymarketLoading" class="signal-loading">
                {{ $tr('Loading Polymarket prediction…', '加载 Polymarket 预测中…', { de: 'Polymarket-Prognose wird geladen…' , fr: 'Chargement de la prédiction Polymarket…'}) }}
              </div>
              <div v-else-if="isPublic && polymarketError" class="signal-empty">
                {{ polymarketError }}
              </div>
              <div v-else-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable the Polymarket prediction.', '发布模拟以启用 Polymarket 预测。', { de: 'Veröffentliche die Simulation, um die Polymarket-Prognose zu aktivieren.' , fr: 'Publiez la simulation pour activer la prédiction Polymarket.'}) }}
              </div>

              <div class="transcript-actions">
                <a
                  v-if="isPublic && polymarketJsonUrl"
                  class="transcript-download-btn"
                  :href="polymarketJsonUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-polymarket.json`"
                >
                  ↓ {{ $tr('Download polymarket.json', '下载 polymarket.json', { de: 'polymarket.json herunterladen' , fr: 'Télécharger polymarket.json'}) }}
                </a>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Polymarket URL', 'Polymarket URL', { de: 'Polymarket-URL' , fr: 'URL Polymarket'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('polymarketUrl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'polymarketUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ polymarketJsonUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('curl snippet', 'curl 片段', { de: 'curl-Snippet', fr: 'extrait curl' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('polymarketCurl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'polymarketCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ polymarketCurlSnippet }}</code></pre>
              </div>
            </div>

            <!-- Simulation clone payload — the first share surface that
                 returns *inputs* rather than outputs. ``clone_payload``
                 is wire-compatible with POST /api/simulation/create, so
                 a caller with the same project_id re-runs the sim with
                 one curl; an AntFleet benchmark workflow forking the sim
                 swaps a knob and POSTs the body. Pairs with the existing
                 /api/simulation/compare endpoint: clone, run, then diff
                 the outputs against the original. Same publish gate as
                 every other surface; cached 1 hour because the inputs
                 are structural and don't shift round-to-round. -->
            <div class="transcript-section signal-section clone-section">
              <div class="transcript-head">
                <span class="transcript-icon">🔁</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Clone configuration (JSON)', '克隆配置(JSON)', { de: 'Klon-Konfiguration (JSON)', fr: 'Configuration du clone (JSON)' }) }}
                    <span v-if="isPublic && clonePayload" class="signal-direction-badge">
                      {{ $tr('inputs', '输入', { de: 'Eingaben', fr: 'Entrées' }) }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('The first share surface that returns inputs rather than outputs. clone_payload is wire-compatible with POST /api/simulation/create — fork the sim with one curl, or swap a knob (agent count, polymarket markets, demographic country) and POST a variant. simulation_requirement is echoed alongside for context; the create body itself does not accept the scenario text (that lives on the project).', '首个返回输入而非输出的共享表面。clone_payload 与 POST /api/simulation/create 完全兼容 —— 一条 curl 即可分叉模拟,或替换某个参数(智能体数量、Polymarket 市场数、人口学国家)再 POST 变体。simulation_requirement 在外层一并回显作为上下文;create 请求体本身不接收场景文本(它属于项目层)。', { de: 'Die erste Freigabeansicht, die Eingaben statt Ausgaben zurückgibt. clone_payload ist wire-kompatibel mit POST /api/simulation/create — simuliere mit einem curl oder tausche einen Parameter (Agentenanzahl, Polymarket-Märkte, demografisches Land) aus und poste eine Variante. simulation_requirement wird für den Kontext daneben angezeigt; der create-Body selbst akzeptiert den Szenariotext nicht (der liegt auf Projektebene).' , fr: 'La première surface de partage qui retourne des entrées plutôt que des sorties.'}) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && clonePayload" class="signal-preview clone-preview">
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Project', '项目', { de: 'Projekt' , fr: 'Projet'}) }}</span>
                  <span class="signal-value">{{ clonePayload.project_id || '—' }}</span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Graph', '图谱', { de: 'Graph', fr: 'Graphe' }) }}</span>
                  <span class="signal-value">{{ clonePayload.graph_id || '—' }}</span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">{{ $tr('Platforms', '平台', { de: 'Plattformen', fr: 'Plateformes' }) }}</span>
                  <span class="signal-value">
                    <span v-if="clonePayload.clone_payload?.enable_twitter">Twitter</span>
                    <span v-if="clonePayload.clone_payload?.enable_reddit">{{ clonePayload.clone_payload?.enable_twitter ? ' · ' : '' }}Reddit</span>
                    <span v-if="clonePayload.clone_payload?.enable_polymarket">{{ (clonePayload.clone_payload?.enable_twitter || clonePayload.clone_payload?.enable_reddit) ? ' · ' : '' }}Polymarket ({{ clonePayload.clone_payload?.polymarket_market_count }})</span>
                  </span>
                </div>
                <div class="signal-row" v-if="clonePayload.clone_payload?.country">
                  <span class="signal-label">{{ $tr('Country pack', '国家包', { de: 'Länderpaket' , fr: 'Pack de pays'}) }}</span>
                  <span class="signal-value">{{ clonePayload.clone_payload.country }}</span>
                </div>
                <div class="signal-row signal-row-breakdown" v-if="clonePayload.scenario_preview">
                  <span class="signal-label">{{ $tr('Scenario', '场景', { de: 'Szenario' , fr: 'Scénario'}) }}</span>
                  <span class="signal-value">{{ clonePayload.scenario_preview }}</span>
                </div>
              </div>
              <div v-else-if="isPublic && cloneLoading" class="signal-loading">
                {{ $tr('Loading clone configuration…', '加载克隆配置中…', { de: 'Klon-Konfiguration wird geladen…' , fr: 'Chargement de la configuration clone…'}) }}
              </div>
              <div v-else-if="isPublic && cloneError" class="signal-empty">
                {{ cloneError }}
              </div>
              <div v-else-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable the clone configuration.', '发布模拟以启用克隆配置。', { de: 'Veröffentliche die Simulation, um die Klon-Konfiguration zu aktivieren.' , fr: 'Publiez la simulation pour activer la configuration clone.'}) }}
              </div>

              <div class="transcript-actions">
                <a
                  v-if="isPublic && cloneJsonUrl"
                  class="transcript-download-btn"
                  :href="cloneJsonUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-clone.json`"
                >
                  ↓ {{ $tr('Download clone.json', '下载 clone.json', { de: 'clone.json herunterladen' , fr: 'Télécharger clone.json'}) }}
                </a>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Clone URL', '克隆 URL', { de: 'Klon-URL' , fr: 'URL du clone'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('cloneUrl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'cloneUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ cloneJsonUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('curl snippet', 'curl 片段', { de: 'curl-Snippet', fr: 'extrait curl' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('cloneCurl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'cloneCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ cloneCurlSnippet }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet" v-if="isPublic && clonePostBody">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('POST body (paste into /api/simulation/create)', 'POST 请求体(粘贴到 /api/simulation/create)', { de: 'POST-Body (in /api/simulation/create einfügen)', fr: 'Corps POST (à coller dans /api/simulation/create)' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('clonePostBody')"
                  >
                    {{ copied === 'clonePostBody' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy body', '复制请求体', { de: 'Body kopieren', fr: 'Copier le corps' }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ clonePostBody }}</code></pre>
              </div>
            </div>

            <!-- Simulation archive bundle — every published share
                 surface collapsed into a single ZIP download plus a
                 manifest.json pairing each contained file with its
                 SHA-256, byte size, and canonical source URL. The
                 take-offline primitive for researchers building
                 citation chains or running comparison studies across
                 multiple sims. Compositional: every bundled file is
                 byte-for-byte identical to what the standalone surface
                 route serves, so citation hashes line up across the
                 two distribution paths. -->
            <div class="transcript-section archive-section">
              <div class="transcript-head">
                <span class="transcript-icon">📦</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('Archive bundle (.zip)', '归档包(.zip)', { de: 'Archiv-Bundle (.zip)', fr: 'Archive (.zip)' }) }}
                    <span v-if="isPublic && archiveFileCount" class="archive-count-badge">
                      {{ archiveFileCount }} {{ $tr('files', '个文件', { de: 'Dateien', fr: 'fichiers' }) }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('One ZIP, every published surface inside — share card, chart SVG, trajectory CSV / JSONL, transcript, thread, reproduce.json, notebook, and signal.json. A manifest.json pairs each file with its SHA-256, byte size, and canonical source URL so citation hashes line up across both distribution paths.', '一个 ZIP,包含所有已发布的资源 — 分享卡、图表 SVG、轨迹 CSV / JSONL、转录稿、推文串、reproduce.json、Notebook 以及 signal.json。manifest.json 为每个文件提供 SHA-256、字节数和规范源 URL,使两种分发路径上的引用哈希保持一致。', { de: 'Ein ZIP mit allen veröffentlichten Inhalten — Share Card, Chart SVG, Trajektorien-CSV/JSONL, Protokoll, Thread, reproduce.json, Notebook und signal.json. Eine manifest.json weist jeder Datei ihren SHA-256, die Byte-Größe und die kanonische Quell-URL zu, sodass Zitierhashes über beide Verteilungspfade hinweg übereinstimmen.', fr: `Un ZIP, toutes les surfaces publiées à l'intérieur — carte de partage, graphique SVG, trajectoire CSV / JSONL, transcription, fil, reproduce.json, notebook, et signal.json. Un manifest.json associe chaque fichier à son SHA-256, sa taille en octets et son URL source canonique pour que les hashes de citation s'alignent sur les deux chemins de distribution.` }) }}
                  </div>
                </div>
              </div>

              <div v-if="isPublic && archiveAvailable" class="archive-summary">
                <div class="archive-summary-row">
                  <span class="archive-label">{{ $tr('Files inside', '包含文件', { de: 'Enthaltene Dateien', fr: 'Fichiers inclus' }) }}</span>
                  <span class="archive-value">{{ archiveFileCount }}</span>
                </div>
                <div class="archive-summary-row">
                  <span class="archive-label">{{ $tr('Format', '格式', { de: 'Format' , fr: 'Format'}) }}</span>
                  <span class="archive-value">application/zip · {{ $tr('deflate-compressed', 'deflate 压缩', { de: 'deflate-komprimiert' , fr: 'compressé (deflate)'}) }}</span>
                </div>
                <div class="archive-summary-row">
                  <span class="archive-label">{{ $tr('Citation', '引用', { de: 'Zitation' , fr: 'Citation'}) }}</span>
                  <span class="archive-value">{{ $tr('manifest.json with per-file SHA-256', 'manifest.json 含逐文件 SHA-256', { de: 'manifest.json mit SHA-256 pro Datei' , fr: 'manifest.json avec SHA-256 par fichier'}) }}</span>
                </div>
              </div>
              <div v-else-if="isPublic && archiveLoading" class="signal-loading">
                {{ $tr('Loading archive…', '加载归档中…', { de: 'Archiv wird geladen…' , fr: 'Chargement de l\'archive…'}) }}
              </div>
              <div v-else-if="isPublic && !archiveAvailable" class="signal-empty">
                {{ $tr(`Archive not available yet — the simulation hasn't recorded any exportable surfaces.`, '尚无可用的归档 — 模拟还没有记录任何可导出的内容。', { de: 'Archiv noch nicht verfügbar — die Simulation hat noch keine exportierbaren Inhalte aufgezeichnet.' , fr: 'Archive pas encore disponible — la simulation n\'a pas encore enregistré de surface exportable.'}) }}
              </div>
              <div v-else-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable the archive bundle.', '发布模拟以启用归档包。', { de: 'Veröffentliche die Simulation, um das Archiv-Bundle zu aktivieren.' , fr: 'Publiez la simulation pour activer le bundle d\'archive.'}) }}
              </div>

              <div class="transcript-actions">
                <a
                  v-if="isPublic && archiveZipUrl"
                  class="transcript-download-btn"
                  :href="archiveZipUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-archive.zip`"
                >
                  ↓ {{ $tr('Download archive.zip', '下载 archive.zip', { de: 'archive.zip herunterladen' , fr: 'Télécharger archive.zip'}) }}
                </a>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Archive URL', '归档 URL', { de: 'Archiv-URL' , fr: 'URL de l\'archive'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('archiveUrl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'archiveUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ archiveZipUrl || '—' }}</code></pre>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('curl snippet', 'curl 片段', { de: 'curl-Snippet', fr: 'extrait curl' }) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('archiveCurl')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'archiveCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                  </button>
                </div>
                <pre class="snippet-code"><code>{{ archiveCurlSnippet }}</code></pre>
              </div>
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
                    {{ $tr('Tweet thread (X / Twitter)', '推文串(X / Twitter)', { de: 'Tweet-Thread (X / Twitter)', fr: 'Fil de tweets (X / Twitter)' }) }}
                    <span v-if="threadTotal" class="thread-count-badge">{{ threadTotal }}</span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Auto-formatted thread — intro tweet, one tweet per belief inflection point (when the dominant stance flips), and a closing tweet with the watch + share URLs. Each tweet ≤280 characters; copy the whole thread or individual tweets.', '自动生成的推文串 — 介绍推文、每个信念转折点一条推文(主导立场翻转时)、末尾推文附带观看 + 分享 URL。每条推文 ≤280 字符;可复制整串或单条推文。', { de: 'Automatisch formatierter Thread — Eröffnungs-Tweet, ein Tweet pro Überzeugungswendepunkt (wenn die dominierende Haltung wechselt) und ein abschließender Tweet mit Watch- und Freigabe-URLs. Jeder Tweet ≤280 Zeichen; kopiere den gesamten Thread oder einzelne Tweets.', fr: `Fil auto-formaté — tweet d'intro, un tweet par point d'inflexion des croyances (quand la position dominante bascule), et un tweet de clôture avec les URLs de watch + share. Chaque tweet ≤280 caractères ; copiez tout le fil ou les tweets individuellement.` }) }}
                  </div>
                </div>
              </div>

              <div class="transcript-actions">
                <button
                  class="transcript-download-btn"
                  :disabled="!isPublic || threadLoading || !threadTweets.length"
                  @click="copy('threadFull')"
                >
                  <span v-if="threadLoading">{{ $tr('Loading…', '加载中…', { de: 'Wird geladen…', fr: 'Chargement…' }) }}</span>
                  <span v-else-if="copied === 'threadFull'">✓ {{ $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) }}</span>
                  <span v-else>📋 {{ $tr('Copy full thread', '复制整串', { de: 'Gesamten Thread kopieren', fr: 'Copier le fil complet' }) }}</span>
                </button>
                <a
                  v-if="isPublic && threadTxtUrl"
                  class="transcript-download-btn transcript-download-btn-secondary"
                  :href="threadTxtUrl"
                  :download="`miroshark-${simulationId.slice(0, 12)}-thread.txt`"
                >
                  ↓ {{ $tr('Download .txt', '下载 .txt', { de: '.txt herunterladen', fr: 'Télécharger .txt' }) }}
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
                  {{ $tr('Publish the simulation to enable the tweet thread.', '发布模拟以启用推文串。', { de: 'Veröffentliche die Simulation, um den Tweet-Thread zu aktivieren.', fr: 'Publiez la simulation pour activer le fil de tweets.' }) }}
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
                    :title="$tr('Copy this tweet', '复制此推文', { de: 'Diesen Tweet kopieren', fr: 'Copier ce tweet' })"
                  >
                    {{ copied === `threadOne-${idx}` ? '✓' : '⧉' }}
                  </button>
                  <span class="thread-tweet-num">{{ idx + 1 }} / {{ threadTweets.length }}</span>
                  <pre class="thread-tweet-body">{{ tweet }}</pre>
                  <span class="thread-tweet-len">{{ tweet.length }}/280</span>
                </div>
                <p v-if="threadTruncated" class="thread-truncated-note">
                  {{ $tr('Thread shortened — many inflections were folded into a single bridge tweet to keep the thread under 15 tweets.', '推文串已缩短 — 多个转折点被合并为一条桥接推文,以使整串保持在 15 条以内。', { de: 'Thread gekürzt — viele Wendepunkte wurden in einem Brücken-Tweet zusammengefasst, um den Thread unter 15 Tweets zu halten.', fr: 'Fil raccourci — plusieurs infléchissements ont été fusionnés dans un tweet-pont pour rester sous 15 tweets.' }) }}
                </p>
              </div>

              <div class="snippet-block transcript-snippet">
                <div class="snippet-head">
                  <span class="snippet-label">{{ $tr('Thread .txt URL (paste into a tweet scheduler)', '推文串 .txt URL(粘贴至推文排程工具)', { de: 'Thread-.txt-URL (in einen Tweet-Scheduler einfügen)' , fr: 'URL du thread .txt (à coller dans un planificateur)'}) }}</span>
                  <button
                    class="snippet-copy-btn"
                    @click="copy('threadTxt')"
                    :disabled="!isPublic"
                  >
                    {{ copied === 'threadTxt' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
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
                    {{ $tr('Distribution', '分发统计', { de: 'Verteilung', fr: 'Distribution' }) }}
                    <span v-if="isPublic && surfaceStatsTotal > 0" class="surface-stats-total-badge">
                      {{ surfaceStatsTotal }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('How many times each share surface has been served — the inbound side of the distribution loop the webhook log tracks on the outbound side.', '每个分享面已被服务的次数 — 分发回路的入站侧,webhook 日志跟踪的是出站侧。', { de: 'Wie oft jede Freigabeansicht ausgeliefert wurde — die Eingangsseite der Verteilungsschleife, die das Webhook-Log auf der Ausgangsseite verfolgt.', fr: 'Combien de fois chaque surface de partage a été servie — le côté entrant de la boucle de distribution que le log webhook suit côté sortant.' }) }}
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
                  {{ $tr('Publish the simulation to see distribution stats.', '发布模拟以查看分发统计。', { de: 'Veröffentliche die Simulation, um Verteilungsstatistiken anzuzeigen.', fr: 'Publiez la simulation pour voir les statistiques de distribution.' }) }}
                </div>
                <div v-else-if="surfaceStatsLoading" class="surface-stats-loading">
                  {{ $tr('Loading distribution data…', '加载分发数据…', { de: 'Verteilungsdaten werden geladen…' , fr: 'Chargement des données de distribution…'}) }}
                </div>
                <div v-else-if="surfaceStatsError" class="transcript-empty surface-stats-error">
                  {{ surfaceStatsError }}
                </div>
                <div v-else-if="surfaceStatsAllZero" class="transcript-empty">
                  {{ $tr('No surface serves recorded yet — share this simulation to see distribution data appear here.', '尚未记录任何分享面服务 — 分享此模拟即可在此查看分发数据。', { de: 'Noch keine Freigabeauslieferungen aufgezeichnet — teile diese Simulation, damit hier Verteilungsdaten erscheinen.' , fr: 'Aucune consultation — partagez cette simulation pour voir les données de distribution.'}) }}
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
                    <span class="surface-stats-label">{{ $tr('Total serves', '总服务数', { de: 'Gesamtauslieferungen' , fr: 'Consultations totales'}) }}</span>
                    <span class="surface-stats-count">{{ surfaceStatsTotal }}</span>
                  </div>
                </div>

                <div v-if="!surfaceStatsAllZero" class="surface-stats-caveat">
                  {{ $tr('Counts origin hits only — CDN and browser caches are not counted, so true audience reach is higher.', '仅统计源服务器命中 — 不计入 CDN 与浏览器缓存,实际受众覆盖更高。', { de: 'Zählt nur Ursprungsserver-Treffer — CDN- und Browser-Caches werden nicht gezählt, sodass die tatsächliche Reichweite höher ist.' , fr: 'Compte uniquement les hits d\'origine — la portée réelle est donc plus élevée.'}) }}
                </div>

                <div v-if="isPublic" class="surface-stats-actions">
                  <button
                    class="surface-stats-refresh"
                    type="button"
                    :disabled="surfaceStatsLoading"
                    @click="loadSurfaceStats"
                  >
                    <span v-if="surfaceStatsLoading">{{ $tr('Refreshing…', '刷新中…', { de: 'Wird aktualisiert…' , fr: 'Actualisation…'}) }}</span>
                    <span v-else>↻ {{ $tr('Refresh', '刷新', { de: 'Aktualisieren', fr: 'Actualiser' }) }}</span>
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
                    {{ $tr('Reproducibility config', '可复现配置', { de: 'Reproduzierbarkeitskonfiguration', fr: 'Configuration de reproductibilité' }) }}
                    <span
                      v-if="reproLineageBadge"
                      class="repro-lineage-badge"
                      :title="reproLineageTitle"
                    >
                      {{ reproLineageBadge }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Every parameter another researcher needs to reproduce this exact run — scenario, agents, rounds, platforms, time-config, director events, fork lineage. Citation-friendly JSON.', '另一位研究者复现此运行所需的全部参数 — 情景、智能体、轮次、平台、时序配置、导演事件、派生谱系。便于引用的 JSON。', { de: 'Alle Parameter, die ein anderer Forscher benötigt, um genau diesen Lauf zu reproduzieren — Szenario, Agenten, Runden, Plattformen, Zeitkonfiguration, Direktionsereignisse, Abstammung. Zitierbares JSON.', fr: 'Chaque paramètre dont un autre chercheur a besoin pour reproduire cette exécution exacte — scénario, agents, tours, plateformes, configuration temporelle, événements directeur, lignée de fork. JSON adapté à la citation.' }) }}
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
                  {{ $tr('Publish the simulation to expose the reproducibility config.', '发布模拟以公开可复现配置。', { de: 'Veröffentliche die Simulation, um die Reproduzierbarkeitskonfiguration freizugeben.', fr: 'Publiez la simulation pour exposer la configuration de reproductibilité.' }) }}
                </div>
                <div v-else-if="reproLoading" class="repro-loading">
                  {{ $tr('Loading reproduction blob…', '加载复现配置…', { de: 'Reproduktions-Blob wird geladen…', fr: 'Chargement du blob de reproduction…' }) }}
                </div>
                <div v-else-if="reproError" class="transcript-empty repro-error">
                  {{ reproError }}
                </div>
                <div v-else-if="reproBlob" class="repro-detail">
                  <div class="repro-summary-grid">
                    <div class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Schema', 'Schema', { de: 'Schema' , fr: 'Schéma'}) }}</span>
                      <span class="repro-summary-value">v{{ reproBlob.schema_version }}</span>
                    </div>
                    <div class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Agents', '智能体数', { de: 'Agenten', fr: 'Agents' }) }}</span>
                      <span class="repro-summary-value">{{ reproBlob.agent_count }}</span>
                    </div>
                    <div class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Rounds', '轮次', { de: 'Runden', fr: 'Tours' }) }}</span>
                      <span class="repro-summary-value">{{ reproBlob.total_rounds }}</span>
                    </div>
                    <div class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Platforms', '平台', { de: 'Plattformen', fr: 'Plateformes' }) }}</span>
                      <span class="repro-summary-value">{{ reproPlatformsLabel }}</span>
                    </div>
                    <div v-if="reproDirectorEventCount > 0" class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Director events', '导演事件', { de: 'Direktionsereignisse', fr: 'Événements Director' }) }}</span>
                      <span class="repro-summary-value">{{ reproDirectorEventCount }}</span>
                    </div>
                    <div v-if="reproBlob.lineage && reproBlob.lineage.kind !== 'original'" class="repro-summary-row">
                      <span class="repro-summary-key">{{ $tr('Lineage', '谱系', { de: 'Abstammung', fr: 'Lignée' }) }}</span>
                      <span class="repro-summary-value">{{ reproLineageDescription }}</span>
                    </div>
                  </div>

                  <div class="repro-curl-block">
                    <div class="repro-curl-head">
                      <span class="repro-curl-label">{{ $tr('Reproduce via curl', '使用 curl 复现', { de: 'Per curl reproduzieren', fr: 'Reproduire via curl' }) }}</span>
                      <button class="snippet-copy-btn" @click="copy('reproCurl')">
                        {{ copied === 'reproCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                      </button>
                    </div>
                    <pre class="snippet-code"><code>{{ reproCurlSnippet }}</code></pre>
                  </div>

                  <div class="repro-note">
                    {{ $tr('Anyone with this config has every parameter that shapes the run — same scenario, same agent count, same rounds, same platform mix. Identical exports of a finished sim are bytewise-identical, so the file hash is a stable citation key.', '获得此配置的任何人都拥有决定该运行的所有参数 — 相同情景、相同智能体数、相同轮次、相同平台组合。已完成模拟的多次导出在字节级别完全一致,因此文件哈希可作为稳定的引用键。', { de: 'Jeder mit dieser Konfiguration hat alle Parameter, die den Lauf bestimmen — gleiches Szenario, gleiche Agentenanzahl, gleiche Runden, gleicher Plattform-Mix. Identische Exporte einer abgeschlossenen Simulation sind byteweise identisch, sodass der Datei-Hash ein stabiler Zitierschlüssel ist.', fr: `Toute personne avec cette configuration a tous les paramètres qui façonnent l'exécution — même scénario, même nombre d'agents, mêmes tours, même mix de plateformes. Les exports identiques d'une simulation terminée sont identiques octet par octet, donc le hash du fichier est une clé de citation stable.` }) }}
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
                    {{ $tr('Download reproduce.json', '下载 reproduce.json', { de: 'reproduce.json herunterladen', fr: 'Télécharger reproduce.json' }) }}
                  </a>
                  <button
                    class="snippet-copy-btn repro-copy-url"
                    type="button"
                    @click="copy('reproUrl')"
                    :disabled="!reproDownloadUrl"
                  >
                    {{ copied === 'reproUrl' ? '✓ ' + $tr('URL copied', '已复制 URL', { de: 'URL kopiert', fr: 'URL copiée' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                  </button>
                  <button
                    class="surface-stats-refresh repro-refresh"
                    type="button"
                    :disabled="reproLoading"
                    @click="loadRepro"
                  >
                    <span v-if="reproLoading">{{ $tr('Refreshing…', '刷新中…', { de: 'Wird aktualisiert…' }) }}</span>
                    <span v-else>↻ {{ $tr('Refresh', '刷新', { de: 'Aktualisieren', fr: 'Actualiser' }) }}</span>
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
                    {{ $tr('Jupyter notebook', 'Jupyter 笔记本', { de: 'Jupyter Notebook', fr: 'Notebook Jupyter' }) }}
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Pre-populated analysis notebook — trajectory data embedded, belief evolution + final consensus charts scaffolded, ready to run in JupyterLab, VS Code, or Colab. No network call back required.', '预填的分析笔记本 — 嵌入轨迹数据,已搭建信念演化与最终共识图表,可在 JupyterLab、VS Code 或 Colab 中直接运行,无需联网。', { de: 'Vorab befülltes Analyse-Notebook — Trajektoriendaten eingebettet, Überzeugungsverlauf und finale Konsensdiagramme vorbereitet, sofort ausführbar in JupyterLab, VS Code oder Colab. Kein Netzwerkabruf erforderlich.', fr: `Notebook d'analyse pré-rempli — données de trajectoire intégrées, graphiques d'évolution des croyances + consensus final pré-écrits, prêt à exécuter dans JupyterLab, VS Code ou Colab. Aucun rappel réseau requis.` }) }}
                  </div>
                </div>
              </div>

              <div class="notebook-body">
                <div v-if="!isPublic" class="transcript-empty">
                  {{ $tr('Publish the simulation to enable the Jupyter notebook export.', '发布模拟以启用 Jupyter 笔记本导出。', { de: 'Veröffentliche die Simulation, um den Jupyter-Notebook-Export zu aktivieren.', fr: `Publiez la simulation pour activer l'export du notebook Jupyter.` }) }}
                </div>
                <template v-else>
                  <div class="repro-curl-block">
                    <div class="repro-curl-head">
                      <span class="repro-curl-label">{{ $tr('Download via curl', '使用 curl 下载', { de: 'Per curl herunterladen', fr: 'Télécharger via curl' }) }}</span>
                      <button class="snippet-copy-btn" @click="copy('notebookCurl')">
                        {{ copied === 'notebookCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                      </button>
                    </div>
                    <pre class="snippet-code"><code>{{ notebookCurlSnippet }}</code></pre>
                  </div>
                  <div class="repro-note">
                    {{ $tr('Identical exports of a finished simulation produce bytewise-identical notebooks — the file hash is a stable citation key, same property the reproduce.json blob has. Opens directly in JupyterLab, VS Code, and Google Colab.', '已完成模拟的多次导出在字节级别完全一致 — 文件哈希可作为稳定的引用键,与 reproduce.json 一致。可直接在 JupyterLab、VS Code 与 Google Colab 中打开。', { de: 'Identische Exporte einer abgeschlossenen Simulation erzeugen byteweise identische Notebooks — der Datei-Hash ist ein stabiler Zitierschlüssel, dieselbe Eigenschaft wie beim reproduce.json-Blob. Öffnet sich direkt in JupyterLab, VS Code und Google Colab.', fr: `Les exports identiques d'une simulation terminée produisent des notebooks identiques octet par octet — le hash du fichier est une clé de citation stable, même propriété que le blob reproduce.json. S'ouvre directement dans JupyterLab, VS Code et Google Colab.` }) }}
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
                      {{ $tr('Download notebook.ipynb', '下载 notebook.ipynb', { de: 'notebook.ipynb herunterladen', fr: 'Télécharger notebook.ipynb' }) }}
                    </a>
                    <button
                      class="snippet-copy-btn repro-copy-url"
                      type="button"
                      @click="copy('notebookUrl')"
                      :disabled="!notebookDownloadUrl"
                    >
                      {{ copied === 'notebookUrl' ? '✓ ' + $tr('URL copied', '已复制 URL', { de: 'URL kopiert', fr: 'URL copiée' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                    </button>
                  </div>
                </template>
              </div>
            </div>

            <!-- BibTeX academic citation — completes the citation
                 arc. Reproduce.json carries the parameters; the
                 notebook carries the analysis; this one carries the
                 reference. Drops straight into a LaTeX \bibliography{}
                 block or imports cleanly into Zotero / Mendeley via
                 their "Import from URL" flow. The note field carries
                 the reproduce.json SHA-256 so a reviewer can verify
                 the citation points at the same parameters years
                 later via sha256sum --check; the annote field carries
                 the OriginTrail DKG UAL when the sim has been
                 anchored on-chain. Same publish gate as every other
                 share surface; pure stdlib, zero new deps. -->
            <div class="transcript-section bibtex-section">
              <div class="transcript-head">
                <span class="transcript-icon">📖</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('BibTeX citation (.bib)', 'BibTeX 引用(.bib)', { de: 'BibTeX-Zitation (.bib)' , fr: 'Citation BibTeX (.bib)'}) }}
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Drop-in @misc{…} entry for a LaTeX paper, Zotero library, or Mendeley collection. The note field carries the reproduce.json SHA-256 (verifiable via sha256sum --check); the annote field carries the OriginTrail DKG UAL when the sim has been anchored on-chain. Zotero + Mendeley both import this URL directly via "Import from URL".', '可直接放入 LaTeX 论文、Zotero 文献库或 Mendeley 集合的 @misc{…} 条目。note 字段携带 reproduce.json 的 SHA-256(可用 sha256sum --check 校验);annote 字段在模拟已上链时携带 OriginTrail DKG UAL。Zotero 与 Mendeley 都可通过"从 URL 导入"直接导入此 URL。', { de: 'Einbettbarer @misc{…}-Eintrag für ein LaTeX-Papier, eine Zotero-Bibliothek oder eine Mendeley-Sammlung. Das note-Feld enthält den SHA-256 von reproduce.json (überprüfbar via sha256sum --check); das annote-Feld enthält den OriginTrail-DKG-UAL, wenn die Simulation on-chain verankert wurde. Zotero und Mendeley importieren diese URL direkt über „Von URL importieren".' }) }}
                  </div>
                </div>
              </div>

              <div v-if="!isPublic" class="signal-empty">
                {{ $tr('Publish the simulation to enable the BibTeX citation.', '发布模拟以启用 BibTeX 引用。', { de: 'Veröffentliche die Simulation, um die BibTeX-Zitation zu aktivieren.' , fr: 'Publiez la simulation pour activer la citation BibTeX.'}) }}
              </div>

              <template v-else>
                <div class="snippet-block transcript-snippet">
                  <div class="snippet-head">
                    <span class="snippet-label">{{ $tr('cite.bib URL', 'cite.bib URL', { de: 'cite.bib URL' , fr: 'URL cite.bib'}) }}</span>
                    <button
                      class="snippet-copy-btn"
                      @click="copy('citeBibUrl')"
                      :disabled="!citeBibUrl"
                    >
                      {{ copied === 'citeBibUrl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy URL', '复制 URL', { de: 'URL kopieren', fr: `Copier l'URL` }) }}
                    </button>
                  </div>
                  <pre class="snippet-code"><code>{{ citeBibUrl || '—' }}</code></pre>
                </div>

                <div class="snippet-block transcript-snippet">
                  <div class="snippet-head">
                    <span class="snippet-label">{{ $tr('curl snippet', 'curl 片段', { de: 'curl-Snippet', fr: 'extrait curl' }) }}</span>
                    <button
                      class="snippet-copy-btn"
                      @click="copy('citeBibCurl')"
                      :disabled="!citeBibUrl"
                    >
                      {{ copied === 'citeBibCurl' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                    </button>
                  </div>
                  <pre class="snippet-code"><code>{{ citeBibCurlSnippet }}</code></pre>
                </div>

                <div class="snippet-block transcript-snippet">
                  <div class="snippet-head">
                    <span class="snippet-label">{{ $tr('LaTeX \\cite', 'LaTeX \\cite', { de: 'LaTeX \\cite', fr: 'LaTeX \\cite' }) }}</span>
                    <button
                      class="snippet-copy-btn"
                      @click="copy('citeBibLatex')"
                      :disabled="!citeBibUrl"
                    >
                      {{ copied === 'citeBibLatex' ? '✓ ' + $tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' }) : $tr('Copy snippet', '复制代码片段', { de: 'Code-Snippet kopieren', fr: `Copier l'extrait` }) }}
                    </button>
                  </div>
                  <pre class="snippet-code"><code>{{ citeBibLatexSnippet }}</code></pre>
                </div>

                <div class="transcript-actions">
                  <a
                    v-if="citeBibUrl"
                    class="transcript-download-btn"
                    :href="citeBibUrl"
                    :download="`miroshark-${simulationId.slice(0, 12)}.bib`"
                  >
                    ↓ {{ $tr('Download .bib', '下载 .bib', { de: '.bib herunterladen', fr: 'Télécharger .bib' }) }}
                  </a>
                </div>
              </template>
            </div>

            <!-- OriginTrail DKG citation — the on-chain provenance
                 surface. Opt-in: rendered only when DKG_* env vars are
                 wired up on this deployment. The "Publish to DKG"
                 button walks the WM→SWM→VM publish pipeline on the
                 operator's local DKG node, hashes the reproduce.json
                 bytes (citation key), and returns the UAL + Merkle
                 root + transaction hash so the simulation gets a
                 blockchain-anchored citation key. Idempotent — once
                 anchored, subsequent dialog opens read the cached
                 citation from disk without re-hitting the daemon. -->
            <div
              v-if="isPublic && notifConfig.dkg_configured"
              class="transcript-section dkg-section"
            >
              <div class="transcript-head dkg-head">
                <span class="transcript-icon">⛓️</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('OriginTrail DKG citation', 'OriginTrail DKG 引用', { de: 'OriginTrail DKG-Zitation', fr: 'Citation OriginTrail DKG' }) }}
                    <span
                      v-if="notifConfig.dkg_network"
                      class="lineage-count-chip"
                      :class="`dkg-network-chip-${notifConfig.dkg_network}`"
                    >
                      {{ notifConfig.dkg_network === 'mainnet'
                          ? $tr('mainnet', '主网', { de: 'Mainnet' , fr: 'mainnet'})
                          : $tr('testnet', '测试网', { de: 'Testnet' , fr: 'testnet'}) }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Anchor the scenario, agent count, consensus, quality, and reproduce.json hash on the OriginTrail DKG as a cryptographically verifiable Knowledge Asset. The returned UAL + Merkle root + transaction hash become a permanent citation key — same provenance property a DOI gives a paper.', '将情景、智能体数、共识、质量与 reproduce.json 哈希作为可加密验证的知识资产锚定到 OriginTrail DKG。返回的 UAL + Merkle 根 + 交易哈希就是永久引用键 — 提供与论文 DOI 同等的来源证明。', { de: 'Verankere Szenario, Agentenanzahl, Konsens, Qualität und reproduce.json-Hash auf dem OriginTrail DKG als kryptografisch verifizierbares Wissens-Asset. Der zurückgegebene UAL + Merkle-Root + Transaktions-Hash werden zum permanenten Zitierschlüssel — dieselbe Herkunftseigenschaft, die ein DOI einem Paper gibt.' , fr: 'Ancrez le scénario, le nombre d\'agents, le consensus, la qualité et le hash reproduce.json sur l\'OriginTrail DKG en tant que Knowledge Asset vérifiable. L\'UAL + racine Merkle + hash de transaction retournés deviennent une clé de citation permanente.'}) }}
                  </div>
                </div>
              </div>

              <div class="dkg-body">
                <!-- Already anchored — show the citation primitives -->
                <div v-if="dkgCitation && dkgCitation.ual" class="dkg-card">
                  <div class="dkg-row">
                    <span class="dkg-row-label">UAL</span>
                    <code
                      class="dkg-row-value dkg-row-mono"
                      :title="dkgCitation.ual"
                    >{{ formatUalShort(dkgCitation.ual) }}</code>
                    <button
                      class="snippet-copy-btn dkg-copy"
                      type="button"
                      @click="copy('dkgUal')"
                    >
                      {{ copied === 'dkgUal' ? '✓' : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                    </button>
                  </div>
                  <div v-if="dkgCitation.merkle_root" class="dkg-row">
                    <span class="dkg-row-label">{{ $tr('Merkle root', 'Merkle 根', { de: 'Merkle-Root', fr: 'Racine de Merkle' }) }}</span>
                    <code
                      class="dkg-row-value dkg-row-mono"
                      :title="dkgCitation.merkle_root"
                    >{{ formatHashShort(dkgCitation.merkle_root) }}</code>
                    <button
                      class="snippet-copy-btn dkg-copy"
                      type="button"
                      @click="copy('dkgMerkle')"
                    >
                      {{ copied === 'dkgMerkle' ? '✓' : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                    </button>
                  </div>
                  <div v-if="dkgCitation.transaction_hash" class="dkg-row">
                    <span class="dkg-row-label">{{ $tr('Transaction', '交易', { de: 'Transaktion', fr: 'Transaction' }) }}</span>
                    <code
                      class="dkg-row-value dkg-row-mono"
                      :title="dkgCitation.transaction_hash"
                    >{{ formatHashShort(dkgCitation.transaction_hash) }}</code>
                    <span v-if="typeof dkgCitation.block_number === 'number'" class="dkg-row-meta">
                      {{ $tr('block', '区块', { de: 'Block' , fr: 'bloc'}) }} #{{ dkgCitation.block_number }}
                    </span>
                  </div>
                  <div v-if="dkgCitation.reproduce_config_sha256" class="dkg-row">
                    <span class="dkg-row-label">{{ $tr('Config hash', '配置哈希', { de: 'Konfigurations-Hash' , fr: 'Hash de configuration'}) }}</span>
                    <code
                      class="dkg-row-value dkg-row-mono"
                      :title="dkgCitation.reproduce_config_sha256"
                    >{{ formatHashShort(dkgCitation.reproduce_config_sha256) }}</code>
                  </div>
                  <div class="dkg-actions">
                    <a
                      v-if="dkgCitation.explorer_url"
                      class="repro-download"
                      :href="dkgCitation.explorer_url"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ $tr('Open on DKG explorer ↗', '在 DKG 浏览器中打开 ↗', { de: 'Im DKG-Explorer öffnen ↗' , fr: 'Ouvrir sur l\'explorateur DKG ↗'}) }}
                    </a>
                    <span v-if="dkgCitation.finalized" class="dkg-finalized-badge">
                      ✓ {{ $tr('Finalized', '已最终确认', { de: 'Abgeschlossen' , fr: 'Finalisé'}) }}
                    </span>
                  </div>
                  <div class="repro-note">
                    {{ $tr('A verifier fetches reproduce.json, SHA-256s the bytes, and compares to the on-chain config hash. Match = the simulation parameters have not been altered since anchoring.', '验证者获取 reproduce.json,计算 SHA-256 后与链上配置哈希比对。匹配则证明该模拟参数自锚定后未被篡改。', { de: 'Ein Prüfer lädt reproduce.json herunter, berechnet den SHA-256 der Bytes und vergleicht ihn mit dem On-Chain-Konfigurations-Hash. Übereinstimmung = die Simulationsparameter wurden seit der Verankerung nicht verändert.' , fr: 'Un vérificateur récupère reproduce.json, en calcule le SHA-256 et le compare au hash de configuration on-chain. Correspondance = les paramètres n\'ont pas été modifiés depuis l\'ancrage.'}) }}
                  </div>
                </div>

                <!-- Not yet anchored — show the publish CTA -->
                <div v-else-if="!dkgLoading" class="dkg-card dkg-card-empty">
                  <div class="dkg-empty-text">
                    {{ $tr('No on-chain citation yet for this simulation.', '该模拟尚未生成链上引用。', { de: 'Noch keine On-Chain-Zitation für diese Simulation.' , fr: 'Pas encore de citation on-chain.'}) }}
                  </div>
                  <div class="dkg-actions">
                    <button
                      class="repro-download dkg-publish-btn"
                      type="button"
                      :disabled="dkgPublishing"
                      @click="publishDkg"
                    >
                      <span v-if="dkgPublishing">
                        {{ $tr('Anchoring on-chain…', '正在上链…', { de: 'Wird on-chain verankert…' , fr: 'Ancrage on-chain…'}) }}
                      </span>
                      <span v-else>
                        ⛓️ {{ $tr('Publish to DKG', '发布至 DKG', { de: 'Auf DKG veröffentlichen' , fr: 'Publier sur le DKG'}) }}
                      </span>
                    </button>
                  </div>
                  <div class="repro-note">
                    {{ $tr('Requires the local DKG daemon to be running (dkg start) and a funded wallet. Anchoring costs TRAC + gas on the configured chain.', '需要本地 DKG 守护进程已启动(dkg start)及一个已充值的钱包。上链需消耗所选链的 TRAC 与 gas 费。', { de: 'Erfordert, dass der lokale DKG-Daemon läuft (dkg start) und eine finanzierte Wallet vorhanden ist. Die Verankerung kostet TRAC + Gas auf der konfigurierten Chain.' , fr: 'Nécessite le démon DKG local et un portefeuille financé. L\'ancrage coûte du TRAC + gas.'}) }}
                  </div>
                </div>

                <div v-if="dkgError" class="webhook-log-message" :class="dkgErrorClass">
                  {{ dkgError }}
                </div>
              </div>
            </div>

            <!-- WaybackClaw AI Agent Archive — the agent-side citation
                 sibling of the DKG card. Opt-in: rendered only when
                 WAYBACKCLAW_AGENT_TOKEN is set on this deployment.
                 The "Submit to WaybackClaw" button POSTs a snapshot
                 (scenario, agent count, consensus, quality,
                 reproduce.json hash) to api.waybackclaw.space, which
                 pins it to IPFS and broadcasts a NIP-01 note to Nostr
                 relays before returning the snapshot id + IPFS CID +
                 Nostr event id. Idempotent — once submitted, subsequent
                 dialog opens read the cached record from disk without
                 re-hitting the API. Free for agents (no on-chain cost). -->
            <div
              v-if="isPublic && notifConfig.waybackclaw_configured"
              class="transcript-section dkg-section"
            >
              <div class="transcript-head dkg-head">
                <span class="transcript-icon">🗄️</span>
                <div class="transcript-head-body">
                  <div class="transcript-title">
                    {{ $tr('WaybackClaw archive', 'WaybackClaw 归档', { de: 'WaybackClaw-Archiv' , fr: 'Archive WaybackClaw'}) }}
                    <span class="lineage-count-chip dkg-network-chip-testnet">
                      {{ $tr('IPFS + Nostr', 'IPFS + Nostr', { de: 'IPFS + Nostr' , fr: 'IPFS + Nostr'}) }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Submit the snapshot (scenario, agent count, consensus, quality, reproduce.json hash) to the WaybackClaw AI Agent Archive. The archive pins the record to IPFS for content-addressed storage and broadcasts it to Nostr relays for real-time distribution — an open, agent-readable history of this MiroShark deployment.', '将快照(情景、智能体数、共识、质量、reproduce.json 哈希)提交至 WaybackClaw AI Agent 归档。归档会将记录固定到 IPFS 以实现内容寻址存储,并广播到 Nostr 中继以实现实时分发 — 为该 MiroShark 部署构建一份开放、可被其他智能体读取的历史记录。', { de: 'Sende den Snapshot (Szenario, Agentenanzahl, Konsens, Qualität, reproduce.json-Hash) an das WaybackClaw AI Agent Archive. Das Archiv pinnt den Eintrag auf IPFS für inhaltsadressierte Speicherung und sendet ihn an Nostr-Relays zur Echtzeit-Verteilung — eine offene, von anderen Agenten lesbare Geschichte dieses MiroShark-Deployments.' , fr: 'Soumettez l\'instantané (scénario, agents, consensus, qualité, hash reproduce.json) au WaybackClaw AI Agent Archive.'}) }}
                  </div>
                </div>
              </div>

              <div class="dkg-body">
                <!-- Already submitted — show the snapshot primitives -->
                <div v-if="wbcRecord && wbcRecord.id" class="dkg-card">
                  <div class="dkg-row">
                    <span class="dkg-row-label">{{ $tr('Snapshot', '快照', { de: 'Snapshot' , fr: 'Instantané'}) }}</span>
                    <code
                      class="dkg-row-value dkg-row-mono"
                      :title="wbcRecord.id"
                    >{{ wbcRecord.id }}</code>
                    <button
                      class="snippet-copy-btn dkg-copy"
                      type="button"
                      @click="copy('wbcId')"
                    >
                      {{ copied === 'wbcId' ? '✓' : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                    </button>
                  </div>
                  <div v-if="wbcRecord.agent_name" class="dkg-row">
                    <span class="dkg-row-label">{{ $tr('Agent', '智能体', { de: 'Agent', fr: 'Agent' }) }}</span>
                    <code class="dkg-row-value dkg-row-mono">
                      {{ wbcRecord.agent_name }}<span v-if="wbcRecord.agent_id"> · {{ wbcRecord.agent_id }}</span>
                    </code>
                  </div>
                  <div v-if="wbcRecord.ipfs_cid" class="dkg-row">
                    <span class="dkg-row-label">IPFS CID</span>
                    <code
                      class="dkg-row-value dkg-row-mono"
                      :title="wbcRecord.ipfs_cid"
                    >{{ formatHashShort(wbcRecord.ipfs_cid) }}</code>
                    <button
                      class="snippet-copy-btn dkg-copy"
                      type="button"
                      @click="copy('wbcIpfs')"
                    >
                      {{ copied === 'wbcIpfs' ? '✓' : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                    </button>
                  </div>
                  <div v-if="wbcRecord.nostr_event_id" class="dkg-row">
                    <span class="dkg-row-label">Nostr</span>
                    <code
                      class="dkg-row-value dkg-row-mono"
                      :title="wbcRecord.nostr_event_id"
                    >{{ formatHashShort(wbcRecord.nostr_event_id) }}</code>
                    <button
                      class="snippet-copy-btn dkg-copy"
                      type="button"
                      @click="copy('wbcNostr')"
                    >
                      {{ copied === 'wbcNostr' ? '✓' : $tr('Copy', '复制', { de: 'Kopieren', fr: 'Copier' }) }}
                    </button>
                  </div>
                  <div v-if="wbcRecord.reproduce_config_sha256" class="dkg-row">
                    <span class="dkg-row-label">{{ $tr('Config hash', '配置哈希', { de: 'Konfigurations-Hash', fr: 'Hash de config' }) }}</span>
                    <code
                      class="dkg-row-value dkg-row-mono"
                      :title="wbcRecord.reproduce_config_sha256"
                    >{{ formatHashShort(wbcRecord.reproduce_config_sha256) }}</code>
                  </div>
                  <div class="dkg-actions">
                    <a
                      v-if="wbcRecord.ipfs_gateway_url"
                      class="repro-download"
                      :href="wbcRecord.ipfs_gateway_url"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ $tr('Open on IPFS gateway ↗', '在 IPFS 网关中打开 ↗', { de: 'Im IPFS-Gateway öffnen ↗', fr: 'Ouvrir sur la passerelle IPFS ↗' }) }}
                    </a>
                    <a
                      v-if="wbcRecord.archive_url"
                      class="repro-download"
                      :href="wbcRecord.archive_url"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ $tr('View agent in archive ↗', '在归档中查看智能体 ↗', { de: 'Agenten im Archiv ansehen ↗', fr: `Voir l'agent dans l'archive ↗` }) }}
                    </a>
                  </div>
                  <div class="repro-note">
                    {{ $tr('A verifier fetches reproduce.json, SHA-256s the bytes, and compares to the config hash stored in the snapshot metadata. The IPFS CID makes the record itself content-addressed, and the Nostr event id gives any relay subscriber an independent witness of the submission.', '验证者获取 reproduce.json,计算 SHA-256 后与快照元数据中的配置哈希比对。IPFS CID 使记录本身可通过内容寻址访问,Nostr 事件 ID 让任意中继订阅者获得对该提交的独立见证。', { de: 'Ein Prüfer lädt reproduce.json herunter, berechnet den SHA-256 der Bytes und vergleicht ihn mit dem Konfigurations-Hash in den Snapshot-Metadaten. Die IPFS-CID macht den Eintrag selbst inhaltsadressierbar, und die Nostr-Ereignis-ID gibt jedem Relay-Abonnenten einen unabhängigen Zeugen der Einreichung.', fr: `Un vérificateur récupère reproduce.json, calcule le SHA-256 des octets et compare au hash de configuration stocké dans les métadonnées du snapshot. Le CID IPFS rend l'enregistrement lui-même adressé par son contenu, et l'id d'événement Nostr donne à tout abonné relais un témoin indépendant de la soumission.` }) }}
                  </div>
                </div>

                <!-- Not yet submitted — show the submit CTA -->
                <div v-else-if="!wbcLoading" class="dkg-card dkg-card-empty">
                  <div class="dkg-empty-text">
                    {{ $tr('Not yet submitted to the WaybackClaw archive.', '尚未提交至 WaybackClaw 归档。', { de: 'Noch nicht an das WaybackClaw-Archiv übermittelt.' , fr: 'Pas encore soumis à l\'archive WaybackClaw.'}) }}
                  </div>
                  <div class="dkg-actions">
                    <button
                      class="repro-download dkg-publish-btn"
                      type="button"
                      :disabled="wbcSubmitting"
                      @click="publishWaybackclaw"
                    >
                      <span v-if="wbcSubmitting">
                        {{ $tr('Submitting…', '正在提交…', { de: 'Wird übermittelt…' , fr: 'Soumission en cours…'}) }}
                      </span>
                      <span v-else>
                        🗄️ {{ $tr('Submit to WaybackClaw', '提交至 WaybackClaw', { de: 'An WaybackClaw übermitteln' , fr: 'Soumettre à WaybackClaw'}) }}
                      </span>
                    </button>
                  </div>
                  <div class="repro-note">
                    {{ $tr('Free for agents — no on-chain cost. The archive pins the snapshot to IPFS and broadcasts to Nostr.', '智能体提交免费 — 无链上费用。归档会将快照固定到 IPFS 并广播到 Nostr。', { de: 'Für Agenten kostenlos — keine On-Chain-Kosten. Das Archiv pinnt den Snapshot auf IPFS und sendet ihn an Nostr.' , fr: 'Gratuit — aucun coût on-chain. L\'archive épingle l\'instantané sur IPFS et le diffuse sur Nostr.'}) }}
                  </div>
                </div>

                <div v-if="wbcError" class="webhook-log-message" :class="wbcErrorClass">
                  {{ wbcError }}
                </div>
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
                    {{ $tr('Lineage', '谱系', { de: 'Abstammung' , fr: 'Lignée'}) }}
                    <span class="lineage-count-chip" v-if="lineageTotalChildren > 0">
                      {{ lineageTotalChildren }}
                      {{ lineageTotalChildren === 1
                          ? $tr('branch', '分支', { de: 'Verzweigung' , fr: 'branche'})
                          : $tr('branches', '分支', { de: 'Verzweigungen', fr: 'branches' }) }}
                    </span>
                  </div>
                  <div class="transcript-sub">
                    {{ $tr('Navigate the fork / counterfactual graph this simulation belongs to. Click a row to open that sim in a new tab.', '浏览此模拟所属的派生 / 反事实分支图。点击任意行可在新标签页中打开对应模拟。', { de: 'Navigiere im Fork-/Kontrafaktual-Graphen, zu dem diese Simulation gehört. Klicke auf eine Zeile, um diese Simulation in einem neuen Tab zu öffnen.' , fr: 'Naviguez dans le graphe de fork / contrefactuel de cette simulation. Cliquez sur une ligne pour l\'ouvrir dans un nouvel onglet.'}) }}
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
                  {{ $tr('Loading lineage…', '加载谱系中…', { de: 'Abstammung wird geladen…' , fr: 'Chargement de la lignée…'}) }}
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
                        <span class="lineage-row-tag">{{ $tr('Parent', '父级', { de: 'Übergeordnet' , fr: 'Parent'}) }}</span>
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
                        {{ $tr('Parent simulation is unpublished.', '父级模拟未发布。', { de: 'Übergeordnete Simulation ist nicht veröffentlicht.' , fr: 'La simulation parente n\'est pas publiée.'}) }}
                      </div>
                      <a
                        v-if="parentWatchUrl"
                        :href="parentWatchUrl"
                        target="_blank"
                        rel="noopener"
                        class="lineage-row-link"
                      >
                        {{ $tr('Open parent ↗', '打开父级 ↗', { de: 'Übergeordnete öffnen ↗' , fr: 'Ouvrir le parent ↗'}) }}
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
                            ? $tr('Child', '子级', { de: 'Untergeordnet' , fr: 'Enfant'})
                            : $tr('Children', '子级', { de: 'Untergeordnete' , fr: 'Enfants'}) }}
                      </span>
                      <span
                        v-if="lineageChildren.length < lineageTotalChildren"
                        class="lineage-truncated-note"
                      >
                        {{ $tr('Showing first', '显示前', { de: 'Zeige erste' , fr: 'Affichage des premiers'}) }}
                        {{ lineageChildren.length }}
                        {{ $tr('of', '/共', { de: 'von', fr: 'de' }) }}
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
                      <span v-if="lineageLoading">{{ $tr('Refreshing…', '刷新中…', { de: 'Wird aktualisiert…', fr: 'Actualisation…' }) }}</span>
                      <span v-else>↻ {{ $tr('Refresh', '刷新', { de: 'Aktualisieren', fr: 'Actualiser' }) }}</span>
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
                    {{ $tr('Mark outcome', '标记结果', { de: 'Ergebnis markieren', fr: 'Marquer le résultat' }) }}
                    <span v-if="outcome && outcome.label" class="outcome-saved-tag">
                      ✓ {{ outcomeLabelText(outcome.label) }}
                    </span>
                  </div>
                  <div class="outcome-sub">
                    {{ $tr('Did this simulation predict a real event? Annotate it and your run lands on', '此模拟预测到了真实事件吗?为它做标注,你的运行将出现在', { de: 'Hat diese Simulation ein reales Ereignis vorhergesagt? Annotiere es und dein Lauf erscheint auf', fr: 'Cette simulation a-t-elle prédit un événement réel ? Annotez-la et votre exécution apparaît sur' }) }}
                    <a href="/verified" target="_blank" rel="noopener">/verified</a>
                    {{ $tr('— the public hall of calls that landed.', ' — 已落地预测的公开展示厅。', { de: '— der öffentlichen Galerie der eingetroffenen Prognosen.', fr: '— le hall public des prédictions qui se sont vérifiées.' }) }}
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
                  :placeholder="$tr('Outcome URL (article, tweet, dashboard) — optional', '结果 URL(文章、推文、仪表板)— 可选', { de: 'Ergebnis-URL (Artikel, Tweet, Dashboard) — optional', fr: 'URL du résultat (article, tweet, dashboard) — optionnel' })"
                  class="outcome-input"
                  :disabled="!isPublic"
                  maxlength="500"
                />
                <textarea
                  v-model="outcomeForm.outcome_summary"
                  :placeholder="$tr('What happened, in one or two sentences (max 280 chars)', '用一两句话描述发生了什么(最多 280 字符)', { de: 'Was ist passiert, in ein oder zwei Sätzen (max. 280 Zeichen)' , fr: 'En une ou deux phrases (max 280 car.)'})"
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
                    <span v-if="outcomeSubmitting">{{ $tr('Saving…', '保存中…', { de: 'Wird gespeichert…' , fr: 'Enregistrement…'}) }}</span>
                    <span v-else-if="outcome">{{ $tr('Update outcome', '更新结果', { de: 'Ergebnis aktualisieren' , fr: 'Mettre à jour le résultat'}) }}</span>
                    <span v-else>{{ $tr('Save outcome', '保存结果', { de: 'Ergebnis speichern' , fr: 'Enregistrer le résultat'}) }}</span>
                  </button>
                  <a
                    v-if="outcome"
                    href="/verified"
                    target="_blank"
                    rel="noopener"
                    class="outcome-link"
                  >
                    {{ $tr('View on /verified ↗', '在 /verified 查看 ↗', { de: 'Auf /verified ansehen ↗' , fr: 'Voir sur /verified ↗'}) }}
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
                    {{ $tr('Webhook delivery history', 'Webhook 投递历史', { de: 'Webhook-Auslieferungsverlauf' , fr: 'Historique de livraison du webhook'}) }}
                    <span v-if="webhookLogTotal > 0" class="webhook-log-count">
                      {{ webhookLogTotal }} {{ webhookLogTotal === 1 ? $tr('attempt', '次', { de: 'Versuch' , fr: 'tentative'}) : $tr('attempts', '次', { de: 'Versuche' }) }}
                    </span>
                  </div>
                  <div class="webhook-log-sub">
                    {{ $tr('Auto-fires on simulation completion. Records the last 50 attempts on disk so a delivery failure is visible without checking server logs.', '在模拟完成时自动触发。最多在磁盘上保留 50 次投递记录,无需查看服务器日志即可发现失败。', { de: 'Wird bei Simulationsabschluss automatisch ausgelöst. Speichert die letzten 50 Versuche auf der Festplatte, sodass ein Auslieferungsfehler ohne Serverprotokoll-Prüfung sichtbar ist.' , fr: 'Se déclenche automatiquement à la fin de la simulation. Enregistre les 50 dernières tentatives sur le disque.'}) }}
                  </div>
                </div>
                <button
                  class="webhook-log-toggle"
                  @click="toggleWebhookLog"
                  :title="webhookLogExpanded ? $tr('Hide history', '隐藏历史', { de: 'Verlauf ausblenden' , fr: 'Masquer l\'historique'}) : $tr('Show history', '显示历史', { de: 'Verlauf anzeigen' })"
                >
                  {{ webhookLogExpanded ? '▾' : '▸' }}
                </button>
              </div>

              <div v-if="webhookLogExpanded" class="webhook-log-body">
                <div v-if="webhookLogLoading" class="webhook-log-loading">
                  {{ $tr('Loading delivery history…', '正在加载投递历史…', { de: 'Auslieferungsverlauf wird geladen…' , fr: 'Chargement de l\'historique de livraison…'}) }}
                </div>

                <div v-else-if="webhookLogConfigError" class="webhook-log-config-hint">
                  {{ $tr('Admin authentication is not configured on this deployment. Set MIROSHARK_ADMIN_TOKEN to enable the delivery log.', '此部署未配置管理员身份验证。设置 MIROSHARK_ADMIN_TOKEN 以启用投递日志。', { de: 'Admin-Authentifizierung ist auf diesem Deployment nicht konfiguriert. Setze MIROSHARK_ADMIN_TOKEN, um das Auslieferungsprotokoll zu aktivieren.' , fr: 'L\'authentification admin n\'est pas configurée. Définissez MIROSHARK_ADMIN_TOKEN pour activer le journal de livraison.'}) }}
                </div>

                <div v-else-if="webhookLogError" class="webhook-log-error">
                  {{ webhookLogError }}
                </div>

                <div v-else-if="webhookLogEntries.length === 0" class="webhook-log-empty">
                  {{ $tr('No deliveries recorded yet. The webhook fires automatically on simulation completion.', '暂无投递记录。Webhook 会在模拟完成时自动触发。', { de: 'Noch keine Auslieferungen aufgezeichnet. Der Webhook wird bei Simulationsabschluss automatisch ausgelöst.' , fr: 'Aucune livraison enregistrée. Le webhook se déclenche automatiquement.'}) }}
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
                    {{ $tr('Refresh', '刷新', { de: 'Aktualisieren', fr: 'Actualiser' }) }}
                  </button>
                  <button
                    class="webhook-log-retry"
                    @click="retryWebhook"
                    :disabled="webhookRetrying || !canRetryWebhook"
                    :title="canRetryWebhook ? $tr('Re-fire the webhook with the same payload', '使用相同 payload 重发 webhook', { de: 'Webhook mit demselben Payload erneut auslösen', fr: 'Re-déclencher le webhook avec le même payload' }) : $tr('Retry available after the simulation reaches a terminal state', '模拟到达终止状态后可重试', { de: 'Erneuter Versuch möglich, sobald die Simulation einen Terminalzustand erreicht', fr: 'Nouvelle tentative disponible après que la simulation atteigne un état terminal' })"
                  >
                    <span v-if="webhookRetrying">{{ $tr('Queueing…', '排队中…', { de: 'Wird in die Warteschlange gestellt…', fr: 'Mise en file…' }) }}</span>
                    <span v-else>{{ $tr('Retry delivery', '重试投递', { de: 'Auslieferung erneut versuchen', fr: `Réessayer l'envoi` }) }}</span>
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
                    :title="signatureHintExpanded ? $tr('Hide signature verification hint', '隐藏签名验证提示', { de: 'Signaturverifizierungshinweis ausblenden' , fr: 'Masquer l\'indice de vérification de signature'}) : $tr('Show signature verification hint', '显示签名验证提示', { de: 'Signaturverifizierungshinweis anzeigen' })"
                  >
                    <span class="signature-hint-icon">🔐</span>
                    <span class="signature-hint-title">
                      {{ $tr('Verify webhook signatures', '验证 webhook 签名', { de: 'Webhook-Signaturen verifizieren' , fr: 'Vérifier les signatures webhook'}) }}
                    </span>
                    <span class="signature-hint-chevron">{{ signatureHintExpanded ? '▾' : '▸' }}</span>
                  </button>
                  <div v-if="signatureHintExpanded" class="signature-hint-body">
                    <p class="signature-hint-line">
                      {{ $tr('Set the WEBHOOK_SECRET environment variable on this MiroShark instance and MiroShark will HMAC-sign every dispatch with an X-MiroShark-Signature header. Recipients verify with three lines of stdlib hmac — same scheme Stripe and GitHub use.',
                        '在这台 MiroShark 实例上设置 WEBHOOK_SECRET 环境变量,MiroShark 就会用 HMAC 对每一次投递签名,并通过 X-MiroShark-Signature 头部送出。消费方用三行 stdlib hmac 即可校验 — Stripe 和 GitHub 用的就是同一套。',
                        { de: 'Setze die Umgebungsvariable WEBHOOK_SECRET auf dieser MiroShark-Instanz und MiroShark signiert jede Auslieferung per HMAC mit einem X-MiroShark-Signature-Header. Empfänger verifizieren mit drei Zeilen stdlib hmac — dasselbe Schema wie Stripe und GitHub.' , fr: 'Définissez WEBHOOK_SECRET et MiroShark signera chaque envoi avec un HMAC via X-MiroShark-Signature.'}
                      ) }}
                    </p>
                    <code class="signature-hint-code">WEBHOOK_SECRET=&lt;your 32+ char secret&gt;</code>
                    <p class="signature-hint-line">
                      <a
                        href="https://github.com/aaronjmars/MiroShark/blob/main/docs/WEBHOOKS.md#verifying-webhook-signatures"
                        target="_blank"
                        rel="noopener"
                      >{{ $tr('Verification snippets (Python / Node.js / curl)', '验证示例(Python / Node.js / curl)', { de: 'Verifizierungs-Snippets (Python / Node.js / curl)' , fr: 'Extraits de vérification (Python / Node.js / curl)'}) }} ↗</a>
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
                  {{ isPublic ? $tr('Live on the public gallery', '已发布到公开画廊', { de: 'Live in der öffentlichen Galerie' , fr: 'En direct sur la galerie publique'}) : $tr('Submit to the public gallery', '提交到公开画廊', { de: 'In die öffentliche Galerie einreichen' }) }}
                </div>
                <div class="gallery-callout-desc">
                  <template v-if="isPublic">
                    {{ $tr('This simulation is now visible on', '此模拟现可在以下页面查看', { de: 'Diese Simulation ist jetzt sichtbar auf' , fr: 'Cette simulation est maintenant visible sur'}) }}
                    <a href="/explore" target="_blank" rel="noopener">/explore</a> —
                    {{ $tr('the public gallery where anyone can browse published runs and fork them into their own simulations.', '公开画廊,任何人都可浏览已发布运行并派生为自己的模拟。', { de: 'der öffentlichen Galerie, wo jeder veröffentlichte Läufe durchsuchen und sie in eigene Simulationen forken kann.' , fr: 'la galerie publique où chacun peut parcourir les runs publiés et les forker dans ses propres simulations.'}) }}
                  </template>
                  <template v-else>
                    {{ $tr(`Toggle "Public" above and this run joins the community gallery at`, '将上方切换为「公开」,该运行将加入社区画廊', { de: 'Schalte oben auf „Öffentlich" um und dieser Lauf erscheint in der Community-Galerie bei' , fr: 'Activez « Public » ci-dessus et ce run rejoint la galerie communautaire sur'}) }}
                    <a href="/explore" target="_blank" rel="noopener">/explore</a>.
                    {{ $tr('Others can browse it, view the full belief drift, and fork your agents into their own scenarios.', '其他人可以浏览、查看完整的信念漂移,并将你的智能体派生到他们自己的情景中。', { de: 'Andere können ihn durchsuchen, den gesamten Überzeugungsdrift einsehen und deine Agenten in ihre eigenen Szenarien forken.' , fr: 'D\'autres peuvent la parcourir et forker vos agents dans leurs propres scénarios.'}) }}
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
                {{ $tr('Open gallery ↗', '打开画廊 ↗', { de: 'Galerie öffnen ↗' , fr: 'Ouvrir la galerie ↗'}) }}
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
                    {{ $tr('Follow the gallery via RSS', '通过 RSS 关注画廊', { de: 'Galerie per RSS verfolgen' , fr: 'Suivre la galerie via RSS'}) }}
                  </div>
                  <div class="feed-callout-desc">
                    {{ $tr('Every newly published MiroShark simulation appears in your reader (Feedly, Readwise, Inoreader, Obsidian RSS, NetNewsWire, …). No login, no account.', '每个新发布的 MiroShark 模拟都会出现在你的阅读器中(Feedly、Readwise、Inoreader、Obsidian RSS、NetNewsWire 等)。无需登录,无需账户。', { de: 'Jede neu veröffentlichte MiroShark-Simulation erscheint in deinem Reader (Feedly, Readwise, Inoreader, Obsidian RSS, NetNewsWire, …). Kein Login, kein Konto.' , fr: 'Chaque nouvelle simulation publiée apparaît dans votre lecteur RSS. Sans connexion, sans compte.'}) }}
                  </div>
                </div>
              </div>
              <div class="feed-callout-actions">
                <a
                  class="feed-callout-link"
                  :href="feedAtomUrl"
                  target="_blank"
                  rel="noopener"
                  :title="$tr('Atom 1.0 feed of the public gallery', '公开画廊的 Atom 1.0 源', { de: 'Atom-1.0-Feed der öffentlichen Galerie' , fr: 'Flux Atom 1.0 de la galerie publique'})"
                >
                  {{ $tr('Atom feed ↗', 'Atom 源 ↗', { de: 'Atom-Feed ↗' , fr: 'Flux Atom ↗'}) }}
                </a>
                <a
                  class="feed-callout-link feed-callout-link-secondary"
                  :href="feedRssUrl"
                  target="_blank"
                  rel="noopener"
                  :title="$tr('RSS 2.0 feed of the public gallery', '公开画廊的 RSS 2.0 源', { de: 'RSS-2.0-Feed der öffentlichen Galerie' , fr: 'Flux RSS 2.0 de la galerie publique'})"
                >
                  RSS 2.0 ↗
                </a>
                <a
                  class="feed-callout-link feed-callout-link-secondary"
                  :href="feedVerifiedAtomUrl"
                  target="_blank"
                  rel="noopener"
                  :title="$tr('Atom feed restricted to verified predictions only', '仅限已验证预测的 Atom 源', { de: 'Atom-Feed nur für verifizierte Prognosen' , fr: 'Flux Atom limité aux prédictions vérifiées uniquement'})"
                >
                  {{ $tr('Verified only ↗', '仅已验证 ↗', { de: 'Nur verifizierte ↗' , fr: 'Vérifiés uniquement ↗'}) }}
                </a>
              </div>

              <!-- Filtered feed builder — the gallery's consensus /
                   quality / sort knobs composed onto the feed URL so a
                   reader can subscribe to a slice ("bullish + excellent",
                   "what's hot right now") rather than the full firehose.
                   The URL is fully composable; defaults are omitted from
                   the query string so an unfiltered selection keeps the
                   original feed URL.  -->
              <div class="feed-filter-builder">
                <div class="feed-filter-builder-title">
                  {{ $tr('Build a filtered feed', '构建筛选源', { de: 'Gefilterten Feed erstellen' , fr: 'Construire un flux filtré'}) }}
                </div>
                <div class="feed-filter-builder-controls">
                  <label class="feed-filter-control">
                    <span class="feed-filter-label">
                      {{ $tr('Consensus', '共识', { de: 'Konsens', fr: 'Consensus' }) }}
                    </span>
                    <select v-model="feedFilters.consensus" class="feed-filter-select">
                      <option value="">{{ $tr('Any', '全部', { de: 'Alle' , fr: 'Tout'}) }}</option>
                      <option value="bullish">{{ $tr('Bullish', '看涨', { de: 'Bullish', fr: 'Haussier' }) }}</option>
                      <option value="neutral">{{ $tr('Neutral', '中性', { de: 'Neutral', fr: 'Neutre' }) }}</option>
                      <option value="bearish">{{ $tr('Bearish', '看跌', { de: 'Bearish', fr: 'Baissier' }) }}</option>
                    </select>
                  </label>
                  <label class="feed-filter-control">
                    <span class="feed-filter-label">
                      {{ $tr('Quality', '质量', { de: 'Qualität', fr: 'Qualité' }) }}
                    </span>
                    <select v-model="feedFilters.quality" class="feed-filter-select">
                      <option value="">{{ $tr('Any', '全部', { de: 'Alle', fr: 'Tous' }) }}</option>
                      <option value="excellent">{{ $tr('Excellent', '优', { de: 'Ausgezeichnet', fr: 'Excellent' }) }}</option>
                      <option value="good">{{ $tr('Good', '良', { de: 'Gut', fr: 'Bon' }) }}</option>
                      <option value="fair">{{ $tr('Fair', '中', { de: 'Befriedigend', fr: 'Moyen' }) }}</option>
                      <option value="poor">{{ $tr('Poor', '差', { de: 'Schlecht', fr: 'Médiocre' }) }}</option>
                    </select>
                  </label>
                  <label class="feed-filter-control">
                    <span class="feed-filter-label">
                      {{ $tr('Sort', '排序', { de: 'Sortieren', fr: 'Trier' }) }}
                    </span>
                    <select v-model="feedFilters.sort" class="feed-filter-select">
                      <option value="date">{{ $tr('Newest', '最新', { de: 'Neueste', fr: 'Plus récents' }) }}</option>
                      <option value="trending">{{ $tr('Trending', '热门', { de: 'Trending', fr: 'Tendances' }) }}</option>
                      <option value="rounds">{{ $tr('Most rounds', '轮次最多', { de: 'Meiste Runden', fr: 'Le plus de tours' }) }}</option>
                      <option value="agents">{{ $tr('Most agents', '智能体最多', { de: 'Meiste Agenten', fr: `Le plus d'agents` }) }}</option>
                    </select>
                  </label>
                </div>
                <div class="feed-filter-builder-actions">
                  <input
                    class="feed-filter-url"
                    type="text"
                    readonly
                    :value="filteredFeedUrl"
                    :title="$tr('Copy and paste into Feedly, n8n, Zapier, or any RSS reader', '复制到 Feedly、n8n、Zapier 或其他任意 RSS 阅读器', { de: 'Kopiere und füge in Feedly, n8n, Zapier oder einen beliebigen RSS-Reader ein', fr: 'Copier-coller dans Feedly, n8n, Zapier, ou tout lecteur RSS' })"
                  />
                  <button
                    type="button"
                    class="feed-filter-copy"
                    :class="{ 'feed-filter-copy-active': filteredFeedActive }"
                    @click="copyFilteredFeedUrl"
                  >
                    <span v-if="copiedFilteredFeed">
                      {{ $tr('Copied ✓', '已复制 ✓', { de: 'Kopiert ✓', fr: 'Copié ✓' }) }}
                    </span>
                    <span v-else>
                      {{ $tr('Copy filtered feed URL', '复制筛选源链接', { de: 'Gefilterte Feed-URL kopieren', fr: `Copier l'URL du flux filtré` }) }}
                    </span>
                  </button>
                </div>
                <div class="feed-filter-builder-note">
                  {{ $tr('Subscribe in Feedly, Inoreader, n8n, Zapier, Make — filters match the gallery API exactly. Same ±0.2 stance threshold every other surface uses.', '可在 Feedly、Inoreader、n8n、Zapier、Make 等订阅。筛选条件与画廊 API 完全一致;采用与其他所有面板相同的 ±0.2 立场阈值。', { de: 'In Feedly, Inoreader, n8n, Zapier, Make abonnieren — Filter stimmen exakt mit der Galerie-API überein. Gleiche ±0,2 Haltungsschwelle wie alle anderen Ansichten.', fr: `S'abonner dans Feedly, Inoreader, n8n, Zapier, Make — les filtres correspondent exactement à l'API galerie. Même seuil de position ±0.2 que toutes les autres surfaces utilisent.` }) }}
                </div>
              </div>
            </div>

            <!-- Search-engine indexing row — every published simulation is
                 a /share/<id> page that researchers might land on through
                 a Google search. This row tells the operator their sim is
                 in the auto-generated /sitemap.xml that crawlers discover
                 via the standard robots.txt Sitemap: directive. -->
            <div class="feed-callout sitemap-callout">
              <div class="feed-callout-head">
                <span class="feed-callout-icon">🔍</span>
                <div class="feed-callout-body">
                  <div class="feed-callout-title">
                    {{ sitemapEnabled
                        ? $tr('Discoverable in web search', '可在网页搜索中发现', { de: 'In der Websuche auffindbar' , fr: 'Découvrable dans la recherche web'})
                        : $tr('Search indexing disabled', '已禁用搜索索引', { de: 'Suchindexierung deaktiviert' , fr: 'Indexation de recherche désactivée'}) }}
                  </div>
                  <div class="feed-callout-desc">
                    {{ sitemapEnabled
                        ? $tr(`Auto-generated /sitemap.xml lists every published simulation's share + watch URLs. /robots.txt advertises it via the standard Sitemap: directive — submit once to Google Search Console and every newly published sim becomes searchable.`, '自动生成的 /sitemap.xml 列出每个已发布模拟的 share 与 watch URL。/robots.txt 通过标准 Sitemap: 指令通告 — 在 Google Search Console 提交一次后,每个新发布的模拟即可被搜索到。', { de: 'Automatisch generierte /sitemap.xml listet die Share- und Watch-URLs jeder veröffentlichten Simulation auf. /robots.txt bewirbt sie über die Standard-Sitemap:-Direktive — einmal in der Google Search Console einreichen und jede neu veröffentlichte Simulation wird auffindbar.' , fr: '/sitemap.xml généré automatiquement liste les URL de partage et de direct de chaque simulation.'})
                        : $tr(`Sitemap disabled — set ENABLE_SITEMAP=true in your environment to surface this deployment's public simulations to search engines.`, '已禁用 Sitemap — 在环境中设置 ENABLE_SITEMAP=true,即可让此部署的公开模拟被搜索引擎收录。', { de: 'Sitemap deaktiviert — setze ENABLE_SITEMAP=true in deiner Umgebung, um die öffentlichen Simulationen dieses Deployments für Suchmaschinen sichtbar zu machen.' , fr: 'Sitemap désactivé — définissez ENABLE_SITEMAP=true pour exposer les simulations publiques dans la recherche.'}) }}
                  </div>
                </div>
              </div>
              <div v-if="sitemapEnabled" class="feed-callout-actions">
                <a
                  class="feed-callout-link"
                  :href="sitemapUrl"
                  target="_blank"
                  rel="noopener"
                  :title="$tr('Open /sitemap.xml in a new tab', '在新标签中打开 /sitemap.xml', { de: '/sitemap.xml in einem neuen Tab öffnen' , fr: 'Ouvrir /sitemap.xml dans un nouvel onglet'})"
                >
                  {{ $tr('View sitemap.xml ↗', '查看 sitemap.xml ↗', { de: 'sitemap.xml anzeigen ↗' , fr: 'Voir sitemap.xml ↗'}) }}
                </a>
              </div>
            </div>

            <!-- Terminal-state notification channels. The generic
                 webhook (PR #46) plus the two channel-native paths
                 land platform-formatted cards in the operator's
                 Discord / Slack channel of choice. Status chips render
                 the live config so an operator can see which of the
                 three channels are wired up without opening Settings.
                 The booleans come from /api/config/notifications. -->
            <div class="feed-callout notifications-callout">
              <div class="feed-callout-head">
                <span class="feed-callout-icon">🔔</span>
                <div class="feed-callout-body">
                  <div class="feed-callout-title">
                    {{ $tr('Channel notifications on completion', '完成时的频道通知', { de: 'Kanal-Benachrichtigungen bei Abschluss' , fr: 'Notifications de canal à la fin'}) }}
                  </div>
                  <div class="feed-callout-desc">
                    {{ $tr('MiroShark POSTs a platform-native card to each configured channel the moment a simulation completes or fails — Discord gets a consensus-coloured embed, Slack gets a Block Kit message, Email gets a multipart/alternative message with plain-text belief bars and an HTML CTA, the generic webhook gets the raw JSON. Each channel is opt-in via its own env var.', 'MiroShark 在模拟完成或失败时,会向每个已配置渠道推送对应平台原生的卡片 — Discord 收到按共识着色的 embed,Slack 收到 Block Kit 消息,邮件渠道发出包含纯文本信念条与 HTML CTA 的 multipart/alternative 邮件,通用 Webhook 收到原始 JSON。每个渠道可通过各自的环境变量单独启用。', { de: 'MiroShark sendet beim Abschluss oder Fehlschlag einer Simulation eine plattformspezifische Card an jeden konfigurierten Kanal — Discord erhält ein konsensgebärbtes Embed, Slack eine Block-Kit-Nachricht, E-Mail eine multipart/alternative-Nachricht mit Text-Überzeugungsbalken und HTML-CTA, der generische Webhook die rohe JSON. Jeder Kanal ist per eigener Umgebungsvariable aktivierbar.' , fr: 'MiroShark POSTe une carte native à chaque canal configuré dès la fin ou l\'échec d\'une simulation — Discord reçoit un embed coloré, Slack un Block Kit, Email un multipart/alternative, le webhook le JSON brut.'}) }}
                  </div>
                  <div class="notifications-chips">
                    <span
                      class="notifications-chip"
                      :class="{ 'notifications-chip-on': notifConfig.webhook_configured }"
                      :title="notifConfig.webhook_configured
                        ? $tr('Generic JSON webhook is wired up — Zapier / Make / n8n / IFTTT / custom listeners', '通用 JSON Webhook 已接入 — Zapier / Make / n8n / IFTTT / 自定义监听端点', { de: 'Generischer JSON-Webhook ist eingerichtet — Zapier / Make / n8n / IFTTT / eigene Listener' , fr: 'Le webhook JSON générique est configuré — Zapier / Make / n8n / IFTTT'})
                        : $tr('Set WEBHOOK_URL to enable the generic JSON webhook channel', '设置 WEBHOOK_URL 即可启用通用 JSON Webhook 渠道', { de: 'Setze WEBHOOK_URL, um den generischen JSON-Webhook-Kanal zu aktivieren' , fr: 'Définissez WEBHOOK_URL pour le webhook JSON'})"
                    >
                      <span class="notifications-chip-dot">{{ notifConfig.webhook_configured ? '✓' : '○' }}</span>
                      Webhook
                    </span>
                    <span
                      class="notifications-chip"
                      :class="{ 'notifications-chip-on': notifConfig.discord_configured }"
                      :title="notifConfig.discord_configured
                        ? $tr('Discord rich embeds are wired up — completed sims land as coloured cards', 'Discord rich embed 已接入 — 模拟完成后会以彩色卡片形式呈现', { de: 'Discord Rich Embeds sind eingerichtet — abgeschlossene Simulationen erscheinen als farbige Cards' , fr: 'Les Discord rich embeds sont configurés — les simulations terminées apparaissent en cartes colorées'})
                        : $tr('Set DISCORD_WEBHOOK_URL to enable Discord rich-embed cards', '设置 DISCORD_WEBHOOK_URL 即可启用 Discord rich embed 卡片', { de: 'Setze DISCORD_WEBHOOK_URL, um Discord-Rich-Embed-Cards zu aktivieren' , fr: 'Définissez DISCORD_WEBHOOK_URL pour les cartes Discord'})"
                    >
                      <span class="notifications-chip-dot">{{ notifConfig.discord_configured ? '✓' : '○' }}</span>
                      Discord
                    </span>
                    <span
                      class="notifications-chip"
                      :class="{ 'notifications-chip-on': notifConfig.slack_configured }"
                      :title="notifConfig.slack_configured
                        ? $tr('Slack Block Kit messages are wired up — completed sims land as channel cards', 'Slack Block Kit 已接入 — 模拟完成后会以频道卡片形式呈现', { de: 'Slack-Block-Kit-Nachrichten sind eingerichtet — abgeschlossene Simulationen erscheinen als Kanal-Cards' , fr: 'Les messages Slack Block Kit sont configurés'})
                        : $tr('Set SLACK_WEBHOOK_URL to enable Slack Block Kit messages', '设置 SLACK_WEBHOOK_URL 即可启用 Slack Block Kit 消息', { de: 'Setze SLACK_WEBHOOK_URL, um Slack-Block-Kit-Nachrichten zu aktivieren' , fr: 'Définissez SLACK_WEBHOOK_URL pour les messages Slack'})"
                    >
                      <span class="notifications-chip-dot">{{ notifConfig.slack_configured ? '✓' : '○' }}</span>
                      Slack
                    </span>
                    <span
                      class="notifications-chip"
                      :class="{ 'notifications-chip-on': notifConfig.email_configured }"
                      :title="notifConfig.email_configured
                        ? $tr('SMTP completion emails are wired up — every terminal-state transition ships a multipart/alternative message to the configured recipients', 'SMTP 完成邮件已接入 — 每次模拟达到终止状态都会向已配置收件人发出 multipart/alternative 邮件', { de: 'SMTP-Abschluss-E-Mails sind eingerichtet — jeder Terminalzustandsübergang sendet eine multipart/alternative-Nachricht an die konfigurierten Empfänger' , fr: 'Les emails de fin SMTP sont configurés — chaque transition envoie un message multipart/alternative'})
                        : $tr('Set SMTP_HOST and SMTP_TO to enable completion emails (SMTP_USER/SMTP_PASSWORD optional)', '设置 SMTP_HOST 与 SMTP_TO 即可启用完成邮件(SMTP_USER/SMTP_PASSWORD 可选)', { de: 'Setze SMTP_HOST und SMTP_TO, um Abschluss-E-Mails zu aktivieren (SMTP_USER/SMTP_PASSWORD optional)' , fr: 'Définissez SMTP_HOST et SMTP_TO pour les emails de fin'})"
                    >
                      <span class="notifications-chip-dot">{{ notifConfig.email_configured ? '✓' : '○' }}</span>
                      Email
                    </span>
                  </div>
                </div>
              </div>
              <div class="feed-callout-actions">
                <a
                  class="feed-callout-link feed-callout-link-secondary"
                  href="https://github.com/aaronjmars/MiroShark/blob/main/docs/NOTIFICATIONS.md"
                  target="_blank"
                  rel="noopener"
                  :title="$tr('Channel setup guide on GitHub', 'GitHub 上的渠道接入指南', { de: 'Kanal-Einrichtungsanleitung auf GitHub' , fr: 'Guide de configuration du canal sur GitHub'})"
                >
                  {{ $tr('Setup guide ↗', '接入指南 ↗', { de: 'Einrichtungsanleitung ↗' , fr: 'Guide de configuration ↗'}) }}
                </a>
              </div>
            </div>
          </div>

          <!-- Hint -->
          <div class="embed-dialog-hint">
            <span class="hint-icon">ⓘ</span>
            {{ $tr(`The widget reads from this instance's API, so viewers must be able to reach`, '组件读取自当前实例的 API,因此查看者必须能访问', { de: 'Das Widget liest von der API dieser Instanz, daher müssen Betrachter erreichbar sein:' , fr: 'Le widget lit depuis l\'API de cette instance, donc les visiteurs doivent pouvoir atteindre'}) }}
            <code>{{ origin }}</code>. {{ $tr('For public embeds, deploy MiroShark somewhere reachable from the internet.', '若要进行公开嵌入,请将 MiroShark 部署到互联网可访问的位置。', { de: 'Für öffentliche Einbettungen deploye MiroShark an einem vom Internet aus erreichbaren Ort.' , fr: 'Pour les embeds publics, déployez MiroShark à un endroit accessible depuis internet.'}) }}
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
  getChartSvgUrl,
  getBadgeUrl,
  getSignalJsonUrl,
  getSignalJson,
  getPeakRoundUrl,
  getPeakRound,
  getVolatilityUrl,
  getVolatility,
  getAgentSparklinesUrl,
  getAgentSparklines,
  getAgentsJsonUrl,
  getAgentsJson,
  getPolymarketJsonUrl,
  getPolymarketJson,
  getCloneJsonUrl,
  getCloneJson,
  getArchiveZipUrl,
  getArchiveSummary,
  getThreadTxtUrl,
  getThreadJsonUrl,
  getSurfaceStats,
  getReproductionUrl,
  getReproduction,
  getCiteBibUrl,
  getNotebookUrl,
  getSimulationLineage,
  getFeedUrl,
  getSitemapUrl,
  getSitemapConfig,
  getNotificationsConfig,
  getSimulationOutcome,
  submitSimulationOutcome,
  getWebhookLog,
  retryWebhookDelivery,
  getDkgCitation,
  publishToDkg,
  getWaybackclawRecord,
  publishToWaybackclaw,
  getFrameMetadata,
  buildWarpcastComposeUrl,
  createShareLink,
  listShareLinks,
  revokeShareLink,
} from '../api/simulation'
import { tr } from '../i18n'

const translatePresetName = (name) => {
  const map = {
    'Compact': tr('Compact', '紧凑', { de: 'Kompakt' , fr: 'Compact'}),
    'Standard': tr('Standard', '标准', { de: 'Standard' , fr: 'Standard'}),
    'Wide': tr('Wide', '宽屏', { de: 'Breit' , fr: 'Large'}),
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
    publishError.value = err?.response?.data?.error || err?.message || tr('Publish failed', '发布失败', { de: 'Veröffentlichung fehlgeschlagen' , fr: 'Échec de la publication'})
  } finally {
    publishing.value = false
  }
}

// ── Private share-link panel state ─────────────────────────────────────────
//
// Private share links bypass the `is_public` gate for the preview page
// only — see backend/app/services/share_link_service.py for the policy
// notes. The panel is admin-token gated (same scheme as publishSimulation);
// the backend surfaces 401/503 via the response interceptor and we render
// the message in `shareLinkError`.

const shareLinkExpiresInDays = ref(30)
const shareLinkBusy = ref(false)
const shareLinkError = ref('')
const shareLinks = ref([])

const loadShareLinks = async () => {
  if (!props.simulationId) return
  try {
    const res = await listShareLinks(props.simulationId)
    const tokens = res?.data?.tokens
    shareLinks.value = Array.isArray(tokens) ? tokens : []
  } catch (err) {
    // A 401/503 from a deployment with admin auth disabled shouldn't
    // crash the panel — leave the list empty and let the user surface
    // the error on a write attempt.
    shareLinks.value = []
  }
}

const mintShareLink = async () => {
  if (!props.simulationId) return
  shareLinkBusy.value = true
  shareLinkError.value = ''
  try {
    await createShareLink(props.simulationId, shareLinkExpiresInDays.value)
    await loadShareLinks()
  } catch (err) {
    shareLinkError.value =
      err?.response?.data?.error || err?.message || tr('Could not generate link', '无法生成链接', { de: 'Link konnte nicht generiert werden' , fr: 'Impossible de générer le lien'})
  } finally {
    shareLinkBusy.value = false
  }
}

const revokeShareLinkEntry = async (token) => {
  if (!props.simulationId || !token) return
  shareLinkBusy.value = true
  shareLinkError.value = ''
  try {
    await revokeShareLink(props.simulationId, token)
    await loadShareLinks()
  } catch (err) {
    shareLinkError.value =
      err?.response?.data?.error || err?.message || tr('Could not revoke link', '无法撤销链接', { de: 'Link konnte nicht widerrufen werden' , fr: 'Impossible de révoquer le lien'})
  } finally {
    shareLinkBusy.value = false
  }
}

const copyShareLink = async (url) => {
  if (!url) return
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(url)
    }
  } catch (err) {
    // Browser denied clipboard access; the URL is still visible in the
    // panel so the user can manually copy.
  }
}

watch(
  () => [props.open, props.simulationId],
  ([isOpen, simId]) => {
    if (isOpen && simId) loadShareLinks()
  },
  { immediate: true }
)

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

const chartSvgUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getChartSvgUrl(props.simulationId, origin.value)
})

const chartSvgEmbedSnippet = computed(() => {
  const url = chartSvgUrl.value || 'https://your-host/api/simulation/<id>/chart.svg'
  return `<img src="${url}" alt="MiroShark belief trajectory chart" style="max-width:100%;height:auto;" />`
})

// ── Status badge state ──────────────────────────────────────────────────
// Shields.io-compatible 20-pixel SVG embedded as `<img>` in any
// GitHub README, Notion page, Substack post, or personal site. The
// embed URL is the API URL — no separate "share badge" surface — so
// the live signal travels with the embed.

const badgeSvgUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getBadgeUrl(props.simulationId, origin.value)
})

const badgeMarkdownSnippet = computed(() => {
  const url = badgeSvgUrl.value || 'https://your-host/api/simulation/<id>/badge.svg'
  return `![MiroShark Belief Badge](${url})`
})

const badgeHtmlSnippet = computed(() => {
  const url = badgeSvgUrl.value || 'https://your-host/api/simulation/<id>/badge.svg'
  return `<img src="${url}" alt="MiroShark Belief Badge" height="20" />`
})

// ── BibTeX academic citation state ──────────────────────────────────────
// The reproduce.json + notebook + DKG triple gives a researcher the
// data, the analysis surface, and the on-chain anchor. cite.bib
// completes the loop: a one-call BibTeX entry that drops straight into
// LaTeX / Zotero / Mendeley. The endpoint URL doubles as the Zotero
// "Import from URL" address — the same string the operator copies for
// a curl pull works inside a reference manager.

const citeBibUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getCiteBibUrl(props.simulationId, origin.value)
})

const citeBibCurlSnippet = computed(() => {
  const url = citeBibUrl.value || 'https://your-host/api/simulation/<id>/cite.bib'
  const short = (props.simulationId || 'sim_unknown').slice(0, 12)
  return `curl -fsSL '${url}' -o miroshark-${short}.bib`
})

const citeBibLatexSnippet = computed(() => {
  // A reader who saw the URL might still want the in-paper reference
  // syntax — the citation key is deterministic from the sim id, same
  // shape the backend builder emits, so a paper author can paste this
  // ``\cite{}`` line before fetching the .bib file.
  const short = (props.simulationId || 'unknown').slice(0, 16)
  const sanitized = short.replace(/[^A-Za-z0-9_-]/g, '') || 'unknown'
  return `\\cite{miroshark-${sanitized}}`
})

// ── Trading signal state ────────────────────────────────────────────────
const signalPayload = ref(null)
const signalLoading = ref(false)
const signalError = ref('')

const signalJsonUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getSignalJsonUrl(props.simulationId, origin.value)
})

const signalDirection = computed(() => signalPayload.value?.direction || '')
const signalConfidence = computed(() => {
  const c = signalPayload.value?.confidence_pct
  return (typeof c === 'number') ? c.toFixed(1) : ''
})

const signalCurlSnippet = computed(() => {
  const url = signalJsonUrl.value || 'https://your-host/api/simulation/<id>/signal.json'
  return `curl -s "${url}"`
})

const loadSignal = async () => {
  if (!props.simulationId || !isPublic.value) {
    signalPayload.value = null
    return
  }
  signalLoading.value = true
  signalError.value = ''
  try {
    const payload = await getSignalJson(props.simulationId)
    if (payload && typeof payload === 'object') {
      signalPayload.value = payload
    } else {
      signalPayload.value = null
      signalError.value = tr('Signal not available yet — the simulation hasn\'t recorded any rounds.',
        '尚无可用的信号 — 模拟还没有记录任何回合。',
        { de: 'Signal noch nicht verfügbar — die Simulation hat noch keine Runden aufgezeichnet.' },
      )
    }
  } catch (err) {
    signalPayload.value = null
    signalError.value = err?.message || tr('Signal fetch failed', '信号获取失败', { de: 'Signal-Abruf fehlgeschlagen' , fr: 'Échec de la récupération du signal'})
  } finally {
    signalLoading.value = false
  }
}

// ── Peak-round analytics state ─────────────────────────────────────────
// The analytical counterpart to trajectory.csv / chart.svg: a single
// O(n) summary of the belief trajectory's inflection points. Same
// publish gate as signal.json; 404 means "no trajectory data yet".

const peakPayload = ref(null)
const peakLoading = ref(false)
const peakError = ref('')

const peakRoundUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getPeakRoundUrl(props.simulationId, origin.value)
})

const peakCurlSnippet = computed(() => {
  const url = peakRoundUrl.value || 'https://your-host/api/simulation/<id>/peak-round'
  return `curl -s "${url}"`
})

const loadPeakRound = async () => {
  if (!props.simulationId || !isPublic.value) {
    peakPayload.value = null
    return
  }
  peakLoading.value = true
  peakError.value = ''
  try {
    const payload = await getPeakRound(props.simulationId)
    if (payload && typeof payload === 'object') {
      peakPayload.value = payload
    } else {
      peakPayload.value = null
      peakError.value = tr('Peak-round analytics not available yet — the simulation has no trajectory data.',
        '尚无可用的峰值回合分析 — 模拟还没有轨迹数据。',
        { de: 'Spitzenrunden-Analyse noch nicht verfügbar — die Simulation hat keine Trajektoriendaten.' , fr: 'Analyse de pic pas encore disponible.'},
      )
    }
  } catch (err) {
    peakPayload.value = null
    peakError.value = err?.message || tr('Peak-round fetch failed', '峰值回合获取失败', { de: 'Spitzenrunden-Abruf fehlgeschlagen' , fr: 'Échec de la récupération du pic de tour'})
  } finally {
    peakLoading.value = false
  }
}

// ── Belief volatility state ────────────────────────────────────────────
// The turbulence counterpart to peak-round. Peak-round picks the single
// most-volatile round; volatility describes the *distribution* of
// round-over-round swings — mean / std dev / max / volatility_index /
// trend. Same publish gate; 404 means the sim has fewer than two rounds.

const volatilityPayload = ref(null)
const volatilityLoading = ref(false)
const volatilityError = ref('')

const volatilityUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getVolatilityUrl(props.simulationId, origin.value)
})

const volatilityCurlSnippet = computed(() => {
  const url = volatilityUrl.value || 'https://your-host/api/simulation/<id>/volatility'
  return `curl -s "${url}"`
})

const volatilityIndexBucket = (idx) => {
  // Three colour bands matching the documented trend semantics:
  // green ≤33 (calm), amber 34-66 (moderate), red ≥67 (turbulent).
  if (typeof idx !== 'number' || Number.isNaN(idx)) return 'volatility-bar-low'
  if (idx <= 33) return 'volatility-bar-low'
  if (idx <= 66) return 'volatility-bar-mid'
  return 'volatility-bar-high'
}

const volatilityIndexBarWidth = (idx) => {
  // Pin to [0, 100] so a clamped 100 reads as a full bar even if the
  // payload ever ships a value slightly over (it can't, but the UI
  // shouldn't break if the contract drifts).
  if (typeof idx !== 'number' || Number.isNaN(idx)) return '0%'
  return `${Math.max(0, Math.min(100, idx))}%`
}

const volatilityTrendLabel = (trend) => {
  if (trend === 'converging') return tr('Converging', '收敛', { de: 'Konvergierend' , fr: 'Convergence'})
  if (trend === 'contested') return tr('Contested', '争议', { de: 'Umstritten' , fr: 'Contesté'})
  return tr('Stable', '稳定', { de: 'Stabil', fr: 'Stable' })
}

const volatilityTrendBadgeClass = (trend) => {
  if (trend === 'converging') return 'signal-direction-bullish'
  if (trend === 'contested') return 'signal-direction-bearish'
  return 'signal-direction-neutral'
}

const loadVolatility = async () => {
  if (!props.simulationId || !isPublic.value) {
    volatilityPayload.value = null
    return
  }
  volatilityLoading.value = true
  volatilityError.value = ''
  try {
    const payload = await getVolatility(props.simulationId)
    if (payload && typeof payload === 'object') {
      volatilityPayload.value = payload
    } else {
      volatilityPayload.value = null
      volatilityError.value = tr('Volatility analytics not available yet — the simulation needs at least two rounds.',
        '尚无可用的波动率分析 — 模拟至少需要两个回合。',
        { de: 'Volatilitätsanalyse noch nicht verfügbar — die Simulation benötigt mindestens zwei Runden.' , fr: 'Analyse de volatilité pas encore disponible — besoin d\'au moins deux tours.'},
      )
    }
  } catch (err) {
    volatilityPayload.value = null
    volatilityError.value = err?.message || tr('Volatility fetch failed', '波动率获取失败', { de: 'Volatilitäts-Abruf fehlgeschlagen' , fr: 'Échec de la récupération de la volatilité'})
  } finally {
    volatilityLoading.value = false
  }
}

// ── Per-agent sparklines state ─────────────────────────────────────────
// The agent-level companion to chart.svg / peak-round. Each agent's
// belief position over rounds, drawn as a compact SVG polyline colored
// by final stance. Same publish gate; 404 means "no per-agent
// trajectory data yet".

const sparklinesPayload = ref(null)
const sparklinesLoading = ref(false)
const sparklinesError = ref('')

// Sparkline viewBox — small enough to render inline next to a name chip,
// large enough that a multi-round trajectory reads as a curve.
const SPARK_W = 60
const SPARK_H = 16

const agentSparklinesUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getAgentSparklinesUrl(props.simulationId, origin.value)
})

const sparklinesCurlSnippet = computed(() => {
  const url = agentSparklinesUrl.value || 'https://your-host/api/simulation/<id>/agents/sparklines'
  return `curl -s "${url}"`
})

// Project one agent's trajectory into an SVG polyline `points` string.
// Belief position (clamped to [-1, 1]) maps to y so +1 sits at the top
// and -1 at the bottom; round index maps to x across the full width. A
// single-point trajectory renders a centered dot via two identical
// coordinates so the <polyline> still paints.
const sparklinePoints = (trajectory) => {
  const pts = Array.isArray(trajectory) ? trajectory : []
  if (pts.length === 0) return ''
  const n = pts.length
  const toXY = (p, i) => {
    const x = n === 1 ? SPARK_W / 2 : (i / (n - 1)) * SPARK_W
    const pos = Math.max(-1, Math.min(1, Number(p.position) || 0))
    const y = (SPARK_H * (1 - pos)) / 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }
  if (n === 1) {
    const xy = toXY(pts[0], 0)
    return `${xy} ${xy}`
  }
  return pts.map(toXY).join(' ')
}

const loadAgentSparklines = async () => {
  if (!props.simulationId || !isPublic.value) {
    sparklinesPayload.value = null
    return
  }
  sparklinesLoading.value = true
  sparklinesError.value = ''
  try {
    const payload = await getAgentSparklines(props.simulationId)
    if (payload && Array.isArray(payload.agents)) {
      sparklinesPayload.value = payload
    } else {
      sparklinesPayload.value = null
      sparklinesError.value = tr('Per-agent sparklines not available yet — the simulation has no per-agent trajectory data.',
        '尚无可用的单智能体迷你趋势图 — 模拟还没有单智能体轨迹数据。',
        { de: 'Sparklines pro Agent noch nicht verfügbar — die Simulation hat keine agentenspezifischen Trajektoriendaten.' , fr: 'Sparklines par agent pas encore disponibles.'},
      )
    }
  } catch (err) {
    sparklinesPayload.value = null
    sparklinesError.value = err?.message || tr('Agent sparklines fetch failed', '单智能体迷你趋势图获取失败', { de: 'Agenten-Sparklines-Abruf fehlgeschlagen' , fr: 'Échec de la récupération des sparklines d\'agents'})
  } finally {
    sparklinesLoading.value = false
  }
}

// ── Agent roster (agents.json) state ──────────────────────────────────
// The participants surface — agent identity / persona preview / demographics
// + final stance + rounds participated. Same publish gate; 404 means
// "no profile data on disk yet". Distinct from sparklines (per-round
// belief trajectories) — this exposes *who was in the debate*.

const agentsPayload = ref(null)
const agentsLoading = ref(false)
const agentsError = ref('')

const agentsJsonUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getAgentsJsonUrl(props.simulationId, origin.value)
})

const agentsCurlSnippet = computed(() => {
  const url = agentsJsonUrl.value || 'https://your-host/api/simulation/<id>/agents.json'
  return `curl -s "${url}" | jq '.agents[] | {name, profession, final_stance}'`
})

// Render the agent's compact demographic chip — small tags shown next to
// the name. Empty fields are omitted so an agent missing one of the
// optional fields doesn't render an empty chip.
const agentDemographicTags = (agent) => {
  if (!agent || typeof agent !== 'object') return []
  const tags = []
  if (agent.profession) tags.push(agent.profession)
  if (agent.country) tags.push(agent.country)
  if (typeof agent.age === 'number') tags.push(`${agent.age}`)
  if (agent.mbti) tags.push(agent.mbti)
  return tags
}

// Map a stance string to the canonical hex color used across every
// other surface (chart_svg / badge_service / agent_sparklines_service).
// Keeps the participant chip color identical to the agent's sparkline.
const AGENT_STANCE_COLORS = {
  bullish: '#22c55e',
  neutral: '#6b7280',
  bearish: '#ef4444',
}
const agentStanceColor = (stance) => AGENT_STANCE_COLORS[stance] || AGENT_STANCE_COLORS.neutral

const loadAgentsJson = async () => {
  if (!props.simulationId || !isPublic.value) {
    agentsPayload.value = null
    return
  }
  agentsLoading.value = true
  agentsError.value = ''
  try {
    const payload = await getAgentsJson(props.simulationId)
    if (payload && Array.isArray(payload.agents)) {
      agentsPayload.value = payload
    } else {
      agentsPayload.value = null
      agentsError.value = tr('Agent roster not available yet — the simulation has no profile data on disk.',
        '尚无可用的智能体名册 — 模拟还没有磁盘上的画像数据。',
        { de: 'Agentenliste noch nicht verfügbar — die Simulation hat keine Profildaten auf der Festplatte.' , fr: 'Registre des agents pas encore disponible — la simulation n\'a pas de données de profil sur le disque.'},
      )
    }
  } catch (err) {
    agentsPayload.value = null
    agentsError.value = err?.message || tr('Agent roster fetch failed', '智能体名册获取失败', { de: 'Agentenliste-Abruf fehlgeschlagen' , fr: 'Échec de la récupération du registre des agents'})
  } finally {
    agentsLoading.value = false
  }
}

// ── Polymarket prediction state ────────────────────────────────────────
// The Polymarket-shaped re-envelope of signal.json. Stricter publish
// gate than signal.json: only completed sims emit a payload. A bot
// reading a 404 should treat the sim as "not ready" rather than
// retry.

const polymarketPayload = ref(null)
const polymarketLoading = ref(false)
const polymarketError = ref('')

const polymarketJsonUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getPolymarketJsonUrl(props.simulationId, origin.value)
})

const polymarketYesPct = computed(() => {
  const y = polymarketPayload.value?.yes_probability
  return (typeof y === 'number') ? (y * 100).toFixed(2) : ''
})
const polymarketNoPct = computed(() => {
  const n = polymarketPayload.value?.no_probability
  return (typeof n === 'number') ? (n * 100).toFixed(2) : ''
})

const polymarketCurlSnippet = computed(() => {
  const url = polymarketJsonUrl.value || 'https://your-host/api/simulation/<id>/polymarket.json'
  return `curl -s "${url}" | jq '.yes_probability,.no_probability,.confidence_tier'`
})

const loadPolymarket = async () => {
  if (!props.simulationId || !isPublic.value) {
    polymarketPayload.value = null
    return
  }
  polymarketLoading.value = true
  polymarketError.value = ''
  try {
    const payload = await getPolymarketJson(props.simulationId)
    if (payload && typeof payload === 'object') {
      polymarketPayload.value = payload
    } else {
      polymarketPayload.value = null
      polymarketError.value = tr('Polymarket prediction not available yet — the simulation is not complete.',
        '尚无可用的 Polymarket 预测 — 模拟尚未完成。',
        { de: 'Polymarket-Prognose noch nicht verfügbar — die Simulation ist noch nicht abgeschlossen.' , fr: 'Prédiction Polymarket pas encore disponible.'},
      )
    }
  } catch (err) {
    polymarketPayload.value = null
    polymarketError.value = err?.message || tr('Polymarket fetch failed', 'Polymarket 获取失败', { de: 'Polymarket-Abruf fehlgeschlagen' , fr: 'Échec de la récupération Polymarket'})
  } finally {
    polymarketLoading.value = false
  }
}

// ── Clone payload state ─────────────────────────────────────────────────
// The first surface that returns *inputs* (the configuration this sim
// was built with) rather than outputs. ``clone_payload`` is wire-
// compatible with POST /api/simulation/create — the dialog renders the
// shape so a viewer can see at a glance whether the cloned sim ran with
// twitter/reddit/polymarket toggles, a demographic country pack, etc.

const clonePayload = ref(null)
const cloneLoading = ref(false)
const cloneError = ref('')

const cloneJsonUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getCloneJsonUrl(props.simulationId, origin.value)
})

const cloneCurlSnippet = computed(() => {
  const url = cloneJsonUrl.value || 'https://your-host/api/simulation/<id>/clone.json'
  return `curl -s "${url}" | jq '.clone_payload'`
})

const clonePostBody = computed(() => {
  const body = clonePayload.value?.clone_payload
  if (!body || typeof body !== 'object') return ''
  return JSON.stringify(body, null, 2)
})

const loadClone = async () => {
  if (!props.simulationId || !isPublic.value) {
    clonePayload.value = null
    return
  }
  cloneLoading.value = true
  cloneError.value = ''
  try {
    const payload = await getCloneJson(props.simulationId)
    if (payload && typeof payload === 'object') {
      clonePayload.value = payload
    } else {
      clonePayload.value = null
      cloneError.value = tr('Clone payload not available yet — the simulation has no state on disk.',
        '尚无可用的克隆配置 — 该模拟尚无磁盘状态。',
        { de: 'Klon-Konfiguration noch nicht verfügbar — die Simulation hat noch keinen Zustand auf der Festplatte.' , fr: 'Payload clone pas encore disponible — la simulation n\'a pas d\'état sur le disque.'},
      )
    }
  } catch (err) {
    clonePayload.value = null
    cloneError.value = err?.message || tr('Clone fetch failed', '克隆配置获取失败', { de: 'Klon-Konfiguration-Abruf fehlgeschlagen' , fr: 'Échec de la récupération du clone'})
  } finally {
    cloneLoading.value = false
  }
}

// ── Archive bundle state ────────────────────────────────────────────────
// Loaded on dialog open whenever the sim is public. The HEAD request
// reads ``X-MiroShark-Archive-Files`` so the dialog can show the file
// count without downloading the full ZIP. Failure is silent — the
// section falls back to the static "Download archive.zip" button.
const archiveFileCount = ref(0)
const archiveLoading = ref(false)
const archiveAvailable = ref(false)

const archiveZipUrl = computed(() => {
  if (!props.simulationId || !origin.value) return ''
  return getArchiveZipUrl(props.simulationId, origin.value)
})

const archiveCurlSnippet = computed(() => {
  const url = archiveZipUrl.value || 'https://your-host/api/simulation/<id>/archive.zip'
  return `curl -OJ "${url}"`
})

const loadArchive = async () => {
  if (!props.simulationId || !isPublic.value) {
    archiveAvailable.value = false
    archiveFileCount.value = 0
    return
  }
  archiveLoading.value = true
  try {
    const summary = await getArchiveSummary(props.simulationId)
    if (summary && typeof summary.fileCount === 'number') {
      archiveAvailable.value = true
      archiveFileCount.value = summary.fileCount
    } else {
      archiveAvailable.value = false
      archiveFileCount.value = 0
    }
  } catch (err) {
    archiveAvailable.value = false
    archiveFileCount.value = 0
  } finally {
    archiveLoading.value = false
  }
}

// ── Farcaster Frame state ───────────────────────────────────────────────
// Loaded on dialog open whenever the sim is public. The endpoint hands
// back the chart-SVG image URL (or share-card fallback for sims with no
// trajectory yet), the share URL, and the button shape — the section
// renders the image as a preview and offers a Warpcast composer link
// pre-filled with the share URL.
const farcasterFrameImage = ref('')
const farcasterShareUrl = ref('')
const farcasterHasTrajectory = ref(null)

const farcasterComposeUrl = computed(() => {
  if (!farcasterShareUrl.value) return ''
  return buildWarpcastComposeUrl(farcasterShareUrl.value)
})

const loadFrameMetadata = async () => {
  if (!props.simulationId || !isPublic.value) {
    farcasterFrameImage.value = ''
    farcasterShareUrl.value = ''
    farcasterHasTrajectory.value = null
    return
  }
  try {
    const res = await getFrameMetadata(props.simulationId)
    const data = res && res.data && res.data.success ? res.data.data : null
    if (data) {
      farcasterFrameImage.value = data.image_url || ''
      farcasterShareUrl.value = data.share_url || ''
      farcasterHasTrajectory.value = data.has_trajectory === true
    } else {
      farcasterFrameImage.value = shareLandingUrl.value
        ? `${origin.value}/api/simulation/${props.simulationId}/share-card.png`
        : ''
      farcasterShareUrl.value = shareLandingUrl.value
      farcasterHasTrajectory.value = null
    }
  } catch (_err) {
    // Frame metadata is best-effort. Fall back to the share-landing
    // URL we already render in the share section so the operator can
    // still paste *something* into Farcaster — the share page will
    // emit the matching Frame tags on its own when the cast is
    // scraped.
    farcasterShareUrl.value = shareLandingUrl.value
    farcasterFrameImage.value = ''
    farcasterHasTrajectory.value = null
  }
}

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
          ? tr('Publish the simulation to enable the tweet thread.', '发布模拟以启用推文串。', { de: 'Veröffentliche die Simulation, um den Tweet-Thread zu aktivieren.', fr: 'Publiez la simulation pour activer le fil de tweets.' })
          : `${tr('Could not load thread', '无法加载推文串', { de: 'Thread konnte nicht geladen werden', fr: 'Impossible de charger le fil' })} (HTTP ${res.status})`
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
      err?.message || tr('Could not load thread', '无法加载推文串', { de: 'Thread konnte nicht geladen werden', fr: 'Impossible de charger le fil' })
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
  { key: 'share_card', label: tr('Share card · PNG', '分享卡片 · PNG', { de: 'Share Card · PNG', fr: 'Carte de partage · PNG' }) },
  { key: 'replay_gif', label: tr('Replay GIF', '回放 GIF', { de: 'Wiedergabe-GIF', fr: 'GIF de rejeu' }) },
  { key: 'transcript_md', label: tr('Transcript · Markdown', '记录 · Markdown', { de: 'Protokoll · Markdown', fr: 'Transcription · Markdown' }) },
  { key: 'transcript_json', label: tr('Transcript · JSON', '记录 · JSON', { de: 'Protokoll · JSON', fr: 'Transcription · JSON' }) },
  { key: 'trajectory_csv', label: tr('Trajectory · CSV', '轨迹 · CSV', { de: 'Trajektorie · CSV' , fr: 'Trajectoire · CSV'}) },
  { key: 'trajectory_jsonl', label: tr('Trajectory · JSONL', '轨迹 · JSONL', { de: 'Trajektorie · JSONL' , fr: 'Trajectoire · JSONL'}) },
  { key: 'thread_txt', label: tr('Tweet thread · TXT', '推文串 · TXT', { de: 'Tweet-Thread · TXT' , fr: 'Thread tweet · TXT'}) },
  { key: 'thread_json', label: tr('Tweet thread · JSON', '推文串 · JSON', { de: 'Tweet-Thread · JSON' , fr: 'Thread tweet · JSON'}) },
  { key: 'watch_page', label: tr('Watch page', '观看页面', { de: 'Watch-Seite' , fr: 'Page de direct'}) },
  { key: 'feed_atom', label: tr('Atom feed', 'Atom 源', { de: 'Atom-Feed' , fr: 'Flux Atom'}) },
  { key: 'feed_rss', label: tr('RSS feed', 'RSS 源', { de: 'RSS-Feed' , fr: 'Flux RSS'}) },
  { key: 'reproduce_json', label: tr('Reproduce config · JSON', '可复现配置 · JSON', { de: 'Reproduktionskonfiguration · JSON' , fr: 'Config de reproduction · JSON'}) },
  { key: 'lineage', label: tr('Lineage graph', '谱系图', { de: 'Abstammungsgraph' , fr: 'Graphe de lignée'}) },
  { key: 'notebook_ipynb', label: tr('Jupyter notebook · IPYNB', 'Jupyter 笔记本 · IPYNB', { de: 'Jupyter Notebook · IPYNB' , fr: 'Jupyter notebook · IPYNB'}) },
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
        || tr('Could not load distribution stats.', '无法加载分发统计。', { de: 'Verteilungsstatistiken konnten nicht geladen werden.' , fr: 'Impossible de charger les statistiques de distribution.'})
    }
  } catch (err) {
    if (err?.response?.status === 403) {
      surfaceStatsError.value = tr('Publish the simulation to see distribution stats.',
        '发布模拟以查看分发统计。',
        { de: 'Veröffentliche die Simulation, um Verteilungsstatistiken anzuzeigen.' , fr: 'Publiez la simulation pour voir les stats de distribution.'},
      )
    } else {
      surfaceStatsError.value = err?.response?.data?.error
        || err?.message
        || tr('Could not load distribution stats.', '无法加载分发统计。', { de: 'Verteilungsstatistiken konnten nicht geladen werden.' })
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
  if (p.twitter) parts.push(tr('Twitter', 'Twitter', { de: 'Twitter' , fr: 'Twitter'}))
  if (p.reddit) parts.push(tr('Reddit', 'Reddit', { de: 'Reddit' , fr: 'Reddit'}))
  if (p.polymarket) {
    const count = Number(p.polymarket_market_count || 1)
    parts.push(`${tr('Polymarket', 'Polymarket', { de: 'Polymarket' , fr: 'Polymarket'})} ×${count}`)
  }
  return parts.length
    ? parts.join(' · ')
    : tr('No platforms enabled', '未启用平台', { de: 'Keine Plattformen aktiviert' , fr: 'Aucune plateforme activée'})
})

const reproDirectorEventCount = computed(() => {
  const events = reproBlob.value?.director_events
  return Array.isArray(events) ? events.length : 0
})

const reproLineageBadge = computed(() => {
  const lineage = reproBlob.value?.lineage
  if (!lineage) return ''
  if (lineage.kind === 'fork') return tr('🪐 Forked', '🪐 派生', { de: '🪐 Geforkt' , fr: '🪐 Forké'})
  if (lineage.kind === 'counterfactual') return tr('🔀 Counterfactual', '🔀 反事实', { de: '🔀 Kontrafaktual' , fr: '🔀 Contrefactuel'})
  return ''
})

const reproLineageDescription = computed(() => {
  const lineage = reproBlob.value?.lineage
  if (!lineage || lineage.kind === 'original') return ''
  const parent = lineage.parent_simulation_id
    ? lineage.parent_simulation_id.slice(0, 12)
    : ''
  if (lineage.kind === 'fork') {
    return tr('Forked from ', '派生自 ', { de: 'Geforkt von ' }) + parent
  }
  // Counterfactual — surface the trigger round and label so the
  // reader sees "Counterfactual branch of sim_X at round 12 (ceo_resigns)"
  // without opening the parent.
  const cf = lineage.counterfactual || {}
  const round = Number.isInteger(cf.trigger_round) ? cf.trigger_round : '?'
  const label = cf.label
    ? ` (${cf.label})`
    : ''
  return tr('Counterfactual of ', '反事实分支自 ', { de: 'Kontrafaktual von ' })
    + parent
    + tr(' at round ', ' · 第 ', { de: ' in Runde ' })
    + round
    + tr('', ' 轮', { de: '' })
    + label
})

const reproLineageTitle = computed(() => {
  // Tooltip seen on hover — full parent ID, not the truncated 12-char
  // version, so the operator can grab the canonical sim id for
  // /share/<id> or /watch/<id>.
  const lineage = reproBlob.value?.lineage
  if (!lineage || lineage.kind === 'original') {
    return tr('Original simulation — no parent run.',
      '原始模拟 — 无父运行。',
      { de: 'Originale Simulation — kein übergeordneter Lauf.' , fr: 'Simulation originale — aucun run parent.'},
    )
  }
  const parent = lineage.parent_simulation_id || '?'
  if (lineage.kind === 'fork') {
    return tr('Fork of ', '派生自 ', { de: 'Fork von ' }) + parent
  }
  return tr('Counterfactual branch of ', '反事实分支自 ', { de: 'Kontrafaktual-Zweig von ' }) + parent
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
      reproError.value = tr('Could not parse the reproduction config.',
        '无法解析复现配置。',
        { de: 'Reproduktionskonfiguration konnte nicht geparst werden.' , fr: 'Impossible d\'analyser la configuration de reproduction.'},
      )
    }
  } catch (err) {
    if (err?.response?.status === 403) {
      reproError.value = tr('Publish the simulation to expose the reproducibility config.',
        '发布模拟以公开可复现配置。',
        { de: 'Veröffentliche die Simulation, um die Reproduzierbarkeitskonfiguration freizugeben.' , fr: 'Publiez la simulation pour exposer la configuration de reproductibilité.'},
      )
    } else if (err?.response?.status === 404) {
      reproError.value = tr('Simulation not found.',
        '未找到模拟。',
        { de: 'Simulation nicht gefunden.' , fr: 'Simulation introuvable.'},
      )
    } else {
      reproError.value = err?.response?.data?.error
        || err?.message
        || tr('Could not load the reproduction config.', '无法加载复现配置。', { de: 'Reproduktionskonfiguration konnte nicht geladen werden.' , fr: 'Impossible de charger la configuration de reproduction.'})
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
  if (child.kind === 'counterfactual') return tr('🔀 Counterfactual', '🔀 反事实', { de: '🔀 Kontrafaktual' })
  if (child.kind === 'fork') return tr('🪐 Forked', '🪐 派生', { de: '🪐 Geforkt' })
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
    const head = tr('At round ', '第 ', { de: 'In Runde ' }) + round + tr('', ' 轮', { de: '' }) + label
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
      lineageError.value = tr('Could not parse the lineage payload.',
        '无法解析谱系数据。',
        { de: 'Abstammungsdaten konnten nicht geparst werden.' , fr: 'Impossible d\'analyser le payload de lignée.'},
      )
    }
  } catch (err) {
    if (err?.response?.status === 403) {
      lineageError.value = tr('Publish the simulation to see its lineage.',
        '发布模拟以查看谱系。',
        { de: 'Veröffentliche die Simulation, um ihre Abstammung zu sehen.' , fr: 'Publiez la simulation pour voir sa lignée.'},
      )
    } else if (err?.response?.status === 404) {
      lineageError.value = tr('Simulation not found.',
        '未找到模拟。',
        { de: 'Simulation nicht gefunden.' },
      )
    } else {
      lineageError.value = err?.response?.data?.error
        || err?.message
        || tr('Could not load the lineage.', '无法加载谱系。', { de: 'Abstammung konnte nicht geladen werden.' , fr: 'Impossible de charger la lignée.'})
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

// Filtered feeds — the operator picks a slice once and copies the URL
// into Feedly / n8n / Zapier / any RSS consumer. Defaults match the
// most-asked slices ("bullish-only signal", "excellent-quality only",
// "what's hot right now"); the underlying URL is fully composable so a
// reader could hand-edit the query string to combine knobs.
const feedFilters = reactive({
  consensus: '',
  quality: '',
  sort: 'date',
})
const filteredFeedUrl = computed(() =>
  getFeedUrl({
    format: 'atom',
    origin: origin.value,
    consensus: feedFilters.consensus || undefined,
    quality: feedFilters.quality || undefined,
    sort: feedFilters.sort || undefined,
  }),
)
const filteredFeedActive = computed(
  () =>
    !!feedFilters.consensus ||
    !!feedFilters.quality ||
    (!!feedFilters.sort && feedFilters.sort !== 'date'),
)
const copiedFilteredFeed = ref(false)
const copyFilteredFeedUrl = async () => {
  try {
    await navigator.clipboard.writeText(filteredFeedUrl.value)
    copiedFilteredFeed.value = true
    setTimeout(() => {
      copiedFilteredFeed.value = false
    }, 1800)
  } catch (_err) {
    // Clipboard API can fail in non-secure contexts; the URL is still
    // visible in the input so the user can copy manually.
    copiedFilteredFeed.value = false
  }
}

// Search-engine sitemap surface — independent of `simulationId` (the
// sitemap lists every published sim across the gallery), exposed here
// so an operator who just published gets a one-click "your sim is
// crawler-discoverable" callout. The flag comes from the public
// /api/config/sitemap endpoint so the dialog can swap to a "disabled"
// hint when the deployment opted out.
const sitemapUrl = computed(() => {
  if (!origin.value) return ''
  return getSitemapUrl(origin.value)
})
const sitemapEnabled = ref(true)
const sitemapConfigLoaded = ref(false)
const loadSitemapConfig = async () => {
  if (sitemapConfigLoaded.value) return
  try {
    const res = await getSitemapConfig()
    sitemapEnabled.value = !!res?.data?.enabled
  } catch {
    // Best-effort — a transient failure shouldn't blank out the row.
    // Default to ``enabled = true`` so the operator still sees the
    // sitemap link; the route itself returns 404 when disabled, which
    // is the authoritative answer.
    sitemapEnabled.value = true
  } finally {
    sitemapConfigLoaded.value = true
  }
}

// Notification-channel config — four booleans tracking the live
// state of WEBHOOK_URL / DISCORD_WEBHOOK_URL / SLACK_WEBHOOK_URL /
// (SMTP_HOST + SMTP_TO).
// The chips render off these booleans so an operator sees at a
// glance which channels will fire on the next terminal-state event.
// We default everything to ``false`` (chip = ○) so a fetch failure
// degrades to "no channels wired up" rather than a misleading green.
const notifConfig = ref({
  webhook_configured: false,
  discord_configured: false,
  slack_configured: false,
  email_configured: false,
  dkg_configured: false,
  dkg_network: null,
  waybackclaw_configured: false,
})
const notifConfigLoaded = ref(false)
const loadNotificationsConfig = async () => {
  if (notifConfigLoaded.value) return
  try {
    const res = await getNotificationsConfig()
    const data = res?.data || {}
    notifConfig.value = {
      webhook_configured: !!data.webhook_configured,
      discord_configured: !!data.discord_configured,
      slack_configured: !!data.slack_configured,
      email_configured: !!data.email_configured,
      dkg_configured: !!data.dkg_configured,
      dkg_network: data.dkg_network || null,
      waybackclaw_configured: !!data.waybackclaw_configured,
    }
  } catch {
    notifConfig.value = {
      webhook_configured: false,
      discord_configured: false,
      slack_configured: false,
      email_configured: false,
      dkg_configured: false,
      dkg_network: null,
      waybackclaw_configured: false,
    }
  } finally {
    notifConfigLoaded.value = true
  }
}

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
  else if (which === 'chartSvg') text = chartSvgUrl.value
  else if (which === 'chartSvgEmbed') text = chartSvgEmbedSnippet.value
  else if (which === 'badgeUrl') text = badgeSvgUrl.value
  else if (which === 'badgeMd') text = badgeMarkdownSnippet.value
  else if (which === 'badgeHtml') text = badgeHtmlSnippet.value
  else if (which === 'signalUrl') text = signalJsonUrl.value
  else if (which === 'signalCurl') text = signalCurlSnippet.value
  else if (which === 'peakUrl') text = peakRoundUrl.value
  else if (which === 'peakCurl') text = peakCurlSnippet.value
  else if (which === 'volatilityUrl') text = volatilityUrl.value
  else if (which === 'volatilityCurl') text = volatilityCurlSnippet.value
  else if (which === 'sparkUrl') text = agentSparklinesUrl.value
  else if (which === 'sparkCurl') text = sparklinesCurlSnippet.value
  else if (which === 'agentsUrl') text = agentsJsonUrl.value
  else if (which === 'agentsCurl') text = agentsCurlSnippet.value
  else if (which === 'polymarketUrl') text = polymarketJsonUrl.value
  else if (which === 'polymarketCurl') text = polymarketCurlSnippet.value
  else if (which === 'cloneUrl') text = cloneJsonUrl.value
  else if (which === 'cloneCurl') text = cloneCurlSnippet.value
  else if (which === 'clonePostBody') text = clonePostBody.value
  else if (which === 'archiveUrl') text = archiveZipUrl.value
  else if (which === 'archiveCurl') text = archiveCurlSnippet.value
  else if (which === 'farcasterShare') text = farcasterShareUrl.value || shareLandingUrl.value
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
  else if (which === 'citeBibUrl') text = citeBibUrl.value
  else if (which === 'citeBibCurl') text = citeBibCurlSnippet.value
  else if (which === 'citeBibLatex') text = citeBibLatexSnippet.value
  else if (which === 'notebookUrl') text = notebookDownloadUrl.value
  else if (which === 'notebookCurl') text = notebookCurlSnippet.value
  else if (which === 'dkgUal') text = dkgCitation.value?.ual || ''
  else if (which === 'dkgMerkle') text = dkgCitation.value?.merkle_root || ''
  else if (which === 'wbcId') text = wbcRecord.value?.id || ''
  else if (which === 'wbcIpfs') text = wbcRecord.value?.ipfs_cid || ''
  else if (which === 'wbcNostr') text = wbcRecord.value?.nostr_event_id || ''
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
  { value: 'correct', label: tr('Called it', '命中', { de: 'Richtig gelegen' , fr: 'Réussi'}), icon: '📍' },
  { value: 'partial', label: tr('Partial', '部分命中', { de: 'Teilweise richtig', fr: 'Partielle' }), icon: '◑' },
  { value: 'incorrect', label: tr('Called wrong', '判断错误', { de: 'Falsch gelegen', fr: 'Prédiction erronée' }), icon: '⚠' },
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
        tr('Outcome saved — your simulation is visible in the Verified filter.', '结果已保存 — 你的模拟现在「已验证」筛选中可见。', { de: 'Ergebnis gespeichert — deine Simulation ist im Verifiziert-Filter sichtbar.', fr: 'Résultat enregistré — votre simulation est visible dans le filtre Vérifiées.' })
      outcomeMessageClass.value = 'outcome-message-success'
    } else {
      outcomeMessage.value = res?.error || tr('Could not save outcome.', '无法保存结果。', { de: 'Ergebnis konnte nicht gespeichert werden.', fr: `Impossible d'enregistrer le résultat.` })
      outcomeMessageClass.value = 'outcome-message-error'
    }
  } catch (err) {
    outcomeMessage.value =
      err?.response?.data?.error || err?.message || tr('Could not save outcome.', '无法保存结果。', { de: 'Ergebnis konnte nicht gespeichert werden.', fr: `Impossible d'enregistrer le résultat.` })
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
      webhookLogError.value = tr('Admin token does not match — set Authorization: Bearer $MIROSHARK_ADMIN_TOKEN at your reverse proxy to view the log.',
        '管理员 token 不匹配 — 请在反向代理处设置 Authorization: Bearer $MIROSHARK_ADMIN_TOKEN 以查看日志。',
        { de: 'Admin-Token stimmt nicht überein — setze Authorization: Bearer $MIROSHARK_ADMIN_TOKEN an deinem Reverse-Proxy, um das Protokoll einzusehen.' , fr: 'Le token admin ne correspond pas — définissez Authorization: Bearer $MIROSHARK_ADMIN_TOKEN sur votre proxy inverse pour voir le journal.'},
      )
    } else {
      webhookLogError.value =
        err?.response?.data?.error || err?.message || tr('Could not load delivery history.', '无法加载投递历史。', { de: 'Auslieferungsverlauf konnte nicht geladen werden.', fr: `Impossible de charger l'historique des livraisons.` })
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
      webhookRetryMessage.value = tr('Queued — refresh in a moment to see the new attempt.',
        '已排队 — 稍后刷新查看新一次投递。',
        { de: 'In die Warteschlange gestellt — in einem Moment aktualisieren, um den neuen Versuch zu sehen.' , fr: 'En file d\'attente — actualisez pour voir la nouvelle tentative.'},
      )
      webhookRetryMessageClass.value = 'webhook-log-message-ok'
      // Pull fresh entries after a short delay so the daemon thread has
      // time to log its result. 1.2s comfortably covers a healthy
      // round-trip; a slow downstream still surfaces on the next manual
      // Refresh click.
      setTimeout(() => loadWebhookLog(), 1200)
    } else {
      webhookRetryMessage.value =
        res?.error || tr('Could not queue retry.', '无法排队重试。', { de: 'Erneuter Versuch konnte nicht in die Warteschlange gestellt werden.' , fr: 'Impossible de planifier une nouvelle tentative.'})
      webhookRetryMessageClass.value = 'webhook-log-message-error'
    }
  } catch (err) {
    const status = err?.response?.status
    if (status === 400) {
      webhookRetryMessage.value = err?.response?.data?.error
        || tr('No webhook URL configured.', '未配置 webhook URL。', { de: 'Keine Webhook-URL konfiguriert.' , fr: 'Aucune URL de webhook configurée.'})
    } else if (status === 409) {
      webhookRetryMessage.value = err?.response?.data?.error
        || tr('Simulation has not finished yet.', '模拟尚未完成。', { de: 'Simulation ist noch nicht abgeschlossen.' , fr: 'La simulation n\'est pas encore terminée.'})
    } else if (status === 503) {
      webhookRetryMessage.value = tr('Admin authentication not configured.',
        '未配置管理员身份验证。',
        { de: 'Admin-Authentifizierung nicht konfiguriert.' , fr: 'Authentification admin non configurée.'},
      )
    } else {
      webhookRetryMessage.value =
        err?.response?.data?.error || err?.message || tr('Could not queue retry.', '无法排队重试。', { de: 'Erneuter Versuch konnte nicht in die Warteschlange gestellt werden.' })
    }
    webhookRetryMessageClass.value = 'webhook-log-message-error'
  } finally {
    webhookRetrying.value = false
  }
}

// ---- DKG citation state -------------------------------------------------
//
// The OriginTrail DKG citation card is an opt-in surface: it lives only
// when ``notifConfig.dkg_configured`` is true. State machine:
//   1. mount → loadDkgCitation() probes for an existing on-chain anchor
//   2. citation present → render UAL + Merkle + tx + explorer link
//   3. citation absent → render "Publish to DKG" button
//   4. click → publishDkg() walks WM→SWM→VM on the daemon, ~15-120s
//   5. on success → citation populated, button hidden
const dkgCitation = ref(null)
const dkgLoading = ref(false)
const dkgPublishing = ref(false)
const dkgError = ref('')
const dkgErrorClass = ref('')

const loadDkgCitation = async () => {
  if (!props.simulationId) return
  if (!notifConfig.value.dkg_configured) return
  if (!isPublic.value) return
  dkgLoading.value = true
  dkgError.value = ''
  try {
    const res = await getDkgCitation(props.simulationId)
    if (res?.success && res.data) {
      dkgCitation.value = res.data
    } else {
      dkgCitation.value = null
    }
  } catch (err) {
    const status = err?.response?.status
    // 404 just means "no anchor yet" — the common pre-publish state,
    // never an error to surface. Anything else (403, 5xx) leaves the
    // citation as null and the card renders the publish CTA.
    if (status !== 404) {
      // Soft-failure: don't paint a red error before the user has
      // even clicked anything. The publish attempt itself will surface
      // any real daemon issue.
    }
    dkgCitation.value = null
  } finally {
    dkgLoading.value = false
  }
}

const publishDkg = async () => {
  if (!props.simulationId || dkgPublishing.value) return
  if (!notifConfig.value.dkg_configured) return
  if (!isPublic.value) return
  dkgPublishing.value = true
  dkgError.value = ''
  dkgErrorClass.value = ''
  try {
    const res = await publishToDkg(props.simulationId)
    if (res?.success && res.data?.ual) {
      dkgCitation.value = res.data
      dkgError.value = res?.cached
        ? tr('Already anchored — returned existing citation.', '已锚定 — 返回现有引用。', { de: 'Bereits verankert — vorhandene Zitation zurückgegeben.' , fr: 'Déjà ancré — citation existante retournée.'})
        : tr('Published to DKG. Citation anchored on-chain.', '已发布至 DKG,引用已上链。', { de: 'Auf DKG veröffentlicht. Zitation on-chain verankert.' , fr: 'Publié sur le DKG. Citation ancrée on-chain.'})
      dkgErrorClass.value = 'webhook-log-message-ok'
    } else {
      dkgError.value = res?.error || tr('Could not publish to DKG.', '无法发布至 DKG。', { de: 'Auf DKG konnte nicht veröffentlicht werden.' , fr: 'Impossible de publier sur le DKG.'})
      dkgErrorClass.value = 'webhook-log-message-error'
    }
  } catch (err) {
    const status = err?.response?.status
    const serverErr = err?.response?.data?.error
    if (status === 401) {
      dkgError.value = tr('Admin token does not match — set Authorization: Bearer $MIROSHARK_ADMIN_TOKEN at your reverse proxy to publish to DKG.',
        '管理员 token 不匹配 — 请在反向代理处设置 Authorization: Bearer $MIROSHARK_ADMIN_TOKEN 才能发布至 DKG。',
        { de: 'Admin-Token stimmt nicht überein — setze Authorization: Bearer $MIROSHARK_ADMIN_TOKEN an deinem Reverse-Proxy, um auf DKG zu veröffentlichen.' , fr: 'Le token admin ne correspond pas — définissez Authorization: Bearer $MIROSHARK_ADMIN_TOKEN sur votre proxy inverse pour publier sur le DKG.'},
      )
    } else if (status === 503) {
      dkgError.value = serverErr || tr('DKG publishing is not configured on this deployment.',
        '该部署未配置 DKG 发布。',
        { de: 'DKG-Veröffentlichung ist auf diesem Deployment nicht konfiguriert.' , fr: 'La publication DKG n\'est pas configurée sur ce déploiement.'},
      )
    } else if (status === 504) {
      dkgError.value = serverErr || tr('DKG daemon unreachable or publish timed out. Check that the local DKG node is running.',
        '无法访问 DKG 守护进程或发布超时,请确认本地 DKG 节点已运行。',
        { de: 'DKG-Daemon nicht erreichbar oder Veröffentlichung hat das Zeitlimit überschritten. Überprüfe, ob der lokale DKG-Knoten läuft.' , fr: 'Démon DKG injoignable — vérifiez que le nœud DKG local est en cours d\'exécution.'},
      )
    } else if (status === 502) {
      dkgError.value = serverErr || tr('DKG daemon returned an error. Check the node logs and TRAC balance.',
        'DKG 守护进程返回错误,请检查节点日志与 TRAC 余额。',
        { de: 'DKG-Daemon hat einen Fehler zurückgegeben. Überprüfe die Knoten-Logs und den TRAC-Saldo.' , fr: 'Le démon DKG a retourné une erreur. Vérifiez les logs du nœud et le solde TRAC.'},
      )
    } else if (status === 422) {
      dkgError.value = serverErr || tr('Simulation has not reached the prepared state — nothing to anchor yet.',
        '模拟尚未到达可发布状态,暂无可锚定的数据。',
        { de: 'Simulation hat den vorbereiteten Zustand noch nicht erreicht — noch nichts zu verankern.' , fr: 'La simulation n\'est pas prête — rien à ancrer.'},
      )
    } else {
      dkgError.value = serverErr || err?.message || tr('Could not publish to DKG.', '无法发布至 DKG。', { de: 'Auf DKG konnte nicht veröffentlicht werden.' })
    }
    dkgErrorClass.value = 'webhook-log-message-error'
  } finally {
    dkgPublishing.value = false
  }
}

const _resetDkgState = () => {
  dkgCitation.value = null
  dkgLoading.value = false
  dkgPublishing.value = false
  dkgError.value = ''
  dkgErrorClass.value = ''
}

// ---- WaybackClaw archive state -----------------------------------------
//
// The WaybackClaw card is the agent-archive sibling of the DKG card:
// opt-in (gated by ``notifConfig.waybackclaw_configured``), follows the
// same load-on-mount → submit-on-click → cached-thereafter state
// machine. Free for agents — no on-chain cost — so the publish CTA is
// simpler than the DKG one (no TRAC / gas balance to worry about).
const wbcRecord = ref(null)
const wbcLoading = ref(false)
const wbcSubmitting = ref(false)
const wbcError = ref('')
const wbcErrorClass = ref('')

const loadWaybackclawRecord = async () => {
  if (!props.simulationId) return
  if (!notifConfig.value.waybackclaw_configured) return
  if (!isPublic.value) return
  wbcLoading.value = true
  wbcError.value = ''
  try {
    const res = await getWaybackclawRecord(props.simulationId)
    if (res?.success && res.data) {
      wbcRecord.value = res.data
    } else {
      wbcRecord.value = null
    }
  } catch (err) {
    const status = err?.response?.status
    if (status !== 404) {
      // Soft-failure same as DKG — leave the card showing the
      // submit CTA. The submit attempt itself surfaces real errors.
    }
    wbcRecord.value = null
  } finally {
    wbcLoading.value = false
  }
}

const publishWaybackclaw = async () => {
  if (!props.simulationId || wbcSubmitting.value) return
  if (!notifConfig.value.waybackclaw_configured) return
  if (!isPublic.value) return
  wbcSubmitting.value = true
  wbcError.value = ''
  wbcErrorClass.value = ''
  try {
    const res = await publishToWaybackclaw(props.simulationId)
    if (res?.success && res.data?.id) {
      wbcRecord.value = res.data
      wbcError.value = res?.cached
        ? tr('Already submitted — returned existing record.', '已提交 — 返回现有归档记录。', { de: 'Bereits übermittelt — vorhandenen Eintrag zurückgegeben.' , fr: 'Déjà soumis — enregistrement existant retourné.'})
        : tr('Submitted to WaybackClaw. Snapshot archived.', '已提交至 WaybackClaw,快照已归档。', { de: 'An WaybackClaw übermittelt. Snapshot archiviert.' , fr: 'Soumis à WaybackClaw. Instantané archivé.'})
      wbcErrorClass.value = 'webhook-log-message-ok'
    } else {
      wbcError.value = res?.error || tr('Could not submit to WaybackClaw.', '无法提交至 WaybackClaw。', { de: 'An WaybackClaw konnte nicht übermittelt werden.' , fr: 'Impossible de soumettre à WaybackClaw.'})
      wbcErrorClass.value = 'webhook-log-message-error'
    }
  } catch (err) {
    const status = err?.response?.status
    const serverErr = err?.response?.data?.error
    if (status === 401) {
      wbcError.value = tr('Admin token does not match — set Authorization: Bearer $MIROSHARK_ADMIN_TOKEN to submit to WaybackClaw.',
        '管理员 token 不匹配 — 请设置 Authorization: Bearer $MIROSHARK_ADMIN_TOKEN 才能提交至 WaybackClaw。',
        { de: 'Admin-Token stimmt nicht überein — setze Authorization: Bearer $MIROSHARK_ADMIN_TOKEN, um an WaybackClaw zu übermitteln.' , fr: 'Le token admin ne correspond pas — définissez Authorization: Bearer $MIROSHARK_ADMIN_TOKEN pour soumettre à WaybackClaw.'},
      )
    } else if (status === 503) {
      wbcError.value = serverErr || tr('WaybackClaw publishing is not configured on this deployment.',
        '该部署未配置 WaybackClaw 发布。',
        { de: 'WaybackClaw-Veröffentlichung ist auf diesem Deployment nicht konfiguriert.' , fr: 'WaybackClaw non configuré sur ce déploiement.'},
      )
    } else if (status === 504) {
      wbcError.value = serverErr || tr('WaybackClaw API unreachable or submit timed out.',
        '无法访问 WaybackClaw API 或提交超时。',
        { de: 'WaybackClaw API nicht erreichbar oder Übermittlung hat das Zeitlimit überschritten.' , fr: 'API WaybackClaw injoignable.'},
      )
    } else if (status === 502) {
      wbcError.value = serverErr || tr('WaybackClaw API returned an error.',
        'WaybackClaw API 返回错误。',
        { de: 'WaybackClaw API hat einen Fehler zurückgegeben.' , fr: 'L\'API WaybackClaw a retourné une erreur.'},
      )
    } else if (status === 429) {
      wbcError.value = serverErr || tr('WaybackClaw rate limit exceeded — back off and retry.',
        'WaybackClaw 速率限制 — 请稍后重试。',
        { de: 'WaybackClaw-Ratenlimit überschritten — bitte warten und erneut versuchen.' , fr: 'Limite de débit WaybackClaw dépassée.'},
      )
    } else if (status === 422) {
      wbcError.value = serverErr || tr('Simulation has not reached the prepared state — nothing to archive yet.',
        '模拟尚未到达可发布状态,暂无可归档的数据。',
        { de: 'Simulation hat den vorbereiteten Zustand noch nicht erreicht — noch nichts zu archivieren.' , fr: 'La simulation n\'est pas prête — rien à archiver.'},
      )
    } else {
      wbcError.value = serverErr || err?.message || tr('Could not submit to WaybackClaw.', '无法提交至 WaybackClaw。', { de: 'An WaybackClaw konnte nicht übermittelt werden.' , fr: 'Impossible de soumettre à WaybackClaw.'})
    }
    wbcErrorClass.value = 'webhook-log-message-error'
  } finally {
    wbcSubmitting.value = false
  }
}

const _resetWaybackclawState = () => {
  wbcRecord.value = null
  wbcLoading.value = false
  wbcSubmitting.value = false
  wbcError.value = ''
  wbcErrorClass.value = ''
}

const formatUalShort = (ual) => {
  if (!ual || typeof ual !== 'string') return ''
  if (ual.length <= 48) return ual
  return `${ual.slice(0, 28)}…${ual.slice(-16)}`
}

const formatHashShort = (hash) => {
  if (!hash || typeof hash !== 'string') return ''
  if (hash.length <= 18) return hash
  return `${hash.slice(0, 10)}…${hash.slice(-6)}`
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
  _resetDkgState()
  _resetWaybackclawState()
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
  // Pull the sitemap config once per dialog open so the search-engine
  // indexing row knows whether to render the "enabled" or "disabled"
  // hint. Cheap (single small JSON) and the result rarely changes,
  // but reading on each open keeps the row in sync if an operator
  // toggles ``ENABLE_SITEMAP`` and reloads.
  loadSitemapConfig()
  // Pull the notification-channel config — cheap (three env reads
  // server-side, no Neo4j) so reading on each dialog open lets the
  // chips reflect a Settings save without requiring a hard refresh.
  await loadNotificationsConfig()
  // Probe for an existing DKG citation. Only meaningful when the
  // deployment has DKG_* env vars wired up *and* the sim is public —
  // the load helper short-circuits on either gate so this is cheap.
  loadDkgCitation()
  // Probe for an existing WaybackClaw submission. Same gating shape
  // as DKG — short-circuits unless waybackclaw_configured && isPublic.
  loadWaybackclawRecord()
  // Bust the share-card image cache so the preview reloads with whatever
  // state the simulation is in right now (resolution may have landed
  // since the dialog was last opened).
  shareCardCacheBust.value = Date.now()
  // Pull the tweet thread alongside the share-card preview — same publish
  // gate, so a private sim resolves cleanly to the empty state without
  // an extra round-trip on every dialog open.
  loadThread()
  // Pull the trading signal alongside the thread — same publish gate,
  // tiny payload (~250 bytes), and the preview row needs the parsed
  // payload to render the direction / confidence / risk-tier chips.
  loadSignal()
  // Peak-round analytics sits on the same publish gate; load alongside
  // so the inflection-point preview renders without a manual refresh.
  loadPeakRound()
  // Belief volatility sits on the same publish gate; load alongside so
  // the turbulence preview renders without a manual refresh.
  loadVolatility()
  // Per-agent sparklines sit on the same publish gate; load alongside so
  // the agent-trajectory rows render without a manual refresh.
  loadAgentSparklines()
  // Agent roster sits on the same publish gate; load alongside so the
  // participants section renders without a manual refresh.
  loadAgentsJson()
  // Polymarket prediction sits on the same gate as signal.json; load
  // alongside so the YES/NO preview row renders without a manual refresh.
  loadPolymarket()
  // Clone payload sits on the same publish gate; load alongside so the
  // inputs preview renders without a manual refresh. Inputs are
  // structural (no LLM round-trip), so the fetch is cheap.
  loadClone()
  // HEAD the archive endpoint so the bundle section can show the file
  // count without downloading the ZIP. Same publish gate as every
  // other surface — a private sim resolves cleanly to "not available".
  loadArchive()
  // Same publish gate for the Farcaster Frame metadata — fetched once on
  // open so the operator sees the Frame image preview + Warpcast
  // composer link without a manual refresh.
  loadFrameMetadata()
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
  // Same publish-gate flip applies to the trading signal — re-fetch.
  loadSignal()
  // Same publish-gate flip applies to peak-round analytics — re-fetch.
  loadPeakRound()
  // Same publish-gate flip applies to belief volatility — re-fetch.
  loadVolatility()
  // Same publish-gate flip applies to per-agent sparklines — re-fetch.
  loadAgentSparklines()
  // Same publish-gate flip applies to the agent roster — re-fetch.
  loadAgentsJson()
  // Polymarket prediction sits on the same gate; re-fetch alongside.
  loadPolymarket()
  // Same publish-gate flip applies to the clone payload — re-fetch so
  // the inputs preview populates after publish.
  loadClone()
  // Same flip applies to the archive bundle — re-HEAD so the bundle
  // section reflects the now-available surface count.
  loadArchive()
  // Same flip applies to the Farcaster Frame metadata — going public
  // means the 403 → 200 gate flip should populate the Frame preview.
  loadFrameMetadata()
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
  // DKG citation probe flips on the same publish gate. The load helper
  // short-circuits when the sim is private or the deployment isn't
  // configured for DKG, so we can always call it.
  loadDkgCitation()
  // WaybackClaw record probe — same gating semantics as DKG.
  loadWaybackclawRecord()
})
</script>

<style scoped>
.embed-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(5, 3, 10, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  overflow-y: auto;
}

.embed-dialog {
  background: linear-gradient(180deg, rgba(40,30,70,0.85) 0%, rgba(18,12,38,0.95) 100%);
  color: #f4f1ff;
  width: min(720px, 100%);
  max-height: calc(100vh - 40px);
  overflow-y: auto;
  border-radius: 18px;
  border: 1px solid rgba(167,139,250,0.22);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.1),
    0 24px 56px rgba(0, 0, 0, 0.45),
    0 0 0 1px rgba(0,0,0,0.4);
  padding: 22px 24px 20px;
  font-family: 'Geist', system-ui, -apple-system, sans-serif;
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
  border-radius: 9999px;
  background: linear-gradient(180deg, rgba(167,139,250,0.55) 0%, rgba(76,29,149,0.75) 100%);
  border: 1px solid rgba(167,139,250,0.55);
  color: #ffffff;
  font-size: 13px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.2);
}

.title-sub {
  font-size: 10px;
  font-weight: 600;
  color: rgba(196,181,253,0.85);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  padding: 3px 10px;
  background: linear-gradient(180deg, rgba(40,30,70,0.55) 0%, rgba(18,12,38,0.85) 100%);
  border: 1px solid rgba(167,139,250,0.18);
  border-radius: 9999px;
}

.embed-dialog-close {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(40,30,70,0.55) 0%, rgba(18,12,38,0.85) 100%);
  border: 1px solid rgba(255,255,255,0.08);
  font-size: 16px;
  line-height: 1;
  color: rgba(228,222,255,0.75);
  cursor: pointer;
  border-radius: 9999px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
  transition: color 0.15s, border-color 0.15s, transform 0.15s;
}

.embed-dialog-close:hover {
  color: #ffffff;
  border-color: rgba(167,139,250,0.55);
  transform: translateY(-1px);
}

.embed-dialog-desc {
  font-size: 13px;
  color: rgba(228,222,255,0.7);
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
  color: rgba(228,222,255,0.62);
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
  border: 1px solid rgba(255,255,255, 0.12);
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  color: #f4f1ff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s;
}

.embed-size-btn:hover {
  border-color: rgba(244, 241, 255, 0.3);
}

.embed-size-btn.active {
  background: linear-gradient(180deg, #6a4ad6 0%, #4922b8 45%, #2a118a 55%, #4f2dc4 100%);
  color: #ffffff;
  border-color: rgba(167,139,250,0.6);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.35);
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
  color: rgba(228,222,255,0.62);
  font-weight: 500;
}

.embed-theme-select {
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  color: #f4f1ff;
  border: 1px solid rgba(255,255,255, 0.12);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.embed-preview-wrap {
  background: repeating-linear-gradient(
    45deg,
    rgba(255,255,255, 0.03),
    rgba(255,255,255, 0.03) 10px,
    rgba(255,255,255, 0.06) 10px,
    rgba(255,255,255, 0.06) 20px
  );
  border: 1px solid rgba(255,255,255, 0.08);
  border-radius: 10px;
  padding: 14px;
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.embed-preview-frame {
  width: 100%;
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
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
  border: 1px solid rgba(255,255,255, 0.08);
  border-radius: 10px;
  overflow: hidden;
  background: rgba(255,255,255, 0.02);
}

.snippet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255,255,255, 0.04);
  font-size: 11px;
  font-weight: 600;
  color: rgba(228,222,255,0.62);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.snippet-copy-btn {
  background: linear-gradient(180deg, #6a4ad6 0%, #4922b8 45%, #2a118a 55%, #4f2dc4 100%);
  color: #ffffff;
  border: 1px solid rgba(167,139,250,0.5);
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.04em;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.3);
  transition: opacity 0.15s, transform 0.15s;
}

.snippet-copy-btn:hover { opacity: 0.85; }

.snippet-code {
  margin: 0;
  padding: 10px 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  line-height: 1.55;
  color: rgba(244,241,255,0.9);
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
  color: rgba(244,241,255,0.86);
  line-height: 1.5;
}

.hint-icon {
  flex-shrink: 0;
  color: #fbbf24;
  font-weight: 700;
}

.embed-dialog-hint code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  padding: 1px 6px;
  background: rgba(255,255,255, 0.06);
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
  color: rgba(228,222,255,0.62);
}

.share-card-divider .divider-line {
  flex: 1;
  height: 1px;
  background: rgba(255,255,255, 0.08);
}

.share-card-divider .divider-text {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.share-card-desc {
  font-size: 12.5px;
  color: rgba(244,241,255,0.86);
  margin: 0;
  line-height: 1.55;
}

.share-card-preview-wrap {
  background: repeating-linear-gradient(
    45deg,
    rgba(255,255,255, 0.03),
    rgba(255,255,255, 0.03) 10px,
    rgba(255,255,255, 0.06) 10px,
    rgba(255,255,255, 0.06) 20px
  );
  border: 1px solid rgba(255,255,255, 0.08);
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
  background: #110a26;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
  object-fit: contain;
  display: block;
}

.share-card-empty {
  color: rgba(228,222,255,0.62);
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  color: rgba(244,241,255,0.86);
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
  color: #fbbf24;
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
  color: rgba(244,241,255,0.86);
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
  color: rgba(244,241,255,0.86);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: linear-gradient(180deg, rgba(255,255,255, 0.15), rgba(255,255,255, 0.4));
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
  background: #110a26;
  border: 1px solid rgba(255,255,255, 0.08);
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
  color: #f4f1ff;
  margin-bottom: 4px;
}

.transcript-sub {
  font-size: 12px;
  line-height: 1.5;
  color: rgba(244,241,255,0.86);
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  color: #f4f1ff;
  border: 1px solid rgba(255,255,255, 0.18);
}

.transcript-download-btn-secondary:hover {
  background: rgba(255,255,255, 0.04);
}

.transcript-empty {
  font-size: 12px;
  color: rgba(228,222,255,0.62);
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
  background: #1a0f3a;
  border: 1px solid rgba(255,255,255, 0.08);
  border-radius: 6px;
  padding: 8px 10px;
  overflow-x: auto;
  white-space: nowrap;
}

.trajectory-quickstart code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: rgba(244,241,255,0.86);
}

/* Trajectory chart SVG — scalable-vector preview block matches the
   transcript / trajectory section visual rhythm. ``loading="lazy"``
   means the bytes don't transit until the dialog is scrolled into
   view, so opening the dialog stays snappy on slow networks. */
.chart-svg-preview {
  margin-top: 10px;
  background: #110a26;
  border: 1px solid rgba(255,255,255, 0.08);
  border-radius: 6px;
  padding: 8px;
  overflow: hidden;
}

.chart-svg-img {
  display: block;
  width: 100%;
  height: auto;
  max-width: 100%;
  border-radius: 4px;
}

/* Status badge — Shields.io-compatible 20-pixel SVG. The preview
   sits on a subtle checkerboard so the badge background colour stays
   visible against the dialog's light grey panel. ``height: 20`` is
   pinned to the badge's intrinsic height so the preview never gets
   stretched. */
.badge-section {
  margin-top: 14px;
}

.badge-preview {
  margin-top: 10px;
  padding: 12px;
  background: #110a26;
  border: 1px solid rgba(255,255,255, 0.08);
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.badge-svg-img {
  display: inline-block;
  height: 20px;
  width: auto;
  vertical-align: middle;
}

/* Trading signal — the action primitive sitting on top of the
   data-export stack. The header badge mirrors what the JSON payload
   carries (direction + one-decimal confidence) so an operator can
   read the verdict without expanding the preview rows below. */
.signal-section {
  margin-top: 14px;
}

.signal-direction-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  vertical-align: middle;
  text-transform: none;
  background: rgba(255,255,255, 0.08);
  color: rgba(244,241,255,0.86);
}

.signal-direction-bullish {
  color: #4ade80;
  background: rgba(34, 197, 94, 0.15);
}

.signal-direction-neutral {
  color: rgba(244,241,255,0.86);
  background: rgba(107, 114, 128, 0.15);
}

.signal-direction-bearish {
  color: #f87171;
  background: rgba(239, 68, 68, 0.15);
}

.signal-preview {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
  margin-top: 10px;
  padding: 10px 12px;
  background: rgba(255,255,255, 0.03);
  border-radius: 8px;
  font-size: 13px;
}

.signal-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.signal-label {
  color: rgba(244,241,255,0.86);
  font-weight: 500;
}

.signal-value {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 600;
  color: rgba(244,241,255,0.86);
}

.signal-risk-low-risk {
  color: #4ade80;
}

.signal-risk-medium-risk {
  color: #fbbf24;
}

.signal-risk-high-risk {
  color: #f87171;
}

.signal-row-breakdown .signal-value {
  font-family: inherit;
  font-weight: 500;
}

.polymarket-tier-speculative {
  color: #fbbf24;
}

.polymarket-tier-moderate {
  color: #fbbf24;
}

.polymarket-tier-confident {
  color: #4ade80;
}

.polymarket-tier-high-conviction {
  color: #4ade80;
  font-weight: 700;
}

.polymarket-yes-badge {
  background: rgba(34, 197, 94, 0.18);
  color: #4ade80;
}

.polymarket-title-value {
  font-family: inherit;
  font-style: italic;
  color: rgba(244,241,255,0.86);
}

.signal-loading,
.signal-empty {
  margin-top: 10px;
  padding: 8px 12px;
  font-size: 13px;
  color: rgba(228,222,255,0.62);
  font-style: italic;
}

/* Belief volatility — the horizontal turbulence bar sitting under the
   index row. Three colour bands match the documented buckets the
   docs/API.md describe: green ≤33 (calm), amber 34-66 (moderate), red
   ≥67 (turbulent). */
.volatility-bar-wrap {
  height: 6px;
  margin: 4px 0 4px;
  background: rgba(255,255,255, 0.06);
  border-radius: 999px;
  overflow: hidden;
}

.volatility-bar {
  height: 100%;
  border-radius: 999px;
  transition: width 0.18s ease-out;
}

.volatility-bar-low {
  background: #22c55e;
}

.volatility-bar-mid {
  background: #f59e0b;
}

.volatility-bar-high {
  background: #ef4444;
}

/* Per-agent sparklines — a scrollable list of agent rows, each a name
   chip + inline SVG belief trajectory + final-stance label. Capped
   height so a 100-agent swarm scrolls within the dialog instead of
   pushing the snippet blocks off-screen. */
.sparklines-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 10px;
  padding: 8px 10px;
  background: rgba(255,255,255, 0.03);
  border-radius: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.sparkline-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.sparkline-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(244,241,255,0.86);
  font-weight: 500;
}

.sparkline-svg {
  flex: 0 0 auto;
  display: block;
}

.sparkline-axis {
  stroke: rgba(255,255,255, 0.12);
  stroke-width: 0.5;
}

.sparkline-stance {
  flex: 0 0 auto;
  width: 56px;
  text-align: right;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 600;
  text-transform: capitalize;
}

.sparkline-note {
  margin-top: 4px;
  padding-top: 6px;
  border-top: 1px solid rgba(255,255,255, 0.06);
  font-size: 12px;
  color: rgba(228,222,255,0.62);
  font-style: italic;
}

/* Agent roster — the participants surface. Vertical list of agent
   cards, each with name + handle + stance chip on top, demographic
   tags on a row, and a persona preview below. Capped height so a
   50-agent swarm scrolls within the dialog instead of pushing the
   snippet blocks off-screen. Sibling visual style to the sparklines
   list above so the participant view reads as the identity layer of
   the same agent set. */
.agents-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
  padding: 10px 12px;
  background: rgba(255,255,255, 0.03);
  border-radius: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.agent-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255,255,255, 0.05);
}

.agent-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.agent-row-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: rgba(244,241,255,0.92);
}

.agent-handle {
  font-size: 12px;
  color: rgba(228,222,255,0.55);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.agent-stance-chip {
  margin-left: auto;
  font-size: 11px;
  font-weight: 600;
  text-transform: capitalize;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.agent-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.agent-tag {
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.02em;
  background: rgba(255,255,255, 0.06);
  color: rgba(228,222,255,0.78);
}

.agent-persona {
  font-size: 12px;
  line-height: 1.4;
  color: rgba(228,222,255,0.72);
  font-style: italic;
}

.agents-overflow-note {
  margin-top: 2px;
  padding-top: 6px;
  border-top: 1px solid rgba(255,255,255, 0.06);
  font-size: 11px;
  color: rgba(228,222,255,0.55);
  font-style: italic;
}

/* Archive bundle — the take-offline composite. One ZIP, every
   published surface inside, plus a manifest.json pairing each file
   with its SHA-256 + size + canonical source URL. Layout mirrors the
   signal section: an at-a-glance summary grid above the snippet
   blocks so an operator can read the file count and citation
   guarantees without expanding anything. */
.archive-section {
  margin-top: 14px;
}

.archive-count-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  vertical-align: middle;
  text-transform: none;
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.archive-summary {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
  margin-top: 10px;
  padding: 10px 12px;
  background: rgba(255,255,255, 0.03);
  border-radius: 8px;
  font-size: 13px;
}

.archive-summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.archive-label {
  color: rgba(244,241,255,0.86);
  font-weight: 500;
}

.archive-value {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 600;
  color: rgba(244,241,255,0.86);
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
  background: rgba(255,255,255, 0.08);
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(244,241,255,0.86);
  vertical-align: middle;
  text-transform: none;
}

.thread-error {
  color: #f87171;
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  border: 1px solid rgba(255,255,255, 0.1);
  border-radius: 8px;
}

.thread-tweet-num {
  position: absolute;
  top: 10px;
  left: 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: rgba(228,222,255,0.62);
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
  border: 1px solid rgba(255,255,255, 0.12);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  color: rgba(244,241,255,0.86);
  transition: background 0.15s, border-color 0.15s;
}

.thread-tweet-copy:hover {
  background: rgba(255,255,255, 0.04);
  border-color: rgba(244, 241, 255, 0.24);
}

.thread-tweet-body {
  margin: 0;
  padding: 0;
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
  font-size: 13px;
  line-height: 1.5;
  color: #f4f1ff;
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
  color: rgba(228,222,255,0.62);
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
  color: #f4f1ff;
}

.surface-stats-total-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 8px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #f4f1ff;
  background: #f4ecd8;
  border-radius: 999px;
  vertical-align: middle;
}

.surface-stats-chevron {
  border: 0;
  background: transparent;
  font-size: 16px;
  line-height: 1;
  color: rgba(228,222,255,0.62);
  cursor: pointer;
  padding: 4px 6px;
  transition: transform 0.15s, color 0.15s;
}

.surface-stats-chevron-open {
  transform: rotate(180deg);
  color: #f4f1ff;
}

.surface-stats-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.surface-stats-loading {
  font-size: 12px;
  color: rgba(228,222,255,0.62);
  font-style: italic;
}

.surface-stats-error {
  color: #f87171;
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
  color: #f4f1ff;
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
  color: rgba(228,222,255,0.62);
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  color: #f4f1ff;
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
  border-color: #fcd34d;
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
  color: #a78bfa;
  vertical-align: middle;
  text-transform: none;
  cursor: help;
}

.repro-chevron {
  align-self: center;
  border: none;
  background: transparent;
  font-size: 14px;
  color: rgba(228,222,255,0.62);
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
  color: rgba(228,222,255,0.62);
  font-style: italic;
}

.repro-error {
  color: #f87171;
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
  background: #110a26;
  border: 1px solid rgba(255,255,255, 0.08);
  border-radius: 8px;
  padding: 10px 12px;
}

.repro-summary-row {
  display: contents;
}

.repro-summary-key {
  color: rgba(228,222,255,0.62);
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.repro-summary-value {
  color: #f4f1ff;
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
  color: rgba(228,222,255,0.62);
}

.repro-note {
  font-size: 11px;
  line-height: 1.5;
  color: rgba(228,222,255,0.62);
  background: #1a0f3a;
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
  color: #4ade80;
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
  border: 1px solid rgba(255,255,255, 0.07);
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
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
  color: #4ade80;
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
  color: rgba(228,222,255,0.62);
}

.lineage-row-id {
  font-family: var(--font-mono, "SFMono-Regular", "Menlo", monospace);
  font-size: 11px;
  font-weight: 600;
  color: rgba(244,241,255,0.86);
}

.lineage-row-scenario {
  font-size: 12px;
  line-height: 1.4;
  color: rgba(244,241,255,0.86);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.lineage-row-private {
  font-size: 11px;
  color: rgba(228,222,255,0.62);
  font-style: italic;
}

.lineage-row-link {
  font-size: 11px;
  font-weight: 600;
  color: #4ade80;
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
  color: rgba(228,222,255,0.62);
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
  color: #a78bfa;
}

.lineage-child-badge-cf {
  background: rgba(234, 88, 12, 0.1);
  color: #fbbf24;
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
  color: rgba(228,222,255,0.62);
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
  color: #f4f1ff;
  margin-bottom: 4px;
}

.watch-sub {
  font-size: 12px;
  line-height: 1.5;
  color: rgba(244,241,255,0.86);
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
  color: rgba(228,222,255,0.62);
  font-style: italic;
}

.watch-snippet {
  margin: 0;
}

.outcome-section {
  margin-top: 18px;
  padding: 14px 16px;
  background: #110a26;
  border: 1px dashed rgba(255,255,255, 0.18);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.outcome-section-live {
  background: rgba(167, 139, 250, 0.04);
  border-color: rgba(167, 139, 250, 0.3);
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
  color: #f4f1ff;
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
  color: var(--color-orange, #a78bfa);
  background: rgba(167, 139, 250, 0.1);
  padding: 2px 8px;
  border-radius: 999px;
}

.outcome-sub {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(244,241,255,0.86);
}

.outcome-sub a {
  color: var(--color-orange, #a78bfa);
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
  border: 1px solid rgba(255,255,255, 0.16);
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  transition: border-color 0.15s, background 0.15s;
}

.outcome-radio input {
  appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1.5px solid rgba(255,255,255, 0.35);
  position: relative;
}

.outcome-radio input:checked {
  border-color: var(--color-orange, #a78bfa);
  background: var(--color-orange, #a78bfa);
  box-shadow: inset 0 0 0 2px #fff;
}

.outcome-radio-active {
  border-color: var(--color-orange, #a78bfa);
  background: rgba(167, 139, 250, 0.08);
}

.outcome-radio-icon { font-family: sans-serif; }

.outcome-input,
.outcome-textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid rgba(255,255,255, 0.14);
  border-radius: 8px;
  font-size: 12.5px;
  font-family: inherit;
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  color: #f4f1ff;
  resize: vertical;
}

.outcome-input:focus,
.outcome-textarea:focus {
  outline: none;
  border-color: var(--color-orange, #a78bfa);
  box-shadow: 0 0 0 3px rgba(167, 139, 250, 0.12);
}

.outcome-input:disabled,
.outcome-textarea:disabled {
  background: rgba(255,255,255, 0.03);
  color: rgba(228,222,255,0.62);
  cursor: not-allowed;
}

.outcome-summary-counter {
  align-self: flex-end;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10.5px;
  color: rgba(228,222,255,0.62);
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
  background: var(--color-orange, #a78bfa);
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
}

.outcome-submit:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.outcome-link {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  color: var(--color-orange, #a78bfa);
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
  background: rgba(196, 181, 253, 0.12);
  color: #4ade80;
}

.outcome-message-error {
  background: rgba(255, 68, 68, 0.12);
  color: #f87171;
}

.gallery-callout {
  margin-top: 18px;
  padding: 14px 16px;
  background: #110a26;
  border: 1px dashed rgba(255,255,255, 0.18);
  border-radius: 10px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.gallery-callout-live {
  background: rgba(167, 139, 250, 0.06);
  border-color: rgba(167, 139, 250, 0.45);
  border-style: solid;
}

.gallery-callout-icon {
  font-size: 22px;
  line-height: 1;
  color: var(--color-orange, #a78bfa);
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
  color: #f4f1ff;
  margin-bottom: 4px;
}

.gallery-callout-desc {
  font-size: 12.5px;
  line-height: 1.5;
  color: rgba(244,241,255,0.86);
}

.gallery-callout-desc a {
  color: var(--color-orange, #a78bfa);
  text-decoration: none;
  font-weight: 600;
}

.gallery-callout-desc a:hover { text-decoration: underline; }

.gallery-callout-link {
  flex-shrink: 0;
  align-self: center;
  padding: 6px 12px;
  background: var(--color-orange, #a78bfa);
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
}

/* RSS / Atom feed callout — same anatomy as the gallery callout but
   with a wraparound action row (three feed flavours). Reads as a
   secondary discovery affordance, not a primary action, so the chips
   are outline-styled rather than filled. */
.feed-callout {
  margin-top: 12px;
  padding: 14px 16px;
  background: #110a26;
  border: 1px dashed rgba(255,255,255, 0.18);
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
  color: var(--color-orange, #a78bfa);
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
  color: #f4f1ff;
  margin-bottom: 4px;
}

.feed-callout-desc {
  font-size: 12.5px;
  line-height: 1.5;
  color: rgba(244,241,255,0.86);
}

.feed-callout-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 34px;
}

.feed-callout-link {
  padding: 6px 12px;
  background: var(--color-orange, #a78bfa);
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
}

.feed-callout-link-secondary {
  background: transparent;
  color: var(--color-orange, #a78bfa);
  border: 1px solid rgba(167, 139, 250, 0.45);
}

.feed-callout-link-secondary:hover {
  background: var(--color-orange, #a78bfa);
  color: #fff;
  border-color: var(--color-orange, #a78bfa);
}

/* Notifications callout — three status chips track WEBHOOK_URL /
   DISCORD_WEBHOOK_URL / SLACK_WEBHOOK_URL. Chips are intentionally
   small and muted; the goal is "at-a-glance" config feedback, not a
   primary action. The chip palette mirrors the feed-callout link
   palette so the notifications row blends with the surrounding
   secondary affordances rather than competing for attention. */
.notifications-chips {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.notifications-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255, 0.12);
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  color: rgba(228,222,255,0.62);
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.03em;
  cursor: help;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.notifications-chip-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  background: rgba(255,255,255, 0.08);
  color: rgba(228,222,255,0.62);
}

.notifications-chip-on {
  border-color: rgba(34, 197, 94, 0.5);
  background: rgba(34, 197, 94, 0.08);
  color: #4ade80;
}

.notifications-chip-on .notifications-chip-dot {
  background: #22c55e;
  color: #ffffff;
}

.feed-filter-builder {
  margin-top: 4px;
  padding: 12px 14px;
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  border: 1px solid rgba(255,255,255, 0.08);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feed-filter-builder-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #f4f1ff;
}

.feed-filter-builder-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.feed-filter-control {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 110px;
  flex: 1 1 110px;
}

.feed-filter-label {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: rgba(228,222,255,0.62);
}

.feed-filter-select {
  padding: 6px 8px;
  font-size: 12.5px;
  border: 1px solid rgba(255,255,255, 0.16);
  border-radius: 6px;
  background: #110a26;
  color: #f4f1ff;
  font-family: inherit;
}

.feed-filter-select:focus {
  outline: none;
  border-color: var(--color-orange, #a78bfa);
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
}

.feed-filter-builder-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: stretch;
}

.feed-filter-url {
  flex: 1 1 220px;
  min-width: 0;
  padding: 6px 10px;
  font-size: 11.5px;
  font-family: 'SFMono-Regular', 'Menlo', monospace;
  border: 1px solid rgba(255,255,255, 0.16);
  border-radius: 6px;
  background: #110a26;
  color: #f4f1ff;
}

.feed-filter-copy {
  padding: 6px 14px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: transparent;
  color: var(--color-orange, #a78bfa);
  border: 1px solid rgba(167, 139, 250, 0.45);
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s ease, color 0.15s ease;
}

.feed-filter-copy:hover {
  background: var(--color-orange, #a78bfa);
  color: #fff;
}

.feed-filter-copy-active {
  background: var(--color-orange, #a78bfa);
  color: #fff;
}

.feed-filter-builder-note {
  font-size: 11.5px;
  line-height: 1.45;
  color: rgba(228,222,255,0.62);
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
  background: #110a26;
  border: 1px solid rgba(255,255,255, 0.08);
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
  color: #f4f1ff;
  display: flex;
  align-items: center;
  gap: 8px;
}

.webhook-log-count {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: none;
  color: rgba(244,241,255,0.86);
  padding: 2px 7px;
  background: rgba(255,255,255, 0.06);
  border-radius: 999px;
}

.webhook-log-sub {
  font-size: 12px;
  line-height: 1.5;
  color: rgba(244,241,255,0.86);
  margin-top: 4px;
}

.webhook-log-toggle {
  flex-shrink: 0;
  background: transparent;
  border: 1px solid rgba(255,255,255, 0.18);
  color: #f4f1ff;
  font-size: 13px;
  font-weight: 600;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.webhook-log-toggle:hover {
  background: rgba(255,255,255, 0.05);
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
  color: rgba(244,241,255,0.86);
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255,255,255, 0.04);
}

.webhook-log-config-hint {
  background: rgba(255, 178, 0, 0.12);
  color: #7a4a00;
}

.webhook-log-error {
  background: rgba(255, 68, 68, 0.10);
  color: #f87171;
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
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  border: 1px solid rgba(255,255,255, 0.06);
}

.webhook-log-row-icon {
  font-weight: 700;
  font-size: 13px;
}

.webhook-log-row-attempt {
  color: rgba(244,241,255,0.86);
  font-size: 11px;
}

.webhook-log-row-code {
  font-weight: 600;
  color: #f4f1ff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.webhook-log-row-latency {
  color: rgba(244,241,255,0.86);
}

.webhook-log-row-trigger {
  color: rgba(228,222,255,0.62);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.webhook-log-row-time {
  color: rgba(228,222,255,0.62);
  font-size: 11px;
  white-space: nowrap;
}

.webhook-row-ok .webhook-log-row-icon { color: #4ade80; }
.webhook-row-fail .webhook-log-row-icon { color: #f87171; }
.webhook-row-timeout .webhook-log-row-icon { color: #fbbf24; }

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
  border: 1px solid rgba(255,255,255, 0.18);
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  color: #f4f1ff;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.webhook-log-refresh:hover,
.webhook-log-retry:hover {
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  color: #fff;
  border-color: #f4f1ff;
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
  background: rgba(196, 181, 253, 0.12);
  color: #4ade80;
}

.webhook-log-message-error {
  background: rgba(255, 68, 68, 0.12);
  color: #f87171;
}

.signature-hint {
  margin-top: 4px;
  border: 1px solid rgba(255,255,255, 0.10);
  border-radius: 6px;
  background: rgba(255,255,255, 0.025);
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
  color: #f4f1ff;
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
  color: rgba(244, 241, 255, 0.5);
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
  color: rgba(244, 241, 255, 0.78);
}

.signature-hint-line a {
  color: #f4f1ff;
  text-decoration: underline;
}

.signature-hint-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  background: rgba(255,255,255, 0.06);
  padding: 6px 8px;
  border-radius: 4px;
  color: #f4f1ff;
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

/* ---- OriginTrail DKG citation card -------------------------------------
 *
 * Visually slots between the Jupyter notebook export and the lineage
 * navigator. The card reuses the same vertical-stack pattern as the
 * reproducibility config block (head + body + actions + note) so it
 * lands in the dialog without a new visual idiom.
 */
.dkg-section {
  margin-top: 18px;
}

.dkg-body {
  padding: 12px 14px 14px;
}

.dkg-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.dkg-card-empty {
  align-items: flex-start;
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  border-style: dashed;
}

.dkg-empty-text {
  color: rgba(228,222,255,0.62);
  font-size: 13px;
  line-height: 1.45;
}

.dkg-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.dkg-row-label {
  color: rgba(228,222,255,0.62);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  min-width: 96px;
}

.dkg-row-value {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 12.5px;
  color: rgba(244,241,255,0.86);
  word-break: break-all;
}

.dkg-row-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  padding: 3px 6px;
  background: linear-gradient(180deg, rgba(50,38,86,0.5) 0%, rgba(18,12,38,0.72) 100%);
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.dkg-row-meta {
  font-size: 11.5px;
  color: rgba(228,222,255,0.62);
}

.dkg-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.dkg-copy {
  flex: 0 0 auto;
}

.dkg-publish-btn {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #ffffff;
  border: none;
}

.dkg-publish-btn:hover:not(:disabled) {
  filter: brightness(1.05);
}

.dkg-publish-btn:disabled {
  opacity: 0.7;
  cursor: progress;
}

.dkg-finalized-badge {
  color: #4ade80;
  background: #dcfce7;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 600;
}

.dkg-network-chip-testnet {
  background: #fef3c7;
  color: #fbbf24;
}

.dkg-network-chip-mainnet {
  background: #dcfce7;
  color: #4ade80;
}

/* ── Private share-link panel ─────────────────────────────────────────── */

.share-link-section {
  margin: 12px 0 8px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(80, 60, 130, 0.18);
  border: 1px solid rgba(167, 139, 250, 0.18);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.share-link-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.share-link-title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #f4f1ff;
}

.share-link-sub {
  font-size: 11px;
  color: rgba(244, 241, 255, 0.6);
  line-height: 1.4;
}

.share-link-mint-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.share-link-expiry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(244, 241, 255, 0.75);
}

.share-link-expiry select {
  background: rgba(20, 14, 40, 0.7);
  color: #f4f1ff;
  border: 1px solid rgba(167, 139, 250, 0.28);
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 12px;
}

.share-link-mint-btn {
  background: #ea580c;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.03em;
}

.share-link-mint-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.share-link-error {
  font-size: 11px;
  color: #fca5a5;
  margin: 0;
}

.share-link-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.share-link-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  background: rgba(20, 14, 40, 0.4);
  border-radius: 8px;
  border: 1px solid rgba(167, 139, 250, 0.12);
}

.share-link-url code {
  font-family: 'JetBrains Mono', 'Geist Mono', ui-monospace, monospace;
  font-size: 11px;
  color: #c4b5fd;
  word-break: break-all;
}

.share-link-meta {
  font-size: 10px;
  color: rgba(244, 241, 255, 0.5);
  letter-spacing: 0.02em;
}

.share-link-actions {
  display: flex;
  gap: 8px;
}

.share-link-copy,
.share-link-revoke {
  background: transparent;
  color: #c4b5fd;
  border: 1px solid rgba(167, 139, 250, 0.28);
  border-radius: 6px;
  padding: 3px 10px;
  font-size: 11px;
  cursor: pointer;
  letter-spacing: 0.02em;
}

.share-link-revoke {
  color: #fca5a5;
  border-color: rgba(252, 165, 165, 0.35);
}

.share-link-empty {
  font-size: 11px;
  color: rgba(244, 241, 255, 0.45);
  margin: 0;
  font-style: italic;
}
</style>
