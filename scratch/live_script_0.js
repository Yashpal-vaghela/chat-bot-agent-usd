
  document.addEventListener("DOMContentLoaded", function () {
    const chatBotContainer = document.querySelector(
      ".voice_chat_bot_container",
    );
    const chatBotIconContainer = document.querySelector(
      ".voice_chat_bot_icon_container",
    );
    const closeIcon = document.querySelector(".close_icon_main");
    const chatIconMain = document.querySelector(".chat_icon_main");
    const headerVoiceIcon = document.querySelector(".header_voice_icon");
    const headerCloseIcon = document.querySelector(".header_close_icon");
    const massageInputMain = document.querySelector(".massge_input_main");
    const inputBoxAndIconMain = document.querySelector(
      ".input_box_and_icon_main",
    );
    const chatAndVoiceContainer = document.querySelector(
      ".chat_icon_and_voice_and_close_icon_container_main",
    );
    const chatMainContainer = document.querySelector(".chat_main_container");

    if (chatBotIconContainer && chatBotContainer) {
      chatBotIconContainer.addEventListener("click", function () {
        chatBotContainer.classList.add("active");
        chatBotIconContainer.classList.add("hidden");
      });
    }

    if (chatIconMain) {
      chatIconMain.addEventListener("click", function () {
        if (massageInputMain) massageInputMain.style.display = "block";
        if (inputBoxAndIconMain) inputBoxAndIconMain.style.display = "flex";
        if (headerVoiceIcon) headerVoiceIcon.style.display = "block";
        if (headerCloseIcon) headerCloseIcon.style.display = "block";
        if (chatAndVoiceContainer) chatAndVoiceContainer.style.display = "none";
      });
    }

    if (headerVoiceIcon) {
      headerVoiceIcon.addEventListener("click", function () {
        if (chatAndVoiceContainer) chatAndVoiceContainer.style.display = "flex";
        if (massageInputMain) massageInputMain.style.display = "none";
        if (inputBoxAndIconMain) inputBoxAndIconMain.style.display = "none";
        if (headerVoiceIcon) headerVoiceIcon.style.display = "none";
        if (headerCloseIcon) headerCloseIcon.style.display = "none";
      });
    }

    const voiceIconMain = document.querySelector(".voice_icon_main");
    if (voiceIconMain) {
      voiceIconMain.addEventListener("click", async function () {
        voiceIconMain.classList.add("is-listening");
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
              channelCount: 1,
              sampleRate: 16000,
            },
            video: false,
          });
          console.log("Microphone access granted");
        } catch (err) {
          console.error("Microphone access denied", err);
          voiceIconMain.classList.remove("is-listening");
        }
      });
    }
  });
