
  const CLOUD_RUN_URL = 'https://usd-chat-bot-705379243140.asia-southeast1.run.app';
  const RENDER_BACKEND_URL = window.location.origin;
  const WS_URL = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host + '/ws/voice-agent/';
 
  // ⚡ Hard Refresh / Page Reload Session Reset: Fresh conversation on full page reload ⚡
  try {
      let isPageReload = false;
      if (window.performance) {
          const navEntries = window.performance.getEntriesByType ? window.performance.getEntriesByType("navigation") : [];
          if (navEntries.length > 0) {
              isPageReload = (navEntries[0].type === 'reload');
          } else if (window.performance.navigation) {
              isPageReload = (window.performance.navigation.type === 1);
          }
      }
      if (isPageReload) {
          sessionStorage.removeItem('usd_chat_history');
          sessionStorage.removeItem('usd_user_name');
          sessionStorage.removeItem('usd_user_concern');
          sessionStorage.removeItem('usd_user_city');
          sessionStorage.removeItem('usd_user_doctor');
          sessionStorage.removeItem('usd_user_phone');
          sessionStorage.removeItem('usd_booking_slots');
          sessionStorage.removeItem('usd_session_slots');
          sessionStorage.removeItem('usd_chat_active');
          sessionStorage.removeItem('usd_submission_id');
          sessionStorage.removeItem('usd_api_id');
          sessionStorage.removeItem('usd_is_voice_mode');
      }
  } catch (e) {
      console.error("Reload check error:", e);
  }

  let currentAgentState = 'off';
  let chatHistory = [];
  let socket = null;
  let globalStream = null;
  let isVoiceMode = true;

  let audioCtx = null;
  let audioChunkQueue = [];
  let isAudioPlaying = false;
  let activeSources = [];
  let nextPlayTime = 0;
  let isReplyComplete = false;

  let localTurnId = 0;
  let pendingAudioDecodes = 0;

  let activeTag = null;
  let activeBotMessageDiv = null;
  let activeUserMessageDiv = null;
  let activeBotTextSpan = null;
  let lastBotMessageDiv = null;
  let isMicSoftwareMuted = true;
  let interruptRestartHoldUntil = 0;
  let liveUserText = "";
  let botSpeakingHeartbeatInterval = null;

  let mediaRecorder = null;
  let recordedAudioChunks = [];
  window.recordedAudioBlob = null;
  window.recordDest = null;
  window.uploadedAudioUrl = null;
  window.myvad = null;

  window.isUserSpeaking = false;

  let userTypingDiv = null;
  let userTypingTimer = null;
  let userSpeakingDiv = null;

  function showUserTypingIndicator() {
      removeUserSpeakingIndicator();
      if (!userTypingDiv) {
          userTypingDiv = document.createElement('div');
          userTypingDiv.className = 'user_message user-typing-div';
          userTypingDiv.innerHTML = `
              <div class="usd-msg-text" style="display: flex; align-items: center; gap: 8px;">
                  <div class="typing-indicator-container" style="justify-content: flex-end; padding: 0; margin: 0;">
                      <span>User is typing</span>
                      <div class="typing-indicator">
                          <span class="dot"></span>
                          <span class="dot"></span>
                          <span class="dot"></span>
                      </div>
                  </div>
              </div>`;
          const log = document.getElementById('usd-chat-log');
          if (log) {
              log.appendChild(userTypingDiv);
              log.scrollTop = log.scrollHeight;
          }
      }
      clearTimeout(userTypingTimer);
      userTypingTimer = setTimeout(removeUserTypingIndicator, 2500);
  }

  function removeUserTypingIndicator() {
      clearTimeout(userTypingTimer);
      if (userTypingDiv) {
          userTypingDiv.remove();
          userTypingDiv = null;
      }
  }

  function showUserSpeakingIndicator() {
      removeUserTypingIndicator();
      if (!userSpeakingDiv) {
          userSpeakingDiv = document.createElement('div');
          userSpeakingDiv.className = 'user_message user-speaking-div';
          userSpeakingDiv.innerHTML = `
              <div class="usd-msg-text" style="display: flex; align-items: center; gap: 8px;">
                  <div class="typing-indicator-container" style="justify-content: flex-end; padding: 0; margin: 0;">
                      <span>User is speaking</span>
                      <div class="typing-indicator">
                          <span class="dot"></span>
                          <span class="dot"></span>
                          <span class="dot"></span>
                      </div>
                  </div>
              </div>`;
          const log = document.getElementById('usd-chat-log');
          if (log) {
              log.appendChild(userSpeakingDiv);
              log.scrollTop = log.scrollHeight;
          }
      }
  }

  function removeUserSpeakingIndicator() {
      if (userSpeakingDiv) {
          userSpeakingDiv.remove();
          userSpeakingDiv = null;
      }
  }

  let botThinkingDiv = null;

  function showBotThinkingIndicator(customText = null) {
      removeUserSpeakingIndicator();
      removeUserTypingIndicator();
      let textToShow = customText;
      if (!textToShow) {
          textToShow = !isVoiceMode ? "Riya is typing" : "Riya is thinking";
      }
      if (botThinkingDiv) {
          const span = botThinkingDiv.querySelector('.typing-indicator-container span');
          if (span) span.innerText = textToShow;
          return;
      }
      botThinkingDiv = document.createElement('div');
      botThinkingDiv.className = 'bot_message bot-thinking-div';
      botThinkingDiv.innerHTML = `
          <div class="usd-msg-text" style="display: inline-flex; align-items: center; gap: 8px; background: rgba(18, 18, 18, 0.9); border: 1px solid rgba(190, 150, 68, 0.35); border-radius: 12px; padding: 6px 14px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);">
              <div class="typing-indicator-container" style="padding: 0; margin: 0; display: flex; align-items: center; gap: 8px;">
                  <span style="color: #F3DC87; font-size: 13px; font-weight: 500; letter-spacing: 0.2px;">${textToShow}</span>
                  <div class="typing-indicator" style="display: inline-flex; gap: 4px; align-items: center;">
                      <span class="dot" style="background: #BE9644; width: 5px; height: 5px;"></span>
                      <span class="dot" style="background: #BE9644; width: 5px; height: 5px;"></span>
                      <span class="dot" style="background: #BE9644; width: 5px; height: 5px;"></span>
                  </div>
              </div>
          </div>`;
      const log = document.getElementById('usd-chat-log');
      if (log) {
          log.appendChild(botThinkingDiv);
          log.scrollTop = log.scrollHeight;
      }
  }

  function removeBotThinkingIndicator() {
      if (botThinkingDiv) {
          botThinkingDiv.remove();
          botThinkingDiv = null;
      }
      const log = document.getElementById('usd-chat-log');
      if (log) {
          log.querySelectorAll('.bot-thinking-div, .bot-typing-div').forEach(el => el.remove());
      }
  }

  window.silenceTimeout = null;
  let silenceNudgeCount = 0;
  let thinkingTimeout = null;

  function disconnectToOffline() {
      removeUserTypingIndicator();
      removeUserSpeakingIndicator();
      silenceNudgeCount = 0;
      if (window.clearSilenceTimer) window.clearSilenceTimer();

      if (window.myvad) {
          try { window.myvad.pause(); } catch (e) { }
          window.myvad = null;
      }
      releaseWakeLock();

      if (socket) {
          socket.onclose = null;
          try { socket.close(); } catch (e) { }
          socket = null;
      }
      if (globalStream) {
          try { globalStream.getTracks().forEach(track => track.stop()); } catch (e) { }
          globalStream = null;
      }

      updateState('off', 'Offline');
      const interimBox = document.getElementById('usd-interim-text');
      if (interimBox && isVoiceMode) {
          interimBox.innerText = "Offline (Tap mic to connect)";
          interimBox.style.color = "#999999";
      }
  }

  window.resetSilenceTimer = () => {
      clearTimeout(window.silenceTimeout);

      // Schedule the silence timer:
      // Voice Mode: 45s for gentle nudge, 45s after nudge for offline
      // Chat Mode: 45s for gentle nudge, 60s after nudge for offline
      const timeoutDuration = isVoiceMode
          ? ((silenceNudgeCount === 0) ? 45000 : 45000)
          : ((silenceNudgeCount === 0) ? 45000 : 60000);

      window.silenceTimeout = setTimeout(() => {
          const isStreaming = (typeof isStreamingToBackend !== 'undefined') ? isStreamingToBackend : false;

          // Only fire if the agent is still idle and listening
          if (currentAgentState !== 'listening' && currentAgentState !== 'online') return;
          if (isAudioPlaying || (activeSources && activeSources.length > 0) || pendingAudioDecodes > 0 || window.isUserSpeaking || isStreaming) {
              // If busy, re-schedule
              window.resetSilenceTimer();
              return;
          }

          if (silenceNudgeCount === 0) {
              silenceNudgeCount = 1; // Mark that we nudged them
              updateState('thinking');
              const uName = extractUserName();
              const uConcern = extractUserConcern();
              const uCity = extractUserCity();
              const seconds = isVoiceMode ? 45 : 45;
              if (socket && socket.readyState === WebSocket.OPEN) {
                  socket.send(JSON.stringify({
                      type: 'text_input',
                      text: `SYSTEM INSTRUCTION: The user has been silent for ${seconds} seconds. Ask them politely: 'Are you still there? Please let me know if you have any questions.' Do not say anything else.`,
                      history: chatHistory,
                      isVoiceMode: isVoiceMode,
                      userName: uName,
                      userConcern: uConcern,
                      userCity: uCity
                  }));
              }
          } else {
              // ⚡ User ignored the nudge. Force Offline
              console.log(`⏳ User unresponsive after ${isVoiceMode ? '15s + 25s' : '30s + 45s'}. Disconnecting to Offline...`);
              silenceNudgeCount = 0;
              disconnectToOffline();
          }
      }, timeoutDuration);
  };

  window.clearSilenceTimer = () => {
      clearTimeout(window.silenceTimeout);
  };

  let wakeLock = null;
  async function requestWakeLock() {
      if ('wakeLock' in navigator) {
          try {
              wakeLock = await navigator.wakeLock.request('screen');
          } catch (err) { }
      }
  }
  function releaseWakeLock() {
      if (wakeLock !== null) {
          wakeLock.release().then(() => { wakeLock = null; });
      }
  }

  document.addEventListener('visibilitychange', async () => {
      if (wakeLock !== null && document.visibilityState === 'visible' && currentAgentState !== 'off') {
          await requestWakeLock();
      }
  });

  const usdLinks = {
      '[LINK_HOME]': { url: 'https://ultimatesmiledesign.com/', label: '🏠 Go to Home Page' },
      '[LINK_DENTISTS]': { url: 'https://ultimatesmiledesign.com/certified-dentists/', label: '📍 Find Nearest Dentist' },
      '[LINK_VTRYON]': { url: 'https://ultimatesmiledesign.com/virtual-smile-try-on/', label: '✨ Virtual Smile Try-On' },
      '[LINK_GALLERY]': { url: 'https://ultimatesmiledesign.com/gallery/', label: '🖼️ Check Out Gallery' },
      '[LINK_CONSULT]': { url: 'https://ultimatesmiledesign.com/consult-with-dentist/', label: '👨‍⚕️ Consult Expert Dentist' },
      '[LINK_CONTACT]': { url: 'https://ultimatesmiledesign.com/contact/', label: '📞 Contact Us' },
      '[LINK_CONNECT]': { url: 'https://ultimatesmiledesign.com/dentist-connect/', label: '🤝 Become Certified Dentist' },
      '[LINK_WARRANTY]': { url: 'https://ultimatesmiledesign.com/verify-warranty/', label: '🛡️ Verify Warranty & Authentication' },
  };

  function saveHistory() {
      sessionStorage.setItem('usd_chat_history', JSON.stringify(chatHistory));
  }

  function addUserHistoryIfNew(text) {
      if (!text) return;
      const last = chatHistory[chatHistory.length - 1];
      if (!(last && last.role === 'user' && last.parts && last.parts[0] && last.parts[0].text === text)) {
          chatHistory.push({ role: "user", parts: [{ text: text }] });
          saveHistory();
          const un = extractUserName();
          if (un) sessionStorage.setItem('usd_user_name', un);
          const uc = extractUserConcern();
          if (uc) sessionStorage.setItem('usd_user_concern', uc);
          const uct = extractUserCity();
          if (uct) sessionStorage.setItem('usd_user_city', uct);
          const udoc = extractUserDoctor();
          if (udoc) sessionStorage.setItem('usd_user_doctor', udoc);
          const uph = extractUserPhone();
          if (uph) sessionStorage.setItem('usd_user_phone', uph);

          const currentSlots = JSON.parse(sessionStorage.getItem('usd_booking_slots') || '{}');
          if (un) {
              const parts = un.split(' ');
              currentSlots.first_name = parts[0];
              currentSlots.last_name = parts.length > 1 ? parts.slice(1).join(' ') : '-';
          }
          if (uct) currentSlots.city = uct;
          if (uc) currentSlots.message = uc;
          if (udoc) currentSlots.doctor_name = udoc;
          if (uph) currentSlots.phone = uph;
          sessionStorage.setItem('usd_booking_slots', JSON.stringify(currentSlots));
      }
  }

  async function handleTypingAutoConnect() {
      const inputEl = document.getElementById('usd-text-input');
      if (!inputEl) return;
      const val = inputEl.value;

      if (val && val.trim().length > 0) {
          showUserTypingIndicator();

          // ⚡ Reset silence timer and nudge count while typing so chat never disconnects mid-typing
          silenceNudgeCount = 0;
          if (window.resetSilenceTimer) window.resetSilenceTimer();

          // ⚡ Send heartbeat to backend to reset backend inactivity timer
          if (socket && socket.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({ type: 'heartbeat' }));
          }

          if (currentAgentState === 'off' || !socket || socket.readyState !== WebSocket.OPEN) {
              console.log("[INFO] User typing while offline. Changing status to online and reconnecting...");
              updateState('online', 'Online');
              await ensureConnected();
          }
      } else {
          removeUserTypingIndicator();
      }
  }

  async function ensureConnected() {
      if (!socket || socket.readyState === WebSocket.CLOSED || socket.readyState === WebSocket.CLOSING) {
          updateState('online', 'Online');
          await startWebSocket();
      }
  }

  function cleanDisplayText(text = "") {
      let result = String(text || "");
      result = result.replace(new RegExp("\\[(hi|bn|ta|te|mr|gu|kn|ml|pa|or|en)-IN\\]", "gi"), "");
      result = result.replace(new RegExp("\\[(LINK_[A-Z_]+|END_CHAT)\\]", "gi"), "");
      result = result.replace(new RegExp("<!--[\\s\\S]*?-->", "g"), "");
      result = result.replace(new RegExp("\\s+", "g"), " ");
      return result.trim();
  }

  function cleanLiveStreamText(text = "") {
      let result = String(text || "");
      result = result.replace(/\[(hi|bn|ta|te|mr|gu|kn|ml|pa|or|en)-IN\]/gi, "");
      result = result.replace(/\[(LINK_[A-Z_]+|END_CHAT)\]/gi, "");
      result = result.replace(/<!--[\s\S]*?-->/g, "");
      result = result.replace(/(<!--|\[[A-Za-z0-9_\-]*)$/g, "");
      result = result.replace(/\s+/g, " ");
      return result;
  }

  function detectLocalTagFromText(text = "") {
      if (!text) return null;
      const str = String(text);
      for (const tag in usdLinks) {
          if (str.toUpperCase().includes(tag)) {
              return tag;
          }
      }
      const commentMatch = str.match(/<!--\s*\[?(LINK_[A-Z_]+)\]?\s*-->/i);
      if (commentMatch) {
          const rawTag = `[${commentMatch[1].toUpperCase()}]`;
          if (usdLinks[rawTag]) return rawTag;
      }
      return null;
  }

  function detectUserTagFromText(text = "") {
      if (!text) return null;
      const str = String(text).toLowerCase().trim();
      if (!str) return null;

      // Allow if the user explicitly typed the tag name itself like "[LINK_CONSULT]"
      for (const tag in usdLinks) {
          if (str.toUpperCase().includes(tag)) return tag;
      }

      // 1. Immediately allow consultation link based on booking/consulting keywords
      if (str.includes("appointment") || str.includes("book") || str.includes("visit") || (str.includes("consult") && !str.includes("consultant") && !str.includes("consulting"))) {
          return '[LINK_CONSULT]';
      }

      // 2. Immediately allow dentist locator link based on dentist/clinic keywords
      if (str.includes("dentist") || str.includes("clinic") || str.includes("designer") || str.includes("location") || str.includes("nearest")) {
          return '[LINK_DENTISTS]';
      }

      // 3. For any OTHER links, we strictly require explicit link request keywords
      const explicitLinkWords = [
          "link", "url", "website", "site", "page", "button", "click", "href", "address",
          "लिंक", "वेबसाइट", "पेज", "बटन", "લિંક", "વેબસાઇટ", "પેજ", "બટન",
          "send me", "share", "give me", "provide", "show me", "open", "go to", "where can i", "how to"
      ];
      const hasExplicitRequest = explicitLinkWords.some(w => str.includes(w));
      if (!hasExplicitRequest) {
          return null;
      }

      if (str.includes("try-on") || str.includes("try on") || str.includes("virtual smile") || str.includes("smile makeover") || str.includes("makeover")) return '[LINK_VTRYON]';
      if (str.includes("contact") || str.includes("call") || str.includes("phone") || str.includes("reach out")) return '[LINK_CONTACT]';
      if (str.includes("partner") || str.includes("collaborate") || str.includes("join")) return '[LINK_CONNECT]';
      if (str.includes("gallery") || str.includes("result") || str.includes("before")) return '[LINK_GALLERY]';
      if (str.includes("warranty") || str.includes("verify") || str.includes("authentic")) return '[LINK_WARRANTY]';

      return null;
  }

  function appendLinkButton(container, tag) {
      if (!container || !tag || !usdLinks[tag]) return;
      if (container.querySelector('.usd-link-card')) return;
      const btn = document.createElement('button');
      btn.className = 'usd-link-card';
      btn.innerText = usdLinks[tag].label;
      btn.onclick = () => handleLinkClick(tag);
      container.appendChild(btn);
  }

  function cleanDisplayText(text) {
      if (!text) return "";
      let str = String(text);
      str = str.replace(/\[(hi|bn|ta|te|mr|gu|kn|ml|pa|or|en)-IN\]/gi, "");
      str = str.replace(/<!--[\s\S]*?-->/g, "");
      str = str.replace(/\d{1,2}:\d{2}(:\d{2})?(\.\d+)?\s*-->\s*\d{1,2}:\d{2}(:\d{2})?(\.\d+)?/g, "");
      str = str.replace(/\b\d{1,2}:\d{2}(:\d{2})?\b/g, "");
      str = str.replace(/\s+/g, " ").trim();
      return str;
  }

  function cleanLiveStreamText(text) {
      return cleanDisplayText(text);
  }

  function updateState(newState, statusText = null) {
      currentAgentState = newState;

      if (newState === 'thinking') {
          clearTimeout(thinkingTimeout);
          thinkingTimeout = setTimeout(() => {
              if (currentAgentState === 'thinking') {
                  console.log("⏳ Thinking timeout reached (no response from Gemini). Resetting state to listening...");
                  updateState('listening');
              }
          }, 6000); // 6 seconds backup safety timeout
      } else {
          clearTimeout(thinkingTimeout);
      }

      if (newState === 'speaking' || newState === 'thinking') {
          if (!botSpeakingHeartbeatInterval) {
              botSpeakingHeartbeatInterval = setInterval(() => {
                  if (socket && socket.readyState === WebSocket.OPEN) {
                      socket.send(JSON.stringify({ type: 'heartbeat' }));
                  }
              }, 5000);
          }
      } else {
          if (botSpeakingHeartbeatInterval) {
              clearInterval(botSpeakingHeartbeatInterval);
              botSpeakingHeartbeatInterval = null;
          }
      }

      const statusBox = document.getElementById('usd-status-box');
      const interimBox = document.getElementById('usd-interim-text');
      const voiceTrigger = document.getElementById('usd-voice-trigger-btn');

      const innerWrap = document.getElementById('usd-chat-inner-wrap');
      if (innerWrap) {
          innerWrap.classList.remove('usd-speaking', 'usd-listening', 'usd-thinking');
          if (newState === 'speaking') {
              innerWrap.classList.add('usd-speaking');
          } else if (newState === 'listening') {
              innerWrap.classList.add('usd-listening');
          } else if (newState === 'thinking') {
              innerWrap.classList.add('usd-thinking');
          }
      }

      if (statusBox) {
          if (newState === 'connecting') {
              statusBox.innerHTML = '<span class="status-dot connecting"></span> ' + (statusText || "Connecting...");
          } else if (newState === 'off') {
              statusBox.innerHTML = '<span class="status-dot offline"></span> ' + (statusText || "Offline");
          } else if (isVoiceMode) {
              statusBox.innerHTML = '<span class="status-dot online"></span> Online';
          } else {
              statusBox.innerHTML = '<span class="status-dot online"></span> ' + (statusText || "Chat Mode Active.");
          }
      }

      if (newState === 'speaking' || newState === 'listening') {
          if (voiceTrigger) voiceTrigger.classList.add('is-listening');
      } else {
          if (voiceTrigger) voiceTrigger.classList.remove('is-listening');
      }

      if (newState === 'listening' || newState === 'online') {
          isMicSoftwareMuted = !isVoiceMode;
          if (isVoiceMode && window.myvad) window.myvad.start();
          if (window.resetSilenceTimer) window.resetSilenceTimer();
          if (isVoiceMode && interimBox) { interimBox.innerText = "Listening..."; interimBox.style.color = "#D4AF37"; }
      } else if (newState === 'speaking' && isVoiceMode) {
          isMicSoftwareMuted = false;
          if (window.myvad) window.myvad.start();
          if (window.clearSilenceTimer) window.clearSilenceTimer();
      } else {
          isMicSoftwareMuted = true;
          if (window.myvad) window.myvad.pause();
          if (window.clearSilenceTimer) window.clearSilenceTimer();
      }

      if (newState === 'thinking') {
          removeUserTypingIndicator();
          removeUserSpeakingIndicator();
          showBotThinkingIndicator();
          if (interimBox) {
              interimBox.innerText = "Answering...";
              interimBox.style.color = "#ffffff";
          }
      } else {
          removeBotThinkingIndicator();
      }

      if (!isVoiceMode && interimBox && newState !== 'thinking') {
          interimBox.innerText = "";
      }
  }

  let vocalMasterNode = null;
  let callAudioElement = null;
  let callAudioDestination = null;

  async function initAudio() {
      if (!audioCtx) {
          audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtx && audioCtx.state === 'suspended') {
          try { await audioCtx.resume(); } catch (e) { }
      }

      if (!vocalMasterNode && audioCtx) {
          try {
              // ========================================================
              // 🎙️ USD STUDIO AURA & HEAVY VOCAL DEPTH ENGINE
              // ========================================================
              const inputNode = audioCtx.createGain();

              // 1. CHEST RESONANCE & HEAVY VOCAL WEIGHT (Gives Despina that deep, rich, authoritative body)
              const chestResonance = audioCtx.createBiquadFilter();
              chestResonance.type = 'peaking';
              chestResonance.frequency.value = 210; // 210Hz fundamental chest resonance
              chestResonance.gain.value = 3.8;       // +3.8dB rich heavy presence
              chestResonance.Q.value = 1.2;

              // 2. VOCAL BODY WARMTH
              const vocalWarmth = audioCtx.createBiquadFilter();
              vocalWarmth.type = 'peaking';
              vocalWarmth.frequency.value = 450;
              vocalWarmth.gain.value = 2.0;
              vocalWarmth.Q.value = 1.0;

              // 3. INTIMATE SPEECH ARTICULATION
              const vocalPresence = audioCtx.createBiquadFilter();
              vocalPresence.type = 'peaking';
              vocalPresence.frequency.value = 2800;
              vocalPresence.gain.value = 2.2;
              vocalPresence.Q.value = 1.0;

              // 4. DE-HARSHING LOW-PASS (Silky top-end, zero digital fatigue)
              const deHarsh = audioCtx.createBiquadFilter();
              deHarsh.type = 'lowpass';
              deHarsh.frequency.value = 10000;
              deHarsh.Q.value = 0.7;

              // Direct Dry Path
              const dryGain = audioCtx.createGain();
              dryGain.gain.value = 0.85;

              inputNode.connect(chestResonance);
              chestResonance.connect(vocalWarmth);
              vocalWarmth.connect(vocalPresence);
              vocalPresence.connect(deHarsh);
              deHarsh.connect(dryGain);

              // ========================================================
              // 🌌 PARALLEL ACOUSTIC AURA & EARLY REFLECTION ENGINE
              // (Sub-35ms multi-tap: creates acoustic mass & spatial weight without repeating echo)
              // ========================================================
              const auraBandpass = audioCtx.createBiquadFilter();
              auraBandpass.type = 'bandpass';
              auraBandpass.frequency.value = 1200;
              auraBandpass.Q.value = 0.6; // Soft, wide room acoustic band

              const tap1 = audioCtx.createDelay();
              tap1.delayTime.value = 0.014; // 14ms
              const tap1Gain = audioCtx.createGain();
              tap1Gain.gain.value = 0.24;

              const tap2 = audioCtx.createDelay();
              tap2.delayTime.value = 0.024; // 24ms
              const tap2Gain = audioCtx.createGain();
              tap2Gain.gain.value = 0.18;

              const tap3 = audioCtx.createDelay();
              tap3.delayTime.value = 0.035; // 35ms
              const tap3Gain = audioCtx.createGain();
              tap3Gain.gain.value = 0.12;

              const auraMasterGain = audioCtx.createGain();
              auraMasterGain.gain.value = 0.38; // The magic blend for that heavy aura!

              deHarsh.connect(auraBandpass);
              auraBandpass.connect(tap1);
              tap1.connect(tap1Gain);
              tap1Gain.connect(auraMasterGain);

              auraBandpass.connect(tap2);
              tap2.connect(tap2Gain);
              tap2Gain.connect(auraMasterGain);

              auraBandpass.connect(tap3);
              tap3.connect(tap3Gain);
              tap3Gain.connect(auraMasterGain);

              // ========================================================
              // 🎚️ MASTER DYNAMICS COMPRESSOR (Glues the aura and voice into one thick, velvety presence)
              // ========================================================
              const masterCompressor = audioCtx.createDynamicsCompressor();
              masterCompressor.threshold.value = -18;
              masterCompressor.knee.value = 14;
              masterCompressor.ratio.value = 3.2;
              masterCompressor.attack.value = 0.003;
              masterCompressor.release.value = 0.09;

              dryGain.connect(masterCompressor);
              auraMasterGain.connect(masterCompressor);

              // Master Output to AudioContext Destination
              masterCompressor.connect(audioCtx.destination);

              // Output to MediaStream <audio> element to maintain Call Audio stream
              callAudioDestination = audioCtx.createMediaStreamDestination();
              masterCompressor.connect(callAudioDestination);

              if (!callAudioElement) {
                  callAudioElement = document.createElement('audio');
                  callAudioElement.autoplay = true;
                  callAudioElement.playsInline = true;
                  callAudioElement.muted = true;
                  callAudioElement.srcObject = callAudioDestination.stream;
                  document.body.appendChild(callAudioElement);
                  callAudioElement.play().catch(() => {});
              }

              vocalMasterNode = inputNode;
          } catch (err) {
              console.warn("Vocal master node setup error:", err);
          }
      }
  }

  function handleLinkClick(tag) {
      const linkInfo = usdLinks[tag];
      if (!linkInfo) return;

      logMessage('bot', "Redirecting you now...");
      chatHistory.push({ role: "model", parts: [{ text: "Redirecting you now..." }] });
      saveHistory();

      window.open(linkInfo.url, '_blank');
      updateState('listening');
  }

  function checkBotFinishedSpeaking() {
      // ⚡ ONLY transition back to listening if server has completed its reply AND all audio has played!
      if (!isReplyComplete) {
          return;
      }
      if (audioChunkQueue.length === 0 && activeSources.length === 0 && pendingAudioDecodes === 0) {
          isReplyComplete = false;
          nextPlayTime = 0;

          if (activeTag === '[END_CHAT]') {
              setTimeout(() => closeChat(true), 2000);
          } else {
              updateState('cooldown');
              setTimeout(() => {
                  if (currentAgentState === 'cooldown' || currentAgentState === 'speaking') {
                      updateState('listening');
                  }
              }, 150);
          }
          activeTag = null;
      }
  }

  async function playAudioChunk(base64) {
      if (!base64) return;
      updateState('speaking');

      try {
          await initAudio();
          const binaryString = window.atob(base64);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
              bytes[i] = binaryString.charCodeAt(i);
          }

          pendingAudioDecodes++;
          const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer);
          pendingAudioDecodes--;

          const source = audioCtx.createBufferSource();
          source.buffer = audioBuffer;
          
          if (vocalMasterNode) {
              source.connect(vocalMasterNode);
          } else {
              source.connect(audioCtx.destination);
          }

          if (window.recordDest) {
              source.connect(window.recordDest);
          }

          source.playbackRate.value = 1.0;

          if (nextPlayTime < audioCtx.currentTime) {
              nextPlayTime = audioCtx.currentTime + 0.05;
          }

          source.start(nextPlayTime);
          nextPlayTime += audioBuffer.duration;

          window.activeAudioSourceNode = source;
          activeSources.push(source);

          source.onended = () => {
              activeSources = activeSources.filter(s => s !== source);
              checkBotFinishedSpeaking();
          };
      } catch (e) {
          pendingAudioDecodes = Math.max(0, pendingAudioDecodes - 1);
          console.error("Audio Decode error:", e);
          checkBotFinishedSpeaking();
      }
  }

  async function processAudioQueue() {
      if (isAudioPlaying) return;
      isAudioPlaying = true;
      try {
          while (audioChunkQueue.length > 0) {
              const chunk = audioChunkQueue.shift();
              await playAudioChunk(chunk.audioBase64 || chunk);
          }
      } finally {
          isAudioPlaying = false;
          checkBotFinishedSpeaking();

          setTimeout(() => {
              if (activeSources.length === 0 && audioChunkQueue.length === 0 && (currentAgentState === 'speaking' || currentAgentState === 'cooldown')) {
                  isReplyComplete = false;
                  updateState('listening');
              }
          }, 600);
      }
  }

  function toggleChatMode() {
      isVoiceMode = !isVoiceMode;

      const textControls = document.getElementById('usd-input-container');
      const voiceFooter = document.getElementById('usd-voice-controls-footer');
      const micText = document.getElementById('usd-interim-text');
      const inputInner = document.querySelector('.input_box_and_icon_main');

      const textMicBtn = document.getElementById('usd-text-mic-btn');
      const textCloseBtn = document.getElementById('usd-text-close-btn');

      if (isVoiceMode) {
          if (textControls) textControls.style.display = "none";
          if (voiceFooter) voiceFooter.style.display = "flex";
          if (micText) micText.style.display = "block";

          if (textMicBtn) textMicBtn.style.display = "none";
          if (textCloseBtn) textCloseBtn.style.display = "none";

          initAudio();
          isMicSoftwareMuted = false;
          if (window.myvad) window.myvad.start();
          updateState('listening');
      } else {
          if (textControls) textControls.style.display = "block";
          if (inputInner) inputInner.style.display = "flex";
          if (voiceFooter) voiceFooter.style.display = "none";
          if (micText) micText.style.display = "none";

          if (textMicBtn) textMicBtn.style.display = "flex";
          if (textCloseBtn) textCloseBtn.style.display = "flex";

          isMicSoftwareMuted = true;
          if (window.myvad) window.myvad.pause();
          updateState('listening');
      }
      sessionStorage.setItem('usd_is_voice_mode', isVoiceMode.toString());
  }

  async function handleCenterMicClick() {
      initAudio();
      requestWakeLock();

      // If currently disconnected/offline, ask if they want to continue or start a new chat
      if (currentAgentState === 'off' || !socket || socket.readyState !== WebSocket.OPEN) {
          document.getElementById('usd-reconnect-confirm-overlay').style.display = 'flex';

          // Connect WebSocket in reconnect-pending mode so bot can speak the query and mic can listen
          window.isAskReconnectChoicePending = true;
          window.isReconnectManual = false;
          audioChunkQueue = [];
          activeSources.forEach(source => { try { source.stop(); } catch (e) { } });
          activeSources = [];
          isAudioPlaying = false;
          isReplyComplete = false;
          pendingAudioDecodes = 0;
          nextPlayTime = 0;
          localTurnId = 0;

          updateState('connecting', 'Connecting...');

          if (socket) {
              try {
                  socket.onclose = null;
                  socket.onerror = null;
                  socket.close();
              } catch (e) { }
          }

          await startWebSocket();
          return;
      }

      window.isReconnectManual = true;
      audioChunkQueue = [];
      activeSources.forEach(source => { try { source.stop(); } catch (e) { } });
      activeSources = [];
      isAudioPlaying = false;
      isReplyComplete = false;
      pendingAudioDecodes = 0;
      nextPlayTime = 0;
      localTurnId = 0;

      updateState('connecting', 'Reconnecting...');

      if (socket) {
          try {
              socket.onclose = null;
              socket.onerror = null;
              socket.close();
          } catch (e) { }
      }

      await startWebSocket();
  }

  function extractUserName() {
      const existing = sessionStorage.getItem('usd_user_name');
      if (existing && existing.trim() && !existing.includes('[') && !existing.includes('-') && !existing.includes(':') && existing.length <= 25) return existing.trim();
      const savedSlots = JSON.parse(sessionStorage.getItem('usd_booking_slots') || '{}');
      if (savedSlots.first_name && !savedSlots.first_name.includes('[') && !savedSlots.first_name.includes('-') && !savedSlots.first_name.includes(':') && savedSlots.first_name.length <= 25) {
          const fn = savedSlots.first_name;
          const ln = savedSlots.last_name && savedSlots.last_name !== '-' && !savedSlots.last_name.includes('[') && !savedSlots.last_name.includes(':') ? savedSlots.last_name : '';
          return `${fn} ${ln}`.trim();
      }

      if (!chatHistory || !chatHistory.length) return "";

      const stopWords = [
          "hi", "hello", "hey", "namaste", "yes", "no", "ok", "okay", "sure", "thanks", "thank", "what", "how", "why", "can", "good", "fine",
          "teeth", "smile", "veneer", "veneers", "crown", "crowns", "cost", "price", "doctor", "system", "dentist", "consult", "appointment",
          "help", "makeover", "oh", "ohh", "ohhh", "ah", "ahh", "umm", "um", "hmm", "hmmm", "accha", "acha", "haan", "ha", "na", "nah",
          "yep", "nope", "alright", "cool", "well", "yo", "bhai", "bro", "sir", "mam", "madam", "dear", "pls", "please", "now", "see",
          "listen", "actually", "start", "unorganise", "unorganized", "irregular", "crooked", "gap", "yellow", "white",
          "planning", "looking", "interested", "trying", "wondering", "suffering", "having", "scared", "worried",
          "afraid", "visiting", "going", "coming", "thinking", "asking", "seeking", "facing", "feeling", "living",
          "staying", "working", "traveling", "searching", "needing", "inquiring", "booking", "consulting", "checking",
          "here", "there", "just", "only", "also", "already", "currently", "trip", "dubai", "india", "patient", "user",
          "ahmedabad", "surat", "mumbai", "pune", "vadodara", "rajkot", "jamnagar", "bharuch", "halvad", "dhrangadhra", "delhi", "gurugram",
          "gurgaon", "indore", "gwalior", "bangalore", "bengaluru", "hyderabad", "chennai", "guntur", "sangli", "guwahati", "faridkot",
          "malda", "mehsana", "mehasana", "gandhinagar", "anand", "nadiad", "morbi", "bhavnagar", "navsari", "valsad", "vapi", "nashik",
          "thane", "noida", "ghaziabad", "faridabad", "chandigarh", "bhopal", "ujjain", "jabalpur", "agra", "kanpur", "lucknow", "kolhapur",
          "satara", "solapur", "mysore", "mangalore", "ludhiana", "amritsar", "jalandhar", "bathinda", "kolkata"
      ];

      function isValidNameCandidate(str) {
          if (!str || str.length < 2 || str.length > 25) return false;
          const l = str.toLowerCase();
          if (stopWords.includes(l) || l.endsWith("ing")) return false;
          return true;
      }

      for (let i = 0; i < chatHistory.length; i++) {
          const turn = chatHistory[i];
          if (turn.role === 'user' && turn.parts && turn.parts[0] && turn.parts[0].text) {
              const text = turn.parts[0].text.trim();

              let expMatch = text.match(/(?:my name is|myself|call me|mera naam|maru naam|i am|i'm|this is|hu)\s+([A-Za-z\u0900-\u097F\u0A80-\u0AFF]+)(?:\s+([A-Za-z\u0900-\u097F\u0A80-\u0AFF]+))?/i);
              if (expMatch && expMatch[1]) {
                  const fn = expMatch[1].charAt(0).toUpperCase() + expMatch[1].slice(1).toLowerCase();
                  const ln = expMatch[2] ? expMatch[2].charAt(0).toUpperCase() + expMatch[2].slice(1).toLowerCase() : "";
                  if (isValidNameCandidate(fn)) {
                      return (fn + (ln && isValidNameCandidate(ln) ? " " + ln : "")).trim();
                  }
              }

              let prevBotAskedName = false;
              if (i > 0 && chatHistory[i - 1].role === 'model') {
                  const prevBotText = (chatHistory[i - 1].parts[0].text || "").toLowerCase();
                  if (prevBotText.includes("your name") || prevBotText.includes("tamaru naam") || prevBotText.includes("aapka naam") || prevBotText.includes("start with your beautiful name")) {
                      prevBotAskedName = true;
                  }
              }

              if (prevBotAskedName || i === 0 || i === 1) {
                  const bareMatch = text.match(/^([A-Za-z\u0900-\u097F\u0A80-\u0AFF]{2,20})(?:\s+([A-Za-z\u0900-\u097F\u0A80-\u0AFF]{2,20}))?$/i);
                  if (bareMatch && bareMatch[1]) {
                      const fn = bareMatch[1].charAt(0).toUpperCase() + bareMatch[1].slice(1).toLowerCase();
                      const ln = bareMatch[2] ? bareMatch[2].charAt(0).toUpperCase() + bareMatch[2].slice(1).toLowerCase() : "";
                      if (isValidNameCandidate(fn)) {
                          return (fn + (ln && isValidNameCandidate(ln) ? " " + ln : "")).trim();
                      }
                  }
              }
          }
      }
      return "";
  }

  function extractUserConcern() {
      const existing = sessionStorage.getItem('usd_user_concern');
      if (existing && existing.trim()) return existing.trim();
      const savedSlots = JSON.parse(sessionStorage.getItem('usd_booking_slots') || '{}');
      if (savedSlots.message) return savedSlots.message;

      if (!chatHistory || !chatHistory.length) return "";

      for (let i = 0; i < chatHistory.length; i++) {
          const turn = chatHistory[i];
          if (turn.role === 'user' && turn.parts && turn.parts[0] && turn.parts[0].text) {
              const text = turn.parts[0].text.toLowerCase();
              if (text.includes("explain") || text.includes("what is") || text.includes("how does") || text.includes("tell me about") || text.includes("su che") || text.includes("kya hai")) {
                  continue;
              }
              if (text.includes("gap") || text.includes("diastema") || text.includes("space between") || text.includes("spacing") || text.includes("gaap") || text.includes("fanko") || text.includes("fanka")) {
                  return "gaps between teeth";
              }
              if (text.includes("crooked") || text.includes("misaligned") || text.includes("crowded") || text.includes("overlap") ||
                  text.includes("straighten") || text.includes("unorganise") || text.includes("unorganized") || text.includes("irregular") ||
                  text.includes("uneven") || text.includes("tedhe") || text.includes("terhe") || text.includes("alignment") || text.includes("baanka") ||
                  text.includes("વાંકા") || text.includes("વાંકાચૂંકા") || text.includes("ટેઢા") || text.includes("ટેઢે") || text.includes("टेढ़े") || text.includes("nibha chuka")) {
                  return "irregular and misaligned teeth";
              }
              if (text.includes("yellow") || text.includes("stain") || text.includes("discolor") || text.includes("bleach") || text.includes("shade") || text.includes("dull") || text.includes("peela") || text.includes("pila")) {
                  return "teeth discoloration and yellowing";
              }
              if (text.includes("chip") || text.includes("broken") || text.includes("crack") || text.includes("broke") || text.includes("punch") || text.includes("toot") || text.includes("bhangi")) {
                  return "chipped or damaged teeth";
              }
              if (text.includes("missing teeth") || text.includes("lost teeth") || text.includes("lost tooth") || text.includes("daant nathi") || text.includes("dant nathi") || text.includes("teeth missing")) {
                  return "missing teeth";
              }
              if (text.includes("wedding") || text.includes("marriage") || text.includes("shaadi") || text.includes("lagna")) {
                  return "upcoming wedding preparation";
              }
              if (text.includes("dukhaavo") || text.includes("dukhavo") || text.includes("dukhado") || text.includes("dukhadho") || text.includes("dukhavu") ||
                  text.includes("dukhe") || text.includes("dukh") || text.includes("dard") || text.includes("pain") || text.includes("daant ma") || text.includes("dant ma") ||
                  text.includes("દુખાવો") || text.includes("દુઃખાવો") || text.includes("દાંતમાં દુખાવો")) {
                  return "pain in teeth";
              }
              if (text.includes("cavity") || text.includes("decay") || text.includes("sado") || text.includes("kido") || text.includes("keeda") || text.includes("khado") || text.includes("સડો") || text.includes("કીડો")) {
                  return "dental cavity and decay";
              }
              if (text.includes("pedha") || text.includes("bleeding") || text.includes("swelling") || text.includes("masoda") || text.includes("gum") || text.includes("પેઢા")) {
                  return "gum bleeding and swelling";
              }
              if (text.includes("daant") || text.includes("dant") || text.includes("rog") || text.includes("infection") || text.includes("rct") || text.includes("sensitivity") || text.includes("દાંત")) {
                  return "pain in teeth";
              }
              if (text.includes("smile makeover") || text.includes("smile design") || text.includes("smile improve") || text.includes("smile sudharvi")) {
                  return "smile makeover and design";
              }
          }
      }
      return "";
  }

  function extractUserCity() {
      const existing = sessionStorage.getItem('usd_user_city');
      const multiCityMap = {
          "અમદાવાદ": "Ahmedabad", "સુરત": "Surat", "વડોદરા": "Vadodara", "બરોડા": "Vadodara",
          "રાજકોટ": "Rajkot", "જામનગર": "Jamnagar", "ભરૂચ": "Bharuch", "હળવદ": "Halvad",
          "ધ્રાંગધ્રા": "Dhrangadhra", "મુંબઈ": "Mumbai", "પુણે": "Pune", "દિલ્હી": "New Delhi",
          "નવી દિલ્હી": "New Delhi", "બેંગલોર": "Bangalore", "બેંગલુરુ": "Bangalore",
          "હૈદરાબાદ": "Hyderabad", "ચેન્નાઈ": "Chennai", "ગ્વાલિયર": "Gwalior", "ઈન્દોર": "Indore",
          "અહમદાબાદ": "Ahmedabad", "सूरत": "Surat", "वडोदरा": "Vadodara", "बड़ौदा": "Vadodara",
          "राजकोट": "Rajkot", "जामनगर": "Jamnagar", "भरूच": "Bharuch", "मुंबई": "Mumbai", "पुणे": "Pune"
      };
      const certifiedCities = [
          "Ahmedabad", "Surat", "Mumbai", "Pune", "Vadodara", "Rajkot", "Jamnagar",
          "Bharuch", "Halvad", "Dhrangadhra", "New Delhi", "Delhi", "Gurugram", "Gurgaon",
          "Indore", "Gwalior", "Bangalore", "Bengaluru", "Hyderabad", "Chennai", "Guntur",
          "Sangli", "Guwahati", "Faridkot", "Sri Ganganagar", "Malda"
      ];
      if (existing && existing.trim()) {
          if (multiCityMap[existing.trim()]) return multiCityMap[existing.trim()];
          const isCert = certifiedCities.some(c => c.toLowerCase() === existing.trim().toLowerCase());
          if (isCert) return existing.trim();
      }
      const savedSlots = JSON.parse(sessionStorage.getItem('usd_booking_slots') || '{}');
      if (savedSlots.city) {
          if (multiCityMap[savedSlots.city.trim()]) return multiCityMap[savedSlots.city.trim()];
          const isCert = certifiedCities.some(c => c.toLowerCase() === savedSlots.city.trim().toLowerCase());
          if (isCert) return savedSlots.city;
      }

      if (chatHistory && chatHistory.length) {
          for (let i = 0; i < chatHistory.length; i++) {
              const turn = chatHistory[i];
              if (turn.role === 'user' && turn.parts && turn.parts[0] && turn.parts[0].text) {
                  const text = turn.parts[0].text;
                  const textLower = text.toLowerCase();
                  for (const [k, v] of Object.entries(multiCityMap)) {
                      if (text.includes(k)) return v;
                  }
                  for (const c of certifiedCities) {
                      const reg = new RegExp('\\b' + c.toLowerCase() + '\\b', 'i');
                      if (reg.test(textLower)) {
                          if (c.toLowerCase() === 'delhi') return 'New Delhi';
                          if (c.toLowerCase() === 'bengaluru') return 'Bangalore';
                          if (c.toLowerCase() === 'gurgaon') return 'Gurugram';
                          if (c.toLowerCase() === 'sri ganganagar' || c.toLowerCase() === 'ganganagar') return 'Sri Ganganagar';
                          return c;
                      }
                  }
              }
          }
      }

      const uDoc = (sessionStorage.getItem('usd_user_doctor') || savedSlots.doctor_name || "").toLowerCase();
      return getCityForDoctor(uDoc);
  }

  const docCityMap = {
      "khushbu": "Vadodara", "kaveena": "Vadodara", "rakesh": "Ahmedabad", "jigar": "Ahmedabad",
      "ankit": "Ahmedabad", "neerav": "Ahmedabad", "alap": "Ahmedabad", "abbas": "Ahmedabad",
      "purvesh": "Ahmedabad", "janu": "Ahmedabad", "bharat r": "Surat", "parita": "Surat",
      "viren": "Surat", "purvi": "Surat", "priyanka": "Surat", "jay": "Surat", "vinita": "Mumbai",
      "deepika": "Mumbai", "nikita": "Mumbai", "rohan": "Mumbai", "moez": "Mumbai", "aarti": "Pune",
      "margie": "Rajkot", "pagisha": "Rajkot", "vishvaraj": "Rajkot", "hetal": "Rajkot",
      "chetariya": "Jamnagar", "prasanna": "Jamnagar", "katarmal": "Jamnagar", "hafsha": "Bharuch",
      "pankaj": "Halvad", "dilip": "Dhrangadhra", "sanjit": "New Delhi", "minu": "New Delhi",
      "agrawal": "Gurugram", "surangana": "Indore", "jaydev roy": "Indore", "himanshu": "Indore",
      "singhal": "Gwalior", "issak": "Bangalore", "srilakshmi": "Hyderabad", "jaydev": "Hyderabad",
      "reuben": "Chennai", "praneeth": "Guntur", "jagdale": "Sangli", "deshpande": "Sangli",
      "lyngdoh": "Guwahati", "sodhi": "Faridkot", "jindal": "Sri Ganganagar", "saha": "Malda"
  };

  function getCityForDoctor(docName) {
      if (!docName) return "";
      const dl = docName.toLowerCase();
      for (const [dKey, cVal] of Object.entries(docCityMap)) {
          if (dl.includes(dKey)) return cVal;
      }
      return "";
  }

  function extractUserDoctor() {
      const userCity = sessionStorage.getItem('usd_user_city') || extractUserCity();
      const existing = sessionStorage.getItem('usd_user_doctor');
      if (existing && existing.trim()) {
          if (userCity) {
              const dCity = getCityForDoctor(existing);
              if (dCity && dCity.toLowerCase() !== userCity.toLowerCase()) {
                  sessionStorage.removeItem('usd_user_doctor');
              } else {
                  return existing.trim();
              }
          } else {
              return existing.trim();
          }
      }
      const savedSlots = JSON.parse(sessionStorage.getItem('usd_booking_slots') || '{}');
      if (savedSlots.doctor_name) {
          if (userCity) {
              const dCity = getCityForDoctor(savedSlots.doctor_name);
              if (dCity && dCity.toLowerCase() !== userCity.toLowerCase()) {
                  delete savedSlots.doctor_name;
                  sessionStorage.setItem('usd_booking_slots', JSON.stringify(savedSlots));
              } else {
                  return savedSlots.doctor_name;
              }
          } else {
              return savedSlots.doctor_name;
          }
      }

      const allDocs = [
          "Dr. Rakesh Patel", "Dr. Jigar P. Thakkar", "Dr. Ankit Mataliya", "Dr. Neerav Jhaveri", "Dr. Alap D Shah", "Dr. Abbas Noorani", "Dr. Purvesh Chauhan", "Dr. Ravi Shah", "Dr. Janu Shah",
          "Dr. Bharat R. Patel", "Dr. Parita Shah", "Dr. Viren K Savani", "Dr. Purvi Patel", "Dr. Priyanka Kathiriya", "Dr. Jay Patel",
          "Dr. Vinita Tekchandani", "Dr. Deepika Dalal", "Dr. Nikita Motwani", "Dr. Rohan Bandi", "Dr. Moez Khakiani",
          "Dr. Aarti Bhatewara", "Dr. Kaveena Parikh", "Dr. Khushbu Patel",
          "Dr. Margie I Aghera", "Dr. Pagisha Sojitra", "Dr. Vishvaraj Agravat", "Dr. Hetal Buch",
          "Dr. D. J. Chetariya", "Dr. Prasanna Patel", "Dr. Bharat Katarmal",
          "Dr. Hafsha Saiyed", "Dr. Pankaj Patel", "Dr. Dilip J Parejiya",
          "Dr. Sanjit Singh", "Dr. Minu Arora", "Dr. Amit Kr. Agrawal",
          "Dr. Surangana Gupta", "Dr. Jaydev Roy", "Dr. Himanshu Sharma",
          "Dr. Aman Singhal", "Dr. Mohammed Issak", "Dr. Srilakshmi CH", "Dr. M Jaydev",
          "Dr. Reuben Joseph", "Dr. Praneeth Kumar", "Dr. Kalyani Jagdale", "Dr. Digvijay Deshpande",
          "Dr. Adil Lyngdoh", "Dr. Asmita Sodhi", "Dr. Neetu Jindal", "Dr. A K Saha"
      ];

      for (let i = 0; i < chatHistory.length; i++) {
          const turn = chatHistory[i];
          if (turn.role === 'user' && turn.parts && turn.parts[0] && turn.parts[0].text) {
              const text = turn.parts[0].text.toLowerCase();
              for (const doc of allDocs) {
                  const docClean = doc.replace(/^dr\.?\s*/i, '').toLowerCase();
                  if (text.includes(docClean) || text.includes(doc.toLowerCase())) {
                      if (userCity) {
                          const dCity = getCityForDoctor(doc);
                          if (dCity && dCity.toLowerCase() !== userCity.toLowerCase()) {
                              continue;
                          }
                      }
                      return doc;
                  }
              }
          }
      }
      return "";
  }

  function extractUserPhone() {
      const existing = sessionStorage.getItem('usd_user_phone');
      if (existing && existing.trim()) return existing.trim();
      const savedSlots = JSON.parse(sessionStorage.getItem('usd_booking_slots') || '{}');
      if (savedSlots.phone) return savedSlots.phone;

      for (let i = 0; i < chatHistory.length; i++) {
          const turn = chatHistory[i];
          if (turn.role === 'user' && turn.parts && turn.parts[0] && turn.parts[0].text) {
              const digits = (turn.parts[0].text || "").replace(/\D/g, '');
              if (digits.length === 10) return digits;
              if (digits.length === 11 && digits.startsWith('0')) return digits.slice(1);
              if (digits.length === 12 && digits.startsWith('91')) return digits.slice(2);
              if (digits.length === 13 && digits.startsWith('091')) return digits.slice(3);
          }
      }
      return "";
  }

  async function confirmReconnect(isContinue) {
      window.isAskReconnectChoicePending = false;
      document.getElementById('usd-reconnect-confirm-overlay').style.display = 'none';

      if (isContinue) {
          // Option 1: Continue previous conversation
          updateState('thinking');
          const savedSlots = JSON.parse(sessionStorage.getItem('usd_booking_slots') || '{}');
          const userName = sessionStorage.getItem('usd_user_name') || extractUserName();
          const userConcern = sessionStorage.getItem('usd_user_concern') || extractUserConcern();
          const userCity = sessionStorage.getItem('usd_user_city') || extractUserCity();
          const userDoctor = sessionStorage.getItem('usd_user_doctor') || extractUserDoctor() || (savedSlots.doctor_name || '');
          const userPhone = sessionStorage.getItem('usd_user_phone') || extractUserPhone() || (savedSlots.phone || '');

          if (userName) {
              const parts = userName.split(' ');
              if (!savedSlots.first_name) savedSlots.first_name = parts[0];
              if (!savedSlots.last_name) savedSlots.last_name = parts.length > 1 ? parts.slice(1).join(' ') : '-';
          }
          if (userCity && !savedSlots.city) savedSlots.city = userCity;
          if (userConcern && !savedSlots.message) savedSlots.message = userConcern;
          if (userDoctor && !savedSlots.doctor_name) savedSlots.doctor_name = userDoctor;
          if (userPhone && !savedSlots.phone) savedSlots.phone = userPhone;
          sessionStorage.setItem('usd_booking_slots', JSON.stringify(savedSlots));

          const reconnectPhrase = userName ? `So ${userName}, can you continue from where you left off?` : `So, can you continue from where you left off?`;
          if (socket && socket.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({
                  type: 'text_input',
                  text: `SYSTEM INSTRUCTION: The user chose to continue the previous conversation. Warmly say EXACTLY this phrase and nothing else: '${reconnectPhrase}'`,
                  history: chatHistory,
                  isVoiceMode: isVoiceMode,
                  userName: userName,
                  userConcern: userConcern,
                  userCity: userCity,
                  userDoctor: userDoctor,
                  userPhone: userPhone,
                  slots: savedSlots
              }));
          }
      } else {
          // Option 2: Start a new conversation
          document.getElementById('usd-chat-log').innerHTML = "";
          chatHistory = [];
          sessionStorage.removeItem('usd_chat_history');
          sessionStorage.removeItem('usd_user_name');
          sessionStorage.removeItem('usd_user_concern');
          sessionStorage.removeItem('usd_user_city');
          sessionStorage.removeItem('usd_user_doctor');
          sessionStorage.removeItem('usd_user_phone');
          sessionStorage.removeItem('usd_booking_slots');
          activeBotMessageDiv = null;
          activeBotTextSpan = null;
          lastBotMessageDiv = null;

          if (socket) {
              try {
                  socket.onclose = null;
                  socket.onerror = null;
                  socket.close();
              } catch (e) { }
              socket = null;
          }

          updateState('connecting', 'Starting new chat...');
          await startWebSocket();
      }
  }

  async function openChat(forceNew = false) {
      initAudio();
      requestWakeLock();
      interruptRestartHoldUntil = 0;
      const container = document.getElementById('usd-chat-container');
      const bubble = document.getElementById('usd-bubble');

      const isClosed = container && (container.style.display === 'none' || !container.classList.contains('active'));

      if (currentAgentState === 'off' || isClosed || forceNew) {

          currentAgentState = 'off';
          audioChunkQueue = [];
          activeSources.forEach(source => { try { source.stop(); } catch (e) { } });
          activeSources = [];
          isAudioPlaying = false;
          isReplyComplete = false;
          pendingAudioDecodes = 0;
          nextPlayTime = 0;
          localTurnId = 0;

          if (bubble) {
              bubble.style.display = 'none';
              bubble.classList.add('hidden');
          }

          if (container) {
              container.style.display = 'flex';
              container.classList.add('active');
          }

          const inlineRating = document.getElementById('usd-inline-rating');
          if (inlineRating) inlineRating.style.display = 'none';
          const ratingThanks = document.getElementById('usd-rating-thanks');
          if (ratingThanks) ratingThanks.style.display = 'none';

          const savedHistStr = sessionStorage.getItem('usd_chat_history');
          const hasExistingSession = !forceNew && (chatHistory.length > 0 || (savedHistStr && savedHistStr !== '[]'));

          if (hasExistingSession) {
              if (!chatHistory.length && savedHistStr) {
                  try { chatHistory = JSON.parse(savedHistStr); } catch (e) { chatHistory = []; }
              }
              isVoiceMode = sessionStorage.getItem('usd_is_voice_mode') !== 'false';

              const textControls = document.getElementById('usd-input-container');
              const voiceFooter = document.getElementById('usd-voice-controls-footer');
              const inputInner = document.querySelector('.input_box_and_icon_main');
              const textMicBtn = document.getElementById('usd-text-mic-btn');
              const textCloseBtn = document.getElementById('usd-text-close-btn');

              if (isVoiceMode) {
                  if (textControls) textControls.style.display = 'none';
                  if (voiceFooter) voiceFooter.style.display = 'flex';
                  if (textMicBtn) textMicBtn.style.display = "none";
                  if (textCloseBtn) textCloseBtn.style.display = "none";
              } else {
                  if (textControls) textControls.style.display = 'block';
                  if (inputInner) inputInner.style.display = 'flex';
                  if (voiceFooter) voiceFooter.style.display = 'none';
                  if (textMicBtn) textMicBtn.style.display = "flex";
                  if (textCloseBtn) textCloseBtn.style.display = "flex";
              }

              document.getElementById('usd-chat-log').innerHTML = "";
              chatHistory.forEach(turn => {
                  const sender = turn.role === 'model' ? 'bot' : 'user';
                  let cleanText = cleanDisplayText(turn.parts[0].text);
                  let foundTag = null;
                  if (turn.role === 'model') { foundTag = detectLocalTagFromText(cleanText); }
                  logMessage(sender, cleanText, foundTag);
              });

              updateState('thinking');
              await startWebSocket();
          } else {
              isVoiceMode = true;
              const textControls = document.getElementById('usd-input-container');
              const voiceFooter = document.getElementById('usd-voice-controls-footer');
              const textMicBtn = document.getElementById('usd-text-mic-btn');
              const textCloseBtn = document.getElementById('usd-text-close-btn');
              if (textControls) textControls.style.display = 'none';
              if (voiceFooter) voiceFooter.style.display = 'flex';
              if (textMicBtn) textMicBtn.style.display = "none";
              if (textCloseBtn) textCloseBtn.style.display = "none";

              document.getElementById('usd-chat-log').innerHTML = "";
              chatHistory = [];
              activeBotMessageDiv = null;
              activeBotTextSpan = null;
              lastBotMessageDiv = null;

              updateState('connecting', "Connecting...");
              sessionStorage.setItem('usd_chat_active', 'true');
              await startWebSocket();
          }
      }
  }

  async function startWebSocket() {
      try {
          localTurnId = 0;
          socket = new WebSocket(WS_URL);

          socket.onopen = async () => {
              updateState('online', "Online");
              isFirstChunk = true;

              // Restore slots if any exist in session storage
              const savedSlotsStr = sessionStorage.getItem('usd_session_slots');
              if (savedSlotsStr) {
                  socket.send(JSON.stringify({
                      type: 'restore_slots',
                      slots: JSON.parse(savedSlotsStr)
                  }));
              }

              await initAudio();
              updateState('thinking');

              // ⚡ 15s Heartbeat to keep WebSocket alive indefinitely ⚡
              if (window.usdHeartbeatInterval) clearInterval(window.usdHeartbeatInterval);
              window.usdHeartbeatInterval = setInterval(() => {
                  if (socket && socket.readyState === WebSocket.OPEN) {
                      socket.send(JSON.stringify({ type: 'heartbeat' }));
                  }
              }, 15000);

              if (window.isAskReconnectChoicePending) {
                  if (socket.readyState === WebSocket.OPEN) {
                      socket.send(JSON.stringify({
                          type: 'text_input',
                          text: "SYSTEM INSTRUCTION: Ask the user warmly: 'Would you like to continue our conversation or start a new one?'",
                          history: chatHistory,
                          isVoiceMode: isVoiceMode
                      }));
                  }
              } else if (chatHistory.length > 0 || sessionStorage.getItem('usd_chat_history')) {
                  window.isReconnectManual = false;
                  if (!chatHistory.length && sessionStorage.getItem('usd_chat_history')) {
                      try { chatHistory = JSON.parse(sessionStorage.getItem('usd_chat_history')); } catch (e) { }
                  }
                  const savedSlots = JSON.parse(sessionStorage.getItem('usd_booking_slots') || '{}');
                  const userName = sessionStorage.getItem('usd_user_name') || extractUserName();
                  const userConcern = sessionStorage.getItem('usd_user_concern') || extractUserConcern();
                  const userCity = sessionStorage.getItem('usd_user_city') || extractUserCity();
                  const userDoctor = sessionStorage.getItem('usd_user_doctor') || extractUserDoctor() || (savedSlots.doctor_name || '');
                  const userPhone = sessionStorage.getItem('usd_user_phone') || extractUserPhone() || (savedSlots.phone || '');

                  if (userName && !userName.includes('[') && !userName.includes('-') && !userName.includes(':') && userName.length <= 25) {
                      const parts = userName.split(' ');
                      if (!savedSlots.first_name) savedSlots.first_name = parts[0];
                      if (!savedSlots.last_name) savedSlots.last_name = parts.length > 1 ? parts.slice(1).join(' ') : '-';
                  } else if (userName && (userName.includes('[') || userName.includes('-') || userName.includes(':') || userName.length > 25)) {
                      sessionStorage.removeItem('usd_user_name');
                      delete savedSlots.first_name;
                      delete savedSlots.last_name;
                  }
                  if (userCity && !savedSlots.city) savedSlots.city = userCity;
                  if (userConcern && !savedSlots.message) savedSlots.message = userConcern;
                  if (userDoctor && !savedSlots.doctor_name) savedSlots.doctor_name = userDoctor;
                  if (userPhone && !savedSlots.phone) savedSlots.phone = userPhone;
                  const userApiId = sessionStorage.getItem('usd_api_id');
                  if (userApiId && !savedSlots.api_id) savedSlots.api_id = userApiId;
                  sessionStorage.setItem('usd_booking_slots', JSON.stringify(savedSlots));

                  const reconnectPhrase = userName ? `So ${userName}, can you continue from where you left off?` : `So, can you continue from where you left off?`;
                  if (socket.readyState === WebSocket.OPEN) {
                      socket.send(JSON.stringify({
                          type: 'text_input',
                          text: `SYSTEM INSTRUCTION: The user has just reconnected to the call. Warmly say EXACTLY this short phrase and nothing else: '${reconnectPhrase}'`,
                          history: chatHistory,
                          isVoiceMode: isVoiceMode,
                          userName: userName,
                          userConcern: userConcern,
                          userCity: userCity,
                          userDoctor: userDoctor,
                          userPhone: userPhone,
                          slots: savedSlots
                      }));
                  }
              } else {
                  if (socket.readyState === WebSocket.OPEN) {
                      socket.send(JSON.stringify({
                          type: 'text_input',
                          text: "SYSTEM INSTRUCTION: Start the conversation by warmly saying EXACTLY this specific phrase and absolutely nothing else: 'Namaste! I am Riya USD Consultant, How can we assist you today? Let's start with your beautiful name, what is your name?'",
                          history: [],
                          isVoiceMode: isVoiceMode
                      }));
                  }
              }

              try {
                  if (window.currentStreamCtx) {
                      try { window.currentStreamCtx.close(); } catch (e) { }
                      window.currentStreamCtx = null;
                  }
                  if (globalStream) {
                      try { globalStream.getTracks().forEach(t => t.stop()); } catch (e) { }
                      globalStream = null;
                  }

                  globalStream = await navigator.mediaDevices.getUserMedia({
                      audio: {
                          echoCancellation: { ideal: true },
                          noiseSuppression: { ideal: true },
                          autoGainControl: { ideal: true },
                          googNoiseSuppression: true,
                          googHighpassFilter: true,
                          googEchoCancellation: true,
                          googAutoGainControl: true,
                          googNoiseSuppression2: true,
                          channelCount: 1,
                          sampleRate: 16000
                      },
                      video: false
                  });

                  await initAudio();
                  window.recordDest = audioCtx.createMediaStreamDestination();
                  const micToRecorder = audioCtx.createMediaStreamSource(globalStream);
                  micToRecorder.connect(window.recordDest);

                  recordedAudioChunks = [];
                  let recMimeType = '';
                  if (typeof MediaRecorder !== 'undefined') {
                      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) recMimeType = 'audio/webm;codecs=opus';
                      else if (MediaRecorder.isTypeSupported('audio/webm')) recMimeType = 'audio/webm';
                      else if (MediaRecorder.isTypeSupported('audio/mp4')) recMimeType = 'audio/mp4';
                      else if (MediaRecorder.isTypeSupported('audio/aac')) recMimeType = 'audio/aac';
                  }

                  try {
                      const recOptions = {
                        audioBitsPerSecond: 16000
                      };
                      if (recMimeType) recOptions.mimeType = recMimeType;
                      const recordStream = (window.recordDest && window.recordDest.stream && window.recordDest.stream.getAudioTracks().length > 0) ? window.recordDest.stream : globalStream;
                      mediaRecorder = new MediaRecorder(recordStream, recOptions);
                      mediaRecorder.ondataavailable = (e) => {
                          if (e.data && e.data.size > 0) recordedAudioChunks.push(e.data);
                      };
                      mediaRecorder.onstop = () => {
                          if (recordedAudioChunks.length > 0) {
                              const mType = mediaRecorder.mimeType || recMimeType || 'audio/webm';
                              window.recordedAudioBlob = new Blob(recordedAudioChunks, { type: mType });
                          }
                      };
                      mediaRecorder.start(500);
                  } catch (e) {
                      console.warn("Primary recorder init failed, trying direct mic stream:", e);
                      try {
                        const fallbackOpts = recMimeType ? { mimeType: recMimeType, audioBitsPerSecond: 16000 } : { audioBitsPerSecond: 16000 };
                          mediaRecorder = new MediaRecorder(globalStream, fallbackOpts);
                          mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) recordedAudioChunks.push(e.data); };
                          mediaRecorder.onstop = () => {
                              if (recordedAudioChunks.length > 0) {
                                  window.recordedAudioBlob = new Blob(recordedAudioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                              }
                          };
                          mediaRecorder.start(500);
                      } catch (err2) {
                          try {
                              mediaRecorder = new MediaRecorder(globalStream);
                              mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) recordedAudioChunks.push(e.data); };
                              mediaRecorder.onstop = () => {
                                  if (recordedAudioChunks.length > 0) {
                                      window.recordedAudioBlob = new Blob(recordedAudioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                                  }
                              };
                              mediaRecorder.start(500);
                          } catch (err3) {
                              console.error("Direct recorder failed:", err3);
                          }
                      }
                  }

                  const streamCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                  window.currentStreamCtx = streamCtx;
                  const source = streamCtx.createMediaStreamSource(globalStream);

                  // ⚡ HARDWARE ANTI-RUMBLE HIGH-PASS FILTER (Cuts out sub-80Hz electrical hum without cutting vocal fundamentals) ⚡
                  const hpf = streamCtx.createBiquadFilter();
                  hpf.type = 'highpass';
                  hpf.frequency.value = 80; // 80Hz cutoff (preserves full human pitch range 85Hz - 8000Hz)
                  hpf.Q.value = 0.707;

                  // ⚡ VOCAL PRESENCE BOOST (Elevates speech clarity across 1.5kHz - 3.5kHz) ⚡
                  const vocalBoost = streamCtx.createBiquadFilter();
                  vocalBoost.type = 'peaking';
                  vocalBoost.frequency.value = 2200; // 2.2kHz speech center
                  vocalBoost.Q.value = 1.0;
                  vocalBoost.gain.value = 2.0; // +2.0dB natural clarity boost

                  source.connect(hpf);
                  hpf.connect(vocalBoost);

                  const bufferSize = 2048; // Low-latency 128ms streaming frames (Google AI Studio standard)
                  const processor = streamCtx.createScriptProcessor(bufferSize, 1, 1);
                  const analyser = streamCtx.createAnalyser();
                  analyser.fftSize = 512;

                  const silenceGain = streamCtx.createGain();
                  silenceGain.gain.value = 0;

                  vocalBoost.connect(analyser);
                  vocalBoost.connect(processor);
                  processor.connect(silenceGain);
                  silenceGain.connect(streamCtx.destination);

                  // ⚡ CONTINUOUS REAL-TIME AUDIO STREAMING TO GEMINI LIVE (Official Google AI Studio Flow) ⚡
                  processor.onaudioprocess = (e) => {
                      if (isMicSoftwareMuted) return;

                      const inputData = e.inputBuffer.getChannelData(0);
                      const pcm16 = new Int16Array(inputData.length);
                      let sumSquares = 0;
                      for (let i = 0; i < inputData.length; i++) {
                          let sample = inputData[i] * 2.0;
                          if (sample > 1) sample = 1; else if (sample < -1) sample = -1;
                          let val = sample * 32767;
                          pcm16[i] = val;
                          sumSquares += val * val;
                      }
                      let rms = Math.sqrt(sumSquares / pcm16.length);

                      // ⚡ ACOUSTIC SPEAKER ECHO GUARD ⚡
                      // Only suppress soft mic audio if the speaker is PHYSICALLY playing audio right at this moment
                      const isPhysicallyPlaying = activeSources.length > 0 || (audioCtx && audioCtx.currentTime < nextPlayTime);
                      if (isPhysicallyPlaying) {
                          if (rms < 1200) {
                              return;
                          }
                      }

                      if (socket && socket.readyState === WebSocket.OPEN) {
                          socket.send(pcm16.buffer);
                      }
                  };
              } catch (err) {
                  console.error("Microphone access denied or error:", err);
                  if (isVoiceMode) { toggleChatMode(); }
                  updateState('listening', "Mic disabled. Chat mode active.");
              }
          };

          socket.onmessage = async (event) => {
              const data = JSON.parse(event.data);

              if (data.type === 'user_speaking_status') {
                  if (data.is_speaking) {
                      window.isUserSpeaking = true;
                      showUserSpeakingIndicator();
                  } else {
                      window.isUserSpeaking = false;
                      removeUserSpeakingIndicator();
                  }
                  return;
              }

              if (isVoiceMode && data.turnId !== undefined) {
                  localTurnId = data.turnId;
              }

              if (data.type === 'interrupted' || (data.serverContent && data.serverContent.interrupted)) {
                  audioChunkQueue = [];
                  activeSources.forEach(source => { try { source.stop(); } catch (e) { } });
                  activeSources = [];
                  isAudioPlaying = false;
                  nextPlayTime = 0;
                  pendingAudioDecodes = 0;

                  // ⚡ WIPES ANY PENDING BUBBLE ⚡
                  lastBotMessageDiv = null;
                  if (activeBotMessageDiv) {
                      if (!activeBotMessageDiv.dataset.rawText || activeBotMessageDiv.dataset.rawText.trim() === "") {
                          activeBotMessageDiv.remove();
                      }
                  }
                  activeBotMessageDiv = null;
                  activeUserMessageDiv = null;

                  updateState('listening');
                  return;
              }

              if (data.type === 'error' && data.error === "Session timed out due to inactivity.") {
                  console.log("Inactivity timeout from backend. Disconnecting...");
                  disconnectToOffline();
                  return;
              }

              if (data.type === 'idle' || data.type === 'error') {
                  removeBotThinkingIndicator();
                  if (data.type === 'error') console.error("Backend Error:", data.error);
                  liveUserText = "";
                  isReplyComplete = false;
                  audioChunkQueue = [];

                  lastBotMessageDiv = null;
                  activeBotMessageDiv = null;
                  activeUserMessageDiv = null;

                  const interimBox = document.getElementById('usd-interim-text');
                  if (interimBox) interimBox.innerText = "";
                  updateState('listening');
              }
              else if (data.type === 'interrupted') {
                  removeBotThinkingIndicator();
                  console.log("⚡ Gemini Official VAD Interruption Signal Received!");
                  localTurnId++;
                  audioChunkQueue = [];
                  activeSources.forEach(src => { try { src.stop(); } catch (e) { } });
                  activeSources = [];
                  isAudioPlaying = false;
                  nextPlayTime = 0;
                  pendingAudioDecodes = 0;

                  if (activeBotMessageDiv) {
                      const rawText = activeBotMessageDiv.dataset.rawText || "";
                      if (rawText.trim()) {
                          const cleanText = cleanLiveStreamText(rawText);
                          const botP = activeBotMessageDiv.querySelector('.usd-msg-text');
                          if (botP && !botP.innerText.endsWith("...")) {
                              botP.innerText = cleanText + " ...";
                          }
                          const last = chatHistory[chatHistory.length - 1];
                          if (!(last && last.role === 'model' && last.parts && last.parts[0] && last.parts[0].text.includes(cleanText))) {
                              chatHistory.push({ role: "model", parts: [{ text: cleanText + " ..." }] });
                              saveHistory();
                          }
                          lastBotMessageDiv = activeBotMessageDiv;
                      } else {
                          activeBotMessageDiv.remove();
                      }
                  }
                  activeBotMessageDiv = null;
                  updateState('listening');
              }
              else if (data.type === 'status_update') {
                  if (data.status === 'submitting') {
                      showBotThinkingIndicator("Riya is submitting");
                      const interimBox = document.getElementById('usd-interim-text');
                      if (interimBox) {
                          interimBox.innerText = "Riya is submitting...";
                          interimBox.style.color = "#F3DC87";
                      }
                  } else if (data.status === 'adding_details') {
                      showBotThinkingIndicator("Riya is adding details");
                      const interimBox = document.getElementById('usd-interim-text');
                      if (interimBox) {
                          interimBox.innerText = "Riya is adding details...";
                          interimBox.style.color = "#F3DC87";
                      }
                  } else if (data.status === 'thinking') {
                      showBotThinkingIndicator("Riya is thinking");
                  }
              }
              else if (data.type === 'user_text_chunk') {
                  silenceNudgeCount = 0;
                  if (!activeUserMessageDiv) {
                      const log = document.getElementById('usd-chat-log');
                      const lastMsg = log ? log.lastElementChild : null;
                      if (lastMsg && lastMsg.classList.contains('usd-msg-user') && lastMsg.dataset.isLive) {
                          activeUserMessageDiv = lastMsg;
                      } else {
                          activeUserMessageDiv = logMessage('user', "");
                          activeUserMessageDiv.dataset.isLive = "true";
                          activeUserMessageDiv.dataset.rawText = "";
                      }
                  }
                  activeUserMessageDiv.dataset.rawText = (activeUserMessageDiv.dataset.rawText || "") + (data.text || "");
                  const rawUserText = activeUserMessageDiv.dataset.rawText;
                  const userP = activeUserMessageDiv.querySelector('.usd-msg-text');
                  if (userP) userP.innerText = cleanLiveStreamText(rawUserText);

                  // ⚡ DETECT TAG STRICTLY FROM USER INPUT SPEECH STREAM ⚡
                  const uTag = detectUserTagFromText(rawUserText);
                  if (uTag) activeTag = uTag;

                  const log = document.getElementById('usd-chat-log');
                  if (log) log.scrollTop = log.scrollHeight;
              }
              else if (data.type === 'bot_text_chunk') {
                  removeBotThinkingIndicator();
                  if (data.slots) {
                      sessionStorage.setItem('usd_booking_slots', JSON.stringify(data.slots));
                      if (data.slots.first_name) {
                          const fn = (data.slots.first_name + (data.slots.last_name && data.slots.last_name !== '-' ? ' ' + data.slots.last_name : '')).trim();
                          sessionStorage.setItem('usd_user_name', fn);
                      }
                      if (data.slots.city) sessionStorage.setItem('usd_user_city', data.slots.city);
                      if (data.slots.message) sessionStorage.setItem('usd_user_concern', data.slots.message);
                      if (data.slots.doctor_name) sessionStorage.setItem('usd_user_doctor', data.slots.doctor_name);
                      if (data.slots.phone) sessionStorage.setItem('usd_user_phone', data.slots.phone);
                  }
                  if (!activeBotMessageDiv) {
                      const log = document.getElementById('usd-chat-log');
                      const lastMsg = log ? log.lastElementChild : null;
                      if (lastMsg && lastMsg.classList.contains('usd-msg-bot') && lastMsg.dataset.isLive) {
                          activeBotMessageDiv = lastMsg;
                      } else {
                          activeBotMessageDiv = logMessage('bot', "");
                          activeBotMessageDiv.dataset.isLive = "true";
                          activeBotMessageDiv.dataset.rawText = "";
                          lastBotMessageDiv = activeBotMessageDiv;
                      }
                  }
                  activeBotMessageDiv.dataset.rawText = (activeBotMessageDiv.dataset.rawText || "") + (data.text || "");
                  const rawText = activeBotMessageDiv.dataset.rawText;
                  const botP = activeBotMessageDiv.querySelector('.usd-msg-text');
                  if (botP) {
                      botP.innerText = cleanLiveStreamText(rawText);
                  }

                  // ⚡ ATTACH LINK CARD STRICTLY FROM USER-DERIVED activeTag (NEVER FROM BOT TEXT) ⚡
                  const streamTag = activeTag || data.tag;
                  if (streamTag && usdLinks[streamTag]) {
                      appendLinkButton(activeBotMessageDiv, streamTag);
                  }
                  const log = document.getElementById('usd-chat-log');
                  if (log) log.scrollTop = log.scrollHeight;
              }
              else if (data.type === 'user_spoken_text') {
                  silenceNudgeCount = 0;
                  const cleanUserText = cleanDisplayText(data.text || "");
                  if (cleanUserText) {
                      // If we are waiting for a reconnect choice, intercept the spoken input
                      if (window.isAskReconnectChoicePending) {
                          const textLower = cleanUserText.toLowerCase();
                          if (textLower.includes("continue") || textLower.includes("previous") || textLower.includes("old") || textLower.includes("where we left") || textLower.includes("left off") || textLower.includes("yes") || textLower.includes("ha") || textLower.includes("haan") || textLower.includes("kar do") || textLower.includes("chalu")) {
                              confirmReconnect(true);
                              return;
                          } else if (textLower.includes("new") || textLower.includes("start over") || textLower.includes("fresh") || textLower.includes("restart") || textLower.includes("no") || textLower.includes("nathi") || textLower.includes("nahi")) {
                              confirmReconnect(false);
                              return;
                          }
                      }

                      const userTag = detectUserTagFromText(cleanUserText);
                      if (userTag) activeTag = userTag;

                      if (activeUserMessageDiv) {
                          const userP = activeUserMessageDiv.querySelector('.usd-msg-text');
                          if (userP) userP.innerText = cleanUserText;
                          delete activeUserMessageDiv.dataset.isLive;
                      } else {
                          const log = document.getElementById('usd-chat-log');
                          const lastMsg = log ? log.lastElementChild : null;
                          if (lastMsg && lastMsg.classList.contains('usd-msg-user')) {
                              const userP = lastMsg.querySelector('.usd-msg-text');
                              if (userP) userP.innerText = cleanUserText;
                              delete lastMsg.dataset.isLive;
                          } else {
                              logMessage('user', cleanUserText);
                          }
                      }
                      if (data.slots) {
                          sessionStorage.setItem('usd_booking_slots', JSON.stringify(data.slots));
                          if (data.slots.first_name) {
                              const fn = (data.slots.first_name + (data.slots.last_name && data.slots.last_name !== '-' ? ' ' + data.slots.last_name : '')).trim();
                              sessionStorage.setItem('usd_user_name', fn);
                          }
                          if (data.slots.city) sessionStorage.setItem('usd_user_city', data.slots.city);
                          if (data.slots.message) sessionStorage.setItem('usd_user_concern', data.slots.message);
                          if (data.slots.doctor_name) sessionStorage.setItem('usd_user_doctor', data.slots.doctor_name);
                          if (data.slots.phone) sessionStorage.setItem('usd_user_phone', data.slots.phone);
                      }
                      addUserHistoryIfNew(cleanUserText);
                      liveUserText = "";
                      activeUserMessageDiv = null;
                      const interimBox = document.getElementById('usd-interim-text');
                      if (interimBox && interimBox.innerText.includes("You:")) {
                          interimBox.innerText = "Answering...";
                          interimBox.style.color = "#ffffff";
                      }
                  }
              }
              else if (data.type === 'bot_spoken_text') {
                  removeBotThinkingIndicator();
                  if (data.slots) {
                      sessionStorage.setItem('usd_booking_slots', JSON.stringify(data.slots));
                      if (data.slots.first_name) {
                          const fn = (data.slots.first_name + (data.slots.last_name && data.slots.last_name !== '-' ? ' ' + data.slots.last_name : '')).trim();
                          sessionStorage.setItem('usd_user_name', fn);
                      }
                      if (data.slots.city) sessionStorage.setItem('usd_user_city', data.slots.city);
                      if (data.slots.message) sessionStorage.setItem('usd_user_concern', data.slots.message);
                      if (data.slots.doctor_name) sessionStorage.setItem('usd_user_doctor', data.slots.doctor_name);
                      if (data.slots.phone) sessionStorage.setItem('usd_user_phone', data.slots.phone);
                  }
                  const finalText = cleanDisplayText(data.text);
                  if (finalText && finalText !== "...") {
                      const tagToUse = data.tag || activeTag;
                      if (activeBotMessageDiv) {
                          const botP = activeBotMessageDiv.querySelector('.usd-msg-text');
                          if (botP) botP.innerText = finalText;
                          delete activeBotMessageDiv.dataset.isLive;
                          lastBotMessageDiv = activeBotMessageDiv;
                      } else {
                          const log = document.getElementById('usd-chat-log');
                          const lastMsg = log ? log.lastElementChild : null;
                          if (lastMsg && lastMsg.classList.contains('usd-msg-bot')) {
                              const botP = lastMsg.querySelector('.usd-msg-text');
                              if (botP) botP.innerText = finalText;
                              delete lastMsg.dataset.isLive;
                              lastBotMessageDiv = lastMsg;
                          } else {
                              lastBotMessageDiv = logMessage('bot', finalText, tagToUse);
                          }
                      }

                      const last = chatHistory[chatHistory.length - 1];
                      if (!(last && last.role === 'model' && last.parts && last.parts[0] && last.parts[0].text === finalText)) {
                          chatHistory.push({ role: "model", parts: [{ text: finalText }] });
                          saveHistory();
                      }

                      if (tagToUse && usdLinks[tagToUse]) {
                          appendLinkButton(lastBotMessageDiv, tagToUse);
                      }

                      activeBotMessageDiv = null;
                      const log = document.getElementById('usd-chat-log');
                      if (log) log.scrollTop = log.scrollHeight;
                  }
              }
              else if (data.type === 'sync_slots') {
                  if (data.slots) {
                      sessionStorage.setItem('usd_session_slots', JSON.stringify(data.slots));
                      sessionStorage.setItem('usd_booking_slots', JSON.stringify(data.slots));
                      if (data.slots.submission_id) {
                          sessionStorage.setItem('usd_submission_id', data.slots.submission_id);
                      }
                      if (data.slots.api_id) {
                          sessionStorage.setItem('usd_api_id', data.slots.api_id);
                      }
                      if (data.slots.first_name) {
                          const fn = (data.slots.first_name + (data.slots.last_name && data.slots.last_name !== '-' ? ' ' + data.slots.last_name : '')).trim();
                          sessionStorage.setItem('usd_user_name', fn);
                      }
                      if (data.slots.city) sessionStorage.setItem('usd_user_city', data.slots.city);
                      if (data.slots.message) sessionStorage.setItem('usd_user_concern', data.slots.message);
                      if (data.slots.doctor_name) sessionStorage.setItem('usd_user_doctor', data.slots.doctor_name);
                      if (data.slots.phone) sessionStorage.setItem('usd_user_phone', data.slots.phone);
                  }
              }
              else if (data.type === 'audio_chunk') {
                  removeBotThinkingIndicator();
                  audioChunkQueue.push(data);
                  processAudioQueue();
              }
              else if (data.type === 'reply_complete') {
                  removeBotThinkingIndicator();
                  isReplyComplete = true;
                  liveUserText = "";
                  const interimBox = document.getElementById('usd-interim-text');
                  if (interimBox) { interimBox.innerText = ""; }

                  if (data.slots) {
                      sessionStorage.setItem('usd_booking_slots', JSON.stringify(data.slots));
                      sessionStorage.setItem('usd_session_slots', JSON.stringify(data.slots));
                      if (data.slots.submission_id) {
                          sessionStorage.setItem('usd_submission_id', data.slots.submission_id);
                      }
                      if (data.slots.api_id) {
                          sessionStorage.setItem('usd_api_id', data.slots.api_id);
                      }
                      if (data.slots.first_name) {
                          const fn = (data.slots.first_name + (data.slots.last_name && data.slots.last_name !== '-' ? ' ' + data.slots.last_name : '')).trim();
                          sessionStorage.setItem('usd_user_name', fn);
                      }
                      if (data.slots.city) sessionStorage.setItem('usd_user_city', data.slots.city);
                      if (data.slots.message) sessionStorage.setItem('usd_user_concern', data.slots.message);
                      if (data.slots.doctor_name) sessionStorage.setItem('usd_user_doctor', data.slots.doctor_name);
                      if (data.slots.phone) sessionStorage.setItem('usd_user_phone', data.slots.phone);
                      // ⚡ Auto-submit transcript and recording to Gmail the moment appointment is confirmed ⚡
                      if (data.slots.is_submitted && !window.isAppointmentConfirmedTranscriptSent) {
                          window.isAppointmentConfirmedTranscriptSent = true;
                          setTimeout(() => {
                              submitChatData("Appointment Confirmed");
                          }, 1200);
                      }
                  }

                  const finalText = cleanDisplayText(data.botText || "").trim();
                  const finalTag = data.tag || activeTag;

                  if (finalText) {
                      if (activeBotMessageDiv) {
                          const botP = activeBotMessageDiv.querySelector('.usd-msg-text');
                          if (botP) botP.innerText = finalText;
                          lastBotMessageDiv = activeBotMessageDiv;
                      } else if (lastBotMessageDiv) {
                          const botP = lastBotMessageDiv.querySelector('.usd-msg-text');
                          if (botP && (!botP.innerText || botP.innerText.trim() === "")) {
                              botP.innerText = finalText;
                          }
                      } else {
                          lastBotMessageDiv = logMessage('bot', finalText, finalTag);
                      }

                      const last = chatHistory[chatHistory.length - 1];
                      if (!(last && last.role === 'model' && last.parts && last.parts[0] && last.parts[0].text === finalText)) {
                          chatHistory.push({ role: "model", parts: [{ text: finalText }] });
                          saveHistory();
                      }
                  }

                  if (finalTag && usdLinks[finalTag]) {
                      if (lastBotMessageDiv) {
                          appendLinkButton(lastBotMessageDiv, finalTag);
                      }
                  }
                  activeTag = null; // ⚡ Reset for next user turn ⚡

                  activeBotMessageDiv = null;
                  activeUserMessageDiv = null;

                  if (!isVoiceMode) {
                      updateState('listening');
                      if (finalTag === '[END_CHAT]') setTimeout(() => closeChat(true), 2000);
                  } else {
                      checkBotFinishedSpeaking();
                      if (finalTag === '[END_CHAT]') setTimeout(() => closeChat(true), 2000);
                  }
              }
          };
          socket.onerror = () => { updateState('listening'); };
          socket.onclose = (event) => {
              console.log("WebSocket closed:", event);
              disconnectToOffline();
          };
      } catch (err) {
          updateState('listening');
      }
  }

  function closeChatBtnClicked() {
      if (currentAgentState === 'off') {
          closeChat(false);
      } else {
          document.getElementById('usd-end-confirm-overlay').style.display = 'flex';
      }
  }

  function confirmEndChat(isYes) {
      document.getElementById('usd-end-confirm-overlay').style.display = 'none';
      if (isYes) {
          updateState('thinking');

          audioChunkQueue = [];
          activeSources.forEach(source => { try { source.stop(); } catch (e) { } });
          activeSources = [];
          isAudioPlaying = false;

          if (mediaRecorder && mediaRecorder.state !== 'inactive') {
              mediaRecorder.onstop = () => {
                  const mimeType = mediaRecorder.mimeType || 'audio/webm';
                  window.recordedAudioBlob = new Blob(recordedAudioChunks, { type: mimeType });
              };
              try { mediaRecorder.stop(); } catch (e) { }
          }

          const goodbyeText = "Thanks for talking with Ultimate Smile Design. Please feel free to check out our reviews or reach out to us.";
          logMessage('bot', goodbyeText);

          if (isVoiceMode) {
              fetch(`${CLOUD_RUN_URL}/voice-agent/api/tts/`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ text: goodbyeText, lang: 'en-IN' })
              })
                  .then(res => res.json())
                  .then(data => {
                      isReplyComplete = true;
                      audioChunkQueue.push(data);
                      processAudioQueue();
                  })
                  .catch(e => console.error("TTS Error:", e));
          }

          closeChat(true);
      }
  }

  function closeChat(showRating = false) {
      updateState('off');

      // ⚡ Finalize audio recording BEFORE stopping microphone tracks ⚡
      if (typeof mediaRecorder !== 'undefined' && mediaRecorder && mediaRecorder.state !== 'inactive') {
          try {
              if (typeof mediaRecorder.requestData === 'function') mediaRecorder.requestData();
              mediaRecorder.stop();
          } catch (e) { }
      }
      if (recordedAudioChunks && recordedAudioChunks.length > 0 && !window.recordedAudioBlob) {
          const mType = (typeof mediaRecorder !== 'undefined' && mediaRecorder && mediaRecorder.mimeType) ? mediaRecorder.mimeType : 'audio/webm';
          window.recordedAudioBlob = new Blob(recordedAudioChunks, { type: mType });
      }

      if (window.myvad) {
          window.myvad.pause();
          window.myvad = null;
      }
      releaseWakeLock();

      if (window.usdHeartbeatInterval) {
          clearInterval(window.usdHeartbeatInterval);
          window.usdHeartbeatInterval = null;
      }
      if (window.currentStreamCtx) {
          try { window.currentStreamCtx.close(); } catch (e) { }
          window.currentStreamCtx = null;
      }

      if (socket) {
          socket.onclose = null;
          socket.close();
          socket = null;
      }
      if (globalStream) {
          globalStream.getTracks().forEach(track => track.stop());
          globalStream = null;
      }

      // ⚡ GUARANTEE SUBMISSION: Submit transcript and recording immediately when chat closes/ends ⚡
      if (!window.isChatFeedbackSubmitted) {
          submitChatData(showRating ? "Call Completed (Pending Rating)" : "Call Ended");
      }

      sessionStorage.removeItem('usd_chat_active');

      const bubble = document.getElementById('usd-bubble');
      const container = document.getElementById('usd-chat-container');

      if (showRating) {
          document.getElementById('usd-input-container').style.display = 'none';
          document.getElementById('usd-voice-controls-footer').style.display = 'none';
          const ratingDiv = document.getElementById('usd-inline-rating');
          if (ratingDiv) ratingDiv.style.display = 'flex';
          logMessage('system', 'The chat has ended. Please rate your experience below.');
      } else {
          if (container) {
              container.style.display = '';
              container.classList.remove('active');
          }
          if (bubble) {
              bubble.style.display = '';
              bubble.classList.remove('hidden');
          }

          const ratingDiv = document.getElementById('usd-inline-rating');
          if (ratingDiv) ratingDiv.style.display = 'none';
          const thanksDiv = document.getElementById('usd-rating-thanks');
          if (thanksDiv) thanksDiv.style.display = 'none';
          document.querySelectorAll('.usd-star').forEach(s => {
              s.style.color = '#333333';
              s.style.textShadow = '0 2px 4px rgba(0,0,0,0.5)';
          });

          window.uploadedAudioUrl = null;
          window.isChatFeedbackSubmitted = false;
      }
  }

  async function submitRating(stars) {
      const starElements = document.querySelectorAll('.usd-star');
      starElements.forEach((s, index) => {
          s.style.color = index < stars ? '#FFD700' : '#444';
          s.style.textShadow = index < stars ? '0 0 10px rgba(255, 215, 0, 0.6)' : '0 2px 4px rgba(0,0,0,0.5)';
      });
      const thanksDiv = document.getElementById('usd-rating-thanks');
      if (thanksDiv) thanksDiv.style.display = 'block';

      window.isChatFeedbackSubmitted = false;
      window.isSubmittingChatData = false;
      await submitChatData(`${stars}/5 Stars`);

      // ⚡ Fresh Start on Re-open: Once call is rated & concluded, clear old conversation so re-opening starts with fresh greeting ⚡
      chatHistory = [];
      sessionStorage.removeItem('usd_chat_history');
      sessionStorage.removeItem('usd_user_name');
      sessionStorage.removeItem('usd_user_concern');
      sessionStorage.removeItem('usd_user_city');
      sessionStorage.removeItem('usd_user_doctor');
      sessionStorage.removeItem('usd_user_phone');
      sessionStorage.removeItem('usd_booking_slots');
      sessionStorage.removeItem('usd_chat_active');

      setTimeout(() => { closeChat(false); }, 1500);
  }

  window.addEventListener('beforeunload', () => {
      if (!window.isChatFeedbackSubmitted && chatHistory && chatHistory.length > 0) {
          submitChatData("Call Ended (Tab Closed)");
      }
  });

  async function submitTextMessage() {
      const inputEl = document.getElementById('usd-text-input');
      const userText = cleanDisplayText(inputEl.value.trim());
      if (!userText) return;

      inputEl.value = '';
      removeUserTypingIndicator();
      removeUserSpeakingIndicator();
      silenceNudgeCount = 0;
      if (window.resetSilenceTimer) window.resetSilenceTimer();
      const userTag = detectUserTagFromText(userText);
      if (userTag) activeTag = userTag;

      if (!socket || socket.readyState !== WebSocket.OPEN) {
          updateState('connecting', 'Connecting...');
          await startWebSocket();
          for (let i = 0; i < 30; i++) {
              if (socket && socket.readyState === WebSocket.OPEN) break;
              await new Promise(r => setTimeout(r, 100));
          }
      }

      localTurnId++;

      // ⚡ Text Input cleanly wipes audio UI too ⚡
      audioChunkQueue = [];
      activeSources.forEach(source => { try { source.stop(); } catch (e) { } });
      activeSources = [];
      isAudioPlaying = false;
      nextPlayTime = 0;
      pendingAudioDecodes = 0;
      lastBotMessageDiv = null;
      if (activeBotMessageDiv) {
          if (!activeBotMessageDiv.dataset.rawText || activeBotMessageDiv.dataset.rawText.trim() === "") {
              activeBotMessageDiv.remove();
          }
      }
      activeBotMessageDiv = null;

      logMessage('user', userText);
      addUserHistoryIfNew(userText);

      updateState('thinking');

      if (socket && socket.readyState === WebSocket.OPEN) {
          const savedSlots = JSON.parse(sessionStorage.getItem('usd_booking_slots') || '{}');
          const userName = sessionStorage.getItem('usd_user_name') || extractUserName();
          const userConcern = sessionStorage.getItem('usd_user_concern') || extractUserConcern();
          const userCity = sessionStorage.getItem('usd_user_city') || extractUserCity();
          const userDoctor = sessionStorage.getItem('usd_user_doctor') || (savedSlots.doctor_name || '');
          const userPhone = sessionStorage.getItem('usd_user_phone') || (savedSlots.phone || '');

          socket.send(JSON.stringify({
              type: 'text_input',
              text: userText,
              history: chatHistory,
              isVoiceMode: isVoiceMode,
              userName: userName,
              userConcern: userConcern,
              userCity: userCity,
              userDoctor: userDoctor,
              userPhone: userPhone,
              slots: savedSlots
          }));
      }
  }

  function handleKeyPress(event) {
      if (event.key === 'Enter') {
          event.preventDefault();
          submitTextMessage();
      }
  }

  function handleLinkClick(tag) {
      const linkInfo = usdLinks[tag];
      if (!linkInfo) return;

      logMessage('bot', "Redirecting you now...");
      chatHistory.push({ role: "model", parts: [{ text: "Redirecting you now..." }] });
      saveHistory();

      // ⚡ Submit conversation lead & transcript to Gmail on Link Click ⚡
      submitChatData(`Clicked Action Link: ${linkInfo.label} (${tag})`);

      window.open(linkInfo.url, '_blank');
      updateState('listening');
  }

  function logMessage(sender, text, tag = null) {
      const log = document.getElementById('usd-chat-log');
      const msgDiv = document.createElement('div');

      if (sender === 'user') {
          msgDiv.className = 'user_message usd-msg-user';
      } else if (sender === 'bot') {
          msgDiv.className = 'bot_message usd-msg-bot';
      } else {
          msgDiv.className = 'msg msg-system';
      }

      const p = document.createElement('p');
      p.className = 'usd-msg-text';

      if (sender === 'user') p.innerText = text;
      else if (sender === 'bot') p.innerText = text;
      else p.innerText = text;

      msgDiv.appendChild(p);

      if (tag && usdLinks[tag]) {
          const btn = document.createElement('button');
          btn.className = 'usd-link-card';
          btn.innerText = usdLinks[tag].label;
          btn.onclick = () => handleLinkClick(tag);
          msgDiv.appendChild(btn);
      }

      if (sender === 'user' && activeBotMessageDiv && activeBotMessageDiv.parentNode === log) {
          log.insertBefore(msgDiv, activeBotMessageDiv);
      } else {
          log.appendChild(msgDiv);
      }
      log.scrollTop = log.scrollHeight;

      if (sender === 'bot') {
          lastBotMessageDiv = msgDiv;
      }

      return msgDiv;
  }

  async function submitChatData(ratingLabel = "Call Ended") {
      if (window.isSubmittingChatData) return;
      window.isSubmittingChatData = true;

      try {
          let transcriptText = "";
          const log = document.getElementById('usd-chat-log');
          if (log) {
              const msgs = log.querySelectorAll('.user_message, .bot_message, .msg, .usd-msg-user, .usd-msg-bot');
              msgs.forEach(m => {
                  const isUser = m.classList.contains('user_message') || m.classList.contains('usd-msg-user');
                  const isBot = m.classList.contains('bot_message') || m.classList.contains('usd-msg-bot');
                  const p = m.querySelector('.usd-msg-text');
                  const txt = p ? p.innerText.trim() : m.innerText.trim();
                  if (txt && !txt.includes("Riya is typing") && !txt.includes("Riya is thinking") && !txt.includes("Listening...") && !txt.includes("Riya is submitting")) {
                      if (isUser) transcriptText += `User: ${txt}\n\n`;
                      else if (isBot) transcriptText += `Assistant (Riya): ${txt}\n\n`;
                  }
              });
          }

          if (!transcriptText.trim() && chatHistory && chatHistory.length > 0) {
              chatHistory.forEach(turn => {
                  const role = turn.role === 'model' ? 'Assistant (Riya)' : 'User';
                  const txt = turn.parts && turn.parts[0] ? turn.parts[0].text : '';
                  if (txt && !txt.startsWith('SYSTEM INSTRUCTION')) {
                      transcriptText += `${role}: ${txt}\n\n`;
                  }
              });
          }

          if (!transcriptText.trim()) {
              transcriptText = "Conversation completed (no text messages exchanged).";
          }

          // Finalize media recorder if active
          if (typeof mediaRecorder !== 'undefined' && mediaRecorder && mediaRecorder.state === 'recording') {
              try {
                  if (typeof mediaRecorder.requestData === 'function') mediaRecorder.requestData();
                  mediaRecorder.stop();
                  await new Promise(r => setTimeout(r, 300));
              } catch (e) { }
          }

          if (!window.recordedAudioBlob && recordedAudioChunks && recordedAudioChunks.length > 0) {
              const mimeType = (typeof mediaRecorder !== 'undefined' && mediaRecorder && mediaRecorder.mimeType) ? mediaRecorder.mimeType : 'audio/webm';
              window.recordedAudioBlob = new Blob(recordedAudioChunks, { type: mimeType });
          }

          let audioBase64 = null;
          let audioFilename = 'voice_recording.webm';

          if (window.recordedAudioBlob && window.recordedAudioBlob.size > 0) {
              const ext = (window.recordedAudioBlob.type && window.recordedAudioBlob.type.includes('mp4')) ? 'mp4' : 'webm';
              audioFilename = `voice_recording.${ext}`;
              try {
                  audioBase64 = await new Promise((resolve) => {
                      const reader = new FileReader();
                      reader.onloadend = () => {
                          resolve(typeof reader.result === 'string' ? reader.result : null);
                      };
                      reader.onerror = () => resolve(null);
                      reader.readAsDataURL(window.recordedAudioBlob);
                  });
                  console.log(`[INFO] Submitting feedback with audio attachment: ${window.recordedAudioBlob.size} bytes (${window.recordedAudioBlob.type})`);
              } catch (convErr) {
                  console.warn("[WARN] Could not convert audio blob to base64:", convErr);
              }
          } else {
              console.log("[INFO] Submitting feedback (transcript only, no audio blob)");
          }

          const payload = {
              rating: ratingLabel,
              transcript: transcriptText,
              audio_base64: audioBase64,
              audio_filename: audioFilename
          };

          // 1. Dispatch over active WebSocket if available (instant delivery, zero CORS)
          if (socket && socket.readyState === WebSocket.OPEN) {
              try {
                  socket.send(JSON.stringify({
                      type: 'submit_feedback',
                      payload: payload
                  }));
                  console.log("[INFO] Dispatched transcript and audio over active WebSocket");
              } catch (wsErr) {
                  console.warn("[WARN] Could not send feedback over WebSocket:", wsErr);
              }
          }

          // 2. Dispatch via HTTP POST (with dual fallback: local/origin endpoint first, then Cloud Run)
          let submittedSuccessfully = false;

          try {
              const localUrl = (window.location.origin && window.location.origin.startsWith('http')) 
                  ? `${window.location.origin}/voice-agent/api/submit-feedback/` 
                  : '/voice-agent/api/submit-feedback/';
              const resp = await fetch(localUrl, {
                  method: 'POST',
                  body: JSON.stringify(payload),
                  headers: { 'Content-Type': 'application/json' }
              });
              if (resp.ok) {
                  const resJson = await resp.json();
                  console.log("[INFO] Transcript and audio submitted successfully to marketing email (via local origin):", resJson);
                  submittedSuccessfully = true;
              }
          } catch (localErr) {
              console.warn("[WARN] Origin submit-feedback failed:", localErr);
          }

          if (submittedSuccessfully) {
              window.isChatFeedbackSubmitted = true;
          }
      } catch (err) {
          console.error("[ERROR] in submitChatData:", err);
      } finally {
          window.isSubmittingChatData = false;
      }
  }

  window.submitChatData = submitChatData;
  window.openChat = openChat;
  window.closeChat = closeChat;
  window.confirmEndChat = confirmEndChat;
  window.confirmReconnect = confirmReconnect;
  window.toggleChatMode = toggleChatMode;
  window.closeChatBtnClicked = closeChatBtnClicked;
  window.submitTextMessage = submitTextMessage;
  window.submitRating = submitRating;
  window.handleKeyPress = handleKeyPress;
  window.handleLinkClick = handleLinkClick;
  window.handleCenterMicClick = handleCenterMicClick;
  window.handleTypingAutoConnect = handleTypingAutoConnect;
  window.ensureConnected = ensureConnected;
