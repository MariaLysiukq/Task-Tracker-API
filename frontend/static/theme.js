"use strict";
/* Runs before the page paints (not deferred), so a saved light theme does not flash dark. */
(() => {
  let choice = null;
  try { choice = localStorage.getItem("tt.theme"); } catch { /* storage unavailable */ }
  document.documentElement.dataset.theme = ["light", "dark", "system"].includes(choice) ? choice : "dark";
})();
