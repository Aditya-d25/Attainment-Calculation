const S = {
  frameworks: [],
  frameworkId: null,
  courses: [],
  courseId: null,
  cos: [],
  pos: [],
  mappings: [],
  editingOutcome: null, // { mode: 'add'|'edit', type: 'CO'|'PO', item: Object }
  editingCell: null
};

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));

async function api(url, opts = {}) {
  const isFormData = opts.body instanceof FormData;
  const headers = isFormData ? { ...opts.headers } : { 'Content-Type': 'application/json', ...opts.headers };
  
  const r = await fetch(url, { ...opts, headers });
  if (!r.ok) {
    const x = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(x.detail || 'Request failed');
  }
  return r.json();
}

function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3500);
}

function updateStepper(step) {
  const s1 = $('step-1-indicator');
  const s2 = $('step-2-indicator');
  const s3 = $('step-3-indicator');

  [s1, s2, s3].forEach(s => {
    if (s) s.classList.remove('active', 'completed');
  });

  if (step === 1) {
    if (s1) s1.classList.add('active');
  } else if (step === 2) {
    if (s1) s1.classList.add('completed');
    if (s2) s2.classList.add('active');
  } else if (step === 3) {
    if (s1) s1.classList.add('completed');
    if (s2) s2.classList.add('completed');
    if (s3) s3.classList.add('active');
  }
}

function switchTab(tabId) {
  document.querySelectorAll('.tabs button').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabId);
  });
  document.querySelectorAll('.page').forEach(p => {
    p.classList.toggle('active', p.id === tabId);
  });

  if (tabId === 'outcomes-tab') {
    updateStepper(2);
  } else if (tabId === 'matrix-tab') {
    updateStepper(3);
  }
}

function sortOutcomes(arr) {
  return [...arr].sort((a, b) => {
    const codeA = a.outcome_code || a.po_code || a.co_code || '';
    const codeB = b.outcome_code || b.po_code || b.co_code || '';
    return codeA.localeCompare(codeB, undefined, { numeric: true });
  });
}

// -------------------------------------------------------------
// INITIALIZATION & SYLLABUS PDF UPLOAD
// -------------------------------------------------------------

function init() {
  // Tab setup
  document.querySelectorAll('.tabs button').forEach(btn => {
    btn.onclick = () => switchTab(btn.dataset.tab);
  });

  // Setup Drag & Drop File Input immediately
  setupFileInput();

  // Attach Event Handlers immediately & synchronously
  const uploadForm = $('pdf-upload-form');
  if (uploadForm) {
    uploadForm.onsubmit = handlePDFUpload;
  }
  const uploadBtn = $('upload-btn');
  if (uploadBtn) {
    uploadBtn.onclick = handlePDFUpload;
  }
  const courseSelect = $('course-select');
  if (courseSelect) {
    courseSelect.onchange = handleCourseSelectChange;
  }

  $('add-co-btn').onclick = () => openOutcomeModal('add', 'CO');
  $('add-po-btn').onclick = () => openOutcomeModal('add', 'PO');
  $('outcome-modal-form').onsubmit = saveOutcomeModal;
  $('outcome-modal-close').onclick = () => $('outcome-modal').classList.remove('open');
  if ($('outcome-modal-cancel')) {
    $('outcome-modal-cancel').onclick = () => $('outcome-modal').classList.remove('open');
  }

  // Workflow Progression Buttons
  $('proceed-matrix-btn').onclick = proceedToMatrixGeneration;
  $('proceed-matrix-btn-bottom').onclick = proceedToMatrixGeneration;
  if ($('back-outcomes-btn')) {
    $('back-outcomes-btn').onclick = () => switchTab('outcomes-tab');
  }

  $('generate-btn').onclick = generateMapping;
  $('export-button').onclick = exportExcel;

  $('drawer-close').onclick = () => $('drawer').classList.remove('open');
  $('edit-close').onclick = () => $('edit-modal').classList.remove('open');
  if ($('edit-cancel')) {
    $('edit-cancel').onclick = () => $('edit-modal').classList.remove('open');
  }
  $('edit-form').onsubmit = saveCellOverride;

  // Async load initial data in background
  loadInitialData();
}

async function loadInitialData() {
  // Health / Config check
  try {
    const cfg = await api('/api/mapping/config/current');
    $('mode-badge').textContent = cfg.mock_mode ? 'Reasoning Engine (Mock Mode)' : 'AI Connected (Gemini)';
  } catch {
    $('mode-badge').textContent = 'Local Workspace';
  }

  // Load Frameworks & Courses
  await fetchFrameworks();
}

function setupFileInput() {
  const fileInput = $('pdf-file-input');
  const fileLabel = $('file-label');
  const dropArea = $('drop-area');

  if (!fileInput || !fileLabel || !dropArea) return;

  fileInput.onchange = () => {
    if (fileInput.files && fileInput.files.length > 0) {
      S.selectedFile = fileInput.files[0];
      fileLabel.textContent = `Selected: ${fileInput.files[0].name}`;
    } else {
      S.selectedFile = null;
      fileLabel.textContent = 'Click or drag & drop syllabus PDF here';
    }
  };

  ['dragenter', 'dragover'].forEach(eventName => {
    dropArea.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
      dropArea.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
      dropArea.classList.remove('dragover');
    }, false);
  });

  dropArea.addEventListener('drop', e => {
    e.preventDefault();
    e.stopPropagation();
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      S.selectedFile = dt.files[0];
      try { fileInput.files = dt.files; } catch {}
      fileLabel.textContent = `Selected: ${S.selectedFile.name}`;
    }
  });
}

async function handlePDFUpload(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  const fileInput = $('pdf-file-input');
  const file = S.selectedFile || (fileInput && fileInput.files && fileInput.files[0]);

  if (!file) {
    toast('Please select or drop a syllabus PDF file first');
    return;
  }

  const uploadBtn = $('upload-btn');
  const statusDiv = $('upload-status');
  
  if (uploadBtn) {
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<span class="spinner-inline"></span> Extracting Outcomes...';
  }
  if (statusDiv) {
    statusDiv.className = 'upload-status';
    statusDiv.innerHTML = '<span class="spinner-inline"></span> Parsing syllabus PDF & extracting outcomes...';
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await api('/api/pdf/upload', {
      method: 'POST',
      body: formData
    });

    if (statusDiv) {
      statusDiv.className = 'upload-status success';
      statusDiv.textContent = `✓ ${res.message} (${res.framework.po_count} POs, ${res.courses.length} Courses)`;
    }
    toast(`Syllabus extracted: ${res.framework.po_count} POs & ${res.courses.length} courses!`);

    // Reload frameworks & select the new framework
    S.frameworks = await api('/api/frameworks');
    if (res.framework && res.framework.id) {
      await selectFramework(res.framework.id);
    } else {
      await fetchFrameworks();
    }

    updateStepper(2);

  } catch (err) {
    console.error('PDF upload error:', err);
    if (statusDiv) {
      statusDiv.className = 'upload-status error';
      statusDiv.textContent = `Error: ${err.message}`;
    }
    toast(`Failed to process PDF: ${err.message}`);
  } finally {
    if (uploadBtn) {
      uploadBtn.disabled = false;
      uploadBtn.textContent = 'Extract POs & COs from PDF';
    }
  }
}
window.handlePDFUpload = handlePDFUpload;

// -------------------------------------------------------------
// FRAMEWORK & COURSE MANAGEMENT
// -------------------------------------------------------------

async function fetchFrameworks(selectFrameworkId = null) {
  try {
    S.frameworks = await api('/api/frameworks');
    if (!S.frameworks || S.frameworks.length === 0) {
      $('current-framework-name').textContent = 'Framework: Upload Syllabus PDF to extract framework';
      $('current-framework-details').textContent = 'Upload syllabus PDF above to automatically populate courses & outcomes.';
      populateCourseDropdown();
      return;
    }

    // Auto-select framework
    let targetId = selectFrameworkId;
    if (!targetId) {
      // Find the framework that has subjects attached
      const allSubjects = await api('/api/subjects').catch(() => []);
      const fwWithSubs = S.frameworks.find(f => allSubjects.some(s => Number(s.framework_id) === Number(f.id)));
      if (fwWithSubs) {
        targetId = fwWithSubs.id;
      } else {
        const sorted = [...S.frameworks].sort((a, b) => Number(b.id) - Number(a.id));
        targetId = sorted[0].id;
      }
    }

    if (targetId) {
      await selectFramework(targetId);
    }
  } catch (err) {
    console.error('Failed to fetch frameworks:', err);
  }
}

async function selectFramework(id) {
  S.frameworkId = id;
  const fw = S.frameworks.find(f => Number(f.id) === Number(id));
  if (fw) {
    $('current-framework-name').textContent = `Framework: ${fw.name}`;
    $('current-framework-details').textContent = `Department: ${fw.department || 'Engineering'} | Shared Outcomes Framework`;
  }

  // Fetch POs/PSOs for this framework
  try {
    S.pos = await api(`/api/frameworks/${id}/outcomes`);
    renderPOs();
  } catch (err) {
    console.error('Failed to fetch framework outcomes:', err);
  }

  // Fetch Courses attached to this framework
  try {
    const allSubjects = await api('/api/subjects');
    S.courses = allSubjects.filter(s => s.framework_id && Number(s.framework_id) === Number(id));
    if (S.courses.length === 0 && allSubjects.length > 0) {
      S.courses = allSubjects;
    }
    populateCourseDropdown();
  } catch (err) {
    console.error('Failed to fetch courses:', err);
  }
}

function populateCourseDropdown() {
  const select = $('course-select');
  if (!S.courses || S.courses.length === 0) {
    select.innerHTML = '<option value="">-- No Courses Extracted Yet --</option>';
    return;
  }

  select.innerHTML = '<option value="">-- Select Course from List --</option>' +
    S.courses.map(c => {
      const coText = (c.co_count !== undefined) ? ` (${c.co_count} COs)` : '';
      return `<option value="${c.id}">[${esc(c.course_code)}] ${esc(c.course_name)}${coText}</option>`;
    }).join('');

  if (S.courseId && S.courses.some(c => Number(c.id) === Number(S.courseId))) {
    select.value = S.courseId;
  } else if (S.courses.length > 0) {
    const targetCourse = S.courses.find(c => (c.co_count || 0) > 0) || S.courses[0];
    select.value = targetCourse.id;
    selectCourse(targetCourse.id);
  }
}

async function handleCourseSelectChange(e) {
  const courseId = parseInt(e.target.value, 10);
  if (courseId) {
    await selectCourse(courseId);
  } else {
    S.courseId = null;
    S.cos = [];
    S.mappings = [];
    renderCOs();
    renderMatrix();
    updateOutcomesSummary();
  }
}

async function selectCourse(courseId) {
  S.courseId = courseId;
  $('course-select').value = courseId;
  const course = S.courses.find(c => c.id === courseId);

  if (course) {
    $('selected-course-banner-title').textContent = `${course.course_code}: ${course.course_name}`;
    $('selected-course-banner-sub').textContent = `Review and edit the extracted outcomes below. When ready, click Proceed to generate the explainable CO-PO matrix.`;
    $('co-card-title').textContent = `Course Outcomes (${course.course_code})`;
    $('matrix-course-title').textContent = `Mapping Matrix: ${course.course_code} - ${course.course_name}`;

    // If course belongs to a specific framework, ensure S.frameworkId is aligned
    if (course.framework_id && Number(course.framework_id) !== Number(S.frameworkId)) {
      S.frameworkId = course.framework_id;
      const fw = S.frameworks.find(f => Number(f.id) === Number(course.framework_id));
      if (fw) {
        $('current-framework-name').textContent = `Framework: ${fw.name}`;
      }
    }
  }

  // Fetch COs for selected course
  try {
    S.cos = await api(`/api/subjects/${courseId}/cos`);
    renderCOs();
  } catch (err) {
    console.error('Failed to fetch COs:', err);
    S.cos = [];
    renderCOs();
  }

  // Fetch POs for selected course
  try {
    if (course && course.framework_id) {
      S.pos = await api(`/api/frameworks/${course.framework_id}/outcomes`);
    } else {
      S.pos = await api(`/api/subjects/${courseId}/pos`);
    }
    renderPOs();
  } catch (err) {
    console.error('Failed to fetch POs:', err);
  }

  // Fetch existing Mappings if any
  try {
    const mapRes = await api(`/api/mapping/${courseId}`);
    S.mappings = mapRes.mappings || [];
    renderMatrix();
  } catch (err) {
    S.mappings = [];
    renderMatrix();
  }

  updateOutcomesSummary();
}

function updateOutcomesSummary() {
  const coCount = S.cos ? S.cos.length : 0;
  const poCount = S.pos ? S.pos.length : 0;

  $('co-count-badge').textContent = `${coCount} COs`;
  $('po-count-badge').textContent = `${poCount} POs`;

  const course = S.courses.find(c => c.id === S.courseId);
  if (course) {
    course.co_count = coCount;
    $('footer-status-text').textContent = `Course ready: ${coCount} COs defined against ${poCount} Program Outcomes.`;
  } else {
    $('footer-status-text').textContent = 'Select a course to review outcomes.';
  }
}

// -------------------------------------------------------------
// RENDER OUTCOMES LISTS (WITH EDIT & REMOVE BUTTONS)
// -------------------------------------------------------------

function renderCOs() {
  const container = $('co-list-container');
  if (!S.courseId) {
    container.innerHTML = '<div class="empty-state">Select a course from the list above to view its Course Outcomes.</div>';
    return;
  }

  if (S.cos.length === 0) {
    container.innerHTML = '<div class="empty-state">No Course Outcomes found for this course yet. Click "+ Add CO" to add one.</div>';
    return;
  }

  const sorted = sortOutcomes(S.cos);
  container.innerHTML = sorted.map(co => `
    <div class="item-row">
      <div class="item-content">
        <span class="item-code">${esc(co.co_code)}</span>
        <span class="item-desc">${esc(co.description)}</span>
      </div>
      <div class="item-actions">
        <button class="btn-icon" onclick="openOutcomeModal('edit', 'CO', ${co.id})">Edit</button>
        <button class="btn-icon danger" onclick="deleteCO(${co.id})">Remove</button>
      </div>
    </div>
  `).join('');
}

function renderPOs() {
  const container = $('po-list-container');
  if (!S.frameworkId && !S.courseId) {
    container.innerHTML = '<div class="empty-state">Upload or select a framework to view Program Outcomes.</div>';
    return;
  }

  if (S.pos.length === 0) {
    container.innerHTML = '<div class="empty-state">No Program Outcomes found in this framework. Click "+ Add PO/PSO" to add one.</div>';
    return;
  }

  const sorted = sortOutcomes(S.pos);
  container.innerHTML = sorted.map(po => {
    const code = po.outcome_code || po.po_code || po.pso_code;
    return `
      <div class="item-row">
        <div class="item-content">
          <span class="item-code">${esc(code)}</span>
          <span class="item-desc">${esc(po.description)}</span>
        </div>
        <div class="item-actions">
          <button class="btn-icon" onclick="openOutcomeModal('edit', 'PO', ${po.id})">Edit</button>
          <button class="btn-icon danger" onclick="deletePO(${po.id})">Remove</button>
        </div>
      </div>
    `;
  }).join('');
}

// -------------------------------------------------------------
// EDIT & REMOVE HANDLERS FOR COs & POs
// -------------------------------------------------------------

async function deleteCO(id) {
  if (!confirm('Are you sure you want to remove this Course Outcome?')) return;
  try {
    await api(`/api/subjects/${S.courseId}/cos/${id}`, { method: 'DELETE' });
    toast('Course Outcome removed.');
    await selectCourse(S.courseId);
  } catch (err) {
    toast(`Failed to delete CO: ${err.message}`);
  }
}

async function deletePO(id) {
  if (!confirm('Are you sure you want to remove this Program Outcome?')) return;
  try {
    await api(`/api/frameworks/${S.frameworkId}/outcomes/item/${id}`, { method: 'DELETE' });
    toast('Program Outcome removed.');
    await selectFramework(S.frameworkId);
    if (S.courseId) await selectCourse(S.courseId);
  } catch (err) {
    toast(`Failed to delete PO: ${err.message}`);
  }
}

function openOutcomeModal(mode, type, itemId = null) {
  if (type === 'CO' && !S.courseId) return toast('Please select a course first');
  if (type === 'PO' && !S.frameworkId) return toast('Please select or upload a framework first');

  let item = null;
  if (mode === 'edit') {
    if (type === 'CO') item = S.cos.find(c => c.id === itemId);
    if (type === 'PO') item = S.pos.find(p => p.id === itemId);
  }

  S.editingOutcome = { mode, type, item };

  $('outcome-modal-kicker').textContent = `${mode.toUpperCase()} ${type === 'CO' ? 'COURSE OUTCOME' : 'PROGRAM OUTCOME'}`;
  $('outcome-modal-title').textContent = mode === 'edit' ? `Edit ${item.co_code || item.outcome_code || item.po_code}` : `New ${type}`;

  $('modal-type-group').style.display = type === 'PO' ? 'block' : 'none';
  if (type === 'PO') {
    $('modal-outcome-type').value = item?.outcome_type || 'PO';
  }

  $('modal-outcome-code').value = item ? (item.co_code || item.outcome_code || item.po_code) : (type === 'CO' ? `CO${S.cos.length + 1}` : `PO${S.pos.length + 1}`);
  $('modal-outcome-desc').value = item ? item.description : '';

  $('outcome-modal').classList.add('open');
}

async function saveOutcomeModal(e) {
  e.preventDefault();
  const { mode, type, item } = S.editingOutcome;
  const code = $('modal-outcome-code').value.trim();
  const desc = $('modal-outcome-desc').value.trim();
  const oType = $('modal-outcome-type').value;

  if (!code || !desc) return toast('Please provide both code and description');

  try {
    if (type === 'CO') {
      if (mode === 'add') {
        await api(`/api/subjects/${S.courseId}/cos`, {
          method: 'POST',
          body: JSON.stringify({ co_code: code, description: desc })
        });
        toast('Course Outcome added successfully.');
      } else {
        await api(`/api/subjects/${S.courseId}/cos/${item.id}`, {
          method: 'PUT',
          body: JSON.stringify({ co_code: code, description: desc })
        });
        toast('Course Outcome updated.');
      }
      await selectCourse(S.courseId);

    } else if (type === 'PO') {
      if (mode === 'add') {
        await api(`/api/frameworks/${S.frameworkId}/outcomes/item`, {
          method: 'POST',
          body: JSON.stringify({ outcome_code: code, outcome_type: oType, description: desc })
        });
        toast('Program Outcome added successfully.');
      } else {
        await api(`/api/frameworks/${S.frameworkId}/outcomes/item/${item.id}`, {
          method: 'PUT',
          body: JSON.stringify({ outcome_code: code, outcome_type: oType, description: desc })
        });
        toast('Program Outcome updated.');
      }
      await selectFramework(S.frameworkId);
      if (S.courseId) await selectCourse(S.courseId);
    }

    $('outcome-modal').classList.remove('open');
  } catch (err) {
    toast(`Error: ${err.message}`);
  }
}

// -------------------------------------------------------------
// WORKFLOW PROGRESSION & MATRIX GENERATION
// -------------------------------------------------------------

async function proceedToMatrixGeneration() {
  if (!S.courseId) {
    return toast('Please select a course first from the list above');
  }
  if (!S.cos || S.cos.length === 0) {
    return toast('This course has no Course Outcomes (COs). Please add at least one CO.');
  }
  if (!S.pos || S.pos.length === 0) {
    return toast('No Program Outcomes (POs) found. Please upload syllabus or add POs.');
  }

  // Switch to matrix tab
  switchTab('matrix-tab');
  updateStepper(3);

  // Generate matrix
  await generateMapping();
}

async function generateMapping() {
  if (!S.courseId) return toast('Please select a course first');
  if (S.cos.length === 0) return toast('Add or extract Course Outcomes (COs) first');
  if (S.pos.length === 0) return toast('Add or extract Program Outcomes (POs) first');

  const btn = $('generate-btn');
  const matrixEmpty = $('matrix-empty');
  btn.disabled = true;
  btn.textContent = 'Generating AI Matrix...';

  if (matrixEmpty) {
    matrixEmpty.style.display = 'block';
    matrixEmpty.textContent = 'Analyzing CO-PO correlations and computing explainable mapping levels...';
  }

  try {
    const res = await api('/api/mapping/generate', {
      method: 'POST',
      body: JSON.stringify({
        subject_id: S.courseId,
        method: 'hybrid'
      })
    });

    S.mappings = res.mappings || [];
    renderMatrix();
    toast('CO-PO mapping matrix generated successfully!');
  } catch (err) {
    toast(`Failed to generate matrix: ${err.message}`);
    if (matrixEmpty) {
      matrixEmpty.textContent = `Error: ${err.message}`;
    }
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Mapping Matrix ⟳';
  }
}

function renderMatrix() {
  const empty = $('matrix-empty');
  const wrap = $('matrix-wrap');

  if (!S.courseId || S.cos.length === 0 || S.pos.length === 0) {
    empty.style.display = 'block';
    empty.textContent = 'Select a course with COs and POs to generate the mapping matrix.';
    wrap.innerHTML = '';
    return;
  }

  if (!S.mappings || S.mappings.length === 0) {
    empty.style.display = 'block';
    empty.textContent = 'No mapping matrix generated yet for this course. Click "Generate Mapping Matrix" above to run AI mapping.';
    wrap.innerHTML = '';
    return;
  }

  empty.style.display = 'none';

  const sortedCos = sortOutcomes(S.cos);
  const sortedPos = sortOutcomes(S.pos);

  const mapLookup = new Map(S.mappings.map(m => [`${m.co_code}|${m.po_pso_code}`, m]));

  let html = `
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Course Outcome (CO)</th>
            ${sortedPos.map(p => {
              const code = p.outcome_code || p.po_code || p.pso_code;
              return `<th title="${esc(p.description)}">${esc(code)}</th>`;
            }).join('')}
          </tr>
        </thead>
        <tbody>
          ${sortedCos.map(co => `
            <tr>
              <td>
                <b>${esc(co.co_code)}</b><br>
                <span class="muted">${esc(co.description)}</span>
              </td>
              ${sortedPos.map(po => {
                const poCode = po.outcome_code || po.po_code || po.pso_code;
                const key = `${co.co_code}|${poCode}`;
                const m = mapLookup.get(key);
                const lvl = m?.final_mapping_level ?? m?.mapping_level ?? 0;
                const mId = m ? m.id : '';
                return `
                  <td>
                    <button class="cell level-${lvl}" 
                            data-id="${mId}" 
                            title="Click: view reasoning · Double-click: edit level">
                      ${lvl === 0 ? '—' : lvl}
                    </button>
                  </td>
                `;
              }).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    <p class="matrix-note">
      <b>Legend:</b> Level 3: Strong · 2: Moderate · 1: Low · —: No relationship.
      Click a cell to see AI reasoning & evidence keywords. Double-click to edit mapping level with faculty audit notes.
    </p>
  `;

  wrap.innerHTML = html;

  // Attach cell click & double-click events
  document.querySelectorAll('.cell').forEach(btn => {
    btn.onclick = () => {
      const id = parseInt(btn.dataset.id, 10);
      if (id) showCellDetails(id);
    };
    btn.ondblclick = e => {
      e.preventDefault();
      const id = parseInt(btn.dataset.id, 10);
      if (id) openCellOverrideModal(id);
    };
  });
}

function showCellDetails(mappingId) {
  const m = S.mappings.find(x => x.id === mappingId);
  if (!m) return;

  $('detail-title').textContent = `${m.co_code} → ${m.po_pso_code}`;
  $('detail-level').textContent = m.final_mapping_level ?? m.mapping_level;
  $('detail-confidence').textContent = `${Math.round(m.confidence * 100)}%`;
  $('detail-similarity').textContent = Number(m.similarity_score).toFixed(2);
  $('detail-reason').textContent = m.reason || 'No explanation generated.';

  const evidenceList = Array.isArray(m.evidence) ? m.evidence : [];
  $('detail-evidence').innerHTML = evidenceList.length > 0
    ? evidenceList.map(tag => `<span>${esc(tag)}</span>`).join('')
    : '<span>General semantic alignment</span>';

  $('drawer').classList.add('open');
}

function openCellOverrideModal(mappingId) {
  const m = S.mappings.find(x => x.id === mappingId);
  if (!m) return;

  S.editingCell = m;
  $('edit-title').textContent = `Override ${m.co_code} → ${m.po_pso_code}`;
  $('edit-level').value = m.final_mapping_level ?? m.mapping_level;
  $('edit-notes').value = m.faculty_notes || '';

  $('edit-modal').classList.add('open');
}

async function saveCellOverride(e) {
  e.preventDefault();
  const m = S.editingCell;
  if (!m) return;

  const finalLvl = parseInt($('edit-level').value, 10);
  const notes = $('edit-notes').value.trim();

  try {
    const res = await api(`/api/mapping/${m.id}/review`, {
      method: 'PUT',
      body: JSON.stringify({
        faculty_decision: 'edited',
        final_mapping_level: finalLvl,
        faculty_notes: notes || null
      })
    });

    Object.assign(m, res.mapping);
    $('edit-modal').classList.remove('open');
    $('drawer').classList.remove('open');
    renderMatrix();
    toast('Cell override saved.');
  } catch (err) {
    toast(`Failed to save override: ${err.message}`);
  }
}

function exportExcel() {
  if (!S.courseId) return toast('Please select a course first');
  window.open(`/api/excel/export/${S.courseId}`, '_blank');
}

// Global initialization on DOM ready
document.addEventListener('DOMContentLoaded', init);
