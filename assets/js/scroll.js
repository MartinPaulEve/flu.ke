/* Cinematic scroll enhancements for fluke.fm.
   Progressive enhancement: content is fully visible without JS. Motion is applied
   only when the user has not asked to reduce it. */
(function () {
  "use strict";

  var reduceMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reduceMotion) {
    return;
  }

  // Subtle parallax on opted-in elements (data-parallax = strength).
  var parallax = Array.prototype.slice.call(document.querySelectorAll("[data-parallax]"));
  if (parallax.length) {
    var ticking = false;
    var apply = function () {
      var mid = window.innerHeight / 2;
      parallax.forEach(function (el) {
        var strength = parseFloat(el.getAttribute("data-parallax")) || 0.15;
        var rect = el.getBoundingClientRect();
        var offset = (rect.top + rect.height / 2 - mid) * -strength;
        el.style.transform = "translate3d(0," + offset.toFixed(1) + "px,0)";
      });
      ticking = false;
    };
    var onScroll = function () {
      if (!ticking) {
        window.requestAnimationFrame(apply);
        ticking = true;
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    apply();
  }
})();
