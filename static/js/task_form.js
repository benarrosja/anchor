//  Wires up the "5 min / 15 min / 25 min / 45 min"
// quick-estimate chips without relying on onclick="..." attributes.
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.estimate-chip').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.getElementById('estimate_mins').value = btn.dataset.mins;
    });
  });
});

Focus_mode.js