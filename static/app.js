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
  // následují funkce jako loadModel(), switchModel(), ask(), uploadKnowledge(),
  // deleteByTime(), deleteByKeyword() atd.
});
