//  Wires up the "5 min / 15 min / 25 min / 45 min"
// quick-estimate chips without relying on onclick="..." attributes.
document.addEventListener('DOMContentLoaded', function() {
  const estimateInput = document.getElementById("estimate_mins");
    const chips = document.querySelectorAll(".estimate-chip");

    if (!estimateInput || !chips.length) return;

    function syncActiveChip() {
        const currentValue = String(estimateInput.value || "");
        chips.forEach(function (chip) {
            chip.classList.toggle("active", chip.dataset.mins === currentValue);
        });
    }

    chips.forEach(function (chip) {
        chip.addEventListener("click", function () {
            estimateInput.value = chip.dataset.mins;
            syncActiveChip();
        });
    });

    estimateInput.addEventListener("input", syncActiveChip);
    syncActiveChip();
  document.querySelectorAll('.estimate-chip').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.getElementById('estimate_mins').value = btn.dataset.mins;
    });
  });
});

Focus_mode.js