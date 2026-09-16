/**
 * AI CO-PO Mapping Agent — Frontend Application
 *
 * Single-page app with tabbed navigation managing the complete
 * CO-PO mapping workflow: setup, generation, review, evaluation, export.
 */

// ---- State ----
const state = {
    currentTab: 'setup',
    subjectId: null,
    subjects: [],
    cos: [],
    pos: [],
    psos: [],
    mappings: [],
    evaluations: [],
    config: {},
};

// ---- API Helpers ----
const API = {
    async get(url) {
        const res = await fetch(url);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Request failed');
        }
        return res.json();
    },

    async post(url, data) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Request failed');
        }
        return res.json();
    },

    async put(url, data) {
        const res = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Request failed');
        }
        return res.json();
    },

    async upload(url, formData) {
        const res = await fetch(url, { method: 'POST', body: formData });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Upload failed');
        }
        return res.json();
    },

    async del(url) {
        const res = await fetch(url, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Delete failed');
        }
        return res.json();
    },
};

// ---- Toast Notifications ----
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ---- Loading ----
function showLoading(text = 'Processing...') {
    const overlay = document.getElementById('loading-overlay');
    document.getElementById('loading-text').textContent = text;
    overlay.classList.add('active');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.remove('active');
}

// ---- Tab Navigation ----
function switchTab(tabId) {
    state.currentTab = tabId;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabId}`);
    });
}

// ---- Initialization ----
document.addEventListener('DOMContentLoaded', async () => {
    // Tab click handlers
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Load config
    try {
        state.config = await API.get('/api/mapping/config/current');
        updateConfigDisplay();
    } catch (e) {
        console.warn('Could not load config:', e);
    }

    // Load existing subjects
    await loadSubjects();

    // Setup form handlers
    setupFormHandlers();
});

function updateConfigDisplay() {
    const badge = document.getElementById('mode-badge');
    if (badge) {
        badge.textContent = state.config.mock_mode ? '🧪 Mock Mode' : `🤖 ${state.config.llm_provider}`;
    }
}

// =============================================
// SETUP TAB
// =============================================

async function loadSubjects() {
    try {
        state.subjects = await API.get('/api/subjects');
        renderSubjectList();
    } catch (e) {
        console.error('Failed to load subjects:', e);
    }
}

function renderSubjectList() {
    const container = document.getElementById('subject-list');
    if (!state.subjects.length) {
        container.innerHTML = '<p class="text-muted">No subjects yet. Create one to get started.</p>';
        return;
    }
    container.innerHTML = state.subjects.map(s => `
        <li>
            <span class="item-code">${s.course_code}</span>
            <span class="item-desc">${s.course_name}</span>
            <div class="item-actions">
                <button class="btn btn-sm btn-primary" onclick="selectSubject(${s.id})">Select</button>
                <button class="btn btn-sm btn-danger" onclick="deleteSubject(${s.id})">✕</button>
            </div>
        </li>
    `).join('');
}

function setupFormHandlers() {
    // Create subject
    document.getElementById('form-subject').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = {
            course_code: document.getElementById('course-code').value,
            course_name: document.getElementById('course-name').value,
            semester: document.getElementById('semester').value || null,
            academic_year: document.getElementById('academic-year').value || null,
            department: document.getElementById('department').value || null,
        };
        try {
            const result = await API.post('/api/subjects', data);
            showToast('Subject created!', 'success');
            await loadSubjects();
            selectSubject(result.id);
            e.target.reset();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Add CO
    document.getElementById('form-add-co').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!state.subjectId) { showToast('Select a subject first', 'warning'); return; }
        const data = {
            co_code: document.getElementById('co-code').value,
            description: document.getElementById('co-desc').value,
            univ_attainment: parseFloat(document.getElementById('co-univ-attainment').value) || 0.0,
            internal_attainment: parseFloat(document.getElementById('co-internal-attainment').value) || 0.0,
        };
        try {
            await API.post(`/api/subjects/${state.subjectId}/cos`, data);
            showToast('CO added!', 'success');
            await loadSubjectData();
            e.target.reset();
            document.getElementById('co-univ-attainment').value = '0.00';
            document.getElementById('co-internal-attainment').value = '3.00';
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Add PO
    document.getElementById('form-add-po').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!state.subjectId) { showToast('Select a subject first', 'warning'); return; }
        const data = {
            po_code: document.getElementById('po-code').value,
            description: document.getElementById('po-desc').value,
        };
        try {
            await API.post(`/api/subjects/${state.subjectId}/pos`, data);
            showToast('PO added!', 'success');
            await loadSubjectData();
            e.target.reset();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Add PSO
    document.getElementById('form-add-pso').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!state.subjectId) { showToast('Select a subject first', 'warning'); return; }
        const data = {
            pso_code: document.getElementById('pso-code').value,
            description: document.getElementById('pso-desc').value,
        };
        try {
            await API.post(`/api/subjects/${state.subjectId}/psos`, data);
            showToast('PSO added!', 'success');
            await loadSubjectData();
            e.target.reset();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Excel upload
    const uploadArea = document.getElementById('excel-upload-area');
    const fileInput = document.getElementById('excel-file-input');

    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
    uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleExcelUpload(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleExcelUpload(e.target.files[0]);
    });
}

async function selectSubject(id) {
    state.subjectId = id;
    const subject = state.subjects.find(s => s.id === id);
    document.getElementById('selected-subject-name').textContent =
        subject ? `${subject.course_code} — ${subject.course_name}` : '';
    document.getElementById('selected-subject-panel').classList.remove('hidden');
    await loadSubjectData();
    showToast(`Selected: ${subject.course_code}`, 'info');
}

async function deleteSubject(id) {
    if (!confirm('Delete this subject and all its data?')) return;
    try {
        await API.del(`/api/subjects/${id}`);
        if (state.subjectId === id) {
            state.subjectId = null;
            document.getElementById('selected-subject-panel').classList.add('hidden');
        }
        showToast('Subject deleted', 'info');
        await loadSubjects();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function loadSubjectData() {
    if (!state.subjectId) return;
    try {
        const [cos, pos, psos] = await Promise.all([
            API.get(`/api/subjects/${state.subjectId}/cos`),
            API.get(`/api/subjects/${state.subjectId}/pos`),
            API.get(`/api/subjects/${state.subjectId}/psos`),
        ]);
        state.cos = cos;
        state.pos = pos;
        state.psos = psos;
        renderCOList();
        renderPOList();
        renderPSOList();
    } catch (err) {
        showToast('Failed to load subject data', 'error');
    }
}

function renderCOList() {
    const el = document.getElementById('co-list');
    if (!state.cos.length) {
        el.innerHTML = '<p class="text-muted">No COs added yet.</p>';
        return;
    }
    el.innerHTML = state.cos.map(co => `
        <li>
            <span class="item-code">${co.co_code}</span>
            <span class="item-desc">${co.description} <small style="color:var(--text-muted); margin-left:8px; font-weight:500;">(Univ: ${(co.univ_attainment ?? 0).toFixed(2)}, Internal: ${(co.internal_attainment ?? 0).toFixed(2)})</small></span>
            <div class="item-actions">
                <button class="btn btn-sm btn-danger" onclick="deleteCO(${co.id})">✕</button>
            </div>
        </li>
    `).join('');
}

async function updateCOAttainment(coId, field, value) {
    const numVal = parseFloat(value) || 0.0;
    try {
        await API.put(`/api/subjects/${state.subjectId}/cos/${coId}`, {
            [field]: numVal,
        });
        const co = state.cos.find(c => c.id === coId);
        if (co) co[field] = numVal;
        renderMappingMatrix();
        showToast('Attainment updated', 'info');
    } catch (err) {
        showToast('Failed to update attainment: ' + err.message, 'error');
    }
}

function renderPOList() {
    const el = document.getElementById('po-list');
    if (!state.pos.length) {
        el.innerHTML = '<p class="text-muted">No POs added yet.</p>';
        return;
    }
    el.innerHTML = state.pos.map(po => `
        <li>
            <span class="item-code">${po.po_code}</span>
            <span class="item-desc">${po.description}</span>
        </li>
    `).join('');
}

function renderPSOList() {
    const el = document.getElementById('pso-list');
    if (!state.psos.length) {
        el.innerHTML = '<p class="text-muted">No PSOs added yet.</p>';
        return;
    }
    el.innerHTML = state.psos.map(pso => `
        <li>
            <span class="item-code">${pso.pso_code}</span>
            <span class="item-desc">${pso.description}</span>
        </li>
    `).join('');
}

async function deleteCO(coId) {
    try {
        await API.del(`/api/subjects/${state.subjectId}/cos/${coId}`);
        await loadSubjectData();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleExcelUpload(file) {
    if (!state.subjectId) {
        showToast('Please select a subject first', 'warning');
        return;
    }
    showLoading('Parsing Excel file...');
    const formData = new FormData();
    formData.append('file', file);
    try {
        const result = await API.upload(`/api/excel/upload-reference/${state.subjectId}`, formData);
        hideLoading();
        if (result.status === 'error') {
            showToast('Parse errors: ' + result.errors.join('; '), 'error');
        } else {
            showToast(`Imported ${result.mappings_count} reference mappings from "${result.sheet_name}"`, 'success');
            await loadSubjectData();
        }
    } catch (err) {
        hideLoading();
        showToast('Upload failed: ' + err.message, 'error');
    }
}

function loadDefaultPOs() {
    if (!state.subjectId) { showToast('Select a subject first', 'warning'); return; }
    const defaultPOs = [
        { po_code: 'PO1', description: 'Engineering knowledge: Apply the knowledge of mathematics, science, engineering fundamentals, and an engineering specialization to the solution of complex engineering problems.' },
        { po_code: 'PO2', description: 'Problem analysis: Identify, formulate, review research literature, and analyze complex engineering problems reaching substantiated conclusions using first principles of mathematics, natural sciences, and engineering sciences.' },
        { po_code: 'PO3', description: 'Design/development of solutions: Design solutions for complex engineering problems and design system components or processes that meet the specified needs with appropriate consideration for the public health and safety, and the cultural, societal, and environmental considerations.' },
        { po_code: 'PO4', description: 'Conduct investigations of complex problems: Use research-based knowledge and research methods including design of experiments, analysis and interpretation of data, and synthesis of the information to provide valid conclusions.' },
        { po_code: 'PO5', description: 'Modern tool usage: Create, select, and apply appropriate techniques, resources, and modern engineering and IT tools including prediction and modeling to complex engineering activities with an understanding of the limitations.' },
        { po_code: 'PO6', description: 'The engineer and society: Apply reasoning informed by the contextual knowledge to assess societal, health, safety, legal and cultural issues and the consequent responsibilities relevant to the professional engineering practice.' },
        { po_code: 'PO7', description: 'Environment and sustainability: Understand the impact of the professional engineering solutions in societal and environmental contexts, and demonstrate the knowledge of, and need for sustainable development.' },
        { po_code: 'PO8', description: 'Ethics: Apply ethical principles and commit to professional ethics and responsibilities and norms of the engineering practice.' },
        { po_code: 'PO9', description: 'Individual and team work: Function effectively as an individual, and as a member or leader in diverse teams, and in multidisciplinary settings.' },
        { po_code: 'PO10', description: 'Communication: Communicate effectively on complex engineering activities with the engineering community and with society at large, such as, being able to comprehend and write effective reports and design documentation, make effective presentations, and give and receive clear instructions.' },
        { po_code: 'PO11', description: 'Project management and finance: Demonstrate knowledge and understanding of the engineering and management principles and apply these to one\'s own work, as a member and leader in a team, to manage projects and in multidisciplinary environments.' },
    ];
    loadBatchPOs(defaultPOs);
}

async function loadBatchPOs(pos) {
    showLoading('Loading POs...');
    try {
        await API.post(`/api/subjects/${state.subjectId}/pos/batch`, pos);
        hideLoading();
        showToast(`Loaded ${pos.length} Program Outcomes`, 'success');
        await loadSubjectData();
    } catch (err) {
        hideLoading();
        showToast(err.message, 'error');
    }
}

function loadDefaultPSOs() {
    if (!state.subjectId) { showToast('Select a subject first', 'warning'); return; }
    const defaultPSOs = [
        { pso_code: 'PSO1', description: 'Apply foundational knowledge of computer science and engineering to solve computational and real-world problems.' },
        { pso_code: 'PSO2', description: 'Design, develop, and deploy software applications using modern tools, programming languages, and frameworks.' },
        { pso_code: 'PSO3', description: 'Apply research-based and innovative approaches to solve interdisciplinary problems using emerging technologies.' },
    ];
    loadBatchPSOs(defaultPSOs);
}

async function loadBatchPSOs(psos) {
    showLoading('Loading PSOs...');
    try {
        await API.post(`/api/subjects/${state.subjectId}/psos/batch`, psos);
        hideLoading();
        showToast(`Loaded ${psos.length} PSOs`, 'success');
        await loadSubjectData();
    } catch (err) {
        hideLoading();
        showToast(err.message, 'error');
    }
}


// =============================================
// AI MAPPING TAB
// =============================================

async function generateMapping() {
    if (!state.subjectId) { showToast('Select a subject first', 'warning'); return; }
    if (!state.cos.length) { showToast('Add Course Outcomes first', 'warning'); return; }
    if (!state.pos.length) { showToast('Add Program Outcomes first', 'warning'); return; }

    const method = document.getElementById('mapping-method').value;
    showLoading(`Generating ${method} mapping...`);

    try {
        const result = await API.post('/api/mapping/generate', {
            subject_id: state.subjectId,
            method: method,
        });
        state.mappings = result.mappings;
        hideLoading();
        showToast(`Generated ${result.count} mappings using ${method} method`, 'success');
        renderMappingMatrix();
        renderReviewTable();
    } catch (err) {
        hideLoading();
        showToast('Generation failed: ' + err.message, 'error');
    }
}

async function loadExistingMappings() {
    if (!state.subjectId) return;
    try {
        const result = await API.get(`/api/mapping/${state.subjectId}`);
        state.mappings = result.mappings;
        if (state.mappings.length) {
            renderMappingMatrix();
            renderReviewTable();
        }
    } catch (e) { /* no mappings yet */ }
}

function renderMappingMatrix() {
    const container = document.getElementById('mapping-matrix');
    if (!state.mappings.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🎯</div>
                <p>No mappings generated yet. Use the button above to generate.</p>
            </div>`;
        return;
    }

    // Build matrix data
    const coSet = [...new Set(state.mappings.map(m => m.co_code))].sort();
    const poSet = [...new Set(state.mappings.filter(m => m.po_pso_type === 'PO').map(m => m.po_pso_code))].sort((a,b) => {
        const na = parseInt(a.replace('PO',''));
        const nb = parseInt(b.replace('PO',''));
        return na - nb;
    });
    const psoSet = [...new Set(state.mappings.filter(m => m.po_pso_type === 'PSO').map(m => m.po_pso_code))].sort((a,b) => {
        const na = parseInt(a.replace('PSO',''));
        const nb = parseInt(b.replace('PSO',''));
        return na - nb;
    });
    const allCols = [...poSet, ...psoSet];

    const lookup = {};
    state.mappings.forEach(m => {
        lookup[`${m.co_code}|${m.po_pso_code}`] = m;
    });

    // Map each CO to its attainment info
    const coAttainments = {};
    coSet.forEach(coCode => {
        const coObj = state.cos.find(c => c.co_code === coCode);
        const a = coObj && coObj.univ_attainment !== null && coObj.univ_attainment !== undefined ? coObj.univ_attainment : 0.0;
        const b = coObj && coObj.internal_attainment !== null && coObj.internal_attainment !== undefined ? coObj.internal_attainment : 3.0;
        const total = (a * 0.6) + (b * 0.4);
        coAttainments[coCode] = { a, b, total, id: coObj ? coObj.id : null };
    });

    let html = '<div class="matrix-container"><table class="matrix-table"><thead><tr>';
    html += '<th>CO</th>';
    html += '<th class="attainment-header" title="University Result Level (a)">CO Attainment Level<br>Through University Result (a)</th>';
    html += '<th class="attainment-header" title="Internal Assessment Level (b)">CO Attainment Level<br>Through Internal Assessment-CCE (b)</th>';
    html += '<th class="attainment-header" title="(a × 0.6) + (b × 0.4)">Total Attainment<br><small>(a &times; 0.6) + (b &times; 0.4)</small></th>';

    allCols.forEach(col => {
        const formattedCol = col.replace(/^(PO|PSO)(\d+)$/, '$1 $2');
        html += `<th>${formattedCol}</th>`;
    });
    html += '</tr></thead><tbody>';

    coSet.forEach(coCode => {
        const att = coAttainments[coCode];
        html += `<tr>`;
        html += `<td><strong>${coCode}</strong></td>`;

        const warnIcon = att.a === 0 ? '<span title="University result is 0 or pending" style="cursor:help; margin-right:4px;">⚠️</span>' : '';
        if (att.id) {
            html += `<td class="attainment-cell">${warnIcon}<input type="number" step="0.01" min="0" max="3" class="attainment-input" value="${att.a.toFixed(2)}" onchange="updateCOAttainment(${att.id}, 'univ_attainment', this.value)"></td>`;
            html += `<td class="attainment-cell"><input type="number" step="0.01" min="0" max="3" class="attainment-input" value="${att.b.toFixed(2)}" onchange="updateCOAttainment(${att.id}, 'internal_attainment', this.value)"></td>`;
        } else {
            html += `<td class="attainment-cell">${warnIcon}${att.a.toFixed(2)}</td>`;
            html += `<td class="attainment-cell">${att.b.toFixed(2)}</td>`;
        }
        html += `<td class="attainment-cell"><span class="attainment-total-val">${att.total.toFixed(2)}</span></td>`;

        allCols.forEach(col => {
            const m = lookup[`${coCode}|${col}`];
            const level = m ? (m.final_mapping_level !== null && m.final_mapping_level !== undefined ? m.final_mapping_level : m.mapping_level) : 0;
            const display = level === 0 ? '—' : level;
            html += `<td onclick="showExplanation('${coCode}','${col}')"><div class="matrix-cell level-${level}">${display}</div></td>`;
        });
        html += '</tr>';
    });

    html += '</tbody>';

    // Footer: PO / PSO Attainment calculation
    html += '<tfoot>';
    html += '<tr>';
    html += '<td colspan="4" style="text-align:right; font-weight:700; padding:12px 16px; background:rgba(99, 102, 241, 0.15); color:var(--text-primary); font-size:0.9rem;">PO / PSO Attainment</td>';

    allCols.forEach(col => {
        let weightedSum = 0;
        let weightSum = 0;

        coSet.forEach(coCode => {
            const m = lookup[`${coCode}|${col}`];
            const level = m ? (m.final_mapping_level !== null && m.final_mapping_level !== undefined ? m.final_mapping_level : m.mapping_level) : 0;
            if (level > 0) {
                const totalAttainment = coAttainments[coCode].total;
                weightedSum += (totalAttainment * level);
                weightSum += level;
            }
        });

        if (weightSum > 0) {
            const poAttainment = (weightedSum / weightSum).toFixed(2);
            html += `<td class="po-attainment-val" title="Calculated as ${weightedSum.toFixed(2)} / ${weightSum}">${poAttainment}</td>`;
        } else {
            html += `<td class="po-attainment-val text-muted">—</td>`;
        }
    });

    html += '</tr></tfoot></table></div>';

    // Legend & formula box
    html += `
        <div class="matrix-legend">
            <div class="legend-item"><div class="legend-swatch" style="background:var(--level-3)"></div>3 — Strong</div>
            <div class="legend-item"><div class="legend-swatch" style="background:var(--level-2)"></div>2 — Moderate</div>
            <div class="legend-item"><div class="legend-swatch" style="background:var(--level-1)"></div>1 — Weak</div>
            <div class="legend-item"><div class="legend-swatch" style="background:var(--level-0)"></div>— No relation</div>
        </div>
        <div class="attainment-formula-box">
            <div class="attainment-formula-title">
                <span>📐</span> <strong>PO/PSO Attainment Formula</strong>
            </div>
            <div class="attainment-formula-latex">
                PO Attainment = Σ(CO attainment × Level of mapping of PO with CO) / Σ(Level of Mapping of PO with CO)
            </div>
            <div style="font-size:0.85rem; color:var(--text-muted); line-height:1.5;">
                • <strong>Total CO Attainment</strong> = (University Result [a] &times; 0.6) + (Internal Assessment-CCE [b] &times; 0.4)<br>
                • You can edit <strong>(a)</strong> and <strong>(b)</strong> directly in the table inputs above to recalculate all attainment scores dynamically.
            </div>
        </div>`;

    container.innerHTML = html;
}

function showExplanation(coCode, poPsoCode) {
    const m = state.mappings.find(x => x.co_code === coCode && x.po_pso_code === poPsoCode);
    if (!m) return;

    const panel = document.getElementById('explanation-panel');
    const co = state.cos.find(c => c.co_code === coCode);
    const poOrPso = state.pos.find(p => p.po_code === poPsoCode) || state.psos.find(p => p.pso_code === poPsoCode);

    let evidence = [];
    try {
        evidence = typeof m.evidence === 'string' ? JSON.parse(m.evidence) : (m.evidence || []);
    } catch (e) {
        evidence = m.evidence || [];
    }

    const confColor = m.confidence > 0.7 ? 'var(--accent-success)' : m.confidence > 0.4 ? 'var(--accent-warning)' : 'var(--accent-danger)';

    document.getElementById('exp-co').textContent = `${coCode}: ${co ? co.description : ''}`;
    document.getElementById('exp-po').textContent = `${poPsoCode}: ${poOrPso ? (poOrPso.description || poOrPso.po_description) : ''}`;
    document.getElementById('exp-similarity').textContent = m.similarity_score.toFixed(4);
    document.getElementById('exp-level').innerHTML = `<span class="decision-badge ${m.mapping_level > 0 ? 'accepted' : 'pending'}">${m.mapping_level === 0 ? '-' : m.mapping_level}</span>`;
    document.getElementById('exp-confidence').textContent = `${(m.confidence * 100).toFixed(1)}%`;
    document.getElementById('exp-confidence-bar').style.width = `${m.confidence * 100}%`;
    document.getElementById('exp-confidence-bar').style.background = confColor;
    document.getElementById('exp-reason').textContent = m.reason || 'No explanation available.';
    document.getElementById('exp-evidence').innerHTML = evidence.length
        ? evidence.map(e => `<span class="evidence-tag">${e}</span>`).join('')
        : '<span class="text-muted">No evidence</span>';
    document.getElementById('exp-decision').innerHTML = `<span class="decision-badge ${m.faculty_decision}">${m.faculty_decision}</span>`;

    panel.classList.add('open');
}

function closeExplanation() {
    document.getElementById('explanation-panel').classList.remove('open');
}


// =============================================
// REVIEW TAB
// =============================================

function renderReviewTable() {
    const container = document.getElementById('review-table-body');
    if (!state.mappings.length) {
        container.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No mappings to review</td></tr>';
        return;
    }

    container.innerHTML = state.mappings.map(m => {
        const levelDisplay = m.mapping_level === 0 ? '—' : m.mapping_level;
        return `
            <tr>
                <td><strong>${m.co_code}</strong></td>
                <td>${m.po_pso_code}</td>
                <td><span class="decision-badge ${m.mapping_level > 0 ? 'accepted' : 'pending'}">${levelDisplay}</span></td>
                <td>${(m.confidence * 100).toFixed(0)}%</td>
                <td>${m.similarity_score.toFixed(3)}</td>
                <td><span class="decision-badge ${m.faculty_decision}">${m.faculty_decision}</span></td>
                <td>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-success" onclick="reviewMapping(${m.id}, 'accepted')">✓</button>
                        <button class="btn btn-sm btn-warning" onclick="openEditModal(${m.id})">✎</button>
                        <button class="btn btn-sm btn-danger" onclick="reviewMapping(${m.id}, 'rejected')">✕</button>
                    </div>
                </td>
            </tr>`;
    }).join('');
}

async function reviewMapping(mappingId, decision) {
    try {
        await API.put(`/api/mapping/${mappingId}/review`, {
            faculty_decision: decision,
        });
        showToast(`Mapping ${decision}`, 'success');
        // Reload mappings
        const result = await API.get(`/api/mapping/${state.subjectId}`);
        state.mappings = result.mappings;
        renderMappingMatrix();
        renderReviewTable();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function acceptAllMappings() {
    if (!state.mappings.length) return;
    const pendingIds = state.mappings.filter(m => m.faculty_decision === 'pending').map(m => m.id);
    if (!pendingIds.length) { showToast('No pending mappings', 'info'); return; }

    try {
        await API.put('/api/mapping/batch-review', {
            mapping_ids: pendingIds,
            faculty_decision: 'accepted',
        });
        showToast(`Accepted ${pendingIds.length} mappings`, 'success');
        const result = await API.get(`/api/mapping/${state.subjectId}`);
        state.mappings = result.mappings;
        renderMappingMatrix();
        renderReviewTable();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function openEditModal(mappingId) {
    const m = state.mappings.find(x => x.id === mappingId);
    if (!m) return;

    document.getElementById('edit-mapping-id').value = mappingId;
    document.getElementById('edit-co-code').textContent = m.co_code;
    document.getElementById('edit-po-code').textContent = m.po_pso_code;
    document.getElementById('edit-ai-level').textContent = m.mapping_level === 0 ? '-' : m.mapping_level;
    document.getElementById('edit-level').value = m.mapping_level;
    document.getElementById('edit-notes').value = m.faculty_notes || '';

    document.getElementById('edit-modal').classList.add('active');
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('active');
}

async function saveEdit() {
    const mappingId = document.getElementById('edit-mapping-id').value;
    const level = parseInt(document.getElementById('edit-level').value);
    const notes = document.getElementById('edit-notes').value;

    try {
        await API.put(`/api/mapping/${mappingId}/review`, {
            faculty_decision: 'edited',
            final_mapping_level: level,
            faculty_notes: notes,
        });
        closeEditModal();
        showToast('Mapping edited', 'success');
        const result = await API.get(`/api/mapping/${state.subjectId}`);
        state.mappings = result.mappings;
        renderMappingMatrix();
        renderReviewTable();
    } catch (err) {
        showToast(err.message, 'error');
    }
}


// =============================================
// EVALUATION TAB
// =============================================

async function runEvaluation() {
    if (!state.subjectId) { showToast('Select a subject first', 'warning'); return; }
    showLoading('Running evaluation against reference mappings...');
    try {
        const result = await API.post('/api/mapping/evaluate', {
            subject_id: state.subjectId,
        });
        hideLoading();
        state.evaluations = result.evaluations;
        renderEvaluationResults(result.evaluations);
        showToast('Evaluation complete!', 'success');
    } catch (err) {
        hideLoading();
        showToast('Evaluation failed: ' + err.message, 'error');
    }
}

async function loadEvaluationResults() {
    if (!state.subjectId) return;
    try {
        const result = await API.get(`/api/mapping/evaluation/${state.subjectId}`);
        if (result.evaluations.length) {
            // Group by method, take latest
            const byMethod = {};
            result.evaluations.forEach(e => { byMethod[e.method] = e; });
            state.evaluations = byMethod;
            renderEvaluationResults(byMethod);
        }
    } catch (e) { /* no evaluations */ }
}

function renderEvaluationResults(evaluations) {
    const container = document.getElementById('evaluation-results');

    if (!evaluations || !Object.keys(evaluations).length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📊</div>
                <p>No evaluation results yet. Upload reference mappings and run evaluation.</p>
            </div>`;
        return;
    }

    // Find the best performing method for highlighting
    let bestMethod = null;
    let bestF1 = -1;
    Object.entries(evaluations).forEach(([method, data]) => {
        if (data.f1_macro > bestF1) { bestF1 = data.f1_macro; bestMethod = method; }
    });

    let html = '';

    // Metrics cards for the best/first method
    const primary = evaluations[Object.keys(evaluations)[0]];
    html += `
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">${(primary.accuracy * 100).toFixed(1)}%</div>
                <div class="metric-label">Accuracy</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${(primary.precision_macro * 100).toFixed(1)}%</div>
                <div class="metric-label">Precision</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${(primary.recall_macro * 100).toFixed(1)}%</div>
                <div class="metric-label">Recall</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${(primary.f1_macro * 100).toFixed(1)}%</div>
                <div class="metric-label">F1 Score</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${primary.agreement_percentage.toFixed(1)}%</div>
                <div class="metric-label">Agreement</div>
            </div>
        </div>`;

    // Comparison table
    if (Object.keys(evaluations).length > 1) {
        html += '<div class="card"><div class="card-title"><span class="icon">📈</span> Method Comparison</div>';
        html += '<table class="comparison-table"><thead><tr><th>Method</th><th>Accuracy</th><th>Precision</th><th>Recall</th><th>F1</th><th>Agreement</th></tr></thead><tbody>';
        Object.entries(evaluations).forEach(([method, data]) => {
            const isBest = method === bestMethod;
            html += `<tr>
                <td><strong>${method}</strong></td>
                <td class="${isBest ? 'best' : ''}">${(data.accuracy * 100).toFixed(1)}%</td>
                <td class="${isBest ? 'best' : ''}">${(data.precision_macro * 100).toFixed(1)}%</td>
                <td class="${isBest ? 'best' : ''}">${(data.recall_macro * 100).toFixed(1)}%</td>
                <td class="${isBest ? 'best' : ''}">${(data.f1_macro * 100).toFixed(1)}%</td>
                <td class="${isBest ? 'best' : ''}">${data.agreement_percentage.toFixed(1)}%</td>
            </tr>`;
        });
        html += '</tbody></table></div>';
    }

    // Confusion matrix
    if (primary.confusion_matrix && primary.confusion_matrix.length) {
        html += '<div class="card"><div class="card-title"><span class="icon">🔢</span> Confusion Matrix</div>';
        html += '<table class="confusion-table"><thead><tr><th>True \\ Pred</th><th>Level 0</th><th>Level 1</th><th>Level 2</th><th>Level 3</th></tr></thead><tbody>';
        const labels = ['Level 0', 'Level 1', 'Level 2', 'Level 3'];
        primary.confusion_matrix.forEach((row, i) => {
            html += `<tr><th>${labels[i]}</th>`;
            row.forEach(val => { html += `<td>${val}</td>`; });
            html += '</tr>';
        });
        html += '</tbody></table></div>';
    }

    // Per-CO accuracy
    if (primary.per_co_accuracy && Object.keys(primary.per_co_accuracy).length) {
        html += '<div class="card"><div class="card-title"><span class="icon">📋</span> Per-CO Accuracy</div><table class="comparison-table"><thead><tr><th>CO</th><th>Accuracy</th></tr></thead><tbody>';
        Object.entries(primary.per_co_accuracy).sort().forEach(([co, acc]) => {
            html += `<tr><td>${co}</td><td>${(acc * 100).toFixed(1)}%</td></tr>`;
        });
        html += '</tbody></table></div>';
    }

    // Per-PO accuracy
    if (primary.per_po_accuracy && Object.keys(primary.per_po_accuracy).length) {
        html += '<div class="card"><div class="card-title"><span class="icon">📋</span> Per-PO Accuracy</div><table class="comparison-table"><thead><tr><th>PO/PSO</th><th>Accuracy</th></tr></thead><tbody>';
        Object.entries(primary.per_po_accuracy).sort().forEach(([po, acc]) => {
            html += `<tr><td>${po}</td><td>${(acc * 100).toFixed(1)}%</td></tr>`;
        });
        html += '</tbody></table></div>';
    }

    container.innerHTML = html;
}


// =============================================
// EXPORT TAB
// =============================================

function exportExcel() {
    if (!state.subjectId) { showToast('Select a subject first', 'warning'); return; }
    window.open(`/api/excel/export/${state.subjectId}`, '_blank');
}
