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

  function authHeader() {
    const token = localStorage.getItem('token') || '';
    return token ? { 'Authorization': 'Bearer ' + token } : {};
  }

  async function loadModel() {
    try {
      const res = await fetch('/model', { headers: authHeader() });
      const data = await res.json();
      const model = data.model || '';
      document.getElementById('current-model').textContent = model;
      const select = document.getElementById('model-select');
      if (select) select.value = model;
      const info = MODEL_INFO[model];
      document.getElementById('model-desc').textContent = info ? info.desc : '';
    } catch (err) {
      console.error(err);
    }
  }

  async function switchModel() {
    const select = document.getElementById('model-select');
    const model = select.value;
    document.getElementById('model-status').textContent = '⏳ Switching…';
    try {
      const res = await fetch('/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ model })
      });
      const data = await res.json();
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
    }
  }

  function setProgress(on) {
    const el = document.getElementById('progress');
    if (el) el.style.display = on ? 'block' : 'none';
  }

  async function ask() {
    const msg = document.getElementById('message').value;
    const fileInput = document.getElementById('file');
    const file = fileInput.files[0];
    const isPrivate = document.getElementById('memory-private').checked;
    const save = document.getElementById('save-txt').checked;

    setProgress(true);
    document.getElementById('activity').textContent = '⏳ Čekejte…';

    try {
      let data;
      if (file) {
        const form = new FormData();
        form.append('message', msg);
        form.append('file', file);
        form.append('private', isPrivate ? '1' : '0');
        if (save) form.append('save', '1');
        const res = await fetch('/ask_file', {
          method: 'POST',
          headers: authHeader(),
          body: form
        });
        data = await res.json();
      } else {
        const res = await fetch('/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader() },
          body: JSON.stringify({ message: msg, private: isPrivate })
        });
        data = await res.json();
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
    try {
      const res = await fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        document.getElementById('feedback-status').textContent = '✅ Díky za hodnocení';
      } else {
        const data = await res.json();
        document.getElementById('feedback-status').textContent = '❌ ' + (data.error || res.status);
      }
    } catch (err) {
      document.getElementById('feedback-status').textContent = '❌ ' + err;
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

  const select = document.getElementById('model-select');
  if (select) {
    select.addEventListener('change', () => {
      const model = select.value;
      const info = MODEL_INFO[model];
      document.getElementById('model-desc').textContent = info ? info.desc : '';
    });
  }

  loadModel();
});
