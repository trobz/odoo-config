// Web tools dropdown
(function () {
  function setOpen(toggle, open) {
    toggle.setAttribute("aria-expanded", open);
    document.getElementById(toggle.getAttribute("aria-controls")).hidden = !open;
  }

  document.addEventListener("click", function (e) {
    var clicked = e.target.closest("[data-web-tools-toggle]");
    document.querySelectorAll("[data-web-tools-toggle]").forEach(function (toggle) {
      var open = toggle === clicked && toggle.getAttribute("aria-expanded") !== "true";
      setOpen(toggle, open);
    });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    document.querySelectorAll("[data-web-tools-toggle]").forEach(function (toggle) {
      setOpen(toggle, false);
    });
  });
})();
