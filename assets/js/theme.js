/* Light/dark theme toggle for fluke.fm.
   Light is the default; dark is opt-in via data-theme="dark" on <html>.
   The no-flash inline script in <head> applies the stored choice before paint;
   this file wires up the toggle button and keeps its ARIA state in sync. */
(function () {
  "use strict";

  var STORAGE_KEY = "theme";
  var root = document.documentElement;

  function currentTheme() {
    return root.dataset.theme === "dark" ? "dark" : "light";
  }

  function syncButton(button, theme) {
    var isDark = theme === "dark";
    // aria-pressed reflects "dark theme is on" (light is the default).
    button.setAttribute("aria-pressed", isDark ? "true" : "false");
    button.setAttribute(
      "aria-label",
      isDark ? "Switch to light theme" : "Switch to dark theme"
    );
  }

  function apply(theme) {
    if (theme === "dark") {
      root.dataset.theme = "dark";
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
      var next = currentTheme() === "dark" ? "light" : "dark";
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
