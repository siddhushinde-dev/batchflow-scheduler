/**
 * script.js — BatchFlow Batch Job Scheduler
 * Handles: UI rendering, API calls, polling, notifications, sidebar nav
 */

'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let knownJobIds = new Set();      // Track which rows are already in the DOM
let pollInterval = null;
let localLogs = [];               // Client-side filtered view of logs

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  AOS.init({ duration: 600, once: true, easing: 'ease-out-quad' });
  startPolling();
  initSidebarNav();
  initSidebarToggle();
  bindEnterKey();
});

// ── Polling ────────────────────────────────────────────────────────────────
function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(fetchState, 1000);
  fetchState(); // Immediate first fetch
}

async function fetchState() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    renderAll(data);
  } catch (e) {
    console.warn('Poll error:', e);
  }
}

// ── Master render ──────────────────────────────────────────────────────────
function renderAll(state) {
  renderStats(state.stats);
  renderJobs(state.jobs);
  renderLogs(state.logs);
  renderControls(state);
  renderAlgorithmLabels(state.algorithm);
}

// ── Stats ──────────────────────────────────────────────────────────────────
function renderStats(stats) {
  animateCounter('statTotal',     stats.total);
  animateCounter('statWaiting',   stats.waiting);
  animateCounter('statRunning',   stats.running);
  animateCounter('statCompleted', stats.completed);
}

function animateCounter(id, newVal) {
  const el = document.getElementById(id);
  if (!el) return;
  const current = parseInt(el.textContent) || 0;
  if (current === newVal) return;
  el.style.transform = 'scale(1.15)';
  el.style.color = 'var(--accent)';
  el.textContent = newVal;
  setTimeout(() => {
    el.style.transform = '';
    el.style.color = '';
  }, 300);
}

// ── Job Table ──────────────────────────────────────────────────────────────
function renderJobs(jobs) {
  const tbody = document.getElementById('jobsBody');
  const emptyRow = document.getElementById('emptyRow');

  if (jobs.length === 0) {
    tbody.innerHTML = '';
    tbody.appendChild(emptyRow);
    emptyRow.style.display = '';
    hideBanner();
    return;
  }
  if (emptyRow) emptyRow.style.display = 'none';

  // Find running job for banner
  const runningJob = jobs.find(j => j.status === 'Running');
  if (runningJob) {
    showBanner(runningJob);
  } else {
    hideBanner();
  }

  // Detect new job IDs for animation
  const currentIds = new Set(jobs.map(j => j.id));
  const newIds = [...currentIds].filter(id => !knownJobIds.has(id));
  knownJobIds = currentIds;

  // Build/update rows
  jobs.forEach(job => {
    let row = document.getElementById('row-' + job.id);
    if (!row) {
      row = document.createElement('tr');
      row.id = 'row-' + job.id;
      row.className = 'job-row';
      tbody.appendChild(row);
      if (newIds.includes(job.id)) {
        row.classList.add('row-enter');
        setTimeout(() => row.classList.remove('row-enter'), 600);
      }
    }
    updateRow(row, job);
  });

  // Remove stale rows
  [...tbody.querySelectorAll('tr.job-row')].forEach(r => {
    const id = r.id.replace('row-', '');
    if (!currentIds.has(id)) r.remove();
  });
}

function updateRow(row, job) {
  // Status class
  row.className = 'job-row';
  if (job.status === 'Running')   row.classList.add('is-running');
  if (job.status === 'Completed') row.classList.add('is-completed');
  if (job.status === 'Cancelled') row.classList.add('is-cancelled');

  const prio = Math.min(Math.max(parseInt(job.priority), 1), 10);
  const cancelBtn = (job.status === 'Waiting')
    ? `<button class="btn btn-xs btn-outline-danger btn-anim" onclick="cancelJob('${job.id}')">
         <i class="bi bi-x-lg"></i>
       </button>`
    : `<span class="text-muted">—</span>`;

  row.innerHTML = `
    <td class="text-mono" style="color:var(--text-secondary);font-size:0.75rem">${job.id}</td>
    <td style="font-weight:500">${escHtml(job.name)}</td>
    <td class="text-mono">${job.execution_time}s</td>
    <td><span class="prio-chip prio-${prio}">${prio}</span></td>
    <td>${statusBadge(job.status)}</td>
    <td>
      <div class="mini-progress">
        <div class="mini-bar" style="width:${job.progress}%"></div>
      </div>
      <span style="font-size:0.7rem;color:var(--text-secondary);font-family:var(--font-mono)">${job.progress}%</span>
    </td>
    <td>${cancelBtn}</td>
  `;
}

function statusBadge(status) {
  const map = {
    'Waiting':   ['badge-waiting',   'bi-clock',             'Waiting'],
    'Running':   ['badge-running',   'bi-lightning-fill',    'Running'],
    'Completed': ['badge-completed', 'bi-check-circle-fill', 'Done'],
    'Cancelled': ['badge-cancelled', 'bi-x-circle-fill',     'Cancelled'],
  };
  const [cls, icon, label] = map[status] || ['badge-waiting', 'bi-question', status];
  return `<span class="badge-status ${cls}"><i class="bi ${icon}"></i>${label}</span>`;
}

// ── Running Banner ─────────────────────────────────────────────────────────
function showBanner(job) {
  const banner = document.getElementById('runningJobBanner');
  document.getElementById('runningJobName').textContent = job.name;
  document.getElementById('runningJobPct').textContent = job.progress + '%';
  document.getElementById('runningJobBar').style.width = job.progress + '%';
  banner.classList.remove('d-none');
}
function hideBanner() {
  document.getElementById('runningJobBanner').classList.add('d-none');
}

// ── Logs ───────────────────────────────────────────────────────────────────
let lastLogCount = 0;
function renderLogs(logs) {
  if (logs.length === lastLogCount) return;
  lastLogCount = logs.length;

  const terminal = document.getElementById('logTerminal');
  terminal.innerHTML = '';
  logs.forEach(line => {
    const p = document.createElement('p');
    p.className = 'log-line ' + logClass(line);
    p.textContent = line;
    terminal.appendChild(p);
  });
  terminal.scrollTop = terminal.scrollHeight;
}

function logClass(line) {
  if (line.includes('✔') || line.includes('Completed')) return 'log-success';
  if (line.includes('✖') || line.includes('cancel'))    return 'log-warning';
  if (line.includes('▶') || line.includes('Running'))   return 'log-accent';
  if (line.includes('■') || line.includes('stopped'))   return 'log-error';
  if (line.includes('⏸') || line.includes('paused'))   return 'log-warning';
  return 'log-info';
}

function clearLogsUI() {
  document.getElementById('logTerminal').innerHTML =
    '<p class="log-line log-info">[View cleared — server logs continue in background]</p>';
  lastLogCount = -1;
}

// ── Control State ──────────────────────────────────────────────────────────
function renderControls(state) {
  const dot = document.getElementById('statusDotMain');
  const dotMobile = document.getElementById('statusDot');
  const label = document.getElementById('statusLabel');
  const btnPause  = document.getElementById('btnPause');
  const btnResume = document.getElementById('btnResume');
  const btnStop   = document.getElementById('btnStop');
  const btnStart  = document.getElementById('btnStart');

  let dotClass = '', labelText = 'Idle';

  if (state.is_running && !state.is_paused) {
    dotClass = 'running'; labelText = 'Running';
    btnPause.style.display  = '';
    btnResume.style.display = 'none';
  } else if (state.is_paused) {
    dotClass = 'paused'; labelText = 'Paused';
    btnPause.style.display  = 'none';
    btnResume.style.display = '';
  } else {
    dotClass = 'stopped'; labelText = 'Stopped';
    btnPause.style.display  = 'none';
    btnResume.style.display = 'none';
  }

  [dot, dotMobile].forEach(d => { if (d) { d.className = 'status-dot ' + dotClass; } });
  if (label) label.textContent = labelText;
}

function renderAlgorithmLabels(algo) {
  document.getElementById('sidebarAlgo').textContent = algo;
  document.getElementById('algoLabel').textContent = algo;
  document.getElementById('modalAlgo').textContent = algo;

  const select = document.getElementById('algoSelect');
  if (select.value !== algo) select.value = algo;
}

// ── API Actions ────────────────────────────────────────────────────────────
async function addJob() {
  const name  = document.getElementById('jobName').value.trim();
  const time  = parseInt(document.getElementById('jobTime').value);
  const prio  = parseInt(document.getElementById('jobPriority').value);

  if (!name) { showToast('Please enter a job name.', 'warning'); return; }

  const res = await apiPost('/api/jobs', { name, execution_time: time, priority: prio });
  if (res.success) {
    showToast(`✚ Job "${name}" added!`, 'success');
    bootstrap.Modal.getInstance(document.getElementById('addJobModal')).hide();
    document.getElementById('jobName').value = '';
    document.getElementById('jobTime').value = 5;
    document.getElementById('jobPriority').value = 5;
    fetchState();
  } else {
    showToast(res.message, 'error');
  }
}

async function cancelJob(id) {
  const res = await apiPost(`/api/jobs/${id}/cancel`);
  if (res.success) showToast('Job cancelled.', 'warning');
  else showToast(res.message, 'error');
}

async function clearJobs() {
  if (!confirm('Clear all non-running jobs?')) return;
  const res = await apiPost('/api/jobs/clear');
  if (res.success) showToast('All jobs cleared.', 'info');
}

async function startScheduler() {
  const algo = document.getElementById('algoSelect').value;
  const res = await apiPost('/api/scheduler/start', { algorithm: algo });
  if (res.success) showToast(`▶ Scheduler started (${algo})`, 'success');
  else showToast(res.message, 'error');
}

async function stopScheduler() {
  const res = await apiPost('/api/scheduler/stop');
  if (res.success) showToast('■ Scheduler stopped.', 'info');
}

async function pauseScheduler() {
  const res = await apiPost('/api/scheduler/pause');
  if (res.success) showToast('⏸ Scheduler paused.', 'warning');
}

async function resumeScheduler() {
  const res = await apiPost('/api/scheduler/resume');
  if (res.success) showToast('⏵ Scheduler resumed.', 'success');
}

async function setAlgorithm(algo) {
  const res = await apiPost('/api/scheduler/algorithm', { algorithm: algo });
  if (res.success) showToast(`Algorithm → ${algo}`, 'info');
}

async function saveJobs() {
  const res = await apiPost('/api/jobs/save');
  if (res.success) showToast(res.message, 'success');
  else showToast(res.message, 'error');
}

async function loadJobs() {
  const res = await apiPost('/api/jobs/load');
  if (res.success) { showToast(res.message, 'success'); fetchState(); }
  else showToast(res.message, 'error');
}

// ── HTTP helper ────────────────────────────────────────────────────────────
async function apiPost(url, body = {}) {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return await res.json();
  } catch (e) {
    return { success: false, message: 'Network error: ' + e.message };
  }
}

// ── Toast Notifications ────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const icons = { success: 'bi-check-circle-fill', error: 'bi-x-circle-fill',
                  warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
  const colors = { success: '#00e676', error: '#ff5252', warning: '#ffd600', info: '#00e5ff' };

  const id = 'toast-' + Date.now();
  const el = document.createElement('div');
  el.id = id;
  el.className = `toast toast-${type} align-items-center border-0 show`;
  el.setAttribute('role', 'alert');
  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body d-flex align-items-center gap-2">
        <i class="bi ${icons[type]}" style="color:${colors[type]}"></i>
        ${escHtml(message)}
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="this.closest('.toast').remove()"></button>
    </div>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Sidebar Navigation ─────────────────────────────────────────────────────
function initSidebarNav() {
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      document.querySelectorAll('.sidebar-nav .nav-link').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      const target = document.getElementById(link.dataset.section + '-section');
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Close mobile sidebar
      document.getElementById('sidebar').classList.remove('open');
    });
  });
}

function initSidebarToggle() {
  const btn = document.getElementById('sidebarToggle');
  if (btn) btn.addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
  });
}

// ── Enter key for modal ────────────────────────────────────────────────────
function bindEnterKey() {
  ['jobName','jobTime','jobPriority'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('keydown', e => { if (e.key === 'Enter') addJob(); });
  });
}

// ── Utility ────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
