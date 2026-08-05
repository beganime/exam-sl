import { initializeApp } from "https://www.gstatic.com/firebasejs/12.16.0/firebase-app.js";
import { getMessaging, getToken, onMessage } from "https://www.gstatic.com/firebasejs/12.16.0/firebase-messaging.js";

const button = document.querySelector("[data-enable-push]");
const status = document.querySelector("[data-push-status]");
const title = document.querySelector("[data-push-title]");
const copy = document.querySelector("[data-push-copy]");
const configNode = document.getElementById("firebase-config");
const vapidNode = document.getElementById("fcm-vapid-key");
const vapidKey = vapidNode ? JSON.parse(vapidNode.textContent) : "";

function cookie(name) {
  return document.cookie.split("; ").find(row => row.startsWith(`${name}=`))?.split("=")[1] || "";
}
function setStatus(text, isError = false) {
  status.textContent = text;
  status.style.color = isError ? "#8c3429" : "inherit";
}
function withTimeout(promise, ms, message) {
  let timeoutId;
  const timeout = new Promise((_, reject) => {
    timeoutId = setTimeout(() => reject(new Error(message)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timeoutId));
}

if (!configNode || !button) {
  // Page is not the push settings surface.
} else if (!window.isSecureContext) {
  button.disabled = true;
  setStatus("Web push работает только на HTTPS или localhost/127.0.0.1.", true);
} else if (!("serviceWorker" in navigator) || !("Notification" in window)) {
  button.disabled = true;
  setStatus("Этот браузер не поддерживает web push.", true);
} else {
  const firebaseConfig = JSON.parse(configNode.textContent);
  const app = initializeApp(firebaseConfig);
  const messaging = getMessaging(app);

  if (Notification.permission === "granted") {
    title.textContent = "Уведомления разрешены";
    copy.textContent = "Нажмите кнопку ещё раз, чтобы обновить и синхронизировать токен браузера.";
    button.textContent = "Обновить подключение";
  }

  button.addEventListener("click", async () => {
    try {
      if (!vapidKey) throw new Error("Добавьте FCM_VAPID_PUBLIC_KEY в .env");
      button.disabled = true;
      setStatus("Готовим service worker…");
      const registration = await withTimeout(
        navigator.serviceWorker.register("/firebase-messaging-sw.js", { scope: "/" }),
        15000,
        "Service worker не зарегистрировался за 15 секунд. Обновите страницу и попробуйте ещё раз."
      );
      await navigator.serviceWorker.ready;
      setStatus("Запрашиваем разрешение браузера…");
      const permission = await withTimeout(
        Notification.requestPermission(),
        45000,
        "Браузер не ответил на запрос разрешения. Проверьте, не заблокированы ли уведомления для сайта."
      );
      if (permission !== "granted") throw new Error("Разрешение на уведомления не выдано браузером.");
      setStatus("Получаем FCM-токен…");
      const token = await withTimeout(
        getToken(messaging, { vapidKey, serviceWorkerRegistration: registration }),
        30000,
        "Firebase не вернул токен за 30 секунд. Проверьте Web Push certificate/VAPID и Firebase web config."
      );
      if (!token) throw new Error("Firebase не вернул токен устройства.");
      setStatus("Сохраняем токен…");
      const response = await fetch("/push/register/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(cookie("csrftoken")) },
        body: JSON.stringify({ token, device_id: `${navigator.platform || "Web"} · ${navigator.userAgent.split(" ").slice(-2).join(" ")}` })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "Не удалось сохранить токен.");
      title.textContent = "Уведомления подключены";
      copy.textContent = "Этот браузер готов получать напоминания ExamSL.";
      button.textContent = "Подключено ✓";
      setStatus(data.sync_error ? `Локально сохранено. API: ${data.sync_error}` : "Токен сохранён и синхронизирован.", Boolean(data.sync_error));
      setTimeout(() => location.reload(), 1200);
    } catch (error) {
      setStatus(error.message || String(error), true);
      button.disabled = false;
    }
  });

  onMessage(messaging, payload => {
    const notification = payload.notification || {};
    const link = payload.data?.link || "/";
    setStatus(`Получено: ${notification.title || "ExamSL"}`);
    if (Notification.permission === "granted") {
      const shown = new Notification(notification.title || "ExamSL", {
        body: notification.body || "Новое уведомление",
        icon: "/static/img/push-icon.svg",
        data: { link }
      });
      shown.onclick = () => {
        window.focus();
        window.location.href = shown.data.link || "/";
      };
    }
  });
}
