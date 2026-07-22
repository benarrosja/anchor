// Shared Focus Mode:countdown ring, subtasks, "I'm stuck"
// breakdown, and marking a task complete. Loaded once from base.html so
// every page that includes _focus_overlay.html (dashboard.html and all_tasks.html) 

let focusInterval = null;
let focusTotalSeconds = 0;
let focusRemainingSeconds = 0;
let focusTaskId = null;
let currentTaskEstimate = 0;
let currentTaskPriority = 2;
let currentTaskTitle = '';
let currentTaskDeadline = '';
let currentTaskDetails = '';
const FO_CIRCUMFERENCE = 552.92;

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
}

function playChime() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === 'suspended') ctx.resume();
  const now = ctx.currentTime;
  [523.25, 659.25].forEach(function(freq, i) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = freq;
    osc.type = 'sine';
    gain.gain.setValueAtTime(0.0001, now + i * 0.35);
    gain.gain.exponentialRampToValueAtTime(0.15, now + i * 0.35 + 0.05);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.35 + 1.2);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now + i * 0.35);
    osc.stop(now + i * 0.35 + 1.3);
  });
}

function updateRing() {
  const ring = document.getElementById('fo-ring');
  if (!ring || !focusTotalSeconds) return;
  const fraction = focusRemainingSeconds / focusTotalSeconds;
  ring.style.strokeDashoffset = FO_CIRCUMFERENCE * (1 - fraction);
  ring.style.stroke = fraction <= 0.10 ? '#e63946'
    : fraction <= 0.30 ? '#f4a261'
    : '#4361ee';
}

function subtaskKey(taskId) {
  return 'anchor_subtasks_' + taskId;
}
function loadSubtasks(taskId){
  try {
    return JSON.parse(localStorage.getItem(subtaskKey(taskId))) || [];
  } catch (e) { return []; }
}
function saveSubtasks(taskId, list) {
  localStorage.setItem(subtaskKey(taskId), JSON.stringify(list));
}
function renderSubtasks(taskId){
  const ul = document.getElementById('fo-subtask-list');
  if (!ul) return;
  const list = loadSubtasks(taskId);
  ul.innerHTML = '';
  if (list.length === 0) {
    ul.innerHTML = '<li class="text-muted" style="font-size:0.85rem;">No subtasks yet - add one below.</li>';
    return;
  }
  list.forEach(function(item, idx){
    const li = document.createElement('li');
    li.className = 'd-flex align-items-center gap-2 mb-2';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'form-check-input mt-0';
    checkbox.checked = !!item.done;
    checkbox.addEventListener('change', function() {
      toggleSubtask(taskId, idx, checkbox.checked);
    });

    const span = document.createElement('span');
    span.className = item.done ? 'fo-subtask-done' : '';
    span.style.fontSize = '0.9rem';
    span.textContent = item.text;

    const delBtn = document.createElement('button');
    delBtn.className = 'btn-close btn-sm ms-auto';
    delBtn.style.fontSize = '0.6rem';
    delBtn.addEventListener('click', function() {
        deleteSubtask(taskId, idx);
    });
    li.appendChild(checkbox);
    li.appendChild(span);
    li.appendChild(delBtn);
    ul.appendChild(li);
  });
}

function addSubtask() {
  const input = document.getElementById('fo-subtask-input');
  const text = input.value.trim();
  if (!text || !focusTaskId) return;
  const list = loadSubtasks(focusTaskId);
  list.push({ text: text, done: false });
  saveSubtasks(focusTaskId, list);
  renderSubtasks(focusTaskId);
  input.value = '';
  input.focus();
}

function toggleSubtask(taskId, idx, done) {
  const list = loadSubtasks(taskId);
  if (!list[idx]) return;
  list[idx].done = done;
  saveSubtasks(taskId, list);
  renderSubtasks(taskId);
}

function deleteSubtask(taskId, idx) {
  const list = loadSubtasks(taskId);
  list.splice(idx, 1);
  saveSubtasks(taskId, list);
  renderSubtasks(taskId);
}

function startFocusTimer(taskId, taskTitle, taskDetails, estimateMins, taskDeadline, taskPriority) {
  if (focusInterval) clearInterval(focusInterval);

  focusTaskId =taskId;
  currentTaskTitle = taskTitle;
  currentTaskDetails = taskDetails || '';
  currentTaskEstimate = estimateMins;
  currentTaskPriority = taskPriority;
  currentTaskDeadline = taskDeadline;

  focusTotalSeconds = estimateMins * 60;
  focusRemainingSeconds = focusTotalSeconds;

  document.getElementById('fo-title').textContent = taskTitle;
  const priorityLabel = taskPriority === 3 ? 'High' : taskPriority === 2 ? 'Medium'  : 'Low';
  const deadlineStr = taskDeadline ? ' - Due ' + taskDeadline : '';
  document.getElementById('fo-meta').textContent = priorityLabel + deadlineStr + ' - ' + estimateMins + ' min';
  document.getElementById('fo-time').textContent = formatTime(focusRemainingSeconds);

  const detailsInput = document.getElementById('fo-details-input');
  if (detailsInput) detailsInput.value = currentTaskDetails;
  const detailsWarning = document.getElementById('fo-details-warning');
  if (detailsWarning) detailsWarning.style.display = 'none';

  renderSubtasks(taskId);

  document.getElementById('focus-overlay').classList.add('show');
  document.body.style.overflow = 'hidden';
  updateRing();

  focusInterval = setInterval(function() {
    focusRemainingSeconds -= 1;
    document.getElementById('fo-time').textContent = formatTime(Math.max(focusRemainingSeconds, 0));
    updateRing();

    if (focusRemainingSeconds > 0 && focusRemainingSeconds % 600 === 0) {
      const priorityLabelInner = currentTaskPriority === 3 ? 'High' : currentTaskPriority === 2 ? 'Medium' : 'Low';
      const deadlineInner = currentTaskDeadline ? ' - Due ' + currentTaskDeadline : '';
      document.getElementById('fo-meta').textContent = priorityLabelInner + deadlineInner + ' - Take 10 seconds to tick any finished subtasks';
    }

    if (focusRemainingSeconds <= 0) {
      clearInterval(focusInterval);
      focusInterval = null;
      
      playChime();
      document.getElementById('fo-time').textContent = 'Done!';
      document.getElementById('fo-meta').textContent = 'It is complete! Great work.';
      logFocusSession(taskId, estimateMins);
    }
  }, 1000);
}

function exitFocusMode() {
  if (focusInterval) { clearInterval(focusInterval); focusInterval = null; }
  document.getElementById('focus-overlay').classList.remove('show');
  document.body.style.overflow = '';
  focusTaskId = null;
}

function logFocusSession(taskId, durationMins) {
    fetch('/focus/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, duration_mins: durationMins })
  }).catch(function() {
    console.warn('Could not log focus session.');
  });
}

// Focus Mode counts partial session's elapsed time sending to focus/log
function completeCurrentTask() {
  if (!focusTaskId) return;

  const elapsedSecs= Math.max(0, focusTotalSeconds - focusRemainingSeconds);
  const elapsedMins = Math.max(1, Math.round(elapsedSecs / 60));

  if (focusInterval) { clearInterval(focusInterval); focusInterval = null; }

  const taskIdToComplete = focusTaskId;

  logFocusSessionThenComplete(taskIdToComplete, elapsedMins);
}

function logFocusSessionThenComplete(taskId, elapsedMins) {
  fetch('/focus/log',  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, duration_mins: elapsedMins })
  })
  .catch(function() {
    console.warn('Could not log focus session - completing task anyway.');
  })
  .finally(function() {
    fetch('/tasks/' + taskId + '/complete', { method: 'POST' })
      .then(function() { window.location.reload(); })
      .catch(function() { console.warn('Could not mark task complete - check your connection.');
      });
  });
}

function openBreakdownForCurrentTask() {
  if (!focusTaskId) return;
  const detailsInput = document.getElementById('fo-details-input');
  const details = detailsInput ? detailsInput.value.trim() : '';
  const warning = document.getElementById('fo-details-warning');

  if (!details) {
    if (warning) warning.style.display = 'block';
    if (detailsInput) detailsInput.focus();
    return;
  }
  if (warning) warning.style.display = 'none';
  currentTaskDetails = details;

  fetch('/tasks/' + focusTaskId + '/update_details', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ details: details })
  }).catch(function() {
    console.warn('Could not save details - continuing anyway.');
  }).finally(function() {
    getBreakdown(focusTaskId, currentTaskTitle, currentTaskDetails, currentTaskDeadline, currentTaskPriority, currentTaskEstimate);
  });
}

function getBreakdown(taskId, title, taskDetails, deadline, priority, estimateMins) {
  const box = document.getElementById('breakdown-box');
  const steps = document.getElementById('breakdown-steps');
  const source = document.getElementById('breakdown-source');
  box.style.display = 'block';
  steps.innerHTML = '<p class="text-muted">Breaking it down for you...</p>';
  source.textContent = '';

  fetch('/tasks/' + taskId + '/breakdown', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title:  title,
      details: taskDetails,
      deadline: deadline,
      priority: priority,
      estimate_mins: estimateMins
    })
  })
  .then(function(r) { if (!r.ok) throw new Error(); return r.json(); })
  .then(function(data) {
    steps.innerHTML = '';
data.steps.forEach(function(s) {
  const row = document.createElement('div');
  row.className = 'd-flex gap-2 align-items-start mb-2';

  const badge = document.createElement('span');
  badge.className = 'badge bg-primary rounded-circle flex-shrink-0';
  badge.style.cssText = 'width:24px;height:24px;line-height:16px;text-align:center;';
  badge.textContent = s.step;

  const textWrap = document.createElement('div');
  const actionSpan = document.createElement('span');
  actionSpan.className = 'fw-semibold';
  actionSpan.textContent = s.action;

  const durSpan = document.createElement('span');
  durSpan.className = 'text-muted ms-1';
  durSpan.style.fontSize = '0.8rem';
  durSpan.textContent = '- ' + s.duration_mins + ' min';

  textWrap.appendChild(actionSpan);
  textWrap.appendChild(durSpan);
  row.appendChild(badge);
  row.appendChild(textWrap);
  steps.appendChild(row);
});
    source.textContent = data.source === 'fallback'
      ? 'AI unavailable - showing default steps.'
      : 'Steps generated by Gemini AI';
  })
  .catch(function() {
    steps.innerHTML = '<p class="text-danger">Could not load steps. Please try again another time.</p>';
  });
}

// "Start focus" button + all Focus Mode overlay controls.
// data-* attributes are used instead of inline onclick="..." because
// Jinja's |tojson filter wraps strings in double quotes, colliding with onclick="..."'s own double quotes
// and breaks the HTML attribute;
// data-* attributes go through Jinja's normal auto-escaping instead handling quotes.
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.start-focus-btn').forEach(function(btn){
    btn.addEventListener('click', function() {
      startFocusTimer(
        parseInt(btn.dataset.taskId, 10),
        btn.dataset.taskTitle,
        btn.dataset.taskDetails,
        parseInt(btn.dataset.estimateMins, 10),
        btn.dataset.taskDeadline,
        parseInt(btn.dataset.taskPriority, 10)
      );
    });
  });

  const exitBtn = document.getElementById('fo-exit-btn');
  if (exitBtn) exitBtn.addEventListener('click', exitFocusMode);

  const stuckBtn = document.getElementById('fo-stuck-btn');
  if (stuckBtn) stuckBtn.addEventListener('click', openBreakdownForCurrentTask);

  const addSubtaskBtn = document.getElementById('fo-add-subtask-btn');
  if (addSubtaskBtn) addSubtaskBtn.addEventListener('click', addSubtask);

  const subtaskInput = document.getElementById('fo-subtask-input');
  if (subtaskInput) {
    subtaskInput.addEventListener('keydown', function(event) {
      if (event.key === 'Enter') { event.preventDefault(); addSubtask(); }
    });
  }

  const completeBtn = document.getElementById('fo-complete-link');
  if (completeBtn) completeBtn.addEventListener('click', completeCurrentTask);

  const closeBreakdownBtn = document.getElementById('fo-breakdown-close-btn');
  if (closeBreakdownBtn) {
    closeBreakdownBtn.addEventListener('click', function(){
      document.getElementById('breakdown-box').style.display = 'none';
    });
  }
});

dashboard.js
