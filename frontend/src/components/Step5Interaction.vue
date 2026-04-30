<template>
  <div class="interaction-panel">
    <!-- Main Split Layout -->
    <div class="main-split-layout">
      <!-- LEFT PANEL: Report Style -->
      <div class="left-panel report-style" ref="leftPanel">
        <div v-if="reportOutline" class="report-content-wrapper">
          <!-- Report Header -->
          <div class="report-header-block">
            <div class="report-meta">
              <span class="report-tag">{{ $tr('Prediction Report', '预测报告') }}</span>
              <span class="report-id">ID: {{ reportId || 'REF-2024-X92' }}</span>
            </div>
            <h1 class="main-title">{{ reportOutline.title }}</h1>
            <p class="sub-title">{{ reportOutline.summary }}</p>
            <div class="header-divider"></div>
          </div>

          <!-- Sections List -->
          <div class="sections-list">
            <div 
              v-for="(section, idx) in reportOutline.sections" 
              :key="idx"
              class="report-section-item"
              :class="{ 
                'is-active': currentSectionIndex === idx + 1,
                'is-completed': isSectionCompleted(idx + 1),
                'is-pending': !isSectionCompleted(idx + 1) && currentSectionIndex !== idx + 1
              }"
            >
              <div class="section-header-row" @click="toggleSectionCollapse(idx)" :class="{ 'clickable': isSectionCompleted(idx + 1) }">
                <span class="section-number">{{ String(idx + 1).padStart(2, '0') }}</span>
                <h3 class="section-title">{{ section.title }}</h3>
                <svg 
                  v-if="isSectionCompleted(idx + 1)" 
                  class="collapse-icon" 
                  :class="{ 'is-collapsed': collapsedSections.has(idx) }"
                  viewBox="0 0 24 24" 
                  width="20" 
                  height="20" 
                  fill="none" 
                  stroke="currentColor" 
                  stroke-width="2"
                >
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </div>
              
              <div class="section-body" v-show="!collapsedSections.has(idx)">
                <!-- Completed Content -->
                <div v-if="generatedSections[idx + 1]" class="generated-content" v-html="renderMarkdown(generatedSections[idx + 1], { stripLeadingH2: true })"></div>
                
                <!-- Loading State -->
                <div v-else-if="currentSectionIndex === idx + 1" class="loading-state">
                  <div class="loading-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <circle cx="12" cy="12" r="10" stroke-width="4" stroke="#E5E7EB"></circle>
                      <path d="M12 2a10 10 0 0 1 10 10" stroke-width="4" stroke="#4B5563" stroke-linecap="round"></path>
                    </svg>
                  </div>
                  <span class="loading-text">{{ $tr('Generating', '正在生成') }} {{ section.title }}...</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Waiting State -->
        <div v-if="!reportOutline" class="waiting-placeholder">
          <div class="waiting-animation">
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
          </div>
          <span class="waiting-text">{{ $tr('Waiting for Report Agent...', '等待报告智能体...') }}</span>
        </div>
      </div>

      <!-- RIGHT PANEL: Interaction Interface -->
      <div class="right-panel" ref="rightPanel">
        <!-- Unified Action Bar - Professional Design -->
        <div class="action-bar">
        <div class="action-bar-header">
          <svg class="action-bar-icon" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <div class="action-bar-text">
            <span class="action-bar-title">{{ $tr('Interactive Tools', '交互工具') }}</span>
            <span class="action-bar-subtitle mono">{{ profiles.length }} {{ $tr('personas available', '个可用人设') }}</span>
          </div>
        </div>
          <div class="action-bar-tabs">
            <button 
              class="tab-pill"
              :class="{ active: activeTab === 'chat' && chatTarget === 'report_agent' }"
              @click="selectReportAgentChat"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
              </svg>
              <span>{{ $tr('Chat with Report Agent', '与报告智能体对话') }}</span>
            </button>
            <div class="agent-dropdown" v-if="profiles.length > 0">
              <button 
                class="tab-pill agent-pill"
                :class="{ active: activeTab === 'chat' && chatTarget === 'agent' }"
                @click="toggleAgentDropdown"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
                <span>{{ selectedAgent ? selectedAgent.username : $tr('Persona Chat', '人设对话') }}</span>
                <svg class="dropdown-arrow" :class="{ open: showAgentDropdown }" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
              <div v-if="showAgentDropdown" class="dropdown-menu">
                <div class="dropdown-header">{{ $tr('Select Chat Target', '选择对话对象') }}</div>
                <div 
                  v-for="(agent, idx) in profiles" 
                  :key="idx"
                  class="dropdown-item"
                  @click="selectAgent(agent, idx)"
                >
                  <div class="agent-avatar">{{ (agent.username || 'A')[0] }}</div>
                  <div class="agent-info">
                    <span class="agent-name">{{ agent.username }}</span>
                    <span class="agent-role">{{ agent.profession || $tr('Unknown Profession', '未知职业') }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="tab-divider"></div>
            <button 
              class="tab-pill survey-pill"
              :class="{ active: activeTab === 'survey' }"
              @click="selectSurveyTab"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 11l3 3L22 4"></path>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              <span>{{ $tr('Group Questions', '群组提问') }}</span>
            </button>
          </div>
        </div>

        <!-- Chat Mode -->
        <div v-if="activeTab === 'chat'" class="chat-container">

          <!-- Report Agent Tools Card -->
          <div v-if="chatTarget === 'report_agent'" class="report-agent-tools-card">
            <div class="tools-card-header">
              <div class="tools-card-avatar">R</div>
              <div class="tools-card-info">
                <div class="tools-card-name">{{ $tr('Report Agent - Chat', '报告智能体 - 对话') }}</div>
                <div class="tools-card-subtitle">{{ $tr('Quick chat version of the report generation agent. Can call 4 professional tools. Has complete MiroShark memory', '报告生成智能体的快速对话版本。可调用 4 个专业工具,具备完整的 MiroShark 记忆') }}</div>
              </div>
              <button class="tools-card-toggle" @click="showToolsDetail = !showToolsDetail">
                <svg :class="{ 'is-expanded': showToolsDetail }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>
            <div v-if="showToolsDetail" class="tools-card-body">
              <div class="tools-grid">
                <div class="tool-item tool-purple">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.5V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.5A7 7 0 0 0 12 2z"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $tr('InsightForge Deep Attribution', 'InsightForge 深度归因') }}</div>
                    <div class="tool-desc">{{ $tr('Aligns real-world seed data with simulation environment state, combining Global/Local Memory mechanisms to provide cross-temporal deep attribution analysis', '将真实世界种子数据与模拟环境状态对齐,结合全局/局部记忆机制提供跨时序深度归因分析') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-blue">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $tr('PanoramaSearch Panoramic Tracking', 'PanoramaSearch 全景追踪') }}</div>
                    <div class="tool-desc">{{ $tr('Graph-based breadth traversal algorithm that reconstructs event propagation paths and captures the full topology of information flow', '基于图的广度遍历算法,重建事件传播路径并捕捉信息流的完整拓扑结构') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-orange">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $tr('QuickSearch Quick Retrieval', 'QuickSearch 快速检索') }}</div>
                    <div class="tool-desc">{{ $tr('GraphRAG-based instant query interface with optimized indexing efficiency for quickly extracting specific node attributes and discrete facts', '基于 GraphRAG 的即时查询接口,优化索引效率,快速提取特定节点属性和离散事实') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-green">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                      <circle cx="9" cy="7" r="4"></circle>
                      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $tr('InterviewSubAgent Virtual Interview', 'InterviewSubAgent 虚拟访谈') }}</div>
                    <div class="tool-desc">{{ $tr('Autonomous interviews that conduct parallel multi-round dialogues with individuals in the simulated world, collecting unstructured opinion data and psychological states', '自主访谈,与模拟世界中的个体进行并行多轮对话,采集非结构化的观点数据与心理状态') }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Agent Profile Card -->
          <div v-if="chatTarget === 'agent' && selectedAgent" class="agent-profile-card">
            <div class="profile-card-header">
              <div class="profile-card-avatar clickable" @click="openProfilePopup(selectedAgent)">{{ (selectedAgent.username || 'A')[0] }}</div>
              <div class="profile-card-info clickable" @click="openProfilePopup(selectedAgent)">
                <div class="profile-card-name">{{ selectedAgent.username }}</div>
                <div class="profile-card-meta">
                  <span v-if="selectedAgent.name" class="profile-card-handle">@{{ selectedAgent.name }}</span>
                  <span class="profile-card-profession">{{ selectedAgent.profession || $tr('Unknown Profession', '未知职业') }}</span>
                </div>
              </div>
              <button class="profile-card-toggle" @click="showFullProfile = !showFullProfile">
                <svg :class="{ 'is-expanded': showFullProfile }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>
            <div v-if="showFullProfile && selectedAgent.bio" class="profile-card-body">
              <div class="profile-card-bio">
                <div class="profile-card-label">{{ $tr('Bio', '简介') }}</div>
                <p>{{ selectedAgent.bio }}</p>
              </div>
            </div>
          </div>

          <!-- Chat Messages -->
          <div class="chat-messages" ref="chatMessages">
            <div v-if="chatHistory.length === 0" class="chat-empty">
              <div class="empty-icon">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
              </div>
              <p class="empty-text">
                {{ chatTarget === 'report_agent' ? $tr('Chat with Report Agent to explore report details', '与报告智能体对话,探索报告详情') : $tr('Chat with simulated individuals to understand their perspectives', '与模拟个体对话,了解他们的观点') }}
              </p>
            </div>
            <div 
              v-for="(msg, idx) in chatHistory" 
              :key="idx"
              class="chat-message"
              :class="msg.role"
            >
              <div class="message-avatar">
                <span v-if="msg.role === 'user'">U</span>
                <span v-else>{{ msg.role === 'assistant' && chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}</span>
              </div>
              <div class="message-content">
                <div class="message-header">
                  <span class="sender-name">
                    {{ msg.role === 'user' ? $tr('You', '你') : (chatTarget === 'report_agent' ? $tr('Report Agent', '报告智能体') : (selectedAgent?.username || $tr('Agent', '智能体'))) }}
                  </span>
                  <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
                </div>
                <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>
            <div v-if="isSending" class="chat-message assistant">
              <div class="message-avatar">
                <span>{{ chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}</span>
              </div>
              <div class="message-content">
                <div class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          </div>

          <!-- Chat Input -->
          <div class="chat-input-area">
            <textarea 
              v-model="chatInput"
              class="chat-input"
              :placeholder="$tr('Enter your question...', '请输入你的问题...')"
              @keydown.enter.exact.prevent="sendMessage"
              :disabled="isSending || (!selectedAgent && chatTarget === 'agent')"
              rows="1"
              ref="chatInputRef"
            ></textarea>
            <button 
              class="send-btn"
              @click="sendMessage"
              :disabled="!chatInput.trim() || isSending || (!selectedAgent && chatTarget === 'agent')"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>

        <!-- Survey Mode -->
        <div v-if="activeTab === 'survey'" class="survey-container">
          <!-- Survey Setup -->
          <div class="survey-setup">
            <div class="setup-section">
              <div class="section-header section-header-toggle" @click="showPersonaSection = !showPersonaSection">
                <div class="section-header-left">
                  <svg :class="['toggle-chevron', { expanded: showPersonaSection }]" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="9 18 15 12 9 6"></polyline>
                  </svg>
                  <span class="section-title">{{ $tr('Select Persona', '选择人设') }}</span>
                </div>
                <span class="selection-count">{{ $tr('Selected', '已选') }} {{ selectedAgents.size }} / {{ profiles.length }}</span>
              </div>
              <div v-show="showPersonaSection" class="agents-grid">
                <label
                  v-for="(agent, idx) in profiles"
                  :key="idx"
                  class="agent-checkbox"
                  :class="{ checked: selectedAgents.has(idx) }"
                >
                  <input
                    type="checkbox"
                    :checked="selectedAgents.has(idx)"
                    @change="toggleAgentSelection(idx)"
                  >
                  <div class="checkbox-avatar">{{ (agent.username || 'A')[0] }}</div>
                  <div class="checkbox-info">
                    <span class="checkbox-name">{{ agent.username }}</span>
                    <span class="checkbox-role">{{ agent.profession || $tr('Unknown Profession', '未知职业') }}</span>
                  </div>
                  <div class="checkbox-indicator">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  </div>
                </label>
              </div>
              <div v-show="showPersonaSection" class="selection-actions">
                <button class="action-link" @click="selectAllAgents">{{ $tr('Select All', '全选') }}</button>
                <span class="action-divider">|</span>
                <button class="action-link" @click="clearAgentSelection">{{ $tr('Clear', '清空') }}</button>
              </div>
            </div>

            <div class="setup-section">
              <div class="section-header">
                <span class="section-title">{{ $tr('Persona Question', '人设问题') }}</span>
              </div>
              <textarea
                v-model="surveyQuestion"
                class="survey-input"
                :placeholder="$tr('Enter the question you want to ask all selected targets...', '输入你想向所有选中对象提出的问题...')"
                rows="3"
              ></textarea>
            </div>

            <button 
              class="survey-submit-btn"
              :disabled="selectedAgents.size === 0 || !surveyQuestion.trim() || isSurveying"
              @click="submitSurvey"
            >
              <span v-if="isSurveying" class="loading-spinner"></span>
              <span v-else>{{ $tr('Send Question', '发送问题') }}</span>
            </button>
          </div>

          <!-- Results -->
          <div v-if="surveyResults.length > 0" class="survey-results">
            <div class="results-header">
              <span class="results-title">{{ $tr('Results', '结果') }}</span>
              <span class="results-count">{{ surveyResults.length }} {{ $tr('responses', '条回复') }}</span>
            </div>
            <div class="results-list">
              <div 
                v-for="(result, idx) in surveyResults" 
                :key="idx"
                class="result-card"
              >
                <div class="result-header">
                  <div class="result-avatar">{{ (result.agent_name || 'A')[0] }}</div>
                  <div class="result-info">
                    <span class="result-name">{{ result.agent_name }}</span>
                    <span class="result-role">{{ result.profession || $tr('Unknown Profession', '未知职业') }}</span>
                  </div>
                </div>
                <div class="result-question">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                  </svg>
                  <span>{{ result.question }}</span>
                </div>
                <div class="result-answer" v-html="renderMarkdown(result.answer)"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Profile Popup Modal -->
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showProfilePopup && profilePopupAgent" class="profile-popup-overlay" @click.self="closeProfilePopup">
        <div class="profile-popup">
          <div class="profile-popup-header">
            <div class="profile-popup-avatar">{{ (profilePopupAgent.username || 'A')[0] }}</div>
            <div class="profile-popup-info">
              <div class="profile-popup-name">{{ profilePopupAgent.username }}</div>
              <div class="profile-popup-meta">{{ profilePopupAgent.profession || '' }}</div>
            </div>
            <button class="profile-popup-close" @click="closeProfilePopup">&times;</button>
          </div>

          <div class="profile-popup-details">
            <div class="profile-popup-row" v-if="profilePopupAgent.bio">
              <span class="popup-label">{{ $tr('Bio', '简介') }}</span>
              <span class="popup-value">{{ profilePopupAgent.bio }}</span>
            </div>
            <div class="profile-popup-stats">
              <span v-if="profilePopupAgent.age" class="popup-stat">{{ profilePopupAgent.age }}{{ $tr('y', '岁') }}</span>
              <span v-if="profilePopupAgent.gender" class="popup-stat">{{ profilePopupAgent.gender }}</span>
              <span v-if="profilePopupAgent.mbti" class="popup-stat">{{ profilePopupAgent.mbti }}</span>
              <span v-if="profilePopupAgent.country" class="popup-stat">{{ profilePopupAgent.country }}</span>
            </div>
            <div class="profile-popup-row" v-if="profilePopupAgent.persona">
              <span class="popup-label" @click="showFullPersona = !showFullPersona" style="cursor:pointer">{{ $tr('Persona', '人设') }} {{ showFullPersona ? '▼' : '▶' }}</span>
              <span class="popup-value popup-persona" :class="{ clamped: !showFullPersona }">{{ profilePopupAgent.persona }}</span>
            </div>
          </div>

          <div class="profile-popup-activity">
            <div class="popup-section-title">{{ $tr('Simulation Activity', '模拟活动') }} ({{ profilePopupActions.length }})</div>
            <div v-if="profilePopupLoading" class="popup-loading">{{ $tr('Loading...', '加载中...') }}</div>
            <div v-else-if="profilePopupActions.length === 0" class="popup-empty">{{ $tr('No activity recorded', '没有活动记录') }}</div>
            <div v-else class="popup-actions-list">
              <div
                v-for="(action, i) in profilePopupActions"
                :key="i"
                class="popup-action-item"
                :class="{ expanded: expandedActions.has(i) }"
                @click="toggleAction(i)"
              >
                <div class="popup-action-header">
                  <span class="popup-action-badge" :class="'type-' + (action.action_type || '').toLowerCase()">{{ getActionLabel(action.action_type) }}</span>
                  <span class="popup-action-round">R{{ action.round_num }}</span>
                  <span class="popup-action-preview" v-if="action.action_args?.content">{{ action.action_args.content }}</span>
                  <span class="popup-action-preview" v-else-if="action.action_args?.quote_content">{{ action.action_args.quote_content }}</span>
                  <span class="popup-action-preview" v-else-if="action.action_args?.post_content">"{{ action.action_args.post_content }}"</span>
                  <span class="popup-action-preview" v-else-if="action.action_args?.target_user_name">@{{ action.action_args.target_user_name }}</span>
                </div>
                <div v-if="expandedActions.has(i)" class="popup-action-full">
                  <p v-if="action.action_args?.content">{{ action.action_args.content }}</p>
                  <p v-if="action.action_args?.quote_content"><strong>{{ $tr('Quote:', '引用:') }}</strong> {{ action.action_args.quote_content }}</p>
                  <p v-if="action.action_args?.post_content"><strong>{{ $tr('Original:', '原文:') }}</strong> {{ action.action_args.post_content }}</p>
                  <p v-if="action.action_args?.original_content"><strong>{{ $tr('Ref:', '引用:') }}</strong> {{ action.action_args.original_content }}</p>
                  <p v-if="action.action_args?.target_user_name"><strong>{{ $tr('Target:', '对象:') }}</strong> @{{ action.action_args.target_user_name }}</p>
                  <p v-if="action.action_args?.query"><strong>{{ $tr('Query:', '查询:') }}</strong> {{ action.action_args.query }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { chatWithReport, getReport, getAgentLog } from '../api/report'
import { interviewAgents, getSimulationProfilesRealtime, getSimulationActions } from '../api/simulation'
import { renderMarkdown } from '../utils/markdown'
import { tr } from '../i18n'

const props = defineProps({
  reportId: String,
  simulationId: String
})

const emit = defineEmits(['add-log', 'update-status'])

// State
const activeTab = ref('chat')
const chatTarget = ref('report_agent')
const showAgentDropdown = ref(false)
const dropdownMenuRef = ref(null)
const dropdownStyle = ref({})
const showProfilePopup = ref(false)
const profilePopupAgent = ref(null)
const profilePopupActions = ref([])
const profilePopupLoading = ref(false)
const showFullPersona = ref(false)
const showPersonaSection = ref(true)
const expandedActions = ref(new Set())

const toggleAction = (i) => {
  const s = new Set(expandedActions.value)
  if (s.has(i)) s.delete(i); else s.add(i)
  expandedActions.value = s
}

const openProfilePopup = async (agent) => {
  profilePopupAgent.value = agent
  profilePopupActions.value = []
  showFullPersona.value = false
  expandedActions.value = new Set()
  showProfilePopup.value = true
  profilePopupLoading.value = true
  try {
    const res = await getSimulationActions(props.simulationId, { agent_id: agent.user_id, limit: 200 })
    if (res.success && res.data) {
      profilePopupActions.value = res.data.actions || res.data || []
    }
  } catch (err) {
    console.warn('Failed to load agent actions:', err)
  } finally {
    profilePopupLoading.value = false
  }
}

const closeProfilePopup = () => {
  showProfilePopup.value = false
  profilePopupAgent.value = null
  profilePopupActions.value = []
}

const getActionLabel = (type) => {
  const labels = {
    'CREATE_POST': 'POST', 'REPOST': 'REPOST', 'LIKE_POST': 'LIKE',
    'CREATE_COMMENT': 'COMMENT', 'QUOTE_POST': 'QUOTE', 'FOLLOW': 'FOLLOW',
    'DO_NOTHING': 'IDLE', 'SEARCH_POSTS': 'SEARCH',
    'UPVOTE_POST': 'UPVOTE', 'DOWNVOTE_POST': 'DOWNVOTE'
  }
  return labels[type] || type
}
const selectedAgent = ref(null)
const selectedAgentIndex = ref(null)
const showFullProfile = ref(true)
const showToolsDetail = ref(true)

// Chat State
const chatInput = ref('')
const chatHistory = ref([])
const chatHistoryCache = ref({}) // Cache all chat records: { 'report_agent': [], 'agent_0': [], 'agent_1': [], ... }
const isSending = ref(false)
const chatMessages = ref(null)
const chatInputRef = ref(null)

// Survey State
const selectedAgents = ref(new Set())
const surveyQuestion = ref('')
const surveyResults = ref([])
const isSurveying = ref(false)

// Report Data
const reportOutline = ref(null)
const generatedSections = ref({})
const collapsedSections = ref(new Set())
const currentSectionIndex = ref(null)
const profiles = ref([])

// Helper Methods
const isSectionCompleted = (sectionIndex) => {
  return !!generatedSections.value[sectionIndex]
}

// Refs
const leftPanel = ref(null)
const rightPanel = ref(null)

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

const toggleSectionCollapse = (idx) => {
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(collapsedSections.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  collapsedSections.value = newSet
}

const selectChatTarget = (target) => {
  chatTarget.value = target
  if (target === 'report_agent') {
    showAgentDropdown.value = false
  }
}

// Save current chat records to cache
const saveChatHistory = () => {
  if (chatHistory.value.length === 0) return
  
  if (chatTarget.value === 'report_agent') {
    chatHistoryCache.value['report_agent'] = [...chatHistory.value]
  } else if (selectedAgentIndex.value !== null) {
    chatHistoryCache.value[`agent_${selectedAgentIndex.value}`] = [...chatHistory.value]
  }
}

const selectReportAgentChat = () => {
  // Save current chat records
  saveChatHistory()

  activeTab.value = 'chat'
  chatTarget.value = 'report_agent'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false

  // Restore Report Agent chat records
  chatHistory.value = chatHistoryCache.value['report_agent'] || []
}

const selectSurveyTab = () => {
  activeTab.value = 'survey'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false
}

const toggleAgentDropdown = () => {
  showAgentDropdown.value = !showAgentDropdown.value
  if (showAgentDropdown.value) {
    activeTab.value = 'chat'
    chatTarget.value = 'agent'
  }
}

const selectAgent = (agent, idx) => {
  // Save current chat records
  saveChatHistory()

  selectedAgent.value = agent
  selectedAgentIndex.value = idx
  chatTarget.value = 'agent'
  showAgentDropdown.value = false

  // Restore this Agent's chat records
  chatHistory.value = chatHistoryCache.value[`agent_${idx}`] || []
  addLog(`${tr('Select chat target', '选择对话对象')}: ${agent.username}`)
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit'
    })
  } catch {
    return ''
  }
}

// Chat Methods
const sendMessage = async () => {
  if (!chatInput.value.trim() || isSending.value) return
  
  const message = chatInput.value.trim()
  chatInput.value = ''
  
  // Add user message
  chatHistory.value.push({
    role: 'user',
    content: message,
    timestamp: new Date().toISOString()
  })
  
  scrollToBottom()
  isSending.value = true
  
  try {
    if (chatTarget.value === 'report_agent') {
      await sendToReportAgent(message)
    } else {
      await sendToAgent(message)
    }
  } catch (err) {
    addLog(`${tr('Send failed', '发送失败')}: ${err.message}`)
    chatHistory.value.push({
      role: 'assistant',
      content: `${tr('Sorry, an error occurred', '抱歉,发生了错误')}: ${err.message}`,
      timestamp: new Date().toISOString()
    })
  } finally {
    isSending.value = false
    scrollToBottom()
    // Auto-save chat records to cache
    saveChatHistory()
  }
}

const sendToReportAgent = async (message) => {
  addLog(`${tr('Sending to Report Agent', '发送至报告智能体')}: ${message.substring(0, 50)}...`)
  
  // Build chat history for API
  const historyForApi = chatHistory.value
    .filter(msg => msg.role !== 'user' || msg.content !== message)
    .slice(-10) // Keep last 10 messages
    .map(msg => ({
      role: msg.role,
      content: msg.content
    }))
  
  const res = await chatWithReport({
    simulation_id: props.simulationId,
    message: message,
    chat_history: historyForApi
  })
  
  if (res.success && res.data) {
    chatHistory.value.push({
      role: 'assistant',
      content: res.data.response || res.data.answer || tr('No response', '无响应'),
      timestamp: new Date().toISOString()
    })
    addLog(tr('Report Agent has replied', '报告智能体已回复'))
  } else {
    throw new Error(res.error || tr('Request failed', '请求失败'))
  }
}

const sendToAgent = async (message) => {
  if (!selectedAgent.value || selectedAgentIndex.value === null) {
    throw new Error(tr('Please select a simulated individual first', '请先选择一个模拟个体'))
  }
  
  addLog(`${tr('Sending to', '发送至')} ${selectedAgent.value.username}: ${message.substring(0, 50)}...`)
  
  // Build prompt with chat history
  let prompt = message
  if (chatHistory.value.length > 1) {
    const historyContext = chatHistory.value
      .filter(msg => msg.content !== message)
      .slice(-6)
      .map(msg => `${msg.role === 'user' ? 'Questioner' : 'You'}: ${msg.content}`)
      .join('\n')
    prompt = `Here is our previous conversation:\n${historyContext}\n\nMy new question is: ${message}`
  }
  
  const res = await interviewAgents({
    simulation_id: props.simulationId,
    interviews: [{
      agent_id: selectedAgentIndex.value,
      prompt: prompt
    }]
  })
  
  if (res.success && res.data) {
    // Correct data path: res.data.result.results is an object dictionary
    // Format: {"twitter_0": {...}, "reddit_0": {...}} or single platform {"reddit_0": {...}}
    const resultData = res.data.result || res.data
    const resultsDict = resultData.results || resultData

    // Convert object dictionary to array, prioritize reddit platform replies
    let responseContent = null
    const agentId = selectedAgentIndex.value

    if (typeof resultsDict === 'object' && !Array.isArray(resultsDict)) {
      // Prefer reddit platform reply, then twitter
      const redditKey = `reddit_${agentId}`
      const twitterKey = `twitter_${agentId}`
      const agentResult = resultsDict[redditKey] || resultsDict[twitterKey] || Object.values(resultsDict)[0]
      if (agentResult) {
        responseContent = agentResult.response || agentResult.answer
      }
    } else if (Array.isArray(resultsDict) && resultsDict.length > 0) {
      // Compatible with array format
      responseContent = resultsDict[0].response || resultsDict[0].answer
    }
    
    if (responseContent) {
      chatHistory.value.push({
        role: 'assistant',
        content: responseContent,
        timestamp: new Date().toISOString()
      })
      addLog(`${selectedAgent.value.username} ${tr('has replied', '已回复')}`)
    } else {
      throw new Error(tr('No response data', '没有响应数据'))
    }
  } else {
    throw new Error(res.error || tr('Request failed', '请求失败'))
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatMessages.value) {
      chatMessages.value.scrollTop = chatMessages.value.scrollHeight
    }
  })
}

// Survey Methods
const toggleAgentSelection = (idx) => {
  const newSet = new Set(selectedAgents.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  selectedAgents.value = newSet
}

const selectAllAgents = () => {
  const newSet = new Set()
  profiles.value.forEach((_, idx) => newSet.add(idx))
  selectedAgents.value = newSet
}

const clearAgentSelection = () => {
  selectedAgents.value = new Set()
}

const submitSurvey = async () => {
  if (selectedAgents.value.size === 0 || !surveyQuestion.value.trim()) return
  
  isSurveying.value = true
  addLog(`${tr('Sending survey to', '正在向')} ${selectedAgents.value.size} ${tr('targets...', '个对象发送问卷...')}`)
  
  try {
    const interviews = Array.from(selectedAgents.value).map(idx => ({
      agent_id: idx,
      prompt: surveyQuestion.value.trim()
    }))
    
    const res = await interviewAgents({
      simulation_id: props.simulationId,
      interviews: interviews
    })
    
    if (res.success && res.data) {
      // Correct data path: res.data.result.results is an object dictionary
      // Format: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
      const resultData = res.data.result || res.data
      const resultsDict = resultData.results || resultData

      // Convert object dictionary to array format
      const surveyResultsList = []
      
      for (const interview of interviews) {
        const agentIdx = interview.agent_id
        const agent = profiles.value[agentIdx]

        // Prefer reddit platform reply, then twitter
        let responseContent = tr('No response', '无响应')

        if (typeof resultsDict === 'object' && !Array.isArray(resultsDict)) {
          const redditKey = `reddit_${agentIdx}`
          const twitterKey = `twitter_${agentIdx}`
          const agentResult = resultsDict[redditKey] || resultsDict[twitterKey]
          if (agentResult) {
            responseContent = agentResult.response || agentResult.answer || tr('No response', '无响应')
          }
        } else if (Array.isArray(resultsDict)) {
          // Compatible with array format
          const matchedResult = resultsDict.find(r => r.agent_id === agentIdx)
          if (matchedResult) {
            responseContent = matchedResult.response || matchedResult.answer || tr('No response', '无响应')
          }
        }

        surveyResultsList.push({
          agent_id: agentIdx,
          agent_name: agent?.username || `Agent ${agentIdx}`,
          profession: agent?.profession,
          question: surveyQuestion.value.trim(),
          answer: responseContent
        })
      }

      surveyResults.value = surveyResultsList
      addLog(`${tr('Received', '已收到')} ${surveyResults.value.length} ${tr('replies', '条回复')}`)
    } else {
      throw new Error(res.error || tr('Request failed', '请求失败'))
    }
  } catch (err) {
    addLog(`${tr('Survey send failed', '问卷发送失败')}: ${err.message}`)
  } finally {
    isSurveying.value = false
  }
}

// Load Report Data
const loadReportData = async () => {
  if (!props.reportId) return
  
  try {
    addLog(`${tr('Loading report data', '加载报告数据')}: ${props.reportId}`)
    
    // Get report info
    const reportRes = await getReport(props.reportId)
    if (reportRes.success && reportRes.data) {
      // Load agent logs to get report outline and sections
      await loadAgentLogs()
    }
  } catch (err) {
    addLog(`${tr('Failed to load report', '加载报告失败')}: ${err.message}`)
  }
}

const loadAgentLogs = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getAgentLog(props.reportId, 0)
    if (res.success && res.data) {
      const logs = res.data.logs || []
      
      logs.forEach(log => {
        if (log.action === 'planning_complete' && log.details?.outline) {
          reportOutline.value = log.details.outline
        }
        
        if (log.action === 'section_complete' && log.section_index < 100 && log.details?.content) {
          generatedSections.value[log.section_index] = log.details.content
        }
      })
      
      addLog(tr('Report data loaded', '报告数据已加载'))
    }
  } catch (err) {
    addLog(`${tr('Failed to load report logs', '加载报告日志失败')}: ${err.message}`)
  }
}

const loadProfiles = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getSimulationProfilesRealtime(props.simulationId, 'reddit')
    if (res.success && res.data) {
      profiles.value = res.data.profiles || []
      addLog(`${tr('Loaded', '已加载')} ${profiles.value.length} ${tr('simulated individuals', '个模拟个体')}`)
    }
  } catch (err) {
    addLog(`${tr('Failed to load simulated individuals', '加载模拟个体失败')}: ${err.message}`)
  }
}

// Click outside to close dropdown
const handleClickOutside = (e) => {
  const dropdown = document.querySelector('.agent-dropdown')
  if (dropdown && !dropdown.contains(e.target)) {
    showAgentDropdown.value = false
  }
}

// Lifecycle
onMounted(() => {
  addLog(tr('Step 5 Deep Interaction initializing', '步骤 5 深度交互初始化中'))
  loadReportData()
  loadProfiles()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

watch(() => props.reportId, (newId) => {
  if (newId) {
    loadReportData()
  }
}, { immediate: true })

watch(() => props.simulationId, (newId) => {
  if (newId) {
    loadProfiles()
  }
}, { immediate: true })
</script>

<style scoped>
.interaction-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-gray, #F5F5F5);
  font-family: var(--font-mono);
  overflow: hidden;
}

/* Utility Classes */
.mono {
  font-family: var(--font-mono);
}

/* Main Split Layout */
.main-split-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Left Panel - Report Style (Same as Step4Report.vue) */
.left-panel.report-style {
  width: 45%;
  min-width: 450px;
  background: #FAFAFA;
  border-right: 2px solid rgba(10,10,10,0.12);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 34px 56px 56px 56px;
}

.left-panel::-webkit-scrollbar {
  width: 6px;
}

.left-panel::-webkit-scrollbar-track {
  background: transparent;
}

.left-panel::-webkit-scrollbar-thumb {
  background: transparent;
  transition: background 0.3s ease;
}

.left-panel:hover::-webkit-scrollbar-thumb {
  background: rgba(10,10,10,0.15);
}

.left-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(10,10,10,0.25);
}

/* Report Header */
.report-content-wrapper {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.report-header-block {
  margin-bottom: 34px;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 22px;
}

.report-tag {
  background: #0A0A0A;
  color: #FAFAFA;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 6px 11px;
  letter-spacing: 3px;
  text-transform: uppercase;
}

.report-id {
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  font-weight: 500;
  letter-spacing: 0.02em;
}

.main-title {
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 700;
  color: #0A0A0A;
  line-height: 1.2;
  margin: 0 0 22px 0;
  letter-spacing: -0.02em;
}

.sub-title {
  font-family: var(--font-display);
  font-size: 16px;
  color: rgba(10,10,10,0.5);
  font-style: italic;
  line-height: 1.6;
  margin: 0 0 34px 0;
  font-weight: 400;
}

.header-divider {
  height: 2px;
  background: rgba(10,10,10,0.12);
  width: 100%;
}

/* Sections List */
.sections-list {
  display: flex;
  flex-direction: column;
  gap: 34px;
}

.report-section-item {
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.section-header-row {
  display: flex;
  align-items: baseline;
  gap: 11px;
  transition: background-color 0.2s ease;
  padding: 6px 11px;
  margin: -6px -11px;
}

.section-header-row.clickable {
  cursor: pointer;
}

.section-header-row.clickable:hover {
  background-color: var(--color-gray, #F5F5F5);
}

.collapse-icon {
  margin-left: auto;
  color: rgba(10,10,10,0.4);
  transition: transform 0.3s ease;
  flex-shrink: 0;
  align-self: center;
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.section-number {
  font-family: var(--font-mono);
  font-size: 16px;
  color: rgba(10,10,10,0.12);
  font-weight: 500;
  transition: color 0.3s ease;
}

.section-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 600;
  color: #0A0A0A;
  margin: 0;
  transition: color 0.3s ease;
}

/* States */
.report-section-item.is-pending .section-number {
  color: rgba(10,10,10,0.12);
}
.report-section-item.is-pending .section-title {
  color: rgba(10,10,10,0.2);
}

.report-section-item.is-active .section-number,
.report-section-item.is-completed .section-number {
  color: rgba(10,10,10,0.4);
}

.report-section-item.is-active .section-title,
.report-section-item.is-completed .section-title {
  color: #0A0A0A;
}

.section-body {
  padding-left: 22px;
  overflow: hidden;
}

/* Generated Content */
.generated-content {
  font-family: var(--font-display);
  font-size: 14px;
  line-height: 1.8;
  color: rgba(10,10,10,0.7);
}

.generated-content :deep(p) {
  margin-bottom: 1em;
}

.generated-content :deep(.md-h2),
.generated-content :deep(.md-h3),
.generated-content :deep(.md-h4) {
  font-family: var(--font-display);
  color: #0A0A0A;
  margin-top: 1.5em;
  margin-bottom: 0.8em;
  font-weight: 700;
}

.generated-content :deep(.md-h2) { font-size: 20px; border-bottom: 2px solid rgba(10,10,10,0.08); padding-bottom: 6px; }
.generated-content :deep(.md-h3) { font-size: 18px; }
.generated-content :deep(.md-h4) { font-size: 16px; }

.generated-content :deep(.md-ul),
.generated-content :deep(.md-ol) {
  padding-left: 22px;
  margin-bottom: 1em;
}

.generated-content :deep(.md-li) {
  margin-bottom: 0.5em;
}

.generated-content :deep(.md-quote) {
  border-left: 3px solid rgba(10,10,10,0.12);
  padding-left: 22px;
  margin: 1.5em 0;
  color: rgba(10,10,10,0.5);
  font-style: italic;
  font-family: var(--font-display);
}

.generated-content :deep(.code-block) {
  background: var(--color-gray, #F5F5F5);
  padding: 11px;
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-x: auto;
  margin: 1em 0;
  border: 2px solid rgba(10,10,10,0.08);
}

.generated-content :deep(strong) {
  font-weight: 600;
  color: #0A0A0A;
}

/* Loading State */
.loading-state {
  display: flex;
  align-items: center;
  gap: 11px;
  color: rgba(10,10,10,0.5);
  font-size: 14px;
  margin-top: 6px;
}

.loading-icon {
  width: 18px;
  height: 18px;
  animation: spin 1s linear infinite;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-text {
  font-family: var(--font-mono);
  font-size: 15px;
  color: rgba(10,10,10,0.5);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Content Styles Override */
.generated-content :deep(.md-h2) {
  font-family: var(--font-display);
  font-size: 18px;
  margin-top: 0;
}

/* Waiting Placeholder */
.waiting-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 22px;
  padding: 34px;
  color: rgba(10,10,10,0.4);
}

.waiting-animation {
  position: relative;
  width: 48px;
  height: 48px;
}

.waiting-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 2px solid rgba(10,10,10,0.12);
  border-radius: 50%;
  animation: ripple 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

.waiting-ring:nth-child(2) {
  animation-delay: 0.4s;
}

.waiting-ring:nth-child(3) {
  animation-delay: 0.8s;
}

@keyframes ripple {
  0% { transform: scale(0.5); opacity: 1; }
  100% { transform: scale(2); opacity: 0; }
}

.waiting-text {
  font-size: 14px;
  font-family: var(--font-mono);
}

/* Right Panel - Interaction */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #FAFAFA;
}

/* Action Bar - Professional Design */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11px 22px;
  border-bottom: 2px solid rgba(10,10,10,0.12);
  background: #FAFAFA;
  gap: 22px;
  position: relative;
  z-index: 20;
  overflow: visible;
}

.action-bar-header {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 160px;
}

.action-bar-icon {
  color: #0A0A0A;
  flex-shrink: 0;
}

.action-bar-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.action-bar-title {
  font-size: 13px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: #0A0A0A;
  letter-spacing: -0.01em;
}

.action-bar-subtitle {
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
}

.action-bar-subtitle.mono {
  font-family: var(--font-mono);
}

.action-bar-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  justify-content: flex-end;
}

.tab-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px;
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  background: var(--color-gray, #F5F5F5);
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.tab-pill:hover {
  background: rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.7);
}

.tab-pill.active {
  background: #0A0A0A;
  color: #FAFAFA;
}

.tab-pill svg {
  flex-shrink: 0;
  opacity: 0.7;
}

.tab-pill.active svg {
  opacity: 1;
}

.tab-divider {
  width: 2px;
  height: 24px;
  background: rgba(10,10,10,0.12);
  margin: 0 6px;
}

.agent-pill {
  width: 200px;
  justify-content: space-between;
}

.agent-pill span {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.survey-pill {
  background: rgba(67,193,101,0.1);
  color: #43C165;
}

.survey-pill:hover {
  background: rgba(67,193,101,0.15);
  color: #43C165;
}

.survey-pill.active {
  background: #43C165;
  color: #FAFAFA;
}

/* Interaction Header */
.interaction-header {
  padding: 22px;
  border-bottom: 2px solid rgba(10,10,10,0.12);
  background: #FAFAFA;
}

.tab-switcher {
  display: flex;
  gap: 6px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 11px 22px;
  font-size: 13px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  background: transparent;
  border: 2px solid rgba(10,10,10,0.12);
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.tab-btn:hover {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.2);
}

.tab-btn.active {
  background: #0A0A0A;
  color: #FAFAFA;
  border-color: #0A0A0A;
}

.tab-btn svg {
  flex-shrink: 0;
}

/* Chat Container */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Report Agent Tools Card */
.report-agent-tools-card {
  border-bottom: 2px solid rgba(10,10,10,0.12);
  background: var(--color-gray, #F5F5F5);
}

.tools-card-header {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 22px;
}

.tools-card-avatar {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  background: #0A0A0A;
  color: #FAFAFA;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
}

.tools-card-info {
  flex: 1;
  min-width: 0;
}

.tools-card-name {
  font-size: 15px;
  font-weight: 600;
  color: #0A0A0A;
  margin-bottom: 2px;
}

.tools-card-subtitle {
  font-size: 12px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.5);
}

.tools-card-toggle {
  width: 28px;
  height: 28px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(10,10,10,0.5);
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.tools-card-toggle:hover {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.12);
}

.tools-card-toggle svg {
  transition: transform 0.3s ease;
}

.tools-card-toggle svg.is-expanded {
  transform: rotate(180deg);
}

.tools-card-body {
  padding: 0 22px 22px 22px;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 11px;
}

.tool-item {
  display: flex;
  gap: 11px;
  padding: 11px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  transition: all 0.2s ease;
}

.tool-item:hover {
  border-color: rgba(10,10,10,0.12);
}

.tool-icon-wrapper {
  width: 32px;
  height: 32px;
  min-width: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-purple .tool-icon-wrapper {
  background: rgba(139, 92, 246, 0.1);
  color: #8B5CF6;
}

.tool-blue .tool-icon-wrapper {
  background: rgba(255,107,26,0.1);
  color: #FF6B1A;
}

.tool-orange .tool-icon-wrapper {
  background: rgba(255,107,26,0.1);
  color: #FF6B1A;
}

.tool-green .tool-icon-wrapper {
  background: rgba(67,193,101,0.1);
  color: #43C165;
}

.tool-content {
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: #0A0A0A;
  margin-bottom: 4px;
}

.tool-desc {
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Agent Profile Card */
.agent-profile-card {
  border-bottom: 2px solid rgba(10,10,10,0.12);
  background: var(--color-gray, #F5F5F5);
}

.profile-card-header {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 22px;
}

.profile-card-avatar {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  background: #0A0A0A;
  color: #FAFAFA;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
}

.profile-card-info {
  flex: 1;
  min-width: 0;
}

.profile-card-name {
  font-size: 15px;
  font-weight: 600;
  color: #0A0A0A;
  margin-bottom: 2px;
}

.profile-card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.5);
}

.profile-card-handle {
  color: rgba(10,10,10,0.4);
}

.profile-card-profession {
  padding: 2px 6px;
  background: rgba(10,10,10,0.08);
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
}

.profile-card-toggle {
  width: 28px;
  height: 28px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(10,10,10,0.5);
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.profile-card-toggle:hover {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.12);
}

.profile-card-toggle svg {
  transition: transform 0.3s ease;
}

.profile-card-toggle svg.is-expanded {
  transform: rotate(180deg);
}

.profile-card-body {
  padding: 0 22px 22px 22px;
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.profile-card-label {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 6px;
}

.profile-card-bio {
  background: #FAFAFA;
  padding: 11px;
  border: 2px solid rgba(10,10,10,0.08);
}

.profile-card-bio p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: rgba(10,10,10,0.5);
}

/* Target Selector */
.target-selector {
  padding: 22px;
  border-bottom: 2px solid rgba(10,10,10,0.12);
}

.selector-label {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 11px;
}

.selector-options {
  display: flex;
  gap: 11px;
}

.target-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 11px 22px;
  font-size: 13px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.7);
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.target-option:hover {
  border-color: rgba(10,10,10,0.12);
}

.target-option.active {
  background: #0A0A0A;
  color: #FAFAFA;
  border-color: #0A0A0A;
}

/* Agent Dropdown */
.agent-dropdown {
  position: relative;
}

.dropdown-arrow {
  margin-left: 4px;
  transition: transform 0.2s ease;
  opacity: 0.6;
}

.dropdown-arrow.open {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  width: 280px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.12);
  max-height: 50vh;
  overflow-y: auto;
  z-index: 1000;
}

.dropdown-header {
  padding: 11px 22px 6px;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 22px;
  cursor: pointer;
  transition: all 0.15s ease;
  border-left: 3px solid transparent;
}

.dropdown-item:hover {
  background: var(--color-gray, #F5F5F5);
  border-left-color: #FF6B1A;
}

.dropdown-item:first-of-type {
  margin-top: 6px;
}

.dropdown-item:last-child {
  margin-bottom: 6px;
}

.agent-avatar {
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
  background: #0A0A0A;
  color: #FAFAFA;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: #0A0A0A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-role {
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Chat Messages */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 22px;
  color: rgba(10,10,10,0.4);
}

.empty-icon {
  opacity: 0.3;
}

.empty-text {
  font-size: 14px;
  font-family: var(--font-mono);
  text-align: center;
  max-width: 280px;
  line-height: 1.6;
}

.chat-message {
  display: flex;
  gap: 11px;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.chat-message.user .message-avatar {
  background: #0A0A0A;
  color: #FAFAFA;
}

.chat-message.assistant .message-avatar {
  background: rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.7);
}

.message-content {
  max-width: 70%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-message.user .message-content {
  align-items: flex-end;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.chat-message.user .message-header {
  flex-direction: row-reverse;
}

.sender-name {
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

.message-time {
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
}

.message-text {
  padding: 11px;
  font-size: 14px;
  line-height: 1.5;
  border: 2px solid rgba(10,10,10,0.08);
}

.chat-message.user .message-text {
  background: #0A0A0A;
  color: #FAFAFA;
  border-color: #0A0A0A;
}

.chat-message.assistant .message-text {
  background: var(--color-gray, #F5F5F5);
  color: rgba(10,10,10,0.7);
  border-color: rgba(10,10,10,0.08);
}

.message-text :deep(.md-p) {
  margin: 0;
}

.message-text :deep(.md-p:last-child) {
  margin-bottom: 0;
}

/* Fix ordered list numbering - use CSS counters to make multiple ol elements number consecutively */
.message-text {
  counter-reset: list-counter;
}

.message-text :deep(.md-ol) {
  list-style: none;
  padding-left: 0;
  margin: 6px 0;
}

.message-text :deep(.md-oli) {
  counter-increment: list-counter;
  display: flex;
  gap: 6px;
  margin: 4px 0;
}

.message-text :deep(.md-oli)::before {
  content: counter(list-counter) ".";
  font-weight: 600;
  color: rgba(10,10,10,0.7);
  min-width: 20px;
  flex-shrink: 0;
}

/* Unordered list styles */
.message-text :deep(.md-ul) {
  padding-left: 22px;
  margin: 6px 0;
}

.message-text :deep(.md-li) {
  margin: 4px 0;
}

/* Typing Indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: rgba(10,10,10,0.4);
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) { animation-delay: 0s; }
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}

/* Chat Input */
.chat-input-area {
  padding: 22px;
  border-top: 2px solid rgba(10,10,10,0.12);
  display: flex;
  gap: 11px;
  align-items: flex-end;
}

.chat-input {
  flex: 1;
  padding: 11px 22px;
  font-size: 14px;
  border: 2px solid rgba(10,10,10,0.08);
  resize: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.2s ease;
  background: #FAFAFA;
}

.chat-input:focus {
  outline: none;
  border-color: #FF6B1A;
}

.chat-input:disabled {
  background: var(--color-gray, #F5F5F5);
  cursor: not-allowed;
}

.send-btn {
  width: 44px;
  height: 44px;
  background: #0A0A0A;
  color: #FAFAFA;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  background: rgba(10,10,10,0.7);
}

.send-btn:disabled {
  background: rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.4);
  cursor: not-allowed;
}

/* Survey Container */
.survey-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.survey-setup {
  display: flex;
  flex-direction: column;
  padding: 22px;
  border-bottom: 2px solid rgba(10,10,10,0.12);
  overflow: hidden;
}

.setup-section {
  margin-bottom: 22px;
}

.setup-section:first-child {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.setup-section:last-child {
  margin-bottom: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 11px;
}

.setup-section .section-header .section-title {
  font-size: 13px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

.selection-count {
  font-size: 12px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
}

/* Agents Grid */
.section-header-toggle {
  cursor: pointer;
  user-select: none;
  padding: 6px 0;
  transition: background-color 0.15s ease;
}

.section-header-toggle:hover {
  background-color: var(--color-gray, #F5F5F5);
}

.section-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toggle-chevron {
  transition: transform 0.2s ease;
  color: rgba(10,10,10,0.4);
  flex-shrink: 0;
}

.toggle-chevron.expanded {
  transform: rotate(90deg);
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 11px;
  max-height: 110px;
  overflow-y: auto;
  padding: 6px;
  align-content: start;
}

.agent-checkbox {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  cursor: pointer;
  transition: all 0.2s ease;
}

.agent-checkbox:hover {
  border-color: rgba(10,10,10,0.12);
}

.agent-checkbox.checked {
  background: rgba(67,193,101,0.1);
  border-color: #43C165;
}

.agent-checkbox input {
  display: none;
}

.checkbox-avatar {
  width: 28px;
  height: 28px;
  min-width: 28px;
  min-height: 28px;
  background: rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.7);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.agent-checkbox.checked .checkbox-avatar {
  background: #43C165;
  color: #FAFAFA;
}

.checkbox-info {
  flex: 1;
  min-width: 0;
}

.checkbox-name {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #0A0A0A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.checkbox-role {
  display: block;
  font-size: 10px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.checkbox-indicator {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(10,10,10,0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.agent-checkbox.checked .checkbox-indicator {
  background: #43C165;
  border-color: #43C165;
  color: #FAFAFA;
}

.checkbox-indicator svg {
  opacity: 0;
  transform: scale(0.5);
  transition: all 0.2s ease;
}

.agent-checkbox.checked .checkbox-indicator svg {
  opacity: 1;
  transform: scale(1);
}

.selection-actions {
  display: flex;
  gap: 6px;
  margin-top: 11px;
}

.action-link {
  font-size: 12px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.5);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}

.action-link:hover {
  color: #0A0A0A;
  text-decoration: underline;
}

.action-divider {
  color: rgba(10,10,10,0.12);
}

/* Survey Input */
.survey-input {
  width: 100%;
  padding: 11px 22px;
  font-size: 14px;
  border: 2px solid rgba(10,10,10,0.08);
  resize: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.2s ease;
  background: #FAFAFA;
}

.survey-input:focus {
  outline: none;
  border-color: #FF6B1A;
}

.survey-submit-btn {
  width: 100%;
  padding: 11px 22px;
  font-size: 14px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: #FAFAFA;
  background: #0A0A0A;
  border: none;
  cursor: pointer;
  transition: background 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 22px;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.survey-submit-btn:hover:not(:disabled) {
  background: rgba(10,10,10,0.7);
}

.survey-submit-btn:disabled {
  background: rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.4);
  cursor: not-allowed;
}

.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(250, 250, 250, 0.3);
  border-top-color: #FAFAFA;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Results */
.survey-results {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 22px;
}

.results-title {
  font-size: 14px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: #0A0A0A;
}

.results-count {
  font-size: 12px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.result-card {
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  padding: 22px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 11px;
}

.result-avatar {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  background: #0A0A0A;
  color: #FAFAFA;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result-name {
  font-size: 14px;
  font-weight: 600;
  color: #0A0A0A;
}

.result-role {
  font-size: 12px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
}

.result-question {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 11px;
  background: #FAFAFA;
  margin-bottom: 11px;
  font-size: 13px;
  color: rgba(10,10,10,0.5);
  border: 2px solid rgba(10,10,10,0.08);
}

.result-question svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.result-answer {
  font-size: 14px;
  line-height: 1.7;
  color: rgba(10,10,10,0.7);
}

/* Markdown Styles */
:deep(.md-p) {
  margin: 0 0 11px 0;
}

:deep(.md-h2) {
  font-size: 20px;
  font-family: var(--font-display);
  font-weight: 700;
  color: #0A0A0A;
  margin: 22px 0 11px 0;
}

:deep(.md-h3) {
  font-size: 16px;
  font-family: var(--font-display);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
  margin: 22px 0 11px 0;
}

:deep(.md-h4) {
  font-size: 14px;
  font-family: var(--font-display);
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  margin: 22px 0 6px 0;
}

:deep(.md-h5) {
  font-size: 13px;
  font-family: var(--font-display);
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  margin: 11px 0 6px 0;
}

:deep(.md-ul), :deep(.md-ol) {
  margin: 11px 0;
  padding-left: 22px;
}

:deep(.md-li), :deep(.md-oli) {
  margin: 6px 0;
}

/* Chat/survey area quote styles */
.chat-messages :deep(.md-quote),
.result-answer :deep(.md-quote) {
  margin: 11px 0;
  padding: 11px 22px;
  background: var(--color-gray, #F5F5F5);
  border-left: 3px solid #0A0A0A;
  color: rgba(10,10,10,0.5);
}

:deep(.code-block) {
  margin: 11px 0;
  padding: 11px 22px;
  background: #0A0A0A;
  overflow-x: auto;
}

:deep(.code-block code) {
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(250,250,250,0.8);
}

:deep(.inline-code) {
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--color-gray, #F5F5F5);
  padding: 2px 6px;
  color: #0A0A0A;
}

:deep(.md-hr) {
  border: none;
  border-top: 2px solid rgba(10,10,10,0.12);
  margin: 22px 0;
}

/* Profile Popup */
.profile-popup-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.profile-popup {
  background: #FAFAFA;
  width: 520px;
  max-width: 90vw;
  max-height: 80vh;
  border: 2px solid rgba(10,10,10,0.12);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  font-family: var(--font-mono);
}

.profile-popup-header {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 22px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
  position: sticky;
  top: 0;
  background: #FAFAFA;
  z-index: 1;
}

.profile-popup-avatar {
  width: 40px;
  height: 40px;
  min-width: 40px;
  background: #0A0A0A;
  color: #FAFAFA;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  text-transform: uppercase;
}

.profile-popup-info { flex: 1; min-width: 0; }
.profile-popup-name { font-size: 16px; font-weight: 600; color: #0A0A0A; }
.profile-popup-meta { font-size: 12px; color: rgba(10,10,10,0.4); margin-top: 2px; }

.profile-popup-close {
  background: none;
  border: none;
  font-size: 22px;
  color: rgba(10,10,10,0.4);
  cursor: pointer;
  padding: 0 6px;
  line-height: 1;
}
.profile-popup-close:hover { color: rgba(10,10,10,0.7); }

.profile-popup-details {
  padding: 22px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

.profile-popup-row {
  margin-bottom: 11px;
}

.popup-label {
  display: block;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  color: rgba(10,10,10,0.4);
  margin-bottom: 6px;
}

.popup-value {
  font-size: 13px;
  color: rgba(10,10,10,0.5);
  line-height: 1.5;
}

.popup-persona {
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  line-height: 1.5;
}

.popup-persona.clamped {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.profile-popup-stats {
  display: flex;
  gap: 6px;
  margin-bottom: 11px;
  flex-wrap: wrap;
}

.popup-stat {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
  padding: 3px 6px;
  background: var(--color-gray, #F5F5F5);
  color: rgba(10,10,10,0.5);
}

.profile-popup-activity {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
}

.popup-section-title {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  color: rgba(10,10,10,0.4);
  margin-bottom: 11px;
}

.popup-loading, .popup-empty {
  font-size: 12px;
  color: rgba(10,10,10,0.4);
  text-align: center;
  padding: 22px;
}

.popup-actions-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.popup-action-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 6px 6px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
  font-size: 12px;
}

.popup-action-badge {
  font-size: 9px;
  font-family: var(--font-mono);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  padding: 2px 6px;
  background: rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.5);
  flex-shrink: 0;
}

.popup-action-badge.type-create_post, .popup-action-badge.type-quote_post { background: rgba(67,193,101,0.1); color: #43C165; }
.popup-action-badge.type-like_post, .popup-action-badge.type-upvote_post { background: rgba(255,107,26,0.1); color: #FF6B1A; }
.popup-action-badge.type-create_comment { background: rgba(255,107,26,0.1); color: #FF6B1A; }
.popup-action-badge.type-repost { background: rgba(139, 92, 246, 0.1); color: #7B1FA2; }
.popup-action-badge.type-follow { background: rgba(14, 116, 144, 0.1); color: #00838F; }

.popup-action-round {
  font-size: 10px;
  color: rgba(10,10,10,0.2);
  font-family: var(--font-mono);
  flex-shrink: 0;
}

.popup-action-header {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}

.popup-action-preview {
  color: rgba(10,10,10,0.5);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.popup-action-item { cursor: pointer; padding: 6px; }
.popup-action-item:hover { background: #FAFAFA; }

.popup-action-item.expanded .popup-action-preview { display: none; }
.popup-action-item.expanded .popup-action-badge { display: none; }

.popup-action-full {
  margin-top: 6px;
  padding: 6px 11px;
  background: var(--color-gray, #F5F5F5);
  font-size: 12px;
  color: rgba(10,10,10,0.7);
  line-height: 1.6;
}

.popup-action-full p {
  margin: 0 0 4px;
}

.popup-action-full p:last-child { margin-bottom: 0; }

.clickable { cursor: pointer; }
.clickable:hover { opacity: 0.8; }

.modal-enter-active { transition: opacity 0.2s; }
.modal-leave-active { transition: opacity 0.15s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
