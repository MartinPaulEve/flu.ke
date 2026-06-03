/* Mobile navigation: the hamburger button toggles a dropdown holding the
   primary nav links and the theme switcher. Desktop shows them inline (the
   button is hidden via CSS), so this only matters on small screens. */
(function () {
  "use strict";

  var btn = document.getElementById("nav-toggle");
  var group = document.getElementById("nav-group");
  if (!btn || !group) {
    return;
  }

  function setOpen(open) {
    group.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  btn.addEventListener("click", function (event) {
    event.stopPropagation();
    setOpen(!group.classList.contains("open"));
  });

  // Close once a destination is chosen.
  group.querySelectorAll(".site-nav a").forEach(function (link) {
    link.addEventListener("click", function () {
      setOpen(false);
    });
  });

  // Close on Escape or a click/tap outside the menu.
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      setOpen(false);
    }
  });
  document.addEventListener("click", function (event) {
    if (
      group.classList.contains("open") &&
      !group.contains(event.target) &&
      !btn.contains(event.target)
    ) {
      setOpen(false);
    }
  });
})();
