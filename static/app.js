document.addEventListener('DOMContentLoaded', () => {
  const MODEL_INFO = {
    'openchat': {
      label: 'OpenChat – chytrý AI asistent 🌐',
      web: true,
      desc: 'Chytrý AI asistent. Vhodný pro běžné otázky, dialog a porozumění pokynům.'
    },
    'nous-hermes2': {
      label: 'Nous Hermes 2 – jemně doladěný Mistral 🌐',
      web: true,
      desc: 'Dobře zvládá otázky, formální texty i instrukce, vhodný i pro složitější dotazy s doplněním z internetu.'
    },
    'llama3:8b': {
      label: 'LLaMA 3 8B – velký jazykový model 🌐',
      web: true,
      desc: 'Vysoká přesnost, vhodný pro složitější dotazy, rozumí webovému obsahu i dokumentům.'
    },
    'command-r': {
      label: 'Command R – model pro RAG 🌐',
      web: true,
      desc: 'Optimalizovaný pro programování, Python, shell, kódové úkoly.'
    },
    'api': {
      label: 'Externí API',
      web: false,
      desc: 'Externí API – dotazy jsou posílány do API.'
    }
  };

  let DEVLAB_URL = '';
  let useDevlab = false;
  const originalFetch = window.fetch.bind(window);

  function envFetch(url, opts) {
    if (useDevlab && DEVLAB_URL && typeof url === 'string' && url.startsWith('/')) {
      return originalFetch(DEVLAB_URL + url, opts);
    }
    return originalFetch(url, opts);
  }

  window.fetch = envFetch;

  async function safeJson(res) {
    const txt = await res.text();
    try {
      return JSON.parse(txt);
    } catch (_) {
      console.error('Invalid JSON response:', txt);
      throw new Error('Server returned invalid response');
    }
  }

  function updateEnvDisplay() {
    const info = document.getElementById('env-info');
    const btn = document.getElementById('env-toggle');
    if (info) info.textContent = useDevlab ? 'devlab' : 'local';
    if (btn) btn.textContent = useDevlab ? 'Use Local' : 'Use DevLab';
  }

  function toggleEnv() {
    if (!DEVLAB_URL) return;
    useDevlab = !useDevlab;
    updateEnvDisplay();
  }

  async function initEnv() {
    try {
      const res = await originalFetch('/devlab_config.json');
      if (res.ok) {
        const cfg = await res.json();
        if (cfg && cfg.url) {
          DEVLAB_URL = String(cfg.url).replace(/\/$/, '');
          const btn = document.getElementById('env-toggle');
          if (btn) btn.style.display = 'inline';
        }
      }
    } catch (_) {
      /* ignore */
    }
    updateEnvDisplay();
  }

  function authHeader() {
    const token = localStorage.getItem('token') || '';
    const key = localStorage.getItem('apikey') || '';
    const headers = {};
    if (token) headers['Authorization'] = 'Bearer ' + token;
    if (key) headers['X-API-Key'] = key;
    return headers;
  }

  async function doLogin() {
    const nick = document.getElementById('nick').value;
    const password = document.getElementById('password').value;
    const apiKey = document.getElementById('apikey').value;
    document.getElementById('login-status').textContent = '⏳ Logging in…';
    try {
      const res = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nick, password })
      });
      const data = await res.json();
      if (res.ok && data.token) {
        localStorage.setItem('token', data.token);
        if (apiKey) localStorage.setItem('apikey', apiKey);
        else localStorage.removeItem('apikey');
        document.getElementById('token-display').textContent = data.token;
        document.getElementById('login').style.display = 'none';
        document.getElementById('interface').style.display = 'block';
        loadModel();
        loadTopics();
      } else {
        document.getElementById('login-status').textContent = '❌ ' + (data.error || res.status);
      }
    } catch (err) {
      document.getElementById('login-status').textContent = '❌ ' + err;
    }
  }

  function copyToken() {
    const token = localStorage.getItem('token') || '';
    if (token) navigator.clipboard.writeText(token);
  }

  async function loadModel() {
    setProgress(true);
    try {
      const res = await fetch('/model', { headers: authHeader() });
      const data = await safeJson(res);
      const model = data.model || '';
      document.getElementById('current-model').textContent = model;
      const select = document.getElementById('model-select');
      if (select) select.value = model;
      const info = MODEL_INFO[model];
      document.getElementById('model-desc').textContent = info ? info.desc : '';
    } catch (err) {
      console.error(err);
    } finally {
      setProgress(false);
    }
  }

  async function switchModel() {
    const select = document.getElementById('model-select');
    const model = select.value;
    document.getElementById('model-status').textContent = '⏳ Switching…';
    setProgress(true);
    try {
      const res = await fetch('/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ model })
      });
      const data = await safeJson(res);
      if (res.ok) {
        document.getElementById('model-status').textContent = '🔄 Restarting…';
        document.getElementById('current-model').textContent = model;
        const info = MODEL_INFO[model];
        document.getElementById('model-desc').textContent = info ? info.desc : '';
      } else {
        document.getElementById('model-status').textContent = '❌ ' + (data.error || res.status);
      }
    } catch (err) {
      document.getElementById('model-status').textContent = '❌ ' + err;
    } finally {
      setProgress(false);
    }
  }

  function setProgress(on) {
    const el = document.getElementById('progress');
    if (el) el.style.display = on ? 'block' : 'none';
  }

  async function loadTopics() {
    setProgress(true);
    try {
      const res = await fetch('/knowledge/topics', { headers: authHeader() });
      const data = await res.json();
      const topics = Array.isArray(data) ? data : Object.keys(data);
      const container = document.getElementById('topic-checkboxes');
      if (container) {
        container.innerHTML = '';
        topics.forEach(t => {
          const label = document.createElement('label');
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.value = t;
          label.appendChild(cb);
          label.appendChild(document.createTextNode(' ' + t));
          container.appendChild(label);
          container.appendChild(document.createElement('br'));
        });
      }
    } catch (err) {
      console.error(err);
    } finally {
      setProgress(false);
    }
  }

  async function ask() {
    const msg = document.getElementById('message').value;
    const fileInput = document.getElementById('file');
    const file = fileInput.files[0];
    const isPrivate = document.getElementById('memory-private').checked;
    const save = document.getElementById('save-txt').checked;
    const topics = Array.from(
      document.querySelectorAll('#topic-checkboxes input:checked')
    ).map(cb => cb.value);

    setProgress(true);
    document.getElementById('activity').textContent = '⏳ Čekejte…';

    try {
      let data;
      if (file) {
        const form = new FormData();
        form.append('message', msg);
        form.append('file', file);
        form.append('private', isPrivate ? '1' : '0');
        if (topics.length) form.append('topics', topics.join(','));
        if (save) form.append('save', '1');
        const res = await fetch('/ask_file', {
          method: 'POST',
          headers: authHeader(),
          body: form
        });
        data = await safeJson(res);
      } else {
        const payload = { message: msg, private: isPrivate };
        if (topics.length) payload.topics = topics;
        const res = await fetch('/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader() },
          body: JSON.stringify(payload)
        });
        data = await safeJson(res);
      }

      if (data.response) {
        document.getElementById('response').textContent = data.response;
        document.getElementById('debug').textContent = (data.debug || []).join('\n');
        if (data.download_url) {
          const dl = document.getElementById('download');
          dl.href = data.download_url;
          dl.style.display = 'inline';
        } else {
          document.getElementById('download').style.display = 'none';
        }
        document.getElementById('feedback').style.display = 'block';
        document.getElementById('activity').textContent = '✅ Hotovo';
      } else if (data.error) {
        document.getElementById('activity').textContent = '❌ ' + data.error;
      }
    } catch (err) {
      document.getElementById('activity').textContent = '❌ ' + err;
    } finally {
      setProgress(false);
    }
  }

  async function sendFeedback(type) {
    const question = document.getElementById('message').value;
    const answer = document.getElementById('response').textContent;
    const correction = document.getElementById('correction-text').value;
    const payload = { agree: type === 'good', question, answer };
    if (type === 'bad') payload.correction = correction;
    document.getElementById('feedback-status').textContent = '⏳ Odesílám…';
    setProgress(true);
    try {
      const res = await fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        document.getElementById('feedback-status').textContent = '✅ Díky za hodnocení';
      } else {
        const data = await safeJson(res);
        document.getElementById('feedback-status').textContent = '❌ ' + (data.error || res.status);
      }
    } catch (err) {
      document.getElementById('feedback-status').textContent = '❌ ' + err;
    } finally {
      setProgress(false);
    }
  }

  window.loadModel = loadModel;
  window.switchModel = switchModel;
  window.ask = ask;
  window.sendFeedback = sendFeedback;
  window.submitCorrection = () => sendFeedback('bad');
  window.showCorrection = () => {
    document.getElementById('correction').style.display = 'block';
  };

  async function uploadKnowledge() {
    const fileInput = document.getElementById('knowledge-file');
    const file = fileInput.files[0];
    if (!file) {
      document.getElementById('knowledge-status').textContent = '❌ Vyber soubor.';
      return;
    }

    const isPrivate = document.getElementById('knowledge-private').checked;
    const description = document.getElementById('knowledge-desc').value;
    const topicSelect = document.getElementById('knowledge-topic');
    const topic = topicSelect.value || '';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('private', isPrivate ? 'true' : 'false');
    formData.append('description', description);
    formData.append('topic', topic);

    try {
      const res = await fetch('/knowledge/upload', {
        method: 'POST',
        headers: authHeader(),
        body: formData,
      });

      const data = await safeJson(res);
      if (data.status === 'saved') {
        document.getElementById('knowledge-status').textContent = `✅ Soubor uložen jako: ${data.file}`;
      } else {
        document.getElementById('knowledge-status').textContent = '❌ Chyba: ' + JSON.stringify(data);
      }
    } catch (err) {
      document.getElementById('knowledge-status').textContent = '❌ Výjimka: ' + err;
    }
  }

  async function loadPending() {
    const list = document.getElementById('pending-list');
    if (list) list.innerHTML = '';
    document.getElementById('status').textContent = '⏳ Načítám…';
    try {
      const res = await fetch('/knowledge/pending', { headers: authHeader() });
      const data = await safeJson(res);
      if (res.ok) {
        if (Array.isArray(data) && list) {
          data.forEach(item => {
            const li = document.createElement('li');
            const file = item.file || item.name || '';
            li.textContent = file + ' ';
            const appr = document.createElement('button');
            appr.textContent = '✔';
            appr.onclick = () => approvePending(file);
            const rej = document.createElement('button');
            rej.textContent = '✖';
            rej.onclick = () => rejectPending(file);
            li.appendChild(appr);
            li.appendChild(rej);
            list.appendChild(li);
          });
        }
        document.getElementById('status').textContent = `✅ Načteno: ${data.length}`;
      } else {
        document.getElementById('status').textContent = '❌ ' + (data.error || res.status);
      }
    } catch (err) {
      document.getElementById('status').textContent = '❌ ' + err;
    }
  }

  async function approvePending(file) {
    document.getElementById('status').textContent = '⏳ Schvaluji…';
    try {
      const res = await fetch('/knowledge/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ file })
      });
      const data = await safeJson(res);
      if (res.ok) {
        document.getElementById('status').textContent = '✅ Schváleno';
        loadPending();
      } else {
        document.getElementById('status').textContent = '❌ ' + (data.error || res.status);
      }
    } catch (err) {
      document.getElementById('status').textContent = '❌ ' + err;
    }
  }

  async function rejectPending(file) {
    document.getElementById('status').textContent = '⏳ Přesouvám…';
    try {
      const res = await fetch('/knowledge/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ file })
      });
      const data = await safeJson(res);
      if (res.ok) {
        document.getElementById('status').textContent = '✅ Zamítnuto';
        loadPending();
      } else {
        document.getElementById('status').textContent = '❌ ' + (data.error || res.status);
      }
    } catch (err) {
      document.getElementById('status').textContent = '❌ ' + err;
    }
  }

  async function deleteByTime() {
    const from = document.getElementById('delete-from').value;
    const to = document.getElementById('delete-to').value;
    document.getElementById('delete-status').textContent = '⏳ Mažu…';
    try {
      const res = await fetch('/memory/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ from, to })
      });
      const data = await safeJson(res);
      document.getElementById('delete-status').textContent = res.ok ? data.message : '❌ ' + (data.error || res.status);
    } catch (err) {
      document.getElementById('delete-status').textContent = '❌ ' + err;
    }
  }

  async function deleteByKeyword() {
    const keyword = document.getElementById('delete-keyword').value;
    document.getElementById('delete-status').textContent = '⏳ Mažu…';
    try {
      const res = await fetch('/memory/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ keyword })
      });
      const data = await safeJson(res);
      document.getElementById('delete-status').textContent = res.ok ? data.message : '❌ ' + (data.error || res.status);
    } catch (err) {
      document.getElementById('delete-status').textContent = '❌ ' + err;
    }
  }

  async function startJarvik() {
    const status = document.getElementById('service-status');
    if (status) status.textContent = '⏳ Spouštím…';
    try {
      const res = await fetch('/start', {
        method: 'POST',
        headers: authHeader()
      });
      const data = await safeJson(res);
      if (res.ok) {
        if (status) status.textContent = '✅ Spouštím';
      } else if (status) {
        status.textContent = '❌ ' + (data.error || res.status);
      }
    } catch (err) {
      if (status) status.textContent = '❌ ' + err;
    }
  }

  async function stopJarvik() {
    const status = document.getElementById('service-status');
    if (status) status.textContent = '⏳ Zastavuji…';
    try {
      const res = await fetch('/stop', {
        method: 'POST',
        headers: authHeader()
      });
      const data = await safeJson(res);
      if (res.ok) {
        if (status) status.textContent = '✅ Zastavuji';
      } else if (status) {
        status.textContent = '❌ ' + (data.error || res.status);
      }
    } catch (err) {
      if (status) status.textContent = '❌ ' + err;
    }
  }

  function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('apikey');
    const login = document.getElementById('login');
    const iface = document.getElementById('interface');
    if (login) login.style.display = 'block';
    if (iface) iface.style.display = 'none';

    const ids = ['message', 'response', 'debug', 'context', 'activity', 'status',
      'duration', 'model-status', 'token-display'];
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      if ('value' in el) el.value = '';
      else el.textContent = '';
    });

    const download = document.getElementById('download');
    if (download) download.style.display = 'none';
    const feedback = document.getElementById('feedback');
    if (feedback) feedback.style.display = 'none';
    const progress = document.getElementById('progress');
    if (progress) progress.style.display = 'none';

    const file = document.getElementById('file');
    if (file) file.value = '';
  }
  window.doLogin = doLogin;
  window.copyToken = copyToken;
  window.authHeader = authHeader;
  window.toggleEnv = toggleEnv;
  window.safeJson = safeJson;
  window.uploadKnowledge = uploadKnowledge;
  window.loadPending = loadPending;
  window.approvePending = approvePending;
  window.rejectPending = rejectPending;
  window.deleteByTime = deleteByTime;
  window.deleteByKeyword = deleteByKeyword;
  window.startJarvik = startJarvik;
  window.stopJarvik = stopJarvik;
  window.logout = logout;

  const modelSelect = document.getElementById('model-select');
  if (modelSelect) {
    modelSelect.addEventListener('change', () => {
      const model = modelSelect.value;
      const info = MODEL_INFO[model];
      document.getElementById('model-desc').textContent = info ? info.desc : '';
    });
  }

  initEnv();

  const storedToken = localStorage.getItem('token');
  const loginDiv = document.getElementById('login');
  const interfaceDiv = document.getElementById('interface');
  if (storedToken) {
    if (loginDiv) loginDiv.style.display = 'none';
    if (interfaceDiv) interfaceDiv.style.display = 'block';
    document.getElementById('token-display').textContent = storedToken;
    loadModel();
    loadTopics();
  } else {
    if (loginDiv) loginDiv.style.display = 'block';
    if (interfaceDiv) interfaceDiv.style.display = 'none';
  }
});
