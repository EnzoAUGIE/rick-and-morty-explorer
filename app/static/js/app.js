// Dialogue "Quitter" — reprise du showExitConfirmation() de la version Java
(() => {
  const dlg = document.getElementById("quit-dialog");
  const btn = document.getElementById("quit-btn");
  if (!dlg || !btn) return;

  const show = (step) =>
    dlg.querySelectorAll("[data-step]").forEach((el) => (el.hidden = el.dataset.step !== step));

  btn.addEventListener("click", () => { show("ask"); dlg.showModal(); });

  dlg.addEventListener("click", (e) => {
    const answer = e.target.dataset.answer;
    if (answer === "yes") {
      show("yes");
      setTimeout(() => { dlg.close(); window.location.href = "/"; }, 2000);
    } else if (answer === "no") {
      show("no");
    } else if (e.target.hasAttribute("data-close")) {
      dlg.close();
    }
  });
})();
