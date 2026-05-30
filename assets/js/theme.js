/* Light/dark theme toggle for flu.ke.
   Dark is the default; light is opt-in via data-theme="light" on <html>.
   The no-flash inline script in <head> applies the stored choice before paint;
   this file wires up the toggle button and keeps its ARIA state in sync. */
(function () {
  "use strict";

  var STORAGE_KEY = "theme";
  var root = document.documentElement;

  function currentTheme() {
    return root.dataset.theme === "light" ? "light" : "dark";
  }

  function syncButton(button, theme) {
    var isLight = theme === "light";
    // aria-pressed reflects "light theme is on".
    button.setAttribute("aria-pressed", isLight ? "true" : "false");
    button.setAttribute(
      "aria-label",
      isLight ? "Switch to dark theme" : "Switch to light theme"
    );
  }

  function apply(theme) {
    if (theme === "light") {
      root.dataset.theme = "light";
    } else {
      delete root.dataset.theme;
    }
  }

  function init() {
    var button = document.getElementById("theme-toggle");
    if (!button) {
      return;
    }

    // Sync the initial ARIA state to whatever the no-flash script decided.
    syncButton(button, currentTheme());

    button.addEventListener("click", function () {
      var next = currentTheme() === "light" ? "dark" : "light";
      apply(next);
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch (e) {}
      syncButton(button, next);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
