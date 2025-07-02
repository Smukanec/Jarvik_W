if (/Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
  window.location.href = '/static/mobile.html';
}

document.addEventListener('DOMContentLoaded', () => {
      let apiBase = '';
      let devlabUrl = '';
      let useDevlab = false;

      function buildUrl(path) {
        if (apiBase) {
          const base = apiBase.replace(/\/$/, '');
          return base + path;
        }
        return path;
      }

      function updateEnvDisplay() {
        const info = document.getElementById('env-info');
        const btn = document.getElementById('env-toggle');
        if (!info || !btn) return;
        info.textContent = useDevlab ? 'DevLab' : 'local';
        btn.textContent = useDevlab ? 'Use Local' : 'Use DevLab';
        btn.style.display = devlabUrl ? 'inline' : 'none';
      }

      function toggleEnv() {
        if (!devlabUrl) return;
        useDevlab = !useDevlab;
        apiBase = useDevlab ? devlabUrl : '';
        updateEnvDisplay();
      }

      async function initEnv() {
        try {
          const res = await fetch('/static/devlab_config.json');
          if (res.ok) {
            const cfg = await res.json();
            if (cfg.url) {
              devlabUrl = cfg.url;
            }
          }
        } catch (e) {}
        updateEnvDisplay();
      }
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
  
      const MODEL_NAMES = Object.fromEntries(
        Object.entries(MODEL_INFO).map(([k, v]) => [k, v.label])
      );
      const MODEL_DESCRIPTIONS = Object.fromEntries(
        Object.entries(MODEL_INFO).map(([k, v]) => [k, v.desc])
      );
  
      function updateModelDesc() {
        const val = document.getElementById('model-select').value;
        document.getElementById('model-desc').textContent = MODEL_DESCRIPTIONS[val] || '';
      }
  
      async function loadTopics() {
        try {
          const res = await authFetch('/knowledge/topics');
          if (!res.ok) return;
          const data = await res.json();
          const sel = document.getElementById('knowledge-topic');
          if (sel) {
            sel.appendChild(new Option('', ''));
            Object.entries(data).forEach(([k, v]) => {
              sel.appendChild(new Option(v, k));
            });
          }
          const box = document.getElementById('topic-checkboxes');
          if (box) {
            box.textContent = '';
            Object.entries(data).forEach(([k, v]) => {
              const label = document.createElement('label');
              const cb = document.createElement('input');
              cb.type = 'checkbox';
              cb.value = k;
              label.appendChild(cb);
              label.append(' ' + v);
              box.appendChild(label);
              box.appendChild(document.createTextNode(' '));
            });
          }
        } catch (e) {}
      }
  
      let token = localStorage.getItem('token') || '';
      let apiKey = localStorage.getItem('apiKey') || '';
  
      function copyToken() {
        if (token) navigator.clipboard.writeText(token);
      }
  
      function authFetch(url, options = {}) {
        options.headers = options.headers || {};
        if (token) options.headers['Authorization'] = 'Bearer ' + token;
        if (apiKey) options.headers['X-API-Key'] = apiKey;
        return fetch(buildUrl(url), options);
      }
  
      async function loadModel() {
        const res = await authFetch('/model');
        const data = await res.json();
        const name = MODEL_NAMES[data.model] || data.model;
        document.getElementById('current-model').textContent = name;
        const sel = document.getElementById('model-select');
        if (sel) {
          let option = Array.from(sel.options).find(o => o.value === data.model);
          if (!option) {
            option = new Option(name, data.model);
            sel.appendChild(option);
          }
          sel.value = data.model;
          updateModelDesc();
        }
      }
  
      async function switchModel() {
        const model = document.getElementById('model-select').value;
        document.getElementById('model-status').textContent = '⏳ Restartuji...';
        await authFetch('/model', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model })
        });
        document.getElementById('model-status').textContent = '🔄 Restartuji, chvíli strpení...';
        const name = MODEL_NAMES[model] || model;
        document.getElementById('current-model').textContent = name;
        updateModelDesc();
      }
  
    function showInterface() {
       document.getElementById('login').style.display = 'none';
       document.getElementById('interface').style.display = 'block';
       loadModel();
       loadTopics();
       loadPending();
       document.getElementById('token-display').textContent = token;
        const select = document.getElementById('model-select');
        if (select) {
          select.addEventListener('change', () => {
            switchModel();
            updateModelDesc();
          });
          updateModelDesc();
        }
      }
  
      async function checkAuth() {
        if (!token) {
          document.getElementById('login').style.display = 'block';
          document.getElementById('apikey').value = apiKey;
          return;
        }
        const res = await authFetch('/model');
        if (res.status === 401) {
          document.getElementById('login').style.display = 'block';
          token = '';
          localStorage.removeItem('token');
        } else {
          showInterface();
        }
      }
  
      async function doLogin() {
        const nick = document.getElementById('nick').value.trim();
        const password = document.getElementById('password').value;
        apiKey = document.getElementById('apikey').value.trim();
        if (apiKey) localStorage.setItem('apiKey', apiKey);
        const res = await fetch(buildUrl('/login'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ nick, password })
        });
        if (res.ok) {
          const data = await res.json();
          token = data.token;
          localStorage.setItem('token', token);
          document.getElementById('token-display').textContent = token;
          document.getElementById('login-status').textContent = '';
          showInterface();
        } else {
          document.getElementById('login-status').textContent = 'Login failed';
        }
      }
  
      let conversationLog = "";
  
      async function ask() {
        const msg = document.getElementById("message").value.trim();
        const fileInput = document.getElementById("file");
        const file = fileInput.files[0];
        if (!msg && !file) return;
        document.getElementById("status").textContent = "⏳ Zpracovávám…";
        document.getElementById("activity").textContent = "Čekám na odpověď…";
        document.getElementById("duration").textContent = "";
  
        // try to load context for display
        try {
          const selectedTopics = Array.from(
            document.querySelectorAll('#topic-checkboxes input:checked')
          ).map(cb => cb.value);
          const topicParam = selectedTopics.length
            ? '&topics=' + encodeURIComponent(selectedTopics.join(','))
            : '';
          const ctxRes = await authFetch(
            "/knowledge/search?q=" + encodeURIComponent(msg) + topicParam
          );
          if (ctxRes.ok) {
            const ctxData = await ctxRes.json();
            const ctxText = ctxData.length
              ? ctxData.join("\n\n---\n\n")
              : "(žádný kontext)";
            document.getElementById("context").textContent = ctxText;
          } else {
            document.getElementById("context").textContent =
              "❌ Kontext se nepodařilo načíst";
          }
        } catch (e) {
          document.getElementById("context").textContent =
            "❌ Kontext se nepodařilo načíst";
        }
  
        // measure the time it takes to get a response
        const startTime = performance.now();
  
        const formData = new FormData();
        formData.append("message", msg);
        formData.append(
          "private",
          document.getElementById('memory-private').checked ? '1' : '0'
        );
        if (file) {
          formData.append("file", file);
        }
        if (document.getElementById('save-txt').checked) {
          formData.append('save', '1');
        }
  
        let res;
        try {
          res = await authFetch("/ask_file", {
            method: "POST",
            body: formData
          });
        } catch (e) {
          document.getElementById("response").textContent =
            "❌ Chyba při odesílání";
          document.getElementById("download").style.display = "none";
          document.getElementById('feedback').style.display = 'block';
          return;
        }
  
        const contentType = res.headers.get("Content-Type") || "";
        const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
        const timestamp = new Date().toLocaleTimeString();
  
        if (!res.ok) {
          let errText = res.statusText || `HTTP ${res.status}`;
          if (contentType.includes("application/json")) {
            const data = await res.json();
            errText = data.error || errText;
            document.getElementById("debug").textContent = data.debug ? data.debug.join("\n") : "(žádný debug)";
          }
          document.getElementById("response").textContent = `❌ ${errText}`;
          document.getElementById("download").style.display = "none";
          document.getElementById('feedback').style.display = 'block';
          conversationLog += `[${timestamp}] 👤 ${msg}\n[${timestamp}] ❌ ${errText}\n\n`;
        } else if (contentType.includes("application/json")) {
          const data = await res.json();
          document.getElementById("response").textContent = data.response || "❌ Chyba odpovědi";
          document.getElementById("debug").textContent = data.debug ? data.debug.join("\n") : "(žádný debug)";
          conversationLog += `[${timestamp}] 👤 ${msg}\n[${timestamp}] 🤖 ${data.response}\n\n`;
          const link = document.getElementById("download");
          if (data.download_url) {
            link.href = data.download_url;
            link.textContent = "⬇️ Stáhnout odpověď";
            link.style.display = "inline";
          } else {
            link.style.display = "none";
          }
          document.getElementById('feedback').style.display = 'block';
        } else {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const answer = res.headers.get("X-Answer") || "";
          const debug = res.headers.get("X-Debug");
          const debugData = debug ? JSON.parse(debug) : [];
          document.getElementById("response").textContent = answer || "❌ Chyba odpovědi";
          document.getElementById("debug").textContent = debugData.length ? debugData.join("\n") : "(žádný debug)";
          conversationLog += `[${timestamp}] 👤 ${msg}\n[${timestamp}] 🤖 ${answer}\n\n`;
          document.getElementById('feedback').style.display = 'block';
          const disposition = res.headers.get("Content-Disposition") || "";
          let filename = "response";
          const m = disposition.match(/filename="?([^";]+)"?/);
          if (m) filename = m[1];
          const link = document.getElementById("download");
          link.href = url;
          link.download = filename;
          link.textContent = `⬇️ ${filename}`;
          link.style.display = "inline";
        }
        document.getElementById("log").textContent = conversationLog;
        document.getElementById("duration").textContent = `⏱ ${elapsed} s`;
  
        document.getElementById("message").value = "";
        fileInput.value = "";
  
        document.getElementById("status").textContent = `🟢 Připraven za ${elapsed} s.`;
        document.getElementById("activity").textContent = "";
      }
  
      function sendFeedback(vote) {
        const body = {
          vote,
          response: document.getElementById('response').textContent
        };
        authFetch('/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        }).then(res => {
          let msg;
          if (res.status === 401) {
            msg = '❌ Nepřihlášen – přihlaste se';
          } else {
            msg = res.ok ? '✅ Díky za zpětnou vazbu' : '❌ Chyba při odesílání';
          }
          document.getElementById('feedback-status').textContent = msg;
        });
      }
  
      function showCorrection() {
        document.getElementById('correction').style.display = 'block';
      }
  
      function submitCorrection() {
        const text = document.getElementById('correction-text').value.trim();
        if (!text) return;
        const body = {
          correction: text,
          response: document.getElementById('response').textContent
        };
        authFetch('/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        }).then(res => {
          let msg;
          if (res.status === 401) {
            msg = '❌ Nepřihlášen – přihlaste se';
          } else {
            msg = res.ok ? '✅ Díky za zpětnou vazbu' : '❌ Chyba při odesílání';
          }
          document.getElementById('feedback-status').textContent = msg;
        });
        document.getElementById('correction-text').value = '';
        document.getElementById('correction').style.display = 'none';
      }
  
      async function uploadKnowledge() {
        const fileInput = document.getElementById('knowledge-file');
        const file = fileInput.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);
        formData.append('private', document.getElementById('knowledge-private').checked ? '1' : '0');
        const desc = document.getElementById('knowledge-desc').value.trim();
        if (desc) formData.append('description', desc);
        const topic = document.getElementById('knowledge-topic').value;
        if (topic) formData.append('topic', topic);
        const res = await authFetch('/knowledge/upload', { method: 'POST', body: formData });
        document.getElementById('knowledge-status').textContent = res.ok ? '✅ Uloženo' : '❌ Chyba';
        if (res.ok) {
          document.getElementById('knowledge-desc').value = '';
        }
        fileInput.value = '';
      }
  
      async function deleteByTime() {
        const from = document.getElementById('delete-from').value;
        const to = document.getElementById('delete-to').value;
        const body = {};
        if (from) body.from = from;
        if (to) body.to = to;
        const res = await authFetch('/memory/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        const data = await res.json();
        document.getElementById('delete-status').textContent = res.ok ? data.message : '❌ Chyba';
      }
  
      async function deleteByKeyword() {
        const keyword = document.getElementById('delete-keyword').value.trim();
        if (!keyword) return;
        const res = await authFetch('/memory/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ keyword })
        });
        const data = await res.json();
        document.getElementById('delete-status').textContent = res.ok ? data.message : '❌ Chyba';
      }
  
      async function loadPending() {
        const res = await authFetch('/knowledge/pending');
        if (!res.ok) return;
        const data = await res.json();
        const list = document.getElementById('pending-list');
        list.textContent = '';
        data.forEach(item => {
          const li = document.createElement('li');
          li.textContent = item.file + ' ';
          const ok = document.createElement('button');
          ok.textContent = '✅';
          ok.onclick = () => approveFile(item.file);
          const no = document.createElement('button');
          no.textContent = '❌';
          no.onclick = () => rejectFile(item.file);
          li.appendChild(ok);
          li.appendChild(no);
          list.appendChild(li);
        });
      }
  
      async function approveFile(file) {
        await authFetch('/knowledge/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file })
        });
        loadPending();
      }
  
      async function rejectFile(file) {
        await authFetch('/knowledge/reject', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file })
        });
        loadPending();
      }
  
      document.getElementById("message").addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          ask();
        }
      });
      window.toggleEnv = toggleEnv;
      initEnv();
      checkAuth();
});

