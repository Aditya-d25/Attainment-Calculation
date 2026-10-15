/**
 * CO-PO Mapping Agent - Main Frontend Application
 * Handles cascading curriculum selection (Year -> Department -> Subject),
 * automated outcome verification, PDF extraction, and AI mapping matrix.
 */

const S = {
  hierarchy: { years: [], departments: [], tree: {} },
  selectedYear: null,
  selectedDept: null,
  courseId: null,
  currentCourse: null,
  frameworkId: null,
  cos: [],
  pos: [],
  mappings: [],
  editingOutcome: null, // { mode: 'add'|'edit', type: 'CO'|'PO', item: Object }
  editingCell: null,
  selectedFile: null
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
  if (!t) return;
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
    const codeA = a.outcome_code || a.po_code || a.pso_code || a.co_code || '';
    const codeB = b.outcome_code || b.po_code || b.pso_code || b.co_code || '';
    return codeA.localeCompare(codeB, undefined, { numeric: true });
  });
}

// -------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------

function init() {
  // Tabs setup
  document.querySelectorAll('.tabs button').forEach(btn => {
    btn.onclick = () => switchTab(btn.dataset.tab);
  });

  // Setup Drag & Drop File Input
  setupFileInput();

  // Setup Custom Glassmorphism Dropdowns with blur & animation
  initCustomSelects();

  // PDF Upload actions
  const uploadForm = $('pdf-upload-form');
  if (uploadForm) uploadForm.onsubmit = handlePDFUpload;
  const uploadBtn = $('upload-btn');
  if (uploadBtn) uploadBtn.onclick = handlePDFUpload;

  // Cascading Curriculum Hierarchy Selectors
  const yearSelect = $('year-select');
  if (yearSelect) yearSelect.onchange = handleYearChange;

  const deptSelect = $('dept-select');
  if (deptSelect) deptSelect.onchange = handleDeptChange;

  const courseSelect = $('course-select');
  if (courseSelect) courseSelect.onchange = handleCourseChange;

  const resetBtn = $('btn-reset-hierarchy');
  if (resetBtn) resetBtn.onclick = resetHierarchy;

  // Temporary Database Truncate buttons
  setupTruncateDbHandlers();

  // Outcome add/edit modal events
  const addCoBtn = $('add-co-btn');
  if (addCoBtn) addCoBtn.onclick = () => openOutcomeModal('add', 'CO');
  const addPoBtn = $('add-po-btn');
  if (addPoBtn) addPoBtn.onclick = () => openOutcomeModal('add', 'PO');

  const outcomeModalForm = $('outcome-modal-form');
  if (outcomeModalForm) outcomeModalForm.onsubmit = saveOutcomeModal;
  const outcomeModalClose = $('outcome-modal-close');
  if (outcomeModalClose) outcomeModalClose.onclick = () => $('outcome-modal').classList.remove('open');
  const outcomeModalCancel = $('outcome-modal-cancel');
  if (outcomeModalCancel) outcomeModalCancel.onclick = () => $('outcome-modal').classList.remove('open');

  // Workflow Progression Buttons
  const proceedBtn = $('proceed-matrix-btn');
  if (proceedBtn) proceedBtn.onclick = proceedToMatrixGeneration;
  const proceedBtnBottom = $('proceed-matrix-btn-bottom');
  if (proceedBtnBottom) proceedBtnBottom.onclick = proceedToMatrixGeneration;
  const backOutcomesBtn = $('back-outcomes-btn');
  if (backOutcomesBtn) backOutcomesBtn.onclick = () => switchTab('outcomes-tab');

  const genBtn = $('generate-btn');
  if (genBtn) genBtn.onclick = generateMapping;
  const exportBtn = $('export-button');
  if (exportBtn) exportBtn.onclick = exportExcel;

  // AI Reasoning Drawer and cell override
  const drawerClose = $('drawer-close');
  if (drawerClose) drawerClose.onclick = () => $('drawer').classList.remove('open');
  const editClose = $('edit-close');
  if (editClose) editClose.onclick = () => $('edit-modal').classList.remove('open');
  const editCancel = $('edit-cancel');
  if (editCancel) editCancel.onclick = () => $('edit-modal').classList.remove('open');
  const editForm = $('edit-form');
  if (editForm) editForm.onsubmit = saveCellOverride;

  // Logout button
  const logoutBtn = $('btn-logout');
  if (logoutBtn) {
    logoutBtn.onclick = async (e) => {
      if (e) e.preventDefault();
      try {
        await fetch('/api/auth/logout', { method: 'POST' });
      } catch (err) {
        console.warn('Logout error:', err);
      }
      window.location.href = '/login';
    };
  }

  // Load initial profile, connection status, and hierarchy
  loadInitialData();
}

async function loadUserProfile() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data && data.authenticated && data.user) {
      const user = data.user;
      const avatarEl = $('user-avatar-img');
      const nameEl = $('user-name-display');
      const roleEl = $('user-role-display');
      const badgeEl = $('user-profile-badge');

      if (avatarEl) {
        avatarEl.src = user.picture || `https://api.dicebear.com/7.x/initials/svg?seed=${encodeURIComponent(user.name)}&backgroundColor=10b981`;
      }
      if (nameEl) nameEl.textContent = user.name;
      if (roleEl) roleEl.textContent = user.role || 'Faculty';
      if (badgeEl) badgeEl.style.display = 'flex';
    }
  } catch (err) {
    console.warn('Could not load user profile:', err);
  }
}

async function loadInitialData() {
  loadUserProfile();
  prefetchChatbotAnimation();

  try {
    const cfg = await api('/api/mapping/config/current');
    const badge = $('mode-badge');
    if (badge) badge.textContent = cfg.mock_mode ? 'Reasoning Engine (Mock Mode)' : 'AI Connected (Gemini)';
  } catch {
    const badge = $('mode-badge');
    if (badge) badge.textContent = 'Local Workspace';
  }

  await loadHierarchy();
}

// -------------------------------------------------------------
// GLASSMORPHISM CUSTOM SELECT SYSTEM (BLUR & ANIMATIONS)
// -------------------------------------------------------------

function initCustomSelects() {
  ['year-select', 'dept-select', 'course-select'].forEach(id => {
    const trigger = $(`trigger-${id}`);
    const wrapper = $(`wrapper-${id}`);
    const menu = $(`menu-${id}`);
    if (!trigger || !wrapper || !menu) return;

    trigger.onclick = (e) => {
      e.stopPropagation();
      if (trigger.disabled || trigger.classList.contains('disabled')) return;
      
      const isOpen = wrapper.classList.contains('open');
      closeAllCustomSelects();
      if (!isOpen) {
        wrapper.classList.add('open');
        menu.style.display = 'block';
        trigger.setAttribute('aria-expanded', 'true');
      }
    };
  });

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.custom-select-wrapper')) {
      closeAllCustomSelects();
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeAllCustomSelects();
    }
  });
}

function closeAllCustomSelects() {
  document.querySelectorAll('.custom-select-wrapper').forEach(w => {
    w.classList.remove('open');
    const menu = w.querySelector('.custom-select-menu');
    if (menu) menu.style.display = 'none';
    const trigger = w.querySelector('.custom-select-trigger');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
  });
}

function syncCustomSelect(selectId) {
  const nativeSelect = $(selectId);
  if (!nativeSelect) return;

  const trigger = $(`trigger-${selectId}`);
  const menu = $(`menu-${selectId}`);
  const wrapper = $(`wrapper-${selectId}`);
  if (!trigger || !menu || !wrapper) return;

  // Sync disabled state
  if (nativeSelect.disabled) {
    trigger.disabled = true;
    trigger.classList.add('disabled');
    wrapper.classList.remove('open');
    menu.style.display = 'none';
  } else {
    trigger.disabled = false;
    trigger.classList.remove('disabled');
  }

  // Find currently selected option
  const selectedOption = nativeSelect.options[nativeSelect.selectedIndex] || nativeSelect.options[0];
  const triggerLabel = trigger.querySelector('.trigger-label');
  
  if (triggerLabel && selectedOption) {
    const rawText = selectedOption.text || '';
    const match = rawText.match(/^(.*?)(\s*\((.+?)\))?$/);
    const mainText = match ? match[1].trim() : rawText;
    const badgeText = match && match[3] ? match[3] : '';

    if (badgeText) {
      const isOk = badgeText.includes('COs in DB') && !badgeText.includes('No COs');
      triggerLabel.innerHTML = `<span class="opt-text">${esc(mainText)}</span><span class="opt-tag ${isOk ? 'has-cos' : 'no-cos'}">${esc(badgeText.replace(' in DB', ''))}</span>`;
    } else {
      triggerLabel.textContent = mainText;
    }
  }

  // Populate options menu
  menu.innerHTML = Array.from(nativeSelect.options).map((opt, index) => {
    const isSelected = opt.value === nativeSelect.value;
    const rawText = opt.text || '';
    const isPlaceholder = !opt.value;

    const match = rawText.match(/^(.*?)(\s*\((.+?)\))?$/);
    const mainText = match ? match[1].trim() : rawText;
    const badgeText = match && match[3] ? match[3] : '';

    let badgeHtml = '';
    if (badgeText) {
      const isOk = badgeText.includes('COs in DB') && !badgeText.includes('No COs');
      badgeHtml = `<span class="opt-tag ${isOk ? 'has-cos' : 'no-cos'}">${esc(badgeText.replace(' in DB', ''))}</span>`;
    }

    const checkHtml = isSelected && !isPlaceholder ? '<span class="opt-check">✓</span>' : '';

    return `
      <div class="custom-select-option ${isSelected ? 'selected' : ''} ${isPlaceholder ? 'placeholder-option' : ''}" 
           data-value="${esc(opt.value)}" 
           data-index="${index}">
        <span class="opt-text">${esc(mainText)}</span>
        ${badgeHtml}
        ${checkHtml}
      </div>
    `;
  }).join('');

  // Attach click listeners to options
  menu.querySelectorAll('.custom-select-option').forEach(item => {
    item.onclick = (e) => {
      e.stopPropagation();
      const val = item.dataset.value;
      nativeSelect.value = val;
      closeAllCustomSelects();
      nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
    };
  });
}

// -------------------------------------------------------------
// CASCADING CURRICULUM SELECTION (YEAR -> DEPT -> SUBJECT)
// -------------------------------------------------------------

async function loadHierarchy(autoSelectSubjectId = null) {
  try {
    const data = await api('/api/subjects/meta/hierarchy');
    S.hierarchy = data;

    const yearSelect = $('year-select');
    const deptSelect = $('dept-select');
    const courseSelect = $('course-select');

    if (!yearSelect) return;

    if (!data.years || data.years.length === 0) {
      yearSelect.innerHTML = '<option value="">-- No Years in DB (Upload Syllabus Below) --</option>';
      if (deptSelect) {
        deptSelect.innerHTML = '<option value="">-- First Select Year --</option>';
        deptSelect.disabled = true;
      }
      if (courseSelect) {
        courseSelect.innerHTML = '<option value="">-- First Select Department --</option>';
        courseSelect.disabled = true;
      }
      syncCustomSelect('year-select');
      syncCustomSelect('dept-select');
      syncCustomSelect('course-select');
      showUploadSection();
      return;
    }

    // Populate Year Dropdown
    yearSelect.innerHTML = '<option value="">-- Select Year --</option>' +
      data.years.map(y => `<option value="${esc(y)}">${esc(y)}</option>`).join('');

    syncCustomSelect('year-select');

    if (autoSelectSubjectId) {
      // Find where autoSelectSubjectId lives in the tree
      let foundYear = null;
      let foundDept = null;
      for (const y of Object.keys(data.tree || {})) {
        for (const d of Object.keys(data.tree[y] || {})) {
          if ((data.tree[y][d] || []).some(s => Number(s.id) === Number(autoSelectSubjectId))) {
            foundYear = y;
            foundDept = d;
            break;
          }
        }
        if (foundYear) break;
      }

      if (foundYear && foundDept) {
        yearSelect.value = foundYear;
        S.selectedYear = foundYear;
        populateDepartmentDropdown(foundYear);
        if (deptSelect) deptSelect.value = foundDept;
        S.selectedDept = foundDept;
        populateSubjectDropdown(foundYear, foundDept);
        if (courseSelect) courseSelect.value = autoSelectSubjectId;
        syncCustomSelect('year-select');
        syncCustomSelect('dept-select');
        syncCustomSelect('course-select');
        await checkSubjectOutcomes(autoSelectSubjectId);
        return;
      }
    }

    // Default to clean unselected state
    resetHierarchy();

  } catch (err) {
    console.error('Failed to load hierarchy:', err);
    toast('Failed to load curriculum hierarchy.');
  }
}

function resetHierarchy() {
  S.selectedYear = null;
  S.selectedDept = null;
  S.courseId = null;
  S.currentCourse = null;
  S.cos = [];
  S.pos = [];
  S.mappings = [];

  const yearSelect = $('year-select');
  const deptSelect = $('dept-select');
  const courseSelect = $('course-select');

  if (yearSelect && S.hierarchy.years && S.hierarchy.years.length > 0) yearSelect.value = '';
  if (deptSelect) {
    deptSelect.innerHTML = '<option value="">-- First Select Year --</option>';
    deptSelect.disabled = true;
  }
  if (courseSelect) {
    courseSelect.innerHTML = '<option value="">-- First Select Department --</option>';
    courseSelect.disabled = true;
  }

  syncCustomSelect('year-select');
  syncCustomSelect('dept-select');
  syncCustomSelect('course-select');

  showUploadSection();
  updateStepper(1);
}

function setupTruncateDbHandlers() {
  const truncateButtons = [
    $('btn-truncate-db'),
    $('btn-truncate-db-inline')
  ].filter(Boolean);

  truncateButtons.forEach(btn => {
    btn.onclick = async (e) => {
      e.preventDefault();
      const confirmed = confirm(
        "⚠️ DANGER: Are you sure you want to TRUNCATE the entire database?\n\n" +
        "• All courses, COs, and POs/PSOs will be deleted.\n" +
        "• All AI mapping results will be wiped.\n" +
        "• ChromaDB vector embeddings cache will be reset.\n\n" +
        "This allows you to re-upload a syllabus PDF and test your models completely fresh.\n\n" +
        "Click OK to proceed with database wipe."
      );
      if (!confirmed) return;

      const originalHtml = btn.innerHTML;
      btn.innerHTML = `<span>Truncating...</span>`;
      btn.disabled = true;

      try {
        const resp = await fetch('/api/database/truncate', { method: 'POST' });
        const data = await resp.json();
        if (resp.ok) {
          alert("✅ " + (data.message || "Database successfully truncated!"));
          window.location.reload();
        } else {
          alert("❌ Failed to truncate database: " + (data.detail || "Server error"));
          btn.innerHTML = originalHtml;
          btn.disabled = false;
        }
      } catch (err) {
        alert("❌ Error connecting to server: " + err.message);
        btn.innerHTML = originalHtml;
        btn.disabled = false;
      }
    };
  });
}

function handleYearChange(e) {
  const year = e.target.value;
  S.selectedYear = year;
  S.selectedDept = null;
  S.courseId = null;
  S.currentCourse = null;

  const deptSelect = $('dept-select');
  const courseSelect = $('course-select');

  showUploadSection();
  updateStepper(1);

  if (!year) {
    if (deptSelect) {
      deptSelect.innerHTML = '<option value="">-- First Select Year --</option>';
      deptSelect.disabled = true;
    }
    if (courseSelect) {
      courseSelect.innerHTML = '<option value="">-- First Select Department --</option>';
      courseSelect.disabled = true;
    }
    syncCustomSelect('year-select');
    syncCustomSelect('dept-select');
    syncCustomSelect('course-select');
    return;
  }

  populateDepartmentDropdown(year);
  syncCustomSelect('year-select');
}

function populateDepartmentDropdown(year) {
  const deptSelect = $('dept-select');
  const courseSelect = $('course-select');
  if (!deptSelect) return;

  const depts = Object.keys(S.hierarchy.tree[year] || {});

  deptSelect.disabled = false;
  deptSelect.innerHTML = '<option value="">-- Select Department --</option>' +
    depts.map(d => `<option value="${esc(d)}">${esc(d)}</option>`).join('');

  if (courseSelect) {
    courseSelect.innerHTML = '<option value="">-- First Select Department --</option>';
    courseSelect.disabled = true;
  }

  syncCustomSelect('dept-select');
  syncCustomSelect('course-select');
}

function handleDeptChange(e) {
  const dept = e.target.value;
  S.selectedDept = dept;
  S.courseId = null;
  S.currentCourse = null;

  showUploadSection();
  updateStepper(1);

  if (!dept) {
    const courseSelect = $('course-select');
    if (courseSelect) {
      courseSelect.innerHTML = '<option value="">-- First Select Department --</option>';
      courseSelect.disabled = true;
    }
    syncCustomSelect('dept-select');
    syncCustomSelect('course-select');
    return;
  }

  populateSubjectDropdown(S.selectedYear, dept);
  syncCustomSelect('dept-select');
}

function populateSubjectDropdown(year, dept) {
  const courseSelect = $('course-select');
  if (!courseSelect) return;

  const subjects = (S.hierarchy.tree[year]?.[dept]) || [];

  courseSelect.disabled = false;
  courseSelect.innerHTML = '<option value="">-- Select Subject / Course --</option>' +
    subjects.map(s => {
      const coText = s.co_count ? ` (${s.co_count} COs in DB)` : ' (No COs in DB)';
      return `<option value="${s.id}">[${esc(s.course_code)}] ${esc(s.course_name)}${coText}</option>`;
    }).join('');

  syncCustomSelect('course-select');
}

async function handleCourseChange(e) {
  const courseId = parseInt(e.target.value, 10);
  syncCustomSelect('course-select');

  if (!courseId) {
    S.courseId = null;
    S.currentCourse = null;
    showUploadSection();
    updateStepper(1);
    return;
  }

  await checkSubjectOutcomes(courseId);
}

function showUploadSection(courseMeta = null) {
  const uploadPanel = $('state-upload-syllabus');
  const hasOutcomesPanel = $('state-has-outcomes');
  const kicker = $('upload-kicker');
  const title = $('upload-section-title');
  const subtitle = $('upload-section-subtitle');

  if (hasOutcomesPanel) hasOutcomesPanel.style.display = 'none';
  if (uploadPanel) uploadPanel.style.display = 'block';

  if (courseMeta) {
    if (kicker) kicker.textContent = 'DATABASE OUTCOMES NOT FOUND';
    if (title) title.textContent = `Upload Syllabus PDF for ${courseMeta.course_code}: ${courseMeta.course_name}`;
    if (subtitle) subtitle.textContent = `No Course Outcomes (COs) or Program Outcomes (POs) are stored in the database for this subject yet. Upload the official syllabus PDF below to extract and save them directly into the database.`;
  } else {
    if (kicker) kicker.textContent = 'ACADEMIC SYLLABUS EXTRACTION';
    if (title) title.textContent = 'Upload Syllabus PDF';
    if (subtitle) subtitle.textContent = 'Upload university engineering syllabus PDF (e.g. SPPU, AICTE, NEP-2020) to extract Program Outcomes (POs/PSOs), courses, and Course Outcomes (COs) into the database.';
  }

  // Clear previous upload status and inputs
  const fileInput = $('pdf-file-input');
  if (fileInput) fileInput.value = '';
  const fileLabel = $('file-label');
  if (fileLabel) fileLabel.textContent = 'Click or drag & drop syllabus PDF here';
  const uploadStatus = $('upload-status');
  if (uploadStatus) {
    uploadStatus.className = 'upload-status';
    uploadStatus.textContent = '';
  }
  S.selectedFile = null;
}

// -------------------------------------------------------------
// DYNAMIC OUTCOMES VERIFICATION (DB FETCH vs SYLLABUS PDF UPLOAD)
// -------------------------------------------------------------

async function checkSubjectOutcomes(courseId) {
  S.courseId = courseId;

  // Retrieve course metadata from hierarchy tree
  let courseMeta = null;
  if (S.selectedYear && S.selectedDept) {
    courseMeta = (S.hierarchy.tree[S.selectedYear]?.[S.selectedDept] || []).find(s => s.id === courseId);
  }
  S.currentCourse = courseMeta;

  try {
    const statusData = await api(`/api/subjects/${courseId}/outcomes-status`);

    if (statusData.has_outcomes) {
      // -------------------------------------------------------------
      // SUBJECT HAS OUTCOMES IN DB -> Display outcomes & unlock matrix
      // -------------------------------------------------------------
      const uploadPanel = $('state-upload-syllabus');
      const hasOutcomesPanel = $('state-has-outcomes');
      if (uploadPanel) uploadPanel.style.display = 'none';
      if (hasOutcomesPanel) hasOutcomesPanel.style.display = 'block';

      updateStepper(2);

      S.cos = statusData.cos || [];
      S.pos = statusData.pos || [];
      S.frameworkId = statusData.framework_id;

      const bannerTitle = $('selected-course-banner-title');
      const bannerSub = $('selected-course-banner-sub');
      const coTitle = $('co-card-title');
      const matrixTitle = $('matrix-course-title');

      if (bannerTitle) bannerTitle.textContent = `${statusData.course_code}: ${statusData.course_name}`;
      if (bannerSub) bannerSub.textContent = `Loaded from database (${statusData.framework_name || 'Curriculum Framework'}). Verify outcomes below, then proceed to AI matrix calculation.`;
      if (coTitle) coTitle.textContent = `Course Outcomes (${statusData.course_code})`;
      if (matrixTitle) matrixTitle.textContent = `Mapping Matrix: ${statusData.course_code} - ${statusData.course_name}`;

      renderCOs();
      renderPOs();
      updateOutcomesSummary();

      // Check existing mapping matrix in DB
      try {
        const mapRes = await api(`/api/mapping/${courseId}`);
        S.mappings = mapRes.mappings || [];
        renderMatrix();
      } catch {
        S.mappings = [];
        renderMatrix();
      }

      switchTab('outcomes-tab');

    } else {
      // -------------------------------------------------------------
      // SUBJECT HAS NO OUTCOMES IN DB -> Show syllabus PDF upload option
      // -------------------------------------------------------------
      showUploadSection(statusData);
      updateStepper(1);
    }

  } catch (err) {
    console.error('Failed to check outcomes status:', err);
    toast(`Failed to load outcomes: ${err.message}`);
  }
}

// Backward-compatibility alias
const selectCourse = checkSubjectOutcomes;

// -------------------------------------------------------------
// SYLLABUS PDF UPLOAD (EMPTY STATE HANDLER)
// -------------------------------------------------------------

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
    uploadBtn.innerHTML = '<span class="spinner-inline"></span> Extracting Outcomes & Saving to Database...';
  }
  if (statusDiv) {
    statusDiv.className = 'upload-status';
    statusDiv.innerHTML = '<span class="spinner-inline"></span> Parsing syllabus PDF, extracting POs/COs & saving into database...';
  }

  const formData = new FormData();
  formData.append('file', file);
  if (S.courseId) {
    formData.append('subject_id', S.courseId);
  }

  try {
    const res = await api('/api/pdf/upload', {
      method: 'POST',
      body: formData
    });

    if (statusDiv) {
      statusDiv.className = 'upload-status success';
      statusDiv.textContent = `✓ ${res.message} (${res.framework?.po_count || 0} POs, ${res.courses?.length || 0} Courses saved)`;
    }
    toast(`Syllabus saved to database: ${res.framework?.po_count || 0} POs & ${res.courses?.length || 0} courses!`);

    // Reload hierarchy to include the new/updated courses and outcomes
    const targetSubjectId = res.target_subject_id || S.courseId || (res.courses && res.courses.length > 0 ? res.courses[0].id : null);
    await loadHierarchy(targetSubjectId);

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
      uploadBtn.textContent = 'Extract POs & COs from PDF & Save to Database';
    }
  }
}
window.handlePDFUpload = handlePDFUpload;

// -------------------------------------------------------------
// RENDER OUTCOMES & SUMMARY BADGES
// -------------------------------------------------------------

function updateOutcomesSummary() {
  const coCount = S.cos ? S.cos.length : 0;
  const poCount = S.pos ? S.pos.length : 0;

  const coBadge = $('co-count-badge');
  const poBadge = $('po-count-badge');
  if (coBadge) coBadge.textContent = `${coCount} COs`;
  if (poBadge) poBadge.textContent = `${poCount} POs`;

  const footerText = $('footer-status-text');
  if (footerText) {
    if (S.courseId && coCount > 0) {
      footerText.textContent = `Course ready: ${coCount} COs defined against ${poCount} Program Outcomes.`;
    } else {
      footerText.textContent = 'Select a course to review outcomes.';
    }
  }
}

function renderCOs() {
  const container = $('co-list-container');
  if (!container) return;

  if (!S.courseId) {
    container.innerHTML = '<div class="empty-state">Select a course from the dropdown above to view Course Outcomes.</div>';
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
  if (!container) return;

  if (!S.pos || S.pos.length === 0) {
    container.innerHTML = '<div class="empty-state">No Program Outcomes (POs/PSOs) found in this framework. Click "+ Add PO/PSO" to add one.</div>';
    return;
  }

  const sorted = sortOutcomes(S.pos);
  container.innerHTML = sorted.map(po => {
    const code = po.outcome_code || po.po_code || po.pso_code;
    const type = po.outcome_type || (code.startsWith('PSO') ? 'PSO' : 'PO');
    return `
      <div class="item-row">
        <div class="item-content">
          <span class="item-code po-tag">${esc(code)}</span>
          <span class="item-desc">${esc(po.description)}</span>
        </div>
        <div class="item-actions">
          <button class="btn-icon" onclick="openOutcomeModal('edit', '${type}', ${po.id || `'${code}'`})">Edit</button>
          <button class="btn-icon danger" onclick="deletePO(${po.id || `'${code}'`})">Remove</button>
        </div>
      </div>
    `;
  }).join('');
}

// -------------------------------------------------------------
// OUTCOME CRUD (ADD, EDIT, REMOVE)
// -------------------------------------------------------------

async function deleteCO(id) {
  if (!confirm('Are you sure you want to remove this Course Outcome?')) return;
  try {
    await api(`/api/subjects/${S.courseId}/cos/${id}`, { method: 'DELETE' });
    toast('Course Outcome removed.');
    await checkSubjectOutcomes(S.courseId);
  } catch (err) {
    toast(`Failed to delete CO: ${err.message}`);
  }
}
window.deleteCO = deleteCO;

async function deletePO(id) {
  if (!confirm('Are you sure you want to remove this Program Outcome?')) return;
  try {
    if (S.frameworkId) {
      await api(`/api/frameworks/${S.frameworkId}/outcomes/item/${id}`, { method: 'DELETE' });
    } else {
      await api(`/api/subjects/${S.courseId}/pos/${id}`, { method: 'DELETE' });
    }
    toast('Program Outcome removed.');
    await checkSubjectOutcomes(S.courseId);
  } catch (err) {
    toast(`Failed to delete PO: ${err.message}`);
  }
}
window.deletePO = deletePO;

function openOutcomeModal(mode, type, itemId = null) {
  if (type === 'CO' && !S.courseId) return toast('Please select a course first');
  if (type === 'PO' && !S.frameworkId) return toast('No Framework associated with this subject yet');

  let item = null;
  if (mode === 'edit') {
    if (type === 'CO') item = S.cos.find(c => c.id === itemId);
    if (type === 'PO' || type === 'PSO') item = S.pos.find(p => p.id === itemId);
  }

  S.editingOutcome = { mode, type, item };

  $('outcome-modal-kicker').textContent = `${mode.toUpperCase()} ${type === 'CO' ? 'COURSE OUTCOME' : 'PROGRAM OUTCOME'}`;
  $('outcome-modal-title').textContent = mode === 'edit' ? `Edit ${item?.co_code || item?.outcome_code || item?.po_code || type}` : `New ${type}`;

  const typeGroup = $('modal-type-group');
  if (typeGroup) typeGroup.style.display = (type === 'PO' || type === 'PSO') ? 'block' : 'none';
  if (type === 'PO' || type === 'PSO') {
    const typeSelect = $('modal-outcome-type');
    if (typeSelect) typeSelect.value = item?.outcome_type || type;
  }

  const codeInput = $('modal-outcome-code');
  const descInput = $('modal-outcome-desc');
  if (codeInput) {
    codeInput.value = item ? (item.co_code || item.outcome_code || item.po_code) : (type === 'CO' ? `CO${S.cos.length + 1}` : `PO${S.pos.length + 1}`);
  }
  if (descInput) {
    descInput.value = item ? item.description : '';
  }

  $('outcome-modal').classList.add('open');
}
window.openOutcomeModal = openOutcomeModal;

async function saveOutcomeModal(e) {
  e.preventDefault();
  const { mode, type, item } = S.editingOutcome;
  const code = $('modal-outcome-code').value.trim();
  const desc = $('modal-outcome-desc').value.trim();
  const oType = $('modal-outcome-type') ? $('modal-outcome-type').value : 'PO';

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
      await checkSubjectOutcomes(S.courseId);

    } else if (type === 'PO' || type === 'PSO') {
      if (mode === 'add') {
        await api(`/api/frameworks/${S.frameworkId}/outcomes/item`, {
          method: 'POST',
          body: JSON.stringify({ outcome_code: code, outcome_type: oType, description: desc })
        });
        toast('Program Outcome added.');
      } else {
        await api(`/api/frameworks/${S.frameworkId}/outcomes/item/${item.id}`, {
          method: 'PUT',
          body: JSON.stringify({ outcome_code: code, outcome_type: oType, description: desc })
        });
        toast('Program Outcome updated.');
      }
      await checkSubjectOutcomes(S.courseId);
    }

    $('outcome-modal').classList.remove('open');
  } catch (err) {
    toast(`Failed to save: ${err.message}`);
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

// =============================================================
// AI MAPPING LOADING SCREEN & LOTTIE ANIMATION
// =============================================================

let mappingAnimationInstance = null;
let loaderTickerInterval = null;
let chatbotAnimationDataCache = null;

const LOADER_STATUS_MESSAGES = [
  'Extracting contextual keywords and Bloom\'s taxonomy levels...',
  'Computing hybrid semantic embeddings and correlation vectors...',
  'Evaluating correlation strengths & domain competencies...',
  'Synthesizing explainable AI mapping rationale & evidence...',
  'Calibrating attainment confidence scores and matrix levels...'
];

async function prefetchChatbotAnimation() {
  if (chatbotAnimationDataCache) return chatbotAnimationDataCache;
  try {
    const res = await fetch('/static/animations/chatbot-loading.json');
    if (res.ok) {
      chatbotAnimationDataCache = await res.json();
    }
  } catch (e) {
    console.warn('Could not prefetch chatbot animation JSON:', e);
  }
  return chatbotAnimationDataCache;
}

function syncProgressBarWithBot() {
  const bar = document.querySelector('.loader-progress-bar');
  if (!bar) return;
  bar.style.animation = 'none';
  void bar.offsetWidth; // Force layout reflow to restart CSS keyframes at frame 0
  bar.style.animation = 'botSyncBarAnimation 2.867s infinite cubic-bezier(0.45, 0.05, 0.55, 0.95)';
}

function initMappingLoaderAnimation() {
  const container = $('lottie-bot-container');
  if (!container || !window.lottie) return;

  if (mappingAnimationInstance) {
    mappingAnimationInstance.destroy();
    mappingAnimationInstance = null;
  }
  container.innerHTML = '';

  const animOptions = {
    container: container,
    renderer: 'svg',
    loop: true,
    autoplay: true
  };

  if (chatbotAnimationDataCache) {
    animOptions.animationData = chatbotAnimationDataCache;
  } else {
    animOptions.path = '/static/animations/chatbot-loading.json';
  }

  try {
    mappingAnimationInstance = window.lottie.loadAnimation(animOptions);
    mappingAnimationInstance.addEventListener('DOMLoaded', syncProgressBarWithBot);
    mappingAnimationInstance.addEventListener('loopComplete', syncProgressBarWithBot);
  } catch (err) {
    console.error('Failed to load Lottie chatbot animation:', err);
  }
}

function showMappingLoadingScreen() {
  const loadingBox = $('matrix-loading-state');
  const emptyBox = $('matrix-empty');
  const matrixWrap = $('matrix-wrap');
  const tickerText = $('loader-ticker-text');
  const title = $('loader-title');
  const subtitle = $('loader-subtitle');
  if (!loadingBox) return;

  // Ensure matrix tab is active
  switchTab('matrix-tab');
  updateStepper(3);

  // Hide empty state and existing matrix while loading
  if (emptyBox) emptyBox.style.display = 'none';
  if (matrixWrap) matrixWrap.style.display = 'none';

  if (title) {
    title.textContent = 'Analyzing CO-PO Correlations...';
  }
  if (subtitle) {
    subtitle.textContent = 'Evaluating Bloom\'s Taxonomy cognitive alignment and computing explainable mapping levels.';
  }

  // Initialize and play Lottie animation in the inline container
  initMappingLoaderAnimation();
  if (mappingAnimationInstance) {
    mappingAnimationInstance.play();
  }
  syncProgressBarWithBot();

  // Status message ticker
  let msgIdx = 0;
  if (tickerText) tickerText.textContent = LOADER_STATUS_MESSAGES[0];
  if (loaderTickerInterval) clearInterval(loaderTickerInterval);
  loaderTickerInterval = setInterval(() => {
    msgIdx = (msgIdx + 1) % LOADER_STATUS_MESSAGES.length;
    if (tickerText) {
      tickerText.style.opacity = '0';
      setTimeout(() => {
        tickerText.textContent = LOADER_STATUS_MESSAGES[msgIdx];
        tickerText.style.opacity = '1';
      }, 220);
    }
  }, 2500);

  // Display inline loading box
  loadingBox.style.display = 'flex';
}

function hideMappingLoadingScreen() {
  const loadingBox = $('matrix-loading-state');
  const emptyBox = $('matrix-empty');
  const matrixWrap = $('matrix-wrap');

  if (loadingBox) {
    loadingBox.style.display = 'none';
  }

  if (loaderTickerInterval) {
    clearInterval(loaderTickerInterval);
    loaderTickerInterval = null;
  }

  if (mappingAnimationInstance) {
    mappingAnimationInstance.pause();
  }

  // Restore appropriate view in matrix tab
  if (S.mappings && S.mappings.length > 0) {
    if (matrixWrap) matrixWrap.style.display = 'block';
    if (emptyBox) emptyBox.style.display = 'none';
  } else {
    if (emptyBox) emptyBox.style.display = 'block';
    if (matrixWrap) matrixWrap.style.display = 'none';
  }
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

  showMappingLoadingScreen();

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
    hideMappingLoadingScreen();
    btn.disabled = false;
    btn.textContent = 'Generate Mapping Matrix ⟳';
  }
}

// -------------------------------------------------------------
// MATRIX RENDERING & INTERACTION
// -------------------------------------------------------------

function renderMatrix() {
  const empty = $('matrix-empty');
  const wrap = $('matrix-wrap');
  const loading = $('matrix-loading-state');
  if (loading) loading.style.display = 'none';

  if (!S.courseId || S.cos.length === 0 || S.pos.length === 0) {
    if (empty) {
      empty.style.display = 'block';
      empty.textContent = 'Select a course with COs and POs to generate the mapping matrix.';
    }
    if (wrap) wrap.innerHTML = '';
    return;
  }

  if (!S.mappings || S.mappings.length === 0) {
    if (empty) {
      empty.style.display = 'block';
      empty.textContent = 'No mapping matrix generated yet for this course. Click "Generate Mapping Matrix" above to run AI mapping.';
    }
    if (wrap) wrap.innerHTML = '';
    return;
  }

  if (empty) empty.style.display = 'none';

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

  if (wrap) wrap.innerHTML = html;

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
