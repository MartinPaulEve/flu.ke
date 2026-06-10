/* Cover lightbox / modal gallery for fluke.fm.
   Each `.covers` list (the release-level covers and each edition's covers) is its
   own gallery: clicking a cover opens a larger view in a modal, with prev/next to
   step through the other images in that same list. Progressive enhancement —
   without JS the covers are still shown inline as plain images. */
(function () {
  "use strict";

  var galleries = document.querySelectorAll(".covers");
  if (!galleries.length) {
    return;
  }

  var box, image, prevBtn, nextBtn, closeBtn;
  var items = [];
  var index = 0;
  var lastFocus = null;

  function button(className, label, glyph) {
    var node = document.createElement("button");
    node.type = "button";
    node.className = className;
    node.setAttribute("aria-label", label);
    node.textContent = glyph;
    return node;
  }

  function build() {
    box = document.createElement("div");
    box.className = "lightbox";
    box.hidden = true;
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", "Cover image viewer");

    closeBtn = button("lightbox__close", "Close", "×"); // ×
    prevBtn = button("lightbox__nav lightbox__nav--prev", "Previous image", "‹"); // ‹
    nextBtn = button("lightbox__nav lightbox__nav--next", "Next image", "›"); // ›
    image = document.createElement("img");
    image.className = "lightbox__img";
    image.alt = "";

    box.appendChild(closeBtn);
    box.appendChild(prevBtn);
    box.appendChild(image);
    box.appendChild(nextBtn);
    document.body.appendChild(box);

    closeBtn.addEventListener("click", close);
    prevBtn.addEventListener("click", function () { step(-1); });
    nextBtn.addEventListener("click", function () { step(1); });
    // Click the backdrop (not the image or a button) to close.
    box.addEventListener("click", function (event) {
      if (event.target === box) { close(); }
    });
    document.addEventListener("keydown", onKeydown);
  }

  function render() {
    image.src = items[index].src;
    image.alt = items[index].alt || "";
    var many = items.length > 1;
    prevBtn.hidden = !many;
    nextBtn.hidden = !many;
  }

  function open(galleryItems, startIndex) {
    if (!box) { build(); }
    items = galleryItems;
    index = startIndex;
    lastFocus = document.activeElement;
    render();
    box.hidden = false;
    document.documentElement.style.overflow = "hidden"; // lock background scroll
    closeBtn.focus();
  }

  function step(delta) {
    index = (index + delta + items.length) % items.length; // wrap around
    render();
  }

  function close() {
    if (!box || box.hidden) { return; }
    box.hidden = true;
    document.documentElement.style.overflow = "";
    if (lastFocus && lastFocus.focus) { lastFocus.focus(); }
  }

  function onKeydown(event) {
    if (!box || box.hidden) { return; }
    if (event.key === "Escape") { close(); }
    else if (event.key === "ArrowLeft") { step(-1); }
    else if (event.key === "ArrowRight") { step(1); }
  }

  Array.prototype.forEach.call(galleries, function (gallery) {
    var imgs = Array.prototype.slice.call(gallery.querySelectorAll("img"));
    var galleryItems = imgs.map(function (img) {
      return { src: img.src, alt: img.alt };
    });
    imgs.forEach(function (img, i) {
      img.setAttribute("role", "button");
      img.setAttribute("tabindex", "0");
      img.addEventListener("click", function () { open(galleryItems, i); });
      img.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open(galleryItems, i);
        }
      });
    });
  });
})();
