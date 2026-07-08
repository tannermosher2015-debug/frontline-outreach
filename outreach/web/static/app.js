async function post(url, body) {
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"},
                             body: JSON.stringify(body)});
  return r.json();
}
function cardId(el){ return el.closest(".card").dataset.id; }
function setStatus(el, text){ el.closest(".card").querySelector(".status").textContent = text; }

document.querySelectorAll(".card").forEach(card => {
  const id = card.dataset.id;
  const draft = card.querySelector(".draft");

  card.querySelector(".copy")?.addEventListener("click", async () => {
    await navigator.clipboard.writeText(draft.value);
    setStatus(card.querySelector(".copy"), "copied");
  });
  draft.addEventListener("change", () => post("/action/edit", {place_id:id, draft_text:draft.value}));
  card.querySelector(".skip")?.addEventListener("click", async (e) => {
    await post("/action/skip", {place_id:id}); setStatus(e.target, "skipped");
  });
  card.querySelector(".contacted")?.addEventListener("click", async (e) => {
    await post("/action/contacted", {place_id:id, channel:card.dataset.channel});
    setStatus(e.target, "contacted");
  });
  card.querySelector(".send")?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    const res = await post("/action/send", {place_id:id});
    setStatus(e.target, res.mode === "sent" ? "sent" : res.mode);
    e.target.disabled = false;
  });
  card.querySelector(".send-sample")?.addEventListener("click", async (e) => {
    const url = card.querySelector(".sample-url")?.value.trim();
    if(!url){ setStatus(e.target, "add a demo URL first"); return; }
    e.target.disabled = true;
    const res = await post("/action/send_sample", {place_id:id, sample_url:url});
    setStatus(e.target, res.mode === "sent" ? "sample sent" : res.mode);
    e.target.disabled = false;
  });
});
