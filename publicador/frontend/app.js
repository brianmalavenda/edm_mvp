  // Ajustar a donde corra el backend (ver README del backend para el puerto/host real)
  const API_BASE_URL = 'http://localhost:8990/api';

  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const btnChoose = document.getElementById('btnChoose');
  const fileLoaded = document.getElementById('fileLoaded');
  const fileNameEl = document.getElementById('fileName');
  const btnQuitar = document.getElementById('btnQuitar');
  const actions = document.getElementById('actions');
  const btnPreview = document.getElementById('btnPreview');
  const btnPublicar = document.getElementById('btnPublicar');
  const previewPanel = document.getElementById('previewPanel');
  const previewBody = document.getElementById('previewBody');
  const previewStatus = document.getElementById('previewStatus');
  const resultsPanel = document.getElementById('resultsPanel');
  const resultsBody = document.getElementById('resultsBody');

  let currentFile = null;

  // ---------- Carga de archivo (click, input, drag&drop) ----------
  btnChoose.addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) setFile(e.target.files[0]);
  });

  ['dragenter', 'dragover'].forEach(evt =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add('dragover'); })
  );
  ['dragleave', 'drop'].forEach(evt =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); })
  );
  dropzone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files[0];
    if (file) setFile(file);
  });

  btnQuitar.addEventListener('click', resetFile);

  function setFile(file) {
    if (!file.name.endsWith('.docx')) {
      alert('Solo se aceptan archivos .docx');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      alert('El archivo supera los 15 MB');
      return;
    }
    currentFile = file;
    fileNameEl.textContent = file.name;
    dropzone.style.display = 'none';
    fileLoaded.style.display = 'flex';
    actions.classList.add('visible');
    previewPanel.classList.remove('visible');
    resultsPanel.style.display = 'none';
  }

  function resetFile() {
    currentFile = null;
    fileInput.value = '';
    dropzone.style.display = 'block';
    fileLoaded.style.display = 'none';
    actions.classList.remove('visible');
    previewPanel.classList.remove('visible');
    resultsPanel.style.display = 'none';
  }

  // ---------- Previsualizar ----------
  btnPreview.addEventListener('click', async () => {
    if (!currentFile) return;
    btnPreview.disabled = true;
    previewStatus.textContent = 'Analizando el documento...';
    previewStatus.classList.remove('error');
    previewPanel.classList.add('visible');
    previewBody.innerHTML = '';

    try {
      const formData = new FormData();
      formData.append('file', currentFile);

      const resp = await fetch(`${API_BASE_URL}/preview`, { method: 'POST', body: formData });
      const data = await resp.json();

      if (!resp.ok) throw new Error(data.error || 'error desconocido');

      if (!data.notes.length) {
        previewStatus.textContent = 'No se detectó ninguna nota (¿falta el estilo @1VOLA?)';
        previewStatus.classList.add('error');
        return;
      }

      data.notes.forEach(n => {
        const tr = document.createElement('tr');
        tr.dataset.indice = n.indice;
        tr.innerHTML = `
          <td class="titulo">${escapeHtml(n.titulo)}</td>
          <td>${badge(n.tiene_volanta)}</td>
          <td>${badge(n.tiene_copete)}</td>
          <td>${badge(n.tiene_imagen)}</td>
          <td><input type="checkbox" class="chk-publicar" checked></td>
        `;
        previewBody.appendChild(tr);
      });

      previewStatus.textContent = `${data.notes.length} nota(s) detectada(s).`;
    } catch (err) {
      previewStatus.textContent = `No se pudo previsualizar: ${err.message}`;
      previewStatus.classList.add('error');
    } finally {
      btnPreview.disabled = false;
    }
  });

  function badge(value) {
    return value
      ? '<span class="badge yes">✓</span>'
      : '<span class="badge no">✗</span>';
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ---------- Publicar ----------
  btnPublicar.addEventListener('click', async () => {
    if (!currentFile) return;

    // TODO: hoy el backend publica TODAS las notas del documento.
    // Cuando se agregue el filtro selectivo en el backend, acá se arma
    // la lista de índices tildados y se manda junto con el archivo:
    // const indicesSeleccionados = [...previewBody.querySelectorAll('tr')]
    //   .filter(tr => tr.querySelector('.chk-publicar')?.checked !== false)
    //   .map(tr => tr.dataset.indice);

    btnPublicar.disabled = true;
    btnPreview.disabled = true;
    resultsPanel.style.display = 'block';
    resultsBody.innerHTML = '<div class="status-line">Subiendo y encolando el documento...</div>';

    try {
      const formData = new FormData();
      formData.append('file', currentFile);

      const resp = await fetch(`${API_BASE_URL}/upload`, { method: 'POST', body: formData });
      const data = await resp.json();

      if (resp.status === 409) {
        resultsBody.innerHTML = `<div class="status-line error">Este archivo ya fue procesado antes (documento #${data.document_id}).</div>`;
        return;
      }
      if (!resp.ok) throw new Error(data.error || 'error desconocido');

      resultsBody.innerHTML = '<div class="status-line">Documento encolado. Publicando notas...</div>';
      await pollDocumentStatus(data.document_id);
    } catch (err) {
      resultsBody.innerHTML = `<div class="status-line error">Error al publicar: ${err.message}</div>`;
    } finally {
      btnPublicar.disabled = false;
      btnPreview.disabled = false;
    }
  });

  async function pollDocumentStatus(documentId) {
    const maxIntentos = 60; // ~2 minutos con polling cada 2s
    for (let i = 0; i < maxIntentos; i++) {
      await sleep(2000);
      const resp = await fetch(`${API_BASE_URL}/documents/${documentId}`);
      const doc = await resp.json();

      if (doc.status === 'done' || doc.status === 'error') {
        renderResultados(doc);
        return;
      }
      resultsBody.innerHTML = `<div class="status-line">Estado: ${doc.status}... (${doc.notes.length}/${doc.total_notes || '?'} notas procesadas)</div>`;
    }
    resultsBody.innerHTML = '<div class="status-line error">Se agotó el tiempo de espera. Revisá el estado más tarde en el panel de documentos.</div>';
  }

  function renderResultados(doc) {
    if (doc.status === 'error') {
      resultsBody.innerHTML = `<div class="status-line error">El procesamiento falló: ${escapeHtml(doc.error_message || 'error desconocido')}</div>`;
      return;
    }
    resultsBody.innerHTML = doc.notes.map(n => `
      <div class="result-row">
        ${n.status === 'published' ? '<span class="badge yes">✓</span>' : '<span class="badge no">✗</span>'}
        <span>${escapeHtml(n.titulo)}</span>
        ${n.wp_link ? `<a href="${n.wp_link}" target="_blank">ver nota →</a>` : `<span style="color:var(--fail-red)">${escapeHtml(n.error_message || '')}</span>`}
      </div>
    `).join('');
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }