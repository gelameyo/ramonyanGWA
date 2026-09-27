/**
 * RamonyanGWA - Client-side interactions
 * Handles dynamic row addition/removal and live units meter.
 */

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("gwa-form");
  if (!form) return; // Not on the form page

  const rowsContainer = document.getElementById("subject-rows-container");
  const btnAddRow = document.getElementById("btn-add-row");
  const rowTemplate = document.getElementById("row-template");
  const prescribedInput = document.getElementById("prescribed_units");
  const progressBar = document.getElementById("units-meter-progress");
  const meterStatusText = document.getElementById("meter-status-text");
  const meterStatusIcon = document.getElementById("meter-status-icon");

  // SVG Icons
  const checkIcon = `
    <svg class="icon icon-check" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="#2b6a2f" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="20 6 9 17 4 12"></polyline>
    </svg>
  `;
  const crossIcon = `
    <svg class="icon icon-cross" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="#b0182c" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"></line>
      <line x1="6" y1="6" x2="18" y2="18"></line>
    </svg>
  `;

  // Find highest existing row index to avoid collisions
  let nextRowIndex = 0;
  document.querySelectorAll(".subject-row").forEach((row) => {
    const idx = parseInt(row.getAttribute("data-row-index"), 10);
    if (!isNaN(idx) && idx >= nextRowIndex) {
      nextRowIndex = idx + 1;
    }
  });

  // Calculate and update live meter
  function updateMeter() {
    let creditUnits = 0;
    let noncreditUnits = 0;

    const rows = rowsContainer.querySelectorAll(".subject-row");
    rows.forEach((row) => {
      const unitsInput = row.querySelector(".input-units");
      const typeSelect = row.querySelector(".select-type");

      if (unitsInput && unitsInput.value) {
        const u = parseFloat(unitsInput.value);
        if (!isNaN(u) && u > 0) {
          if (typeSelect && typeSelect.value === "noncredit") {
            noncreditUnits += u;
          } else {
            creditUnits += u;
          }
        }
      }
    });

    const totalUnits = Math.round((creditUnits + noncreditUnits) * 100) / 100;
    const prescribed = prescribedInput && prescribedInput.value ? parseFloat(prescribedInput.value) : 0;

    if (!prescribed || isNaN(prescribed) || prescribed <= 0) {
      progressBar.style.width = "0%";
      progressBar.classList.remove("fill-complete");
      meterStatusIcon.innerHTML = "";
      meterStatusText.textContent = `${totalUnits} units entered: ${creditUnits} credit + ${noncreditUnits} non-credit. Enter prescribed units to check full load.`;
      return;
    }

    const pct = Math.min(100, Math.max(0, Math.round((totalUnits / prescribed) * 100)));
    progressBar.style.width = `${pct}%`;

    if (totalUnits >= prescribed) {
      progressBar.classList.add("fill-complete");
      meterStatusIcon.innerHTML = checkIcon;
      meterStatusText.innerHTML = `<strong>${totalUnits} of ${prescribed} units:</strong> ${creditUnits} credit + ${noncreditUnits} non-credit. Passed: Full load met.`;
    } else {
      progressBar.classList.remove("fill-complete");
      meterStatusIcon.innerHTML = crossIcon;
      const diff = Math.round((prescribed - totalUnits) * 100) / 100;
      meterStatusText.innerHTML = `<strong>${totalUnits} of ${prescribed} units:</strong> ${creditUnits} credit + ${noncreditUnits} non-credit. Attention: Below prescribed load (${diff} more units needed).`;
    }
  }

  // Add new subject row
  if (btnAddRow && rowTemplate) {
    btnAddRow.addEventListener("click", () => {
      const html = rowTemplate.innerHTML.replace(/__INDEX__/g, nextRowIndex.toString());
      nextRowIndex += 1;
      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = html.trim();
      const newRow = tempDiv.firstElementChild;
      rowsContainer.appendChild(newRow);

      // Focus first input of newly added row
      const nameInput = newRow.querySelector(".form-control");
      if (nameInput) nameInput.focus();

      updateMeter();
    });
  }

  // Remove subject row (delegated event)
  rowsContainer.addEventListener("click", (e) => {
    const removeBtn = e.target.closest(".btn-remove-row");
    if (!removeBtn) return;

    const row = removeBtn.closest(".subject-row");
    if (row) {
      row.remove();
      updateMeter();
    }
  });

  // Listen to input and change events on the form
  form.addEventListener("input", updateMeter);
  form.addEventListener("change", updateMeter);

  // Initial meter calculation on load
  updateMeter();
});
