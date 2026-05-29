/* Cinematic scroll enhancements for flu.ke.
   Progressive enhancement: content is fully visible without JS. Motion is applied
   only when the user has not asked to reduce it. */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Mark JS available; CSS only hides reveal elements once this class is present
  // AND motion is allowed, so no-JS / reduced-motion users see everything immediately.
  if (!reduceMotion) {
    root.classList.add("js");
  }
  if (reduceMotion || !("IntersectionObserver" in window)) {
    return;
  }

  // Index staggered children so each can offset its transition.
  document.querySelectorAll('[data-reveal="stagger"]').forEach(function (group) {
    Array.prototype.forEach.call(group.children, function (child, i) {
      child.style.setProperty("--i", i);
    });
  });

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { rootMargin: "0px 0px -10% 0px", threshold: 0.1 }
  );
  document.querySelectorAll(".reveal").forEach(function (el) {
    observer.observe(el);
  });

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
