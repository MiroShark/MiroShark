<template>
  <Teleport to="body">
    <div v-if="open" class="settings-overlay" @click.self="$emit('close')">
      <div class="settings-modal">
        <!-- Header -->
        <div class="modal-header">
          <div class="modal-title">
            <span class="title-label">⚙ {{ $tr('Settings', '设置', { de: 'Einstellungen', fr: 'Paramètres' }) }}</span>
          </div>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>

        <div class="warning-stripe"></div>

        <!-- Language Toggle -->
        <section class="settings-section">
          <div class="section-header">
            <span class="section-label">{{ $tr('Language / 语言', '语言 / Language', { de: 'Sprache / Language', fr: 'Langue / Langue' }) }}</span>
          </div>
          <div class="field-row" style="display:flex;align-items:center;gap:12px;">
            <label class="field-label">{{ $tr('Interface language', '界面语言', { de: 'Oberflächensprache', fr: `Langue de l'interface` }) }}</label>
            <LocaleToggle />
          </div>
        </section>

        <!-- Current Setup Summary -->
        <section class="settings-section">
          <div class="section-header">
            <span class="section-label">{{ $tr('Current Setup', '当前配置', { de: 'Aktuelle Konfiguration', fr: 'Configuration actuelle' }) }}</span>
            <div class="status-badge" :class="testStatus">
              <span class="badge-dot"></span>
              {{ testStatusText }}
            </div>
          </div>

          <div class="setup-grid">
            <div class="setup-row">
              <span class="setup-key">{{ $tr('Default model', '默认模型', { de: 'Standardmodell', fr: 'Modèle par défaut' }) }}</span>
              <span class="setup-val">{{ currentSettings.llm?.model_name || '—' }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">{{ $tr('Smart (reports)', '智能(报告)', { de: 'Smart (Berichte)', fr: 'Smart (rapports)' }) }}</span>
              <span class="setup-val">{{ currentSettings.smart?.model_name || inheritMarker }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">{{ $tr('NER (extraction)', 'NER(实体抽取)', { de: 'NER (Extraktion)', fr: 'NER (extraction)' }) }}</span>
              <span class="setup-val">{{ currentSettings.ner?.model_name || inheritMarker }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">{{ $tr('Wonderwall (sim loop)', 'Wonderwall(模拟循环)', { de: 'Wonderwall (Simulations-Loop)', fr: 'Wonderwall (boucle de simulation)' }) }}</span>
              <span class="setup-val">{{ currentSettings.wonderwall?.model_name || inheritMarker }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">{{ $tr('Embeddings', '嵌入', { de: 'Embeddings', fr: 'Embeddings' }) }}</span>
              <span class="setup-val">
                {{ currentSettings.embedding?.model_name || '—' }}
              </span>
            </div>
            <div class="setup-row">
              <span class="setup-key">{{ $tr('Web search', '网页搜索', { de: 'Websuche', fr: 'Recherche web' }) }}</span>
              <span class="setup-val">{{ currentSettings.web_search_model || inheritMarker }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">{{ $tr('SearXNG', 'SearXNG', { de: 'SearXNG', fr: 'SearXNG' }) }}</span>
              <span class="setup-val">{{ currentSettings.searxng_base_url || $tr('— not set —', '— 未设置 —', { de: '— nicht gesetzt —', fr: '— non défini —' }) }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">{{ $tr('Firecrawl', 'Firecrawl', { de: 'Firecrawl' , fr: 'Firecrawl'}) }}</span>
              <span class="setup-val">{{ currentSettings.firecrawl?.base_url || $tr('— not set —', '— 未设置 —', { de: '— nicht gesetzt —', fr: '— non défini —' }) }}</span>
            </div>
            <div class="setup-row">
              <span class="setup-key">{{ $tr('API key', 'API 密钥', { de: 'API-Schlüssel', fr: 'Clé API' }) }}</span>
              <span class="setup-val">
                <span v-if="currentSettings.llm?.has_api_key">
                  {{ currentSettings.llm.api_key_masked }}
                </span>
                <span v-else class="setup-missing">{{ $tr('not set', '未设置', { de: 'nicht gesetzt', fr: 'non défini' }) }}</span>
              </span>
            </div>
          </div>
        </section>

        <!-- Preset Picker -->
        <section class="settings-section">
          <div class="section-header">
            <span class="section-label">{{ $tr('Preset', '预设', { de: 'Voreinstellung', fr: 'Préréglage' }) }}</span>
          </div>

          <div class="field-row">
            <label class="field-label">{{ $tr('Config template', '配置模板', { de: 'Konfigurationsvorlage', fr: 'Modèle de configuration' }) }}</label>
            <div class="select-wrapper">
              <select v-model="form.preset" class="field-select">
                <option value="">{{ $tr('Custom — leave fields as they are', '自定义 — 保留当前字段', { de: 'Benutzerdefiniert — Felder beibehalten', fr: 'Personnalisé — laissez les champs tels quels' }) }}</option>
                <option
                  v-for="p in presetOptions"
                  :key="p.id"
                  :value="p.id"
                >{{ p.label }}</option>
              </select>
            </div>
            <div class="field-hint">
              {{ $tr('Applies the full set of model slots on save. See', '保存时将应用完整的模型槽配置。请参考', { de: 'Wendet beim Speichern alle Modell-Slots an. Siehe', fr: `Applique l'ensemble des slots de modèles à la sauvegarde. Voir` }) }}
              <a href="https://github.com/aaronjmars/MiroShark/blob/main/.env.example"
                 target="_blank" rel="noopener">.env.example</a>
              {{ $tr('for the exact values each preset uses.', '了解各预设使用的精确值。', { de: 'für die genauen Werte der jeweiligen Voreinstellung.', fr: 'pour les valeurs exactes de chaque préréglage.' }) }}
            </div>
          </div>

          <div v-if="presetNeedsKey" class="field-row">
            <label class="field-label">{{ $tr('OpenRouter API key', 'OpenRouter API 密钥', { de: 'OpenRouter API-Schlüssel', fr: 'Clé API OpenRouter' }) }}</label>
            <div class="key-input-group">
              <input
                v-model="form.presetApiKey"
                class="field-input"
                :type="showKey ? 'text' : 'password'"
                placeholder="sk-or-v1-..."
              />
              <button class="toggle-key-btn" @click="showKey = !showKey">
                {{ showKey ? '◉' : '◎' }}
              </button>
            </div>
            <div class="field-hint">
              {{ $tr('Filled into every slot the preset needs (default, smart, NER, embedding). Leave blank to keep your existing keys.', '将填入预设所需的每个槽(default、smart、NER、embedding)。留空则保留现有密钥。', { de: 'Wird in alle vom Preset benötigten Slots eingetragen (default, smart, NER, embedding). Leer lassen, um vorhandene Schlüssel zu behalten.', fr: 'Renseignée dans tous les slots dont le préréglage a besoin (default, smart, NER, embedding). Laissez vide pour conserver vos clés existantes.' }) }}
            </div>
          </div>
        </section>

        <!-- LLM Configuration -->
        <section class="settings-section">
          <div class="section-header">
            <span class="section-label">{{ $tr('LLM Configuration', 'LLM 配置', { de: 'LLM-Konfiguration', fr: 'Configuration LLM' }) }}</span>
          </div>

          <!-- Provider -->
          <div class="field-row">
            <label class="field-label">{{ $tr('Provider', '提供商', { de: 'Anbieter', fr: 'Fournisseur' }) }}</label>
            <div class="select-wrapper">
              <select v-model="form.llm.provider" class="field-select">
                <option value="openai">{{ $tr('OpenAI-compatible (OpenRouter, Ollama, etc.)', 'OpenAI 兼容(OpenRouter、Ollama 等)', { de: 'OpenAI-kompatibel (OpenRouter, Ollama, etc.)', fr: 'Compatible OpenAI (OpenRouter, Ollama, etc.)' }) }}</option>
                <option value="claude-code">{{ $tr('Claude Code (local CLI)', 'Claude Code(本地 CLI)', { de: 'Claude Code (lokale CLI)', fr: 'Claude Code (CLI local)' }) }}</option>
              </select>
            </div>
          </div>

          <!-- Base URL -->
          <div v-if="form.llm.provider !== 'claude-code'" class="field-row">
            <label class="field-label">{{ $tr('Base URL', '基础 URL', { de: 'Basis-URL', fr: 'URL de base' }) }}</label>
            <input
              v-model="form.llm.base_url"
              class="field-input"
              type="url"
              placeholder="https://openrouter.ai/api/v1"
            />
          </div>

          <!-- Model -->
          <div v-if="form.llm.provider !== 'claude-code'" class="field-row">
            <label class="field-label">{{ $tr('Model', '模型', { de: 'Modell', fr: 'Modèle' }) }}</label>
            <div class="model-input-group">
              <div class="select-wrapper model-select-wrapper">
                <select
                  v-if="modelList.length > 0"
                  v-model="form.llm.model_name"
                  class="field-select"
                >
                  <optgroup
                    v-for="tier in modelTiers"
                    :key="tier.label"
                    :label="tier.label"
                  >
                    <option
                      v-for="m in tier.models"
                      :key="m.id"
                      :value="m.id"
                    >{{ m.name }}</option>
                  </optgroup>
                </select>
                <input
                  v-else
                  v-model="form.llm.model_name"
                  class="field-input"
                  type="text"
                  :placeholder="$tr('e.g. openai/gpt-4o-mini', '例如 openai/gpt-4o-mini', { de: 'z. B. openai/gpt-4o-mini', fr: 'ex. openai/gpt-4o-mini' })"
                />
              </div>
              <button
                class="load-models-btn"
                :disabled="loadingModels || !isOpenRouter"
                @click="loadOpenRouterModels"
                :title="isOpenRouter ? $tr('Load available models from OpenRouter', '从 OpenRouter 加载可用模型', { de: 'Verfügbare Modelle von OpenRouter laden', fr: 'Charger les modèles disponibles depuis OpenRouter' }) : $tr('Only available for OpenRouter base URL', '仅在 OpenRouter 基础 URL 下可用', { de: 'Nur für OpenRouter-Basis-URL verfügbar', fr: `Uniquement disponible pour l'URL de base OpenRouter` })"
              >
                <span v-if="loadingModels">...</span>
                <span v-else>↻</span>
              </button>
            </div>
            <div v-if="modelLoadError" class="field-error">{{ modelLoadError }}</div>
          </div>

          <!-- API Key -->
          <div v-if="form.llm.provider !== 'claude-code'" class="field-row">
            <label class="field-label">{{ $tr('API Key', 'API 密钥', { de: 'API-Schlüssel', fr: 'Clé API' }) }}</label>
            <div class="key-input-group">
              <input
                v-model="form.llm.api_key"
                class="field-input"
                :type="showKey ? 'text' : 'password'"
                :placeholder="currentSettings.llm?.api_key_masked || 'sk-...'"
              />
              <button class="toggle-key-btn" @click="showKey = !showKey">
                {{ showKey ? '◉' : '◎' }}
              </button>
            </div>
            <div v-if="currentSettings.llm?.has_api_key && !form.llm.api_key" class="field-hint">
              {{ $tr('Current key:', '当前密钥:', { de: 'Aktueller Schlüssel:', fr: 'Clé actuelle :' }) }} {{ currentSettings.llm.api_key_masked }} {{ $tr('— leave blank to keep unchanged', ' — 留空则保持不变', { de: '— leer lassen, um unverändert zu behalten', fr: '— laissez vide pour ne pas modifier' }) }}
            </div>
          </div>

          <!-- Test Connection -->
          <div v-if="form.llm.provider !== 'claude-code'" class="field-row test-row">
            <button
              class="test-btn"
              :disabled="testing"
              @click="testConnection"
            >
              <span v-if="testing">{{ $tr('Testing...', '测试中...', { de: 'Wird getestet...', fr: 'Test en cours…' }) }}</span>
              <span v-else>{{ $tr('Test Connection', '测试连接', { de: 'Verbindung testen', fr: 'Tester la connexion' }) }}</span>
            </button>
            <div v-if="testResult" class="test-result" :class="testResult.success ? 'ok' : 'fail'">
              <span v-if="testResult.success">
                ✓ {{ testResult.model }} — {{ testResult.latency_ms }}ms
              </span>
              <span v-else>✗ {{ testResult.error }}</span>
            </div>
          </div>
        </section>

        <!-- Advanced: per-slot overrides -->
        <section class="settings-section">
          <button class="advanced-toggle" @click="advancedOpen = !advancedOpen">
            <span class="section-label">
              {{ $tr('Advanced slot overrides', '高级槽位覆盖', { de: 'Erweiterte Slot-Überschreibungen', fr: 'Remplacements avancés des slots' }) }}
            </span>
            <span class="chevron">{{ advancedOpen ? '−' : '+' }}</span>
          </button>

          <div v-if="advancedOpen" class="advanced-body">
            <div class="advanced-hint">
              {{ $tr('Each slot falls back to the default LLM config when left empty.', '每个槽位为空时将回退到默认 LLM 配置。', { de: 'Jeder Slot fällt auf die Standard-LLM-Konfiguration zurück, wenn er leer ist.', fr: `Chaque slot retombe sur la configuration LLM par défaut s'il est vide.` }) }}
            </div>

            <!-- Smart -->
            <div class="advanced-group">
              <div class="advanced-group-title">{{ $tr('Smart — report generation', '智能 — 报告生成', { de: 'Smart — Berichtsgenerierung', fr: 'Smart — génération de rapport' }) }}</div>
              <div class="field-row">
                <label class="field-label">{{ $tr('Model', '模型', { de: 'Modell', fr: 'Modèle' }) }}</label>
                <input
                  v-model="form.smart.model_name"
                  class="field-input"
                  type="text"
                  :placeholder="$tr('e.g. x-ai/grok-4.1-fast', '例如 x-ai/grok-4.1-fast', { de: 'z. B. x-ai/grok-4.1-fast', fr: 'ex. x-ai/grok-4.1-fast' })"
                />
              </div>
            </div>

            <!-- NER -->
            <div class="advanced-group">
              <div class="advanced-group-title">{{ $tr('NER — entity extraction', 'NER — 实体抽取', { de: 'NER — Entitätsextraktion', fr: `NER — extraction d'entités` }) }}</div>
              <div class="field-row">
                <label class="field-label">{{ $tr('Model', '模型', { de: 'Modell', fr: 'Modèle' }) }}</label>
                <input
                  v-model="form.ner.model_name"
                  class="field-input"
                  type="text"
                  :placeholder="$tr('e.g. x-ai/grok-4.1-fast', '例如 x-ai/grok-4.1-fast', { de: 'z. B. x-ai/grok-4.1-fast', fr: 'ex. x-ai/grok-4.1-fast' })"
                />
              </div>
            </div>

            <!-- Wonderwall -->
            <div class="advanced-group">
              <div class="advanced-group-title">{{ $tr('Wonderwall — simulation loop', 'Wonderwall — 模拟循环', { de: 'Wonderwall — Simulations-Loop', fr: 'Wonderwall — boucle de simulation' }) }}</div>
              <div class="field-row">
                <label class="field-label">{{ $tr('Model', '模型', { de: 'Modell', fr: 'Modèle' }) }}</label>
                <input
                  v-model="form.wonderwall.model_name"
                  class="field-input"
                  type="text"
                  :placeholder="$tr('e.g. inception/mercury-2:nitro', '例如 inception/mercury-2:nitro', { de: 'z. B. inception/mercury-2:nitro', fr: 'ex. inception/mercury-2:nitro' })"
                />
              </div>
              <div class="field-row">
                <label class="field-label">{{ $tr('Base URL', '基础 URL', { de: 'Basis-URL', fr: 'URL de base' }) }}</label>
                <input
                  v-model="form.wonderwall.base_url"
                  class="field-input"
                  type="text"
                  :placeholder="$tr('Inherits LLM base URL when blank', '留空时继承 LLM 基础 URL', { de: 'Übernimmt LLM-Basis-URL, wenn leer', fr: `Hérite de l'URL de base LLM si vide` })"
                />
              </div>
              <div class="field-row">
                <label class="field-label">{{ $tr('API Key', 'API 密钥', { de: 'API-Schlüssel', fr: 'Clé API' }) }}</label>
                <input
                  v-model="form.wonderwall.api_key"
                  class="field-input"
                  type="password"
                  :placeholder="currentSettings.wonderwall?.has_api_key ? `${$tr('Saved:', '已保存:', { de: 'Gespeichert:', fr: 'Enregistré :' })} ${currentSettings.wonderwall.api_key_masked}` : $tr('Inherits LLM key when blank', '留空时继承 LLM 密钥', { de: 'Übernimmt LLM-Schlüssel, wenn leer', fr: 'Hérite de la clé LLM si vide' })"
                />
              </div>
            </div>

            <!-- Embedding -->
            <div class="advanced-group">
              <div class="advanced-group-title">{{ $tr('Embeddings', '嵌入', { de: 'Embeddings', fr: 'Embeddings' }) }}</div>
              <div class="field-row">
                <label class="field-label">{{ $tr('Provider', '提供商', { de: 'Anbieter', fr: 'Fournisseur' }) }}</label>
                <div class="select-wrapper">
                  <select v-model="form.embedding.provider" class="field-select">
                    <option value="ollama">{{ $tr('Ollama (local)', 'Ollama(本地)', { de: 'Ollama (lokal)', fr: 'Ollama (local)' }) }}</option>
                    <option value="openai">{{ $tr('OpenAI-compatible', 'OpenAI 兼容', { de: 'OpenAI-kompatibel', fr: 'Compatible OpenAI' }) }}</option>
                  </select>
                </div>
              </div>
              <div class="field-row">
                <label class="field-label">{{ $tr('Model', '模型', { de: 'Modell', fr: 'Modèle' }) }}</label>
                <input
                  v-model="form.embedding.model_name"
                  class="field-input"
                  type="text"
                  :placeholder="$tr('e.g. openai/text-embedding-3-small', '例如 openai/text-embedding-3-small', { de: 'z. B. openai/text-embedding-3-small', fr: 'ex. openai/text-embedding-3-small' })"
                />
              </div>
            </div>

            <!-- Web Search -->
            <div class="advanced-group">
              <div class="advanced-group-title">{{ $tr('Web search (URL import + enrichment)', '网页搜索(URL 导入 + 丰富)', { de: 'Websuche (URL-Import + Anreicherung)', fr: 'Recherche web (import URL + enrichissement)' }) }}</div>
              <div class="field-row">
                <label class="field-label">{{ $tr('Model', '模型', { de: 'Modell', fr: 'Modèle' }) }}</label>
                <input
                  v-model="form.web_search_model"
                  class="field-input"
                  type="text"
                  :placeholder="$tr('e.g. google/gemini-2.0-flash-001:online', '例如 google/gemini-2.0-flash-001:online', { de: 'z. B. google/gemini-2.0-flash-001:online', fr: 'ex. google/gemini-2.0-flash-001:online' })"
                />
              </div>
            </div>

            <!-- SearXNG -->
            <div class="advanced-group">
              <div class="advanced-group-title">{{ $tr('SearXNG (real web search — works with any model)', 'SearXNG(真实网页搜索——适用于任何模型)', { de: 'SearXNG (echte Websuche — funktioniert mit jedem Modell)', fr: 'SearXNG (recherche web réelle — fonctionne avec tout modèle)' }) }}</div>
              <div class="field-row">
                <label class="field-label">{{ $tr('Instance URL', '实例地址', { de: 'Instanz-URL', fr: `URL de l'instance` }) }}</label>
                <input
                  v-model="form.searxng_base_url"
                  class="field-input"
                  type="text"
                  placeholder="https://sxng.example.org"
                />
              </div>
              <div class="field-row">
                <button
                  class="ai-retry"
                  :disabled="searxngTesting || !form.searxng_base_url"
                  @click="testSearxngFire"
                >
                  {{ searxngTesting ? $tr('Searching…', '搜索中…', { de: 'Wird gesucht…', fr: 'Recherche…' }) : $tr('Test search', '测试搜索', { de: 'Suche testen', fr: 'Tester la recherche' }) }}
                </button>
                <span v-if="searxngTestResult" class="webhook-test-result" :class="searxngTestResult.success ? 'ok' : 'fail'">
                  <template v-if="searxngTestResult.success">
                    ✓ {{ $tr('OK', '正常', { de: 'OK', fr: 'OK' }) }} ({{ searxngTestResult.latency_ms }}ms)
                  </template>
                  <template v-else>
                    ✗ {{ searxngTestResult.error || $tr('Failed', '失败', { de: 'Fehlgeschlagen', fr: 'Échec' }) }}
                  </template>
                </span>
              </div>
            </div>

            <!-- Firecrawl -->
            <div class="advanced-group">
              <div class="advanced-group-title">{{ $tr('Firecrawl (URL import scraping)', 'Firecrawl(URL 导入抓取)', { de: 'Firecrawl (URL-Import-Scraping)', fr: 'Firecrawl (scraping d’import URL)' }) }}</div>
              <div class="field-row">
                <label class="field-label">{{ $tr('Instance URL', '实例地址', { de: 'Instanz-URL', fr: `URL de l'instance` }) }}</label>
                <input
                  v-model="form.firecrawl.base_url"
                  class="field-input"
                  type="text"
                  placeholder="https://fc.example.org"
                />
              </div>
              <div class="field-row">
                <label class="field-label">{{ $tr('API key', 'API 密钥', { de: 'API-Schlüssel', fr: 'Clé API' }) }}</label>
                <input
                  v-model="form.firecrawl.api_key"
                  class="field-input"
                  type="password"
                  :placeholder="currentSettings.firecrawl?.has_api_key ? currentSettings.firecrawl.api_key_masked : $tr('not set', '未设置', { de: 'nicht gesetzt', fr: 'non défini' })"
                />
              </div>
            </div>
          </div>
        </section>

        <!-- Neo4j Configuration -->
        <section class="settings-section">
          <div class="section-header">
            <span class="section-label">{{ $tr('Graph Database (Neo4j)', '图数据库 (Neo4j)', { de: 'Graph-Datenbank (Neo4j)', fr: 'Base de données graphe (Neo4j)' }) }}</span>
          </div>

          <div class="field-row">
            <label class="field-label">{{ $tr('URI', '地址', { de: 'URI', fr: 'URI' }) }}</label>
            <input
              v-model="form.neo4j.uri"
              class="field-input"
              type="text"
              placeholder="bolt://localhost:7687"
            />
          </div>

          <div class="field-row">
            <label class="field-label">{{ $tr('User', '用户', { de: 'Benutzer', fr: 'Utilisateur' }) }}</label>
            <input
              v-model="form.neo4j.user"
              class="field-input"
              type="text"
              placeholder="neo4j"
            />
          </div>

          <div class="field-row">
            <label class="field-label">{{ $tr('Password', '密码', { de: 'Passwort', fr: 'Mot de passe' }) }}</label>
            <input
              v-model="form.neo4j.password"
              class="field-input"
              type="password"
              :placeholder="$tr('Leave blank to keep unchanged', '留空保持不变', { de: 'Leer lassen, um unverändert zu behalten', fr: 'Laissez vide pour ne pas modifier' })"
            />
          </div>
        </section>

        <!-- Outbound webhook · Slack / Discord / Zapier / n8n / custom -->
        <section class="settings-section ai-section">
          <div class="section-header">
            <span class="section-label">{{ $tr('Integrations · Webhook', '集成 · Webhook', { de: 'Integrationen · Webhook', fr: 'Intégrations · Webhook' }) }}</span>
            <div class="status-badge" :class="webhookSavedClass">
              <span class="badge-dot"></span>
              {{ webhookSavedText }}
            </div>
          </div>

          <div class="ai-intro">
            {{ $tr('POST a JSON summary to your URL the moment a simulation finishes — wires Slack, Discord, Zapier, Make, n8n, IFTTT, or any custom listener. Empty to disable. Payload includes scenario, final consensus, quality, and the share-card URL so links auto-unfurl.', '模拟结束时立即向你的 URL POST 一份 JSON 摘要 — 可对接 Slack、Discord、Zapier、Make、n8n、IFTTT 或任何自定义监听器。留空以禁用。负载包括情景、最终共识、质量,以及分享卡 URL 以便链接自动展开。', { de: 'Sendet beim Abschluss einer Simulation eine JSON-Zusammenfassung an deine URL — für Slack, Discord, Zapier, Make, n8n, IFTTT oder beliebige Listener. Leer lassen zum Deaktivieren. Enthält Szenario, Konsens, Qualität und Share-URL.', fr: `Envoie un résumé JSON à votre URL dès qu'une simulation se termine — branche Slack, Discord, Zapier, Make, n8n, IFTTT, ou tout autre listener custom. Vide pour désactiver. Le payload inclut scénario, consensus final, qualité, et URL de share-card pour que les liens s'auto-déploient.` }) }}
          </div>

          <div class="field-row">
            <label class="field-label">{{ $tr('Webhook URL', 'Webhook URL', { de: 'Webhook-URL', fr: 'URL du webhook' }) }}</label>
            <input
              v-model="form.integrations.webhook.url"
              class="field-input"
              type="text"
              :placeholder="webhookPlaceholder"
              autocomplete="off"
              spellcheck="false"
            />
            <div class="field-hint">
              {{ $tr('e.g.', '例如', { de: 'z. B.', fr: 'ex.' }) }}
              <code>https://hooks.slack.com/services/T0…/B0…/abc</code>
              {{ $tr('or any URL that accepts a POST.', '或任何接受 POST 的 URL。', { de: 'oder jede URL, die POST akzeptiert.', fr: 'ou toute URL qui accepte un POST.' }) }}
              {{ $tr('See', '参见', { de: 'Siehe', fr: 'Voir' }) }} <a href="https://github.com/aaronjmars/MiroShark/blob/main/docs/WEBHOOKS.md"
                     target="_blank" rel="noopener">{{ $tr('the webhook docs', 'Webhook 文档', { de: 'die Webhook-Dokumentation', fr: 'la doc du webhook' }) }}</a>
              {{ $tr('for the payload schema.', '了解负载结构。', { de: 'für das Payload-Schema.', fr: 'pour le schéma du payload.' }) }}
            </div>
          </div>

          <div class="field-row">
            <label class="field-label">{{ $tr('Public base URL', '公开基础 URL', { de: 'Öffentliche Basis-URL', fr: 'URL publique de base' }) }} <span class="field-label-optional">{{ $tr('(optional)', '(可选)', { de: '(optional)', fr: '(optionnel)' }) }}</span></label>
            <input
              v-model="form.integrations.webhook.public_base_url"
              class="field-input"
              type="text"
              placeholder="https://miroshark.app"
              autocomplete="off"
              spellcheck="false"
            />
            <div class="field-hint">
              {{ $tr('When set, the payload includes absolute', '设置后,负载将包含绝对的', { de: 'Wenn gesetzt, enthält der Payload absolute', fr: 'Quand défini, le payload inclut des' }) }} <code>share_url</code> +
              <code>share_card_url</code> {{ $tr('so Slack & Discord auto-unfurl with the simulation card. Leave blank for relative paths only.', '以便 Slack 与 Discord 用模拟卡片自动展开。留空则仅使用相对路径。', { de: 'damit Slack & Discord die Simulationskarte automatisch entfalten. Leer lassen für relative Pfade.', fr: 'pour que Slack & Discord auto-déploient la carte de simulation. Laissez vide pour les chemins relatifs uniquement.' }) }}
            </div>
          </div>

          <div class="field-row webhook-actions">
            <button
              class="ai-retry"
              :disabled="webhookTesting || !webhookCanTest"
              @click="testWebhookFire"
            >
              {{ webhookTesting ? $tr('Sending…', '发送中…', { de: 'Wird gesendet…', fr: 'Envoi…' }) : $tr('Send test event', '发送测试事件', { de: 'Testereignis senden', fr: 'Envoyer un événement test' }) }}
            </button>
            <span v-if="webhookTestResult" class="webhook-test-result" :class="webhookTestResult.success ? 'ok' : 'fail'">
              <template v-if="webhookTestResult.success">
                ✓ {{ $tr('Delivered', '已送达', { de: 'Zugestellt', fr: 'Livré' }) }} ({{ webhookTestResult.latency_ms }}ms)
              </template>
              <template v-else>
                ✗ {{ webhookTestResult.error || webhookTestResult.message || $tr('Failed', '失败', { de: 'Fehlgeschlagen', fr: 'Échec' }) }}
              </template>
            </span>
          </div>
        </section>

        <!-- AI Integration (MCP) -->
        <section class="settings-section ai-section">
          <div class="section-header">
            <span class="section-label">{{ $tr('AI Integration · MCP', 'AI 集成 · MCP', { de: 'AI-Integration · MCP', fr: 'Intégration IA · MCP' }) }}</span>
            <div class="status-badge" :class="mcpHealthClass">
              <span class="badge-dot"></span>
              {{ mcpHealthText }}
            </div>
          </div>

          <div class="ai-intro">
            {{ $tr(`Wire MiroShark's knowledge graph into Claude Desktop, Cursor, Windsurf, or Continue. Pick your client, paste the snippet, restart the editor.`, '将 MiroShark 的知识图谱接入 Claude Desktop、Cursor、Windsurf 或 Continue。选择你的客户端,粘贴代码片段,重启编辑器。', { de: 'Verbinde MiroSharks Wissensgraph mit Claude Desktop, Cursor, Windsurf oder Continue. Client auswählen, Snippet einfügen, Editor neustarten.', fr: `Branchez le graphe de connaissances de MiroShark dans Claude Desktop, Cursor, Windsurf ou Continue. Choisissez votre client, collez l'extrait, redémarrez l'éditeur.` }) }}
          </div>

          <div v-if="mcpLoading" class="ai-loading">{{ $tr('Loading MCP catalog…', '加载 MCP 目录…', { de: 'MCP-Katalog wird geladen…', fr: 'Chargement du catalogue MCP…' }) }}</div>
          <div v-else-if="mcpLoadError" class="ai-error">
            {{ mcpLoadError }}
            <button class="ai-retry" @click="loadMcpStatus">{{ $tr('Retry', '重试', { de: 'Erneut versuchen', fr: 'Réessayer' }) }}</button>
          </div>

          <div v-else-if="mcpStatus" class="ai-body">
            <!-- Health summary grid -->
            <div class="ai-summary">
              <div class="ai-summary-row">
                <span class="ai-summary-key">{{ $tr('Server file', '服务文件', { de: 'Server-Datei', fr: 'Fichier serveur' }) }}</span>
                <span class="ai-summary-val" :class="mcpStatus.paths.mcp_script_exists ? '' : 'setup-missing'">
                  {{ mcpStatus.paths.mcp_script_exists ? $tr('present', '存在', { de: 'vorhanden', fr: 'présent' }) : $tr('missing', '缺失', { de: 'fehlend', fr: 'manquant' }) }}
                </span>
              </div>
              <div class="ai-summary-row">
                <span class="ai-summary-key">{{ $tr('Tools exposed', '已暴露工具', { de: 'Verfügbare Tools', fr: 'Outils exposés' }) }}</span>
                <span class="ai-summary-val">{{ mcpStatus.tool_count }}</span>
              </div>
              <div class="ai-summary-row">
                <span class="ai-summary-key">Neo4j</span>
                <span class="ai-summary-val" :class="mcpStatus.neo4j.connected ? '' : 'setup-missing'">
                  {{ mcpStatus.neo4j.connected ? $tr('connected', '已连接', { de: 'verbunden', fr: 'connecté' }) : $tr('unreachable', '不可达', { de: 'nicht erreichbar', fr: 'inaccessible' }) }}
                </span>
              </div>
              <div class="ai-summary-row" v-if="mcpStatus.neo4j.connected">
                <span class="ai-summary-key">{{ $tr('Graphs available', '可用图谱', { de: 'Verfügbare Graphen', fr: 'Graphes disponibles' }) }}</span>
                <span class="ai-summary-val">
                  {{ mcpStatus.neo4j.graph_count ?? 0 }}
                  <span class="setup-aux" v-if="mcpStatus.neo4j.entity_count != null">
                    ({{ mcpStatus.neo4j.entity_count }} {{ $tr('entities', '个实体', { de: 'Entitäten', fr: 'entités' }) }})
                  </span>
                </span>
              </div>
              <div class="ai-summary-row" v-if="mcpStatus.neo4j.error">
                <span class="ai-summary-key">{{ $tr('Error', '错误', { de: 'Fehler', fr: 'Erreur' }) }}</span>
                <span class="ai-summary-val ai-error-text">{{ mcpStatus.neo4j.error }}</span>
              </div>
            </div>

            <!-- Client tabs -->
            <div class="ai-tabs" role="tablist">
              <button
                v-for="key in clientOrder"
                :key="key"
                class="ai-tab"
                :class="{ active: activeClient === key }"
                role="tab"
                :aria-selected="activeClient === key"
                @click="activeClient = key"
              >
                {{ mcpStatus.clients[key]?.label || key }}
              </button>
            </div>

            <!-- Active client snippet -->
            <div v-if="currentClient" class="ai-client">
              <div class="ai-client-file">
                <span class="ai-client-file-label">{{ $tr('Config file:', '配置文件:', { de: 'Konfigurationsdatei:', fr: 'Fichier de config :' }) }}</span>
                <code class="ai-client-file-path">{{ currentClient.file }}</code>
              </div>
              <div class="ai-snippet-wrap">
                <pre class="ai-snippet"><code>{{ formatJson(currentClient.config) }}</code></pre>
                <button
                  class="ai-copy-btn"
                  :class="{ ok: copyState === 'ok', fail: copyState === 'fail' }"
                  @click="copySnippet"
                >
                  {{ copyButtonLabel }}
                </button>
              </div>
              <div v-if="currentClient.notes" class="ai-client-notes">
                {{ currentClient.notes }}
              </div>
            </div>

            <!-- Tool catalog (collapsed by default) -->
            <button class="ai-tools-toggle" @click="toolsOpen = !toolsOpen">
              <span>{{ toolsOpen ? '▾' : '▸' }} {{ mcpStatus.tool_count }} {{ $tr('tools available', '个可用工具', { de: 'Tools verfügbar', fr: 'outils disponibles' }) }}</span>
            </button>
            <ul v-if="toolsOpen" class="ai-tools-list">
              <li v-for="t in mcpStatus.tools" :key="t.name" class="ai-tool">
                <code class="ai-tool-name">{{ t.name }}</code>
                <span class="ai-tool-desc">{{ t.description }}</span>
              </li>
            </ul>

            <div class="ai-docs-link">
              {{ $tr('Need a deeper walkthrough?', '需要更深入的指南?', { de: 'Brauchst du eine ausführlichere Anleitung?', fr: `Besoin d'un guide plus détaillé ?` }) }}
              <a :href="mcpStatus.docs_url" target="_blank" rel="noopener">{{ $tr('Read the full MCP guide →', '阅读完整的 MCP 指南 →', { de: 'Vollständigen MCP-Leitfaden lesen →', fr: 'Lire le guide MCP complet →' }) }}</a>
            </div>
          </div>
        </section>

        <!-- Footer -->
        <div class="modal-footer">
          <div v-if="saveError" class="save-error">{{ saveError }}</div>
          <div v-if="saveSuccess" class="save-success">✓ {{ $tr('Settings saved (runtime — edit .env to persist across restarts)', '设置已保存(运行时 — 编辑 .env 以在重启后保留)', { de: 'Einstellungen gespeichert (Laufzeit — .env bearbeiten, um nach Neustart zu erhalten)', fr: 'Paramètres enregistrés (runtime — modifiez .env pour persister entre redémarrages)' }) }}</div>
          <div class="footer-actions">
            <button class="cancel-btn" @click="$emit('close')">{{ $tr('Cancel', '取消', { de: 'Abbrechen', fr: 'Annuler' }) }}</button>
            <button class="save-btn" :disabled="saving" @click="saveSettings">
              <span v-if="saving">{{ $tr('Saving...', '保存中...', { de: 'Wird gespeichert...', fr: 'Enregistrement…' }) }}</span>
              <span v-else>{{ $tr('Save Settings →', '保存设置 →', { de: 'Einstellungen speichern →', fr: 'Enregistrer les paramètres →' }) }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { getSettings, updateSettings, testLlmConnection, testWebhook, testSearxng } from '../api/settings'
import { getMcpStatus } from '../api/mcp'
import { tr } from '../i18n'
import LocaleToggle from './LocaleToggle.vue'

const props = defineProps({
  open: { type: Boolean, required: true }
})

const emit = defineEmits(['close'])

// Current settings loaded from backend
const currentSettings = ref({})

// Form state
const form = reactive({
  preset: '',
  presetApiKey: '',
  llm: {
    provider: 'openai',
    base_url: '',
    model_name: '',
    api_key: '',
  },
  smart: { model_name: '' },
  ner: { model_name: '' },
  wonderwall: { model_name: '', base_url: '', api_key: '' },
  embedding: { provider: 'ollama', model_name: '' },
  web_search_model: '',
  searxng_base_url: '',
  firecrawl: { base_url: '', api_key: '' },
  neo4j: {
    uri: '',
    user: '',
    password: '',
  },
  integrations: {
    webhook: {
      url: '',
      public_base_url: '',
    },
  },
})

// UI state
const showKey = ref(false)
const saving = ref(false)
const saveError = ref('')
const saveSuccess = ref(false)
const testing = ref(false)
const testResult = ref(null)
const modelList = ref([])
const loadingModels = ref(false)
const modelLoadError = ref('')
const advancedOpen = ref(false)
const inheritMarker = tr('— inherits default —', '— 继承默认值 —', { de: '— übernimmt Standard —', fr: '— hérite de la valeur par défaut —' })

// Webhook integration state
const webhookTesting = ref(false)
const webhookTestResult = ref(null)

// SearXNG test state
const searxngTesting = ref(false)
const searxngTestResult = ref(null)

// MCP / AI Integration state
const mcpStatus = ref(null)
const mcpLoading = ref(false)
const mcpLoadError = ref('')
const clientOrder = ['claude_desktop', 'cursor', 'windsurf', 'continue', 'fallback_direct']
const activeClient = ref('claude_desktop')
const toolsOpen = ref(false)
const copyState = ref('') // '' | 'ok' | 'fail'

// Load current settings when panel opens
watch(() => props.open, async (isOpen) => {
  if (isOpen) {
    saveError.value = ''
    saveSuccess.value = false
    testResult.value = null
    webhookTestResult.value = null
    searxngTestResult.value = null
    form.preset = ''
    form.presetApiKey = ''
    copyState.value = ''
    await Promise.all([loadCurrentSettings(), loadMcpStatus()])
  }
})

const loadCurrentSettings = async () => {
  try {
    // Axios response interceptor already unwraps to the body, so `res`
    // is `{ success, data }` — not the raw axios response.
    const res = await getSettings()
    if (res?.success && res.data) {
      const d = res.data
      currentSettings.value = d
      form.llm.provider = d.llm.provider || 'openai'
      form.llm.base_url = d.llm.base_url || ''
      form.llm.model_name = d.llm.model_name || ''
      form.llm.api_key = '' // never pre-fill
      form.smart.model_name = d.smart?.model_name || ''
      form.ner.model_name = d.ner?.model_name || ''
      form.wonderwall.model_name = d.wonderwall?.model_name || ''
      form.wonderwall.base_url = d.wonderwall?.base_url || ''
      form.wonderwall.api_key = '' // never pre-fill
      form.embedding.provider = d.embedding?.provider || 'ollama'
      form.embedding.model_name = d.embedding?.model_name || ''
      form.web_search_model = d.web_search_model || ''
      form.searxng_base_url = d.searxng_base_url || ''
      form.firecrawl.base_url = d.firecrawl?.base_url || ''
      form.firecrawl.api_key = '' // never pre-fill
      form.neo4j.uri = d.neo4j?.uri || ''
      form.neo4j.user = d.neo4j?.user || ''
      form.neo4j.password = ''
      // Webhook URL is masked server-side — never round-trip the masked
      // form back as a value the user could accidentally save. Leave the
      // input blank when configured so editing is explicit.
      form.integrations.webhook.url = ''
      form.integrations.webhook.public_base_url = d.integrations?.webhook?.public_base_url || ''
    }
  } catch (_) {
    // Non-fatal
  }
}

const presetOptions = computed(() => currentSettings.value.available_presets || [])

// `local` preset doesn't need an API key — the cloud preset does.
const presetNeedsKey = computed(() =>
  form.preset === 'cheap'
)

// Whether current base URL is OpenRouter
const isOpenRouter = computed(() =>
  form.llm.base_url.includes('openrouter.ai')
)

// Model tiering thresholds (cost per 1M tokens, prompt side)
const MODEL_TIERS = [
  { label: 'Fast (< $0.50/M)', max: 0.5 },
  { label: 'Standard ($0.50–$5/M)', max: 5 },
  { label: 'Capable (> $5/M)', max: Infinity },
]

const modelTiers = computed(() => {
  if (modelList.value.length === 0) return []
  return MODEL_TIERS.map(tier => ({
    label: tier.label,
    models: modelList.value.filter(m => {
      const price = m.pricing?.prompt ? parseFloat(m.pricing.prompt) * 1_000_000 : 0
      return price <= tier.max && price > (tier === MODEL_TIERS[0] ? 0 : MODEL_TIERS[MODEL_TIERS.indexOf(tier) - 1].max)
    })
  })).filter(t => t.models.length > 0)
})

const loadOpenRouterModels = async () => {
  loadingModels.value = true
  modelLoadError.value = ''
  try {
    const res = await fetch('https://openrouter.ai/api/v1/models')
    const json = await res.json()
    if (json.data) {
      modelList.value = json.data
        .filter(m => m.id && m.name)
        .sort((a, b) => {
          const pa = parseFloat(a.pricing?.prompt || 0) * 1_000_000
          const pb = parseFloat(b.pricing?.prompt || 0) * 1_000_000
          return pa - pb
        })
    }
  } catch (_) {
    modelLoadError.value = tr('Could not load model list — check your network connection.', '无法加载模型列表 — 请检查网络连接。', { de: 'Modellliste konnte nicht geladen werden — bitte Netzwerkverbindung prüfen.', fr: 'Impossible de charger la liste des modèles — vérifiez votre connexion réseau.' })
  } finally {
    loadingModels.value = false
  }
}

const testConnection = async () => {
  testing.value = true
  testResult.value = null
  try {
    // Interceptor unwraps axios to the body directly.
    const res = await testLlmConnection()
    testResult.value = res
  } catch (e) {
    testResult.value = { success: false, error: e.message }
  } finally {
    testing.value = false
  }
}

const loadMcpStatus = async () => {
  mcpLoading.value = true
  mcpLoadError.value = ''
  try {
    // Axios interceptor unwraps to { success, data }.
    const res = await getMcpStatus()
    if (res?.success && res.data) {
      mcpStatus.value = res.data
    } else {
      mcpLoadError.value = res?.error || tr('MCP status unavailable', 'MCP 状态不可用', { de: 'MCP-Status nicht verfügbar', fr: 'Statut MCP indisponible' })
    }
  } catch (e) {
    mcpLoadError.value = e?.message || tr('MCP status request failed', 'MCP 状态请求失败', { de: 'MCP-Status-Anfrage fehlgeschlagen', fr: 'Échec de la requête de statut MCP' })
  } finally {
    mcpLoading.value = false
  }
}

const currentClient = computed(() => {
  if (!mcpStatus.value) return null
  return mcpStatus.value.clients?.[activeClient.value] || null
})

const mcpHealthClass = computed(() => {
  if (!mcpStatus.value) return 'idle'
  if (!mcpStatus.value.paths.mcp_script_exists) return 'fail'
  return mcpStatus.value.neo4j.connected ? 'ok' : 'fail'
})

const mcpHealthText = computed(() => {
  if (!mcpStatus.value) return tr('Loading', '加载中', { de: 'Wird geladen', fr: 'Chargement' })
  if (!mcpStatus.value.paths.mcp_script_exists) return tr('Server file missing', '服务文件缺失', { de: 'Server-Datei fehlt', fr: 'Fichier serveur manquant' })
  return mcpStatus.value.neo4j.connected ? tr('Ready', '就绪', { de: 'Bereit', fr: 'Prêt' }) : tr('Neo4j down', 'Neo4j 不可用', { de: 'Neo4j nicht erreichbar', fr: 'Neo4j injoignable' })
})

const formatJson = (obj) => JSON.stringify(obj, null, 2)

const copyButtonLabel = computed(() => {
  if (copyState.value === 'ok') return '✓ ' + tr('Copied', '已复制', { de: 'Kopiert', fr: 'Copié' })
  if (copyState.value === 'fail') return '✗ ' + tr('Copy failed', '复制失败', { de: 'Kopieren fehlgeschlagen', fr: 'Échec de la copie' })
  return tr('Copy snippet', '复制代码片段', { de: 'Snippet kopieren', fr: `Copier l'extrait` })
})

const copySnippet = async () => {
  if (!currentClient.value) return
  const text = formatJson(currentClient.value.config)
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      // Fallback for older / non-secure-context browsers.
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      if (!ok) throw new Error('execCommand copy returned false')
    }
    copyState.value = 'ok'
  } catch (_) {
    copyState.value = 'fail'
  } finally {
    setTimeout(() => { copyState.value = '' }, 2200)
  }
}

const testStatus = computed(() => {
  if (!testResult.value) return 'idle'
  return testResult.value.success ? 'ok' : 'fail'
})

const testStatusText = computed(() => {
  if (!testResult.value) return tr('Not tested', '未测试', { de: 'Nicht getestet', fr: 'Non testé' })
  return testResult.value.success ? tr('Connected', '已连接', { de: 'Verbunden', fr: 'Connecté' }) : tr('Failed', '失败', { de: 'Fehlgeschlagen', fr: 'Échec' })
})

const webhookConfigured = computed(() =>
  Boolean(currentSettings.value.integrations?.webhook?.configured)
)

const webhookSavedClass = computed(() => (webhookConfigured.value ? 'ok' : 'idle'))
const webhookSavedText = computed(() =>
  webhookConfigured.value ? tr('Configured', '已配置', { de: 'Konfiguriert', fr: 'Configuré' }) : tr('Not configured', '未配置', { de: 'Nicht konfiguriert', fr: 'Non configuré' })
)

const webhookPlaceholder = computed(() => {
  if (webhookConfigured.value) {
    const masked = currentSettings.value.integrations?.webhook?.url_masked
    return masked
      ? `${masked}${tr(' — leave blank to keep, type to replace', ' — 留空保留,输入以替换', { de: ' — leer lassen zum Behalten, eingeben zum Ersetzen', fr: ' — laissez vide pour garder, saisissez pour remplacer' })}`
      : tr('Leave blank to keep saved URL, type to replace', '留空保留已保存的 URL,输入以替换', { de: 'Leer lassen, um gespeicherte URL zu behalten, eingeben zum Ersetzen', fr: `Laissez vide pour conserver l'URL enregistrée, saisissez pour remplacer` })
  }
  return 'https://hooks.slack.com/services/T0…/B0…/abc'
})

// The button can fire when there's a typed URL OR a saved one to retry.
const webhookCanTest = computed(() =>
  Boolean(form.integrations.webhook.url?.trim()) || webhookConfigured.value
)

const testSearxngFire = async () => {
  searxngTesting.value = true
  searxngTestResult.value = null
  try {
    const res = await testSearxng(form.searxng_base_url?.trim() || '')
    searxngTestResult.value = res
  } catch (e) {
    searxngTestResult.value = { success: false, error: e?.message || tr('Network error', '网络错误', { de: 'Netzwerkfehler', fr: 'Erreur réseau' }) }
  } finally {
    searxngTesting.value = false
  }
}

const testWebhookFire = async () => {
  webhookTesting.value = true
  webhookTestResult.value = null
  try {
    const url = form.integrations.webhook.url?.trim() || ''
    const baseUrl = form.integrations.webhook.public_base_url?.trim() || ''
    const res = await testWebhook(url, baseUrl)
    webhookTestResult.value = res
  } catch (e) {
    webhookTestResult.value = { success: false, error: e?.message || tr('Network error', '网络错误', { de: 'Netzwerkfehler', fr: 'Erreur réseau' }) }
  } finally {
    webhookTesting.value = false
  }
}

const saveSettings = async () => {
  saving.value = true
  saveError.value = ''
  saveSuccess.value = false
  try {
    const payload = {}

    // Preset is applied server-side first; explicit field overrides apply on top.
    if (form.preset) {
      payload.preset = form.preset
      if (form.presetApiKey) payload.preset_api_key = form.presetApiKey
    }

    payload.llm = {
      provider: form.llm.provider,
      base_url: form.llm.base_url,
      model_name: form.llm.model_name,
    }
    if (form.llm.api_key) payload.llm.api_key = form.llm.api_key

    payload.smart = { model_name: form.smart.model_name }
    payload.ner = { model_name: form.ner.model_name }
    payload.wonderwall = {
      model_name: form.wonderwall.model_name,
      base_url: form.wonderwall.base_url,
    }
    if (form.wonderwall.api_key) payload.wonderwall.api_key = form.wonderwall.api_key
    payload.embedding = {
      provider: form.embedding.provider,
      model_name: form.embedding.model_name,
    }
    payload.web_search_model = form.web_search_model
    payload.searxng_base_url = form.searxng_base_url?.trim() || ''
    payload.firecrawl = { base_url: form.firecrawl.base_url?.trim() || '' }
    if (form.firecrawl.api_key) payload.firecrawl.api_key = form.firecrawl.api_key

    payload.neo4j = {
      uri: form.neo4j.uri,
      user: form.neo4j.user,
    }
    if (form.neo4j.password) payload.neo4j.password = form.neo4j.password

    // Webhook integration — only send `url` when the user actually typed
    // something (blank input means "keep what's saved"). The base URL is
    // always sent because clearing it should be a deliberate action.
    const wh = {}
    const typedUrl = form.integrations.webhook.url?.trim()
    if (typedUrl !== undefined && typedUrl !== '') {
      wh.url = typedUrl
    }
    wh.public_base_url = form.integrations.webhook.public_base_url?.trim() || ''
    payload.integrations = { webhook: wh }

    const res = await updateSettings(payload)
    if (res?.success && res.data) {
      saveSuccess.value = true
      currentSettings.value = res.data
      form.llm.api_key = ''
      form.presetApiKey = ''
      form.firecrawl.api_key = ''
      form.neo4j.password = ''
      // Reset the webhook URL input so the placeholder shows the new
      // masked value and we don't accidentally re-save the same string.
      form.integrations.webhook.url = ''
      setTimeout(() => { saveSuccess.value = false }, 4000)
    } else {
      saveError.value = res?.error || tr('Save failed', '保存失败', { de: 'Speichern fehlgeschlagen', fr: `Échec de l'enregistrement` })
    }
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
/* ── Modal Overlay ── */
.settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(5, 3, 10, 0.7);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fade-in 0.15s ease-out;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.settings-modal {
  background: linear-gradient(180deg, rgba(40, 30, 70, 0.95) 0%, rgba(18, 12, 38, 0.97) 100%);
  width: 580px;
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 80px);
  overflow-y: auto;
  border: 1px solid rgba(167, 139, 250, 0.3);
  border-radius: 1.25rem;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    0 30px 80px -20px rgba(0, 0, 0, 0.9),
    0 0 80px -20px rgba(139, 92, 246, 0.4);
  color: #f4f1ff;
  position: relative;
  animation: slide-in 0.2s ease-out;
  font-family: 'Geist', system-ui, -apple-system, sans-serif;
}

@keyframes slide-in {
  from { transform: translateY(-16px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* ── Header ── */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px;
  background: transparent;
  color: #f4f1ff;
  border-bottom: 1px solid rgba(167, 139, 250, 0.18);
}

.title-label {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #c4b5fd;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.close-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 9999px;
  background: linear-gradient(180deg, rgba(70, 55, 120, 0.5) 0%, rgba(20, 14, 42, 0.75) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(244, 241, 255, 0.7);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
  transition: color 180ms ease, border-color 180ms ease, transform 180ms ease;
}
.close-btn:hover {
  color: #ffffff;
  border-color: rgba(167, 139, 250, 0.55);
  transform: translateY(-1px);
}

/* ── Warning Stripe — now a calm metal rule ── */
.warning-stripe {
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

/* ── Sections ── */
.settings-section {
  padding: 22px;
  border-bottom: 2px solid rgba(244, 241, 255,0.08);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.section-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(244, 241, 255,0.4);
}

/* ── Current Setup grid ── */
.setup-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 2px dashed rgba(244, 241, 255,0.1);
  padding: 12px 14px;
  background: #1a0f3a;
}
.setup-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 12px;
  letter-spacing: 0.3px;
}
.setup-key {
  color: rgba(244, 241, 255,0.5);
  flex-shrink: 0;
}
.setup-val {
  color: #f4f1ff;
  font-weight: 700;
  text-align: right;
  overflow-wrap: anywhere;
}
.setup-aux {
  color: rgba(244, 241, 255,0.4);
  font-weight: 400;
  margin-left: 4px;
}
.setup-missing {
  color: #FF4444;
  font-weight: 400;
}

/* ── Status Badge ── */
.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.badge-dot {
  width: 7px;
  height: 7px;
  background: rgba(244, 241, 255,0.2);
  border-radius: 0;
}
.status-badge.ok .badge-dot { background: #c4b5fd; }
.status-badge.fail .badge-dot { background: #FF4444; }
.status-badge.ok { color: #c4b5fd; }
.status-badge.fail { color: #FF4444; }
.status-badge.idle { color: rgba(244, 241, 255,0.3); }

/* ── Form Fields ── */
.field-row {
  margin-bottom: 14px;
}

.field-label {
  display: block;
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(244, 241, 255,0.5);
  margin-bottom: 6px;
}

.field-input {
  width: 100%;
  border: 2px solid rgba(244, 241, 255,0.1);
  background: #1a0f3a;
  padding: 8px 11px;
  font-family: 'Geist Mono', monospace;
  font-size: 13px;
  color: #f4f1ff;
  outline: none;
  transition: border-color 0.1s;
  box-sizing: border-box;
}
.field-input:focus { border-color: #a78bfa; background: #110a26; }
.field-input::placeholder { color: rgba(244, 241, 255,0.3); }

.select-wrapper { position: relative; }
.field-select {
  width: 100%;
  border: 2px solid rgba(244, 241, 255,0.1);
  background: #1a0f3a;
  padding: 8px 11px;
  font-family: 'Geist Mono', monospace;
  font-size: 13px;
  color: #f4f1ff;
  outline: none;
  cursor: pointer;
  appearance: auto;
  transition: border-color 0.1s;
  box-sizing: border-box;
}
.field-select:focus { border-color: #a78bfa; }

/* ── Model input group ── */
.model-input-group {
  display: flex;
  gap: 6px;
}
.model-select-wrapper { flex: 1; min-width: 0; }

.load-models-btn {
  border: 2px solid rgba(244, 241, 255,0.1);
  background: #1a0f3a;
  padding: 8px 12px;
  font-family: 'Geist Mono', monospace;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.1s;
  flex-shrink: 0;
}
.load-models-btn:hover:not(:disabled) { border-color: #a78bfa; color: #a78bfa; }
.load-models-btn:disabled { opacity: 0.35; cursor: not-allowed; }

/* ── Key input group ── */
.key-input-group {
  display: flex;
  gap: 6px;
}
.key-input-group .field-input { flex: 1; }

.toggle-key-btn {
  border: 2px solid rgba(244, 241, 255,0.1);
  background: #1a0f3a;
  padding: 8px 12px;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.1s;
}
.toggle-key-btn:hover { border-color: #a78bfa; }

.field-hint {
  margin-top: 5px;
  font-size: 11px;
  color: rgba(244, 241, 255,0.4);
  letter-spacing: 0.5px;
}
.field-hint a { color: #a78bfa; text-decoration: underline; }

.field-error {
  margin-top: 5px;
  font-size: 11px;
  color: #FF4444;
}

/* ── Test row ── */
.test-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.test-btn {
  border: 1px solid rgba(167, 139, 250, 0.3);
  background: linear-gradient(180deg, rgba(50, 38, 86, 0.5) 0%, rgba(18, 12, 38, 0.7) 100%);
  color: rgba(244, 241, 255, 0.88);
  padding: 9px 18px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}
.test-btn:hover:not(:disabled) {
  border-color: rgba(167, 139, 250, 0.7);
  color: #ffffff;
  transform: translateY(-1px);
  box-shadow: 0 10px 24px -12px rgba(139, 92, 246, 0.6);
}
.test-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.test-result {
  font-size: 12px;
  letter-spacing: 1px;
}
.test-result.ok { color: #c4b5fd; }
.test-result.fail { color: #FF4444; }

/* ── Advanced ── */
.advanced-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  background: transparent;
  border: none;
  padding: 0 0 10px 0;
  cursor: pointer;
  font-family: 'Geist Mono', monospace;
}
.chevron {
  font-size: 16px;
  color: rgba(244, 241, 255,0.4);
  line-height: 1;
}
.advanced-body {
  margin-top: 4px;
}
.advanced-hint {
  font-size: 11px;
  color: rgba(244, 241, 255,0.4);
  margin-bottom: 12px;
  letter-spacing: 0.5px;
}
.advanced-group {
  padding: 10px 0;
  border-top: 1px dashed rgba(244, 241, 255,0.08);
}
.advanced-group:first-child { border-top: none; padding-top: 0; }
.advanced-group-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #f4f1ff;
  margin-bottom: 10px;
}

/* ── Footer ── */
.modal-footer {
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.save-error {
  font-size: 12px;
  color: #FF4444;
  letter-spacing: 0.5px;
}

.save-success {
  font-size: 12px;
  color: #c4b5fd;
  letter-spacing: 1px;
}

.cancel-btn {
  border: 2px solid rgba(244, 241, 255,0.1);
  background: transparent;
  padding: 10px 20px;
  font-family: 'Geist Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  color: rgba(244, 241, 255,0.5);
  transition: all 0.1s;
}
.cancel-btn:hover { border-color: rgba(244, 241, 255,0.3); color: #f4f1ff; }

.save-btn {
  border: 2px solid #f4f1ff;
  background: #f4f1ff;
  color: #110a26;
  padding: 10px 20px;
  font-family: 'Geist Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.15s;
}
.save-btn:hover:not(:disabled) { background: #a78bfa; border-color: #a78bfa; }
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Webhook integration row ── */
.webhook-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.webhook-test-result {
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.5px;
}

.webhook-test-result.ok { color: #15803D; }
.webhook-test-result.fail { color: #FF4444; }

.field-label-optional {
  color: rgba(244, 241, 255,0.4);
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  font-size: 11px;
}

/* ── AI Integration (MCP) ── */
.ai-section {
  background: #1a0f3a;
}

.ai-intro {
  font-size: 12px;
  line-height: 1.5;
  color: rgba(244, 241, 255,0.65);
  margin-bottom: 14px;
}

.ai-loading,
.ai-error {
  font-size: 12px;
  padding: 12px 14px;
  border: 2px dashed rgba(244, 241, 255,0.1);
  background: #110a26;
}

.ai-error {
  color: #FF4444;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.ai-retry {
  background: #f4f1ff;
  color: #110a26;
  border: none;
  padding: 6px 12px;
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
}

.ai-summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border: 2px dashed rgba(244, 241, 255,0.1);
  padding: 12px 14px;
  background: #110a26;
  margin-bottom: 14px;
}

.ai-summary-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 12px;
}

.ai-summary-key {
  color: rgba(244, 241, 255,0.5);
  flex-shrink: 0;
}

.ai-summary-val {
  color: #f4f1ff;
  font-weight: 700;
  text-align: right;
  overflow-wrap: anywhere;
}

.ai-error-text {
  color: #FF4444;
  font-weight: 400;
  font-size: 11px;
}

.ai-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 0;
  border-bottom: 2px solid rgba(244, 241, 255,0.08);
}

.ai-tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  padding: 8px 12px;
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(244, 241, 255,0.45);
  cursor: pointer;
  transition: color 0.1s, border-color 0.1s;
}

.ai-tab:hover { color: #f4f1ff; }

.ai-tab.active {
  color: #f4f1ff;
  border-bottom-color: #a78bfa;
}

.ai-client {
  padding-top: 14px;
}

.ai-client-file {
  font-size: 11px;
  color: rgba(244, 241, 255,0.55);
  margin-bottom: 8px;
  overflow-wrap: anywhere;
}

.ai-client-file-label {
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-right: 4px;
}

.ai-client-file-path {
  font-family: 'Geist Mono', monospace;
  color: #f4f1ff;
  background: #110a26;
  padding: 1px 5px;
  border: 1px solid rgba(244, 241, 255,0.08);
}

.ai-snippet-wrap {
  position: relative;
}

.ai-snippet {
  background: #f4f1ff;
  color: #110a26;
  padding: 14px 16px;
  margin: 0;
  font-family: 'Geist Mono', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.45;
  overflow-x: auto;
  white-space: pre;
  border: 2px solid #f4f1ff;
}

.ai-snippet code {
  font: inherit;
  color: inherit;
}

.ai-copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: #110a26;
  color: #f4f1ff;
  border: 1px solid rgba(250,250,250,0.2);
  padding: 4px 10px;
  font-family: 'Geist Mono', monospace;
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  transition: background 0.1s, color 0.1s;
}

.ai-copy-btn:hover { background: #a78bfa; color: #110a26; }
.ai-copy-btn.ok { background: #c4b5fd; color: #110a26; }
.ai-copy-btn.fail { background: #FF4444; color: #110a26; }

.ai-client-notes {
  font-size: 11px;
  color: rgba(244, 241, 255,0.55);
  margin-top: 8px;
  line-height: 1.5;
}

.ai-tools-toggle {
  display: block;
  width: 100%;
  background: none;
  border: 2px dashed rgba(244, 241, 255,0.1);
  padding: 8px 12px;
  margin-top: 14px;
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(244, 241, 255,0.55);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.1s, color 0.1s;
}

.ai-tools-toggle:hover {
  border-color: rgba(244, 241, 255,0.3);
  color: #f4f1ff;
}

.ai-tools-list {
  list-style: none;
  padding: 12px 14px;
  margin: 6px 0 0 0;
  background: #110a26;
  border: 2px dashed rgba(244, 241, 255,0.1);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-tool {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 12px;
  font-size: 11px;
  line-height: 1.5;
}

.ai-tool-name {
  color: #a78bfa;
  font-weight: 700;
  font-family: 'Geist Mono', monospace;
}

.ai-tool-desc {
  color: rgba(244, 241, 255,0.7);
  overflow-wrap: anywhere;
}

.ai-docs-link {
  font-size: 11px;
  color: rgba(244, 241, 255,0.55);
  margin-top: 14px;
  text-align: right;
}

.ai-docs-link a {
  color: #f4f1ff;
  font-weight: 700;
  text-decoration: none;
  border-bottom: 1px solid #a78bfa;
}

.ai-docs-link a:hover { color: #a78bfa; }

@media (max-width: 480px) {
  .ai-tool {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}
</style>
