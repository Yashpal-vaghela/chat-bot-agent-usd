
  document.addEventListener("DOMContentLoaded", function () {
    if (sessionStorage.getItem('usd_chat_active') === 'true') {
      try { openChat(false); } catch (e) { }
    }
  });
