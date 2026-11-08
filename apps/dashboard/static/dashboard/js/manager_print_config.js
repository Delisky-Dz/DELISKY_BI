"use strict";
(() => {
  const form = document.querySelector("form");
  if (!form) return;
  const boxes = [...form.querySelectorAll('input[name="sections"]')];
  const presets = [...form.querySelectorAll('input[name="preset"]')];
  const quick = new Set(["overview", "sellers", "visits", "actions"]);
  const manual = () => { form.querySelector('[name="preset"][value="manual"]').checked = true; };
  for (const preset of presets) preset.addEventListener("change", () => {
    if (preset.value !== "manual") for (const box of boxes) box.checked = preset.value === "full" || quick.has(box.value);
  });
  for (const box of boxes) box.addEventListener("change", manual);
  for (const button of form.querySelectorAll("[data-select]")) button.addEventListener("click", () => {
    manual();
    for (const box of boxes) box.checked = button.dataset.select === "all";
  });
  form.addEventListener("submit", event => {
    const empty = !boxes.some(box => box.checked);
    document.getElementById("selection-error").hidden = !empty;
    if (empty) { event.preventDefault(); boxes[0].focus(); }
  });
})();
