(() => {
  const modal = document.querySelector("[data-search-modal]");
  const input = document.querySelector("[data-global-search]");
  const results = document.querySelector("[data-search-results]");
  let timer;

  const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  }[char]));

  function openSearch() {
    if (!modal) return;
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    setTimeout(() => input.focus(), 20);
  }
  function closeSearch() {
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = "";
  }
  document.querySelectorAll("[data-search-open]").forEach(el => el.addEventListener("click", openSearch));
  document.querySelectorAll("[data-search-close]").forEach(el => el.addEventListener("click", closeSearch));
  document.addEventListener("keydown", event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); openSearch(); }
    if (event.key === "Escape") closeSearch();
  });

  function renderGroup(title, items, formatter) {
    if (!items?.length) return "";
    return `<div class="result-group"><h3>${title}</h3>${items.map(formatter).join("")}</div>`;
  }
  input?.addEventListener("input", () => {
    clearTimeout(timer);
    const query = input.value.trim();
    if (query.length < 2) { results.innerHTML = '<p class="empty-state">Введите минимум 2 символа.</p>'; return; }
    results.innerHTML = '<p class="empty-state">Ищем…</p>';
    timer = setTimeout(async () => {
      try {
        const response = await fetch(`${window.examSL.searchUrl}?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        const html = renderGroup("Экзамены ExamSL", data.local, item => `<a class="result-item" href="${item.url}"><div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.subject)} · ${escapeHtml(item.university)}</span></div><small>${escapeHtml(item.exam_at)} →</small></a>`) +
          renderGroup("Пользователи Students Life", data.users, item => `<div class="result-item"><div><strong>${escapeHtml([item.first_name, item.last_name].filter(Boolean).join(" ") || item.username)}</strong><span>${escapeHtml(item.email || item.username || "")} · ID ${escapeHtml(item.id)}</span></div><small>${escapeHtml(item.role || "user")}</small></div>`) +
          renderGroup("Профили клиентов", data.profiles, item => `<div class="result-item"><div><strong>${escapeHtml(item.phone || item.telegram || `Профиль ${item.id}`)}</strong><span>${escapeHtml([item.country, item.city, item.citizenship].filter(Boolean).join(" · "))}</span></div><small>ID ${escapeHtml(item.id)}</small></div>`);
        results.innerHTML = html || `<p class="empty-state">По запросу «${escapeHtml(query)}» ничего не найдено.</p>`;
        if (data.api_error) results.insertAdjacentHTML("beforeend", `<p class="empty-state">Внешняя база: ${escapeHtml(data.api_error)}</p>`);
      } catch (error) { results.innerHTML = '<p class="empty-state">Не удалось выполнить поиск. Проверьте соединение.</p>'; }
    }, 280);
  });

  document.querySelectorAll(".toast button").forEach(button => button.addEventListener("click", () => button.parentElement.remove()));
  setTimeout(() => document.querySelectorAll(".toast").forEach(toast => toast.remove()), 8000);

  const countdown = document.querySelector("[data-countdown]");
  if (countdown) {
    const target = new Date(countdown.dataset.countdown);
    const diff = target - new Date();
    if (diff <= 0) countdown.textContent = "Начался";
    else {
      const days = Math.floor(diff / 86400000);
      const hours = Math.floor((diff % 86400000) / 3600000);
      countdown.textContent = days ? `${days} д. ${hours} ч.` : `${hours} ч.`;
    }
  }
})();
