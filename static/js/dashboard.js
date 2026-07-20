let bdTimeframe = 'none';
let bdDuration = null;

function toggleBrainDumpDetails() {
  const panel = document.getElementById('brain-dump-details');
  const arrow = document.getElementById('bd-toggle-arrow');

  if (!panel || !arrow) return;

  const isHidden = panel.style.display === 'none' || panel.style.display === '';
  panel.style.display = isHidden ? 'block' : 'none';
  arrow.textContent = isHidden ? '^' : 'v';
}

document.addEventListener('DOMContentLoaded', function () {
  const toggleBtn = document.getElementById('bd-toggle-btn');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', toggleBrainDumpDetails);
  }

  document.querySelectorAll('.bd-chip').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.bd-chip').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      bdTimeframe = btn.dataset.value;
    });
  });

  document.querySelectorAll('.bd-dur-chip').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.bd-dur-chip').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');

      const customInput = document.getElementById('bd-duration-custom');
      if (!customInput) return;

      if (btn.dataset.value === 'custom') {
        customInput.style.display = 'block';
        customInput.focus();
        bdDuration = null;
      } else {
        customInput.style.display = 'none';
        customInput.value = '';
        bdDuration = parseInt(btn.dataset.value, 10);
      }
    });
  });

  const bdCustomInput = document.getElementById('bd-duration-custom');
  if (bdCustomInput) {
    bdCustomInput.addEventListener('input', function () {
      const val = parseInt(this.value, 10);
      bdDuration = isNaN(val) ? null : val;
    });
  }

  const submitBtn = document.getElementById('bd-submit-btn');
  if (submitBtn) {
    submitBtn.addEventListener('click', submitBrainDump);
  }

  const input = document.getElementById('brain-dump-input');
  if (input) {
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        submitBrainDump();
      }
    });
  }
});

function submitBrainDump() {
  const input = document.getElementById('brain-dump-input');
  if (!input) return;

  const title = input.value.trim();
  if (!title) return;

  const deadlineField = document.getElementById('bd-deadline');
  const deadline = deadlineField && deadlineField.value ? deadlineField.value : null;

  const detailsField = document.getElementById('bd-details');
  const details = detailsField && detailsField.value.trim() ? detailsField.value.trim() : null;

  fetch('/quick_add_task', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: title,
      details: details,
      deadline: deadline,
      timeframe: deadline ? null : bdTimeframe,
      estimate_mins: bdDuration
    })
  })
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      if (data.success) {
        showBrainDumpCheck();
        input.value = '';
        if (detailsField) detailsField.value = '';
        if (deadlineField) deadlineField.value = '';
        bdDuration = null;
        bdTimeframe = 'none';
        input.focus();
      }
    })
    .catch(function () {
      console.warn('Could not save task - check your connection.');
    });
}

function showBrainDumpCheck() {
  const check = document.getElementById('brain-dump-check');
  if (!check) return;

  check.style.opacity = '1';
  setTimeout(function () {
    check.style.opacity = '0';
  }, 400);
}