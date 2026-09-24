document.addEventListener("DOMContentLoaded", () => {
  const modalMap = {
    "btn-nuevo-cliente": "modal-nuevo-cliente",
    "btn-nuevo-producto": "modal-nuevo-producto",
    "btn-nueva-cotizacion": "modal-nueva-cotizacion",
    "btn-nueva-merma": "modal-nueva-merma",
    "btn-nuevo-usuario": "modal-nuevo-usuario",
    "btn-editar-cliente": "modal-editar-cliente"
  };
  Object.entries(modalMap).forEach(([btnId, modalId]) => {
    const btn = document.getElementById(btnId);
    const modal = document.getElementById(modalId);
    if (btn && modal) btn.addEventListener("click", () => modal.hidden = false);
  });
  document.querySelectorAll("[data-close-modal]").forEach(btn => {
    btn.addEventListener("click", () => {
      const modal = btn.closest(".modal-overlay");
      if (modal) modal.hidden = true;
    });
  });
  document.querySelectorAll(".modal-overlay").forEach(modal => {
    modal.addEventListener("click", e => { if (e.target === modal) modal.hidden = true; });
  });

  const searchInputs = document.querySelectorAll('input[type="search"]:not(#global-search)');
  searchInputs.forEach(input => {
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      const table = input.closest(".admin-content")?.querySelector(".data-table");
      if (!table) return;
      table.querySelectorAll("tbody tr").forEach(row => {
        row.hidden = q && !row.textContent.toLowerCase().includes(q);
      });
    });
  });
});