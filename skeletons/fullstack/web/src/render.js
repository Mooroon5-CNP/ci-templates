'use strict';

function renderPage(title) {
    return `<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><title>${title}</title></head>
<body>
  <h1>${title}</h1>
  <p>Front (node) + back (python) dans une seule image.</p>
  <p>Réponse de l'API : <code id="api">…</code></p>
  <script>
    fetch('/api/info').then(r => r.json()).then(d => {
      document.getElementById('api').textContent = JSON.stringify(d);
    });
  </script>
</body>
</html>
`;
}

module.exports = { renderPage };
