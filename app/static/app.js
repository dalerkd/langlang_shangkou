(() => {
  async function requestFragment(method, url, body) {
    const response = await fetch(url, {
      method,
      body,
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }
    return response.text();
  }

  function swap(targetSelector, html, mode) {
  const target = document.querySelector(targetSelector);
  if (!target) {
    return;
  }
  if (mode === "outerHTML") {
    target.outerHTML = html;
    return;
  }
  target.innerHTML = html;
  if (targetSelector === "#references") {
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}
  function formatLocalTime(utcString) {
    if (!utcString) return utcString;
    // SQLite CURRENT_TIMESTAMP: "YYYY-MM-DD HH:MM:SS" (UTC)
    const normalized = utcString.trim().replace(" ", "T") + "Z";
    const date = new Date(normalized);
    if (isNaN(date.getTime())) return utcString;
    const pad = (n) => String(n).padStart(2, "0");
    return (
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
      `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    );
  }

  function initLocalTimes(root = document) {
    root.querySelectorAll("time.local-time").forEach((el) => {
      const local = formatLocalTime(el.getAttribute("datetime"));
      if (local) el.textContent = local;
    });
  }

  function updateFamiliarityStats(type) {
    const sections = document.querySelectorAll(`section[data-term-type="${type}"]`);
    let total = 0;
    let known = 0;
    let uniqueTotal = 0;
    let uniqueKnown = 0;

    sections.forEach((section) => {
      section.querySelectorAll(".term-card").forEach((card) => {
        const form = card.querySelector(".term-editor");
        const frequency = parseInt(form?.dataset.frequency || "1", 10) || 1;
        const select = card.querySelector('select[data-term-canonical]');
        const status = select?.value || "unknown";

        total += frequency;
        uniqueTotal += 1;
        if (status === "familiar") {
          known += frequency;
          uniqueKnown += 1;
        }
      });
    });

    const percent = total > 0 ? Math.round((known / total) * 100) : 0;
    const uniquePercent = uniqueTotal > 0 ? Math.round((uniqueKnown / uniqueTotal) * 100) : 0;

    document.querySelectorAll(`[data-stats-type="${type}"]`).forEach((bar) => {
      const metrics = bar.querySelectorAll(".fam-metric");
      if (bar.classList.contains("familiarity-bar")) {
        if (metrics[0]) metrics[0].textContent = `总量:${known}/${total} (${percent}%)`;
        if (metrics[1]) metrics[1].textContent = `唯一:${uniqueKnown}/${uniqueTotal} (${uniquePercent}%)`;
      } else if (bar.classList.contains("familiarity-mini")) {
        if (metrics[0]) metrics[0].textContent = `${known}/${total} (${percent}%)`;
      }
      bar.title = `总量=${known}/${total}（考量重复）  唯一=${uniqueKnown}/${uniqueTotal}（去重后）`;
    });
  }

  function updateProgress(form, payload) {
    const panel = form.querySelector("[data-analysis-progress]");
    const message = form.querySelector("[data-analysis-message]");
    const percent = form.querySelector("[data-analysis-percent]");
    const bar = form.querySelector("[data-analysis-bar]");
    const value = Math.max(0, Math.min(100, Number(payload.progress || 0)));
    if (panel) {
      panel.hidden = false;
    }
    if (message) {
      message.textContent = payload.message || "正在分析";
    }
    if (percent) {
      percent.textContent = `${Math.round(value)}%`;
    }
    if (bar) {
      bar.style.width = `${value}%`;
    }
  }

  async function pollAnalysis(form, statusUrl, redirectUrl) {
    const button = form.querySelector("button[type='submit']");
    for (;;) {
      const response = await fetch(statusUrl, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        throw new Error(`Progress request failed: ${response.status}`);
      }
      const payload = await response.json();
      updateProgress(form, payload);
      if (payload.status === "succeeded") {
        window.location.assign(payload.redirect_url || redirectUrl);
        return;
      }
      if (payload.status === "failed" || payload.status === "missing") {
        if (button) {
          button.disabled = false;
          button.textContent = "重试生成";
        }
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 600));
    }
  }

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    if (form.hasAttribute("data-analysis-form")) {
      event.preventDefault();
      const button = form.querySelector("button[type='submit']");
      if (button) {
        button.disabled = true;
        button.textContent = "正在生成";
      }
      updateProgress(form, { progress: 1, message: "提交分析任务" });
      try {
        const response = await fetch(form.action, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          throw new Error(`Analyze request failed: ${response.status}`);
        }
        const payload = await response.json();
        updateProgress(form, payload);
        await pollAnalysis(form, payload.status_url, form.dataset.articleUrl);
      } catch (error) {
        updateProgress(form, { progress: 100, message: "分析失败，请重试" });
        if (button) {
          button.disabled = false;
          button.textContent = "重试生成";
        }
        console.error(error);
      }
      return;
    }
    if (!form.hasAttribute("hx-patch") || window.htmx) {
      return;
    }
    event.preventDefault();
    const html = await requestFragment("PATCH", form.getAttribute("hx-patch"), new FormData(form));
    swap(form.getAttribute("hx-target"), html, form.getAttribute("hx-swap"));
  });

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[hx-get]");
    if (!button) {
      return;
    }
    if (window.htmx) {
      return;
    }
    event.preventDefault();
    const html = await requestFragment("GET", button.getAttribute("hx-get"));
    swap(button.getAttribute("hx-target"), html);
  });

  /* ---------- 定位功能 ---------- */
  const locateState = new Map();
  const originalTexts = new Map();

  // 页面加载时保存所有段落的原始文本
  function saveOriginalTexts() {
    document.querySelectorAll('.prose p[id^="p"]').forEach((p) => {
      const textNode = p.childNodes[p.childNodes.length - 1];
      if (textNode && textNode.nodeType === Node.TEXT_NODE) {
        originalTexts.set(p.id, textNode.textContent.trim());
      }
    });
  }
  saveOriginalTexts();

  function restoreAllParagraphs() {
    document.querySelectorAll('.prose p[id^="p"]').forEach((p) => {
      const originalText = originalTexts.get(p.id);
      if (!originalText) return;
      const span = p.querySelector(".paragraph-index");
      p.innerHTML = "";
      if (span) p.appendChild(span);
      p.appendChild(document.createTextNode(originalText));
    });
  }

  function highlightInParagraph(pElement, start, end) {
    restoreAllParagraphs();

    const originalText = originalTexts.get(pElement.id);
    if (!originalText) return;

    const textNode = pElement.childNodes[pElement.childNodes.length - 1];
    if (!textNode || textNode.nodeType !== Node.TEXT_NODE) return;

    const before = originalText.slice(0, start);
    const highlight = originalText.slice(start, end);
    const after = originalText.slice(end);

    const fragment = document.createDocumentFragment();
    if (before) fragment.appendChild(document.createTextNode(before));
    const mark = document.createElement("mark");
    mark.className = "term-highlight";
    mark.textContent = highlight;
    fragment.appendChild(mark);
    if (after) fragment.appendChild(document.createTextNode(after));

    pElement.replaceChild(fragment, textNode);
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest(".locate-btn");
    if (!button) return;

    const termId = button.dataset.termId;
    const articleId = button.dataset.articleId;

    let state = locateState.get(termId);
    if (!state) {
      try {
        const response = await fetch(`/terms/${termId}/occurrences?article_id=${articleId}`);
        if (!response.ok) throw new Error("Failed to load occurrences");
        const occurrences = await response.json();
        state = { occurrences, index: 0 };
        locateState.set(termId, state);
      } catch (err) {
        console.error(err);
        return;
      }
    }

    if (state.occurrences.length === 0) return;

    const occurrence = state.occurrences[state.index];
    state.index = (state.index + 1) % state.occurrences.length;

    const pElement = document.getElementById(`p${occurrence.paragraph_number}`);
    if (!pElement) return;

    const prose = document.querySelector(".prose");
    if (prose) {
      const proseRect = prose.getBoundingClientRect();
      const pRect = pElement.getBoundingClientRect();
      const targetTop = prose.scrollTop + pRect.top - proseRect.top - proseRect.height / 2 + pRect.height / 2;
      prose.scrollTo({ top: Math.max(0, targetTop), behavior: "smooth" });
    }
    highlightInParagraph(pElement, occurrence.char_start, occurrence.char_end);
  });

    /* ---------- 鍙岀嚎寮曠敤锛氬弻鍑诲師鏂囩叢璇嶈烦杞埌鍗曡瘝琛?---------- */
  function lemmatizeWord(word) {
    const value = word.toLowerCase().trim().replace(/^['"]+|['"]+$/g, "");
    const irregular = {
      ran: "run", running: "run", was: "be", were: "be", is: "be", are: "be",
      been: "be", being: "be", has: "have", had: "have", did: "do", done: "do",
      doing: "do", goes: "go", went: "go", gone: "go", going: "go",
      came: "come", coming: "come", saw: "see", seen: "see", seeing: "see",
      made: "make", making: "make", took: "take", taken: "take", taking: "take",
      got: "get", gotten: "get", getting: "get", knew: "know", known: "know",
      knowing: "know", thought: "think", thinking: "think", said: "say",
      saying: "say", told: "tell", telling: "tell", asked: "ask", asking: "ask",
      worked: "work", working: "work", called: "call",
      calling: "call", tried: "try", trying: "try", used: "use", using: "use",
      showed: "show", showing: "show", given: "give", giving: "give",
      found: "find", finding: "find", written: "write", writing: "write",
      spoken: "speak", speaking: "speak", read: "read", reading: "read",
      built: "build", building: "build", sent: "send", sending: "send",
      felt: "feel", feeling: "feel", left: "leave", leaving: "leave",
      put: "put", putting: "put", meant: "mean", meaning: "mean",
      kept: "keep", keeping: "keep", let: "let", letting: "let",
      began: "begin", beginning: "begin", begun: "begin", became: "become",
      becoming: "become", brought: "bring", bringing: "bring", bought: "buy",
      buying: "buy", chose: "choose", choosing: "choose", chosen: "choose",
      drew: "draw", drawing: "draw", drawn: "draw", drove: "drive",
      driving: "drive", driven: "drive", ate: "eat", eating: "eat", eaten: "eat",
      fell: "fall", falling: "fall", fallen: "fall", flew: "fly", flying: "fly",
      flown: "fly", forgot: "forget", forgetting: "forget", forgotten: "forget",
      forgave: "forgive", forgiving: "forgive", forgiven: "forgive",
      froze: "freeze", freezing: "freeze", frozen: "freeze", grew: "grow",
      growing: "grow", grown: "grow", hid: "hide", hiding: "hide", hidden: "hide",
      hit: "hit", hitting: "hit", held: "hold", holding: "hold", hurt: "hurt",
      hurting: "hurt", laid: "lay", laying: "lay", lain: "lie", lying: "lie",
      lit: "light", lighting: "light", lost: "lose", losing: "lose",
      paid: "pay", paying: "pay", rode: "ride", riding: "ride", ridden: "ride",
      rang: "ring", ringing: "ring", rung: "ring", rose: "rise", rising: "rise",
      risen: "rise", ran: "run", running: "run", shook: "shake", shaking: "shake",
      shaken: "shake", shot: "shoot", shooting: "shoot", shut: "shut",
      shutting: "shut", sang: "sing", singing: "sing", sung: "sing", sank: "sink",
      sinking: "sink", sunk: "sink", sat: "sit", sitting: "sit", slept: "sleep",
      sleeping: "sleep", slid: "slide", sliding: "slide", spoken: "speak",
      speaking: "speak", spent: "spend", spending: "spend", stood: "stand",
      standing: "stand", stole: "steal", stealing: "steal", stolen: "steal",
      stuck: "stick", sticking: "stick", struck: "strike", striking: "strike",
      sworn: "swear", swearing: "swear", swept: "sweep", sweeping: "sweep",
      swam: "swim", swimming: "swim", swum: "swim", swung: "swing",
      swinging: "swing", taught: "teach", teaching: "teach", tore: "tear",
      tearing: "tear", torn: "tear", told: "tell", telling: "tell", thought: "think",
      thinking: "think", threw: "throw", throwing: "throw", thrown: "throw",
      understood: "understand", understanding: "understand", woke: "wake",
      waking: "wake", woken: "wake", wore: "wear", wearing: "wear", worn: "wear",
      won: "win", winning: "win", wound: "wind", winding: "wind", wrote: "write",
      writing: "write", written: "write",
    };
    if (irregular[value]) return irregular[value];
    // Match backend analyzer.py logic
    if (value.endsWith("ies") && value.length > 4) {
      return value.slice(0, -3) + "y";
    }
    if (value.endsWith("ing") && value.length > 5) {
      let stem = value.slice(0, -3);
      if (stem.length >= 2 && stem[stem.length - 1] === stem[stem.length - 2]) {
        stem = stem.slice(0, -1);
      }
      return stem;
    }
    if (value.endsWith("ed") && value.length > 4) {
      let stem = value.slice(0, -2);
      if (stem.length >= 2 && stem[stem.length - 1] === stem[stem.length - 2]) {
        stem = stem.slice(0, -1);
      }
      return stem;
    }
    if (value.endsWith("es") && value.length > 4) {
      if (value.endsWith("ses") && value.slice(0, -1).endsWith("se")) {
        return value.slice(0, -1);
      }
      if (value.endsWith("ses") || value.endsWith("xes") || value.endsWith("zes") || value.endsWith("ches") || value.endsWith("shes")) {
        return value.slice(0, -2);
      }
      return value.slice(0, -1);
    }
    if (value.endsWith("s") && value.length > 3 && !value.endsWith("ss")) {
      return value.slice(0, -1);
    }
    return value;
  }
  function _learningPhrase(first, second) {
    const particles = new Set([
      "about", "across", "after", "around", "away", "back", "down",
      "for", "from", "in", "into", "off", "on", "out", "over",
      "through", "to", "up", "with",
    ]);
    if (particles.has(second) && !["a", "an", "the", "and", "or", "but"].includes(first)) {
      return `${first} ${second}`;
    }
    return null;
  }

  function findPhraseForWord(paragraphEl, selectedWord) {
    const selection = window.getSelection();
    if (!selection.rangeCount) return null;
    const range = selection.getRangeAt(0);

    // Get text before the selection (within the same paragraph)
    let beforeText = '';
    try {
      const beforeRange = document.createRange();
      beforeRange.setStart(paragraphEl, 0);
      beforeRange.setEnd(range.startContainer, range.startOffset);
      beforeText = beforeRange.toString();
    } catch (e) { /* ignore */ }

    // Get text after the selection (within the same paragraph)
    let afterText = '';
    try {
      const afterRange = document.createRange();
      afterRange.setStart(range.endContainer, range.endOffset);
      afterRange.setEndAfter(paragraphEl.lastChild || paragraphEl);
      afterText = afterRange.toString();
    } catch (e) { /* ignore */ }

    const selectedCanonical = lemmatizeWord(selectedWord);

    // Extract the immediate previous word
    const prevMatch = beforeText.match(/([A-Za-z]+(?:'[A-Za-z]+)?)\s*$/);
    if (prevMatch) {
      const prevCanonical = lemmatizeWord(prevMatch[1]);
      const p = _learningPhrase(prevCanonical, selectedCanonical);
      if (p) return p;
    }

    // Extract the immediate next word
    const nextMatch = afterText.match(/^\s*([A-Za-z]+(?:'[A-Za-z]+)?)/);
    if (nextMatch) {
      const nextCanonical = lemmatizeWord(nextMatch[1]);
      const p = _learningPhrase(selectedCanonical, nextCanonical);
      if (p) return p;
    }

    return null;
  }

  function getSelectedWord() {
    const selection = window.getSelection();
    if (!selection.rangeCount) return null;
    const text = selection.toString().trim();
    if (!text) return null;
    // Allow only single words (letters + apostrophe)
    if (/[^a-zA-Z']/.test(text)) return null;
    return text;
  }

  function scrollToTermCard(canonical) {
    const termColumn = document.querySelector(".term-column");
    if (!termColumn) return;
    const cards = termColumn.querySelectorAll(".term-card");
    for (const card of cards) {
      const cardCanonical = card.dataset.termCanonical;
      if (!cardCanonical) continue;
      if (cardCanonical.toLowerCase() === canonical.toLowerCase()) {
        const columnRect = termColumn.getBoundingClientRect();
        const cardRect = card.getBoundingClientRect();
        const targetTop = termColumn.scrollTop + cardRect.top - columnRect.top - 60;
        termColumn.scrollTo({ top: Math.max(0, targetTop), behavior: "smooth" });
        // Brief highlight on the card
        card.style.transition = "background 0.3s";
        card.style.background = "var(--soft)";
        setTimeout(() => { card.style.background = ""; }, 1200);
        return;
      }
    }
  }

  let lastDoubleClick = null;

  document.addEventListener("dblclick", (event) => {
    const prose = event.target.closest(".prose");
    if (!prose) return;
    const selected = getSelectedWord();
    if (!selected) return;
    const wordCanonical = lemmatizeWord(selected);
    const now = Date.now();

    // Check if this is a repeat double-click within 5 seconds on the same word
    const isRepeat = lastDoubleClick &&
      lastDoubleClick.canonical === wordCanonical &&
      now - lastDoubleClick.time < 5000;

    // Try to find if this word belongs to a phrase
    const phraseCanonical = findPhraseForWord(prose, selected);

    if (phraseCanonical && !isRepeat) {
      scrollToTermCard(phraseCanonical);
      lastDoubleClick = { canonical: wordCanonical, time: now, target: "phrase" };
    } else {
      scrollToTermCard(wordCanonical);
      lastDoubleClick = null;
    }
  });

  /* ---------- 标注功能 ---------- */
  const ANNOTATE_KEY = "annotate_enabled";
  const ANNOTATE_CONFIG_KEY = "annotate_config";
  const ANNOTATE_TAG_CONFIG_KEY = "annotate_tag_config";

  const DEFAULT_CONFIG = {
    unknown:   { underline: true,  color: "#000000" },
    confusing: { underline: false, color: "#b85c38" },
    familiar:  { underline: false, color: "#2f7d6d" },
  };

  function loadTags() {
    const el = document.querySelector("[data-tags]");
    if (!el) return [];
    try {
      return JSON.parse(el.textContent);
    } catch { return []; }
  }

  function loadTagConfig() {
    try {
      return JSON.parse(localStorage.getItem(ANNOTATE_TAG_CONFIG_KEY)) || {};
    } catch { return {}; }
  }

  function saveTagConfig(cfg) {
    localStorage.setItem(ANNOTATE_TAG_CONFIG_KEY, JSON.stringify(cfg));
  }

  function loadConfig() {
    try {
      return JSON.parse(localStorage.getItem(ANNOTATE_CONFIG_KEY)) || DEFAULT_CONFIG;
    } catch { return DEFAULT_CONFIG; }
  }

  function saveConfig(cfg) {
    localStorage.setItem(ANNOTATE_CONFIG_KEY, JSON.stringify(cfg));
  }

  function isEnabled() {
    return localStorage.getItem(ANNOTATE_KEY) === "1";
  }

  function setEnabled(v) {
    localStorage.setItem(ANNOTATE_KEY, v ? "1" : "0");
  }

  let _wordStatusMapCache = null;

  function getWordStatusMap() {
    if (_wordStatusMapCache) return _wordStatusMapCache;
    const el = document.querySelector("[data-word-status-map]");
    if (!el) return {};
    try {
      _wordStatusMapCache = JSON.parse(el.textContent);
      return _wordStatusMapCache;
    } catch { return {}; }
  }

  function renderAnnotations() {
    const enabled = isEnabled();
    const cfg = loadConfig();
    const statusMap = getWordStatusMap();
    const tags = loadTags();
    const tagConfig = loadTagConfig();
    const wordRe = /[A-Za-z]+(?:'[A-Za-z]+)?/g;

    const wordToColor = new Map();
    for (const tag of tags) {
      const tCfg = tagConfig[tag.id] || { enabled: true, color: tag.color };
      if (!tCfg.enabled) continue;
      for (const word of tag.words) {
        if (!wordToColor.has(word)) {
          wordToColor.set(word, tCfg.color);
        }
      }
    }

    document.querySelectorAll(".prose .paragraph-text").forEach((textEl) => {
      const rawText = textEl.dataset.originalText || textEl.textContent;
      if (!textEl.dataset.originalText) textEl.dataset.originalText = rawText;

      if (!enabled) {
        textEl.textContent = rawText;
        return;
      }

      const parts = [];
      let lastIndex = 0;
      let m;
      while ((m = wordRe.exec(rawText)) !== null) {
        parts.push(document.createTextNode(rawText.slice(lastIndex, m.index)));
        const canonical = lemmatizeWord(m[0]);
        const status = statusMap[canonical];
        const statusCfg = cfg[status];
        const color = wordToColor.get(canonical);

        if ((statusCfg && statusCfg.underline) || color) {
          const span = document.createElement("span");
          span.className = "tag-annotation";
          span.textContent = m[0];
          if (color) {
            span.style.backgroundColor = color;
          }
          if (statusCfg && statusCfg.underline) {
            span.style.textDecoration = "underline";
            span.style.textDecorationColor = statusCfg.color;
            span.style.textDecorationThickness = "2px";
          }
          parts.push(span);
        } else {
          parts.push(document.createTextNode(m[0]));
        }
        lastIndex = m.index + m[0].length;
      }
      parts.push(document.createTextNode(rawText.slice(lastIndex)));

      textEl.innerHTML = "";
      parts.forEach((n) => textEl.appendChild(n));
    });
  }

  // Toggle switch
  const toggleEl = document.querySelector("[data-annotate-toggle]");
  if (toggleEl) {
    toggleEl.checked = isEnabled();
    toggleEl.addEventListener("change", () => {
      setEnabled(toggleEl.checked);
      renderAnnotations();
    });
  }

  // Config panel
  const configBtn = document.querySelector("[data-annotate-config-btn]");
  const configPanel = document.querySelector("[data-annotate-config-panel]");
  if (configBtn && configPanel) {
    configBtn.addEventListener("click", () => {
      configPanel.hidden = !configPanel.hidden;
    });

    // Load current config into inputs
    const cfg = loadConfig();
    ["unknown", "confusing", "familiar"].forEach((status) => {
      const u = configPanel.querySelector(`[data-config-underline="${status}"]`);
      const c = configPanel.querySelector(`[data-config-color="${status}"]`);
      if (u) u.checked = cfg[status].underline;
      if (c) c.value = cfg[status].color;
    });

    // Load tag config into inputs
    const tags = loadTags();
    const tagCfg = loadTagConfig();
    for (const tag of tags) {
      const enableInput = configPanel.querySelector(`[data-config-enable="${tag.id}"]`);
      const colorInput = configPanel.querySelector(`[data-config-color="${tag.id}"]`);
      if (enableInput) enableInput.checked = (tagCfg[tag.id]?.enabled !== false);
      if (colorInput) colorInput.value = tagCfg[tag.id]?.color || tag.color;
    }

    // Save on change
    configPanel.addEventListener("change", () => {
      const newCfg = {};
      ["unknown", "confusing", "familiar"].forEach((status) => {
        const u = configPanel.querySelector(`[data-config-underline="${status}"]`);
        const c = configPanel.querySelector(`[data-config-color="${status}"]`);
        newCfg[status] = {
          underline: u ? u.checked : false,
          color: c ? c.value : "#000000",
        };
      });
      saveConfig(newCfg);

      const newTagCfg = {};
      for (const tag of tags) {
        const enableInput = configPanel.querySelector(`[data-config-enable="${tag.id}"]`);
        const colorInput = configPanel.querySelector(`[data-config-color="${tag.id}"]`);
        newTagCfg[tag.id] = {
          enabled: enableInput ? enableInput.checked : true,
          color: colorInput ? colorInput.value : tag.color,
        };
      }
      saveTagConfig(newTagCfg);

      renderAnnotations();
    });
  }

  // HTMX: show references when loaded, update annotations on term change
  document.addEventListener("htmx:afterSwap", (event) => {
    const target = event.detail.target;
    if (target && target.id === "references") {
      showReferences();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    // 处理词卡更新：outerHTML 替换后 target 已被移出 DOM，需通过 elt 找到 card 再重新查询
    const elt = event.detail.elt;
    const card = (elt && elt.closest && elt.closest(".term-card"))
              || (target && target.closest && target.closest(".term-card"));
    if (card && card.id) {
      const freshCard = document.getElementById(card.id);
      if (freshCard) {
        const select = freshCard.querySelector('select[data-term-canonical]');
        if (select) {
          const canonical = select.dataset.termCanonical;
          const status = select.value;
          const statusMap = getWordStatusMap();
          statusMap[canonical] = status;
        }
      }
      renderAnnotations();
      const section = card.closest('section[data-term-type]');
      if (section) {
        updateFamiliarityStats(section.dataset.termType);
      }
    }
    initLocalTimes(target || document);
  });

  // ---------- 瀹氫綅楂樹寒 ----------
  function highlightWordInParagraphs(canonical) {
    // Clear existing highlights
    document.querySelectorAll(".word-highlight").forEach((el) => {
      const parent = el.parentNode;
      if (parent) parent.replaceChild(document.createTextNode(el.textContent), el);
    });

    document.querySelectorAll(".prose .paragraph-text").forEach((textEl) => {
      const walker = document.createTreeWalker(textEl, NodeFilter.SHOW_TEXT);
      const textNodes = [];
      let node;
      while ((node = walker.nextNode())) {
        textNodes.push(node);
      }

      textNodes.forEach((textNode) => {
        const text = textNode.textContent;
        const wordRe = /[A-Za-z]+(?:'[A-Za-z]+)?/g;
        let m;
        const matches = [];
        while ((m = wordRe.exec(text)) !== null) {
          if (lemmatizeWord(m[0]) === canonical) {
            matches.push({ start: m.index, end: m.index + m[0].length });
          }
        }
        // Process matches in reverse to avoid index shift
        matches.reverse().forEach((match) => {
          const range = document.createRange();
          range.setStart(textNode, match.start);
          range.setEnd(textNode, match.end);
          const highlight = document.createElement("span");
          highlight.className = "word-highlight";
          try {
            range.surroundContents(highlight);
          } catch (e) {
            // Skip if range spans multiple elements
          }
        });
      });
    });
  }

  document.querySelector(".term-column")?.addEventListener("click", (e) => {
    const btn = e.target.closest(".locate-btn");
    if (!btn) return;
    const canonical = lemmatizeWord(btn.dataset.termCanonical || "");
    highlightWordInParagraphs(canonical);
  });


  // 临时查词面板
  const lookupToggle = document.getElementById("lookup-toggle");
  const lookupDrawer = document.getElementById("lookup-drawer");
  const lookupBackdrop = document.getElementById("lookup-backdrop");
  const lookupClose = document.getElementById("lookup-close");
  const lookupInput = document.getElementById("lookup-input");
  const lookupBtn = document.getElementById("lookup-btn");
  const lookupResult = document.getElementById("lookup-result");

  function openLookupDrawer() {
    if (!lookupDrawer || !lookupBackdrop) return;
    lookupDrawer.style.display = "flex";
    lookupBackdrop.style.display = "block";
    requestAnimationFrame(() => {
      lookupDrawer.classList.add("open");
      lookupBackdrop.classList.add("open");
    });
    lookupInput?.focus();
  }

  function closeLookupDrawer() {
    if (!lookupDrawer || !lookupBackdrop) return;
    lookupDrawer.classList.remove("open");
    lookupBackdrop.classList.remove("open");
    setTimeout(() => {
      if (!lookupDrawer.classList.contains("open")) {
        lookupDrawer.style.display = "none";
        lookupBackdrop.style.display = "none";
      }
    }, 300);
  }

  if (lookupToggle && lookupDrawer) {
    lookupToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      if (lookupDrawer.classList.contains("open")) {
        closeLookupDrawer();
      } else {
        openLookupDrawer();
      }
    });

    lookupClose?.addEventListener("click", closeLookupDrawer);
    lookupBackdrop?.addEventListener("click", closeLookupDrawer);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && lookupDrawer.classList.contains("open")) {
        closeLookupDrawer();
      }
    });

    lookupInput?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        doLookup();
      }
    });

    lookupBtn?.addEventListener("click", doLookup);
  }

  async function doLookup() {
    const word = lookupInput?.value.trim();
    if (!word) return;
    lookupResult.innerHTML = '<span class="lookup-loading">查询中…</span>';
    try {
      const formData = new URLSearchParams();
      formData.append("word", word);
      const response = await fetch("/lookup", {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) throw new Error(`请求失败: ${response.status}`);
      const data = await response.json();
      if (data.error) {
        lookupResult.innerHTML = `<span class="lookup-error">${escapeHtml(data.error)}</span>`;
      } else {
        lookupResult.textContent = data.meaning || "（无释义）";
      }
    } catch (err) {
      lookupResult.innerHTML = `<span class="lookup-error">${escapeHtml(err.message)}</span>`;
    }
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Initial render
  renderAnnotations();
  initLocalTimes();
})();
