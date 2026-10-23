(async function () {
  const video = document.getElementById("video");
  const freezeImg = document.getElementById("freezeImg");
  const canvas = document.getElementById("canvas");
  const captureBtn = document.getElementById("captureBtn");
  const recaptureBtn = document.getElementById("recaptureBtn");
  const confirmBtn = document.getElementById("confirmBtn");
  const status = document.getElementById("status");
  const msg = document.getElementById("msg");
  const guideLine = document.getElementById("smileGuideLine");
  const faceOverlay = document.getElementById("faceOverlay");
  const switchCameraBtn = document.getElementById("switchCameraBtn");
  const uploadBtn = document.getElementById("uploadBtn");
  const uploadInput = document.getElementById("uploadInput");

  const resultWrap = document.getElementById("resultWrap");
  const resultStatus = document.getElementById("resultStatus");
  const beforeImg = document.getElementById("beforeImg");
  const afterImg = document.getElementById("afterImg");
  const dlBefore = document.getElementById("dlBefore");
  const dlAfter = document.getElementById("dlAfter");
  const errorBox = document.getElementById("errorBox");

  // Contact modal form elements
  const leadForm = document.getElementById("leadForm");
  const leadName = document.getElementById("leadName");
  const leadPhone = document.getElementById("leadPhone");
  const leadCity = document.getElementById("leadCity");
  const leadEmail = document.getElementById("leadEmail");
  const leadFormMsg = document.getElementById("leadFormMsg");
  const leadSubmitBtn = document.getElementById("leadSubmitBtn");

  const ctx = canvas.getContext("2d", { willReadFrequently: true });

  function pingDetectApi() {
    const dummyCanvas = document.createElement("canvas");
    dummyCanvas.width = 640;
    dummyCanvas.height = 480;
    const dCtx = dummyCanvas.getContext("2d");
    dCtx.fillstyle = "#808080";
    dCtx.fillRect(0, 0, 640, 480);

    fetch("https://ai.ultimatesmiledesign.com/detect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dummyCanvas.toDataURL("image/jpeg") })
    }).catch(() => { });
  }

  // pingDetectApi();

  let stream = null;
  let running = false;
  let capturedDataUrl = null;
  let lastConf = 0;
  let generationPromise = null;
  let generationResult = null;
  let leadSubmitted = false;
  let previewOpened = false;
  let leadId = null;
  let captureNonce = null;
  let isCapturing = false;
  let currentFacingMode = "user"; // "user" or "environment"
  let hasMultipleCameras = false;
  let videoDevices = [];
  let currentDeviceIndex = 0;
  const isMobile = /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

  // ✅ WhatsApp dedupe flags
  let whatsappTriggered = false;
  let whatsappInFlight = false;

  // ✅ NEW: last detect snapshot + freshness
  let lastDetectAt = 0;
  let lastVisible = false;
  const DETECT_FRESH_MS = 350; // adjust if needed
  let detectFailCount = 0;        // consecutive detect API failure counter
  const DETECT_FAIL_LIMIT = 3;    // after this many failures, enable button directly (offline mode)
  let detectOfflineMode = false;  // true = detect API is down, run without it

  function cleanupModalBackdrops() {
    document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
    document.body.classList.remove("modal-open");
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("padding-right");
  }

  function showPreviewLoader() {
    cleanupModalBackdrops();
    const previewLoader = document.getElementById("previewLoader");
    const previewContent = document.getElementById("previewContent");
    const previewError = document.getElementById("previewError");

    if (previewLoader) {
      previewLoader.classList.remove("d-none");
      previewLoader.style.setProperty("display", "block", "important");
    }
    if (previewContent) {
      previewContent.classList.add("d-none");
      previewContent.style.setProperty("display", "none", "important");
    }
    if (previewError) {
      previewError.classList.add("d-none");
      previewError.style.setProperty("display", "none", "important");
    }

    const previewEl = document.getElementById("PreviewModal");
    if (previewEl) {
      const previewModal =
        bootstrap.Modal.getInstance(previewEl) || new bootstrap.Modal(previewEl);
      previewModal.show();
    }
  }

  function tryOpenPreviewInline() {
    if (!generationResult || generationResult.done !== true) return;

    // stop loader in lead form if any
    if (leadFormMsg) {
      leadFormMsg.innerHTML = "";
      leadFormMsg.style.color = "";
    }

    const previewLoader = document.getElementById("previewLoader");
    const previewContent = document.getElementById("previewContent");
    const previewError = document.getElementById("previewError");
    const previewErrorText = document.getElementById("previewErrorText");

    const previewEl = document.getElementById("PreviewModal");
    if (previewEl) {
      const previewModal =
        bootstrap.Modal.getInstance(previewEl) || new bootstrap.Modal(previewEl);
      previewModal.show();
    }

    if (generationResult.ok === true) {
      const pBefore = document.getElementById("previewBeforeImg");
      const pAfter = document.getElementById("previewAfterImg");

      if (pBefore) {
        pBefore.src = generationResult.beforeUrl || capturedDataUrl;
        const syncAspect = () => {
          const wrap = document.querySelector(".preview-modal-wrapper");
          if (wrap && pBefore.naturalWidth && pBefore.naturalHeight) {
            wrap.style.aspectRatio = `${pBefore.naturalWidth} / ${pBefore.naturalHeight}`;
          }
        };
        if (pBefore.complete && pBefore.naturalWidth) {
          syncAspect();
        } else {
          pBefore.onload = syncAspect;
        }
      }
      if (pAfter) pAfter.src = generationResult.afterUrl || generationResult.beforeUrl;

      // Reset slider to 50%
      const slider = document.getElementById("slider");
      const line = document.getElementById("preview-line");
      const imgAfterWrapper = document.querySelector(".preview_img_wrapper:nth-of-type(2)");
      if (slider) slider.value = 50;
      if (line) line.style.left = "50%";
      if (imgAfterWrapper) imgAfterWrapper.style.clipPath = "inset(0px 0px 0px 50%)";

      if (previewLoader) {
        previewLoader.classList.add("d-none");
        previewLoader.style.setProperty("display", "none", "important");
      }
      if (previewError) {
        previewError.classList.add("d-none");
        previewError.style.setProperty("display", "none", "important");
      }
      if (previewContent) {
        previewContent.classList.remove("d-none");
        previewContent.style.setProperty("display", "block", "important");
      }

      const contactEl = document.getElementById("contactModal");
      if (contactEl) {
        const contactModal = bootstrap.Modal.getInstance(contactEl);
        contactModal?.hide();
      }

      previewOpened = true;
      leadForm?.reset();

      // Only triggers once due to whatsappInFlight lock
      tryTriggerWhatsapp();
    } else {
      if (previewLoader) {
        previewLoader.classList.add("d-none");
        previewLoader.style.setProperty("display", "none", "important");
      }
      if (previewContent) {
        previewContent.classList.add("d-none");
        previewContent.style.setProperty("display", "none", "important");
      }
      if (previewError) {
        previewError.classList.remove("d-none");
        previewError.style.setProperty("display", "block", "important");
        if (previewErrorText) previewErrorText.textContent = generationResult.error || "Smile generation failed.";
      }
      if (leadFormMsg) {
        leadFormMsg.style.color = "red";
        leadFormMsg.textContent = generationResult.error || "Smile generation failed.";
      }
    }
  }

  function getThreshold() {
    if (typeof window.THRESHOLD === "number") return window.THRESHOLD;
    if (typeof THRESHOLD === "number") return THRESHOLD;
    return 0.55;
  }

  function showFreeze() {
    freezeImg.classList.remove("hidden");
    freezeImg.classList.remove("visually-hidden");
    video.classList.add("hidden");
  }

  function hideFreeze() {
    freezeImg.classList.add("hidden");
    freezeImg.classList.add("visually-hidden");
    freezeImg.src = "";
    video.classList.remove("hidden");
  }

  function showError(text) {
    if (!errorBox) return;
    if (!text) {
      errorBox.classList.add("hidden");
      errorBox.textContent = "";
      return;
    }
    errorBox.classList.remove("hidden");
    errorBox.textContent = text;
  }

  function setMessage(text, kind) {
    if (!msg) return;
    msg.textContent = text || "";
    msg.className = "muted";
    if (kind === "ok") msg.className = "ok";
    if (kind === "error") msg.className = "error";
  }

  function resetResult() {
    if (!resultWrap || !resultStatus || !beforeImg || !afterImg || !dlBefore || !dlAfter) return;
    resultWrap.classList.add("hidden");
    resultStatus.textContent = "";
    beforeImg.src = "";
    afterImg.src = "";
    dlBefore.href = "#";
    dlAfter.href = "#";
  }

  function setControlsForVerifying() {
    captureBtn.classList.remove("hidden", "d-none");
    recaptureBtn.classList.add("hidden");
    confirmBtn.classList.add("hidden");
    if (uploadBtn) uploadBtn.classList.add("hidden", "d-none");

    captureBtn.disabled = true;
    captureBtn.innerHTML = '<span class="capture-inner">Verifying...</span>';
    if (guideLine) guideLine.classList.add("hidden", "d-none");
    updateSwitchCameraButtonVisibility();
  }


  async function checkCameraDevices() {
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        const devices = await navigator.mediaDevices.enumerateDevices();
        videoDevices = devices.filter((d) => d.kind === "videoinput");
        hasMultipleCameras = videoDevices.length > 1;

        console.log("--- Detected Camera Devices ---");
        console.table(videoDevices.map(c => ({ Name: c.label || 'Unnamed Camera', ID: c.deviceId })));
      }
    } catch (e) {
      console.warn("enumerateDevices failed:", e);
    }
    updateSwitchCameraButtonVisibility();
  }

  function updateSwitchCameraButtonVisibility() {
    if (!switchCameraBtn) return;
    if (running && !isCapturing && !capturedDataUrl) {
      switchCameraBtn.classList.remove("hidden");
    } else {
      switchCameraBtn.classList.add("hidden");
    }
  }

  async function startCamera(preferredDeviceId = null) {
    stopCamera();

    const cameraDeniedOverlay = document.getElementById("cameraDeniedOverlay");
    if (cameraDeniedOverlay) cameraDeniedOverlay.classList.add("d-none");

    let videoConstraints = {
      width: { ideal: 1184 },
      height: { ideal: 864 }
    };

    if (preferredDeviceId) {
      videoConstraints.deviceId = { exact: preferredDeviceId };
    } else if (currentFacingMode) {
      videoConstraints.facingMode = { ideal: currentFacingMode };
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: videoConstraints,
        audio: false,
      });
    } catch (err) {
      console.warn("getUserMedia with preferred constraints failed, trying fallback:", err);
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: currentFacingMode },
          audio: false,
        });
      } catch (err2) {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }
    }

    video.srcObject = stream;

    if (currentFacingMode === "environment") {
      video.classList.add("no-mirror");
    } else {
      video.classList.remove("no-mirror");
    }

    hideFreeze();
    video.classList.remove("hidden");

    await video.play();
    await checkCameraDevices();
  }

  function stopCamera() {
    try {
      if (video && video.srcObject) {
        const s = video.srcObject;
        s.getTracks().forEach((t) => t.stop());
      }
    } catch (e) { }
    video.srcObject = null;
    stream = null;
    updateSwitchCameraButtonVisibility();
  }

  async function detectOnce(canvas) {
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);

    // Primary: relative endpoint (always matches current host: local, tunnel, or live)
    // Fallback: remote endpoint
    const endpoints = [
      "/virtual-smile-try-on/api/detect/",
      "https://detect.ultimatesmiledesign.com/virtual-smile-try-on/api/detect/"
    ];

    let lastError = null;
    for (const url of endpoints) {
      try {
        const resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image: dataUrl }),
        });

        if (resp.ok) {
          const data = await resp.json();
          return data;
        }
      } catch (e) {
        lastError = e;
      }
    }

    throw lastError || new Error("Detection endpoints unreachable");
  }

  async function saveCapture(frameDataUrl, conf) {
    const resp = await fetch("/virtual-smile-try-on/api/capture/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken,
      },
      body: JSON.stringify({ image: frameDataUrl, conf: conf }),
    });
    return await resp.json();
  }

  async function callGemini(frameDataUrl) {
    const resp = await fetch("/virtual-smile-try-on/api/smile-design/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: frameDataUrl }),
    });

    const data = await resp.json();

    if (!resp.ok || !data.ok) {
      return {
        ok: false,
        error: data?.error || "Smile design failed",
        status: resp.status,
      };
    }

    return {
      ok: true,
      beforeUrl: data.before_url,
      afterUrl: data.after_url,
    };
  }

  function updateCaptureButtonState(enabled) {
    if (!captureBtn) return;

    captureBtn.classList.remove("hidden", "d-none");

    if (enabled) {
      captureBtn.disabled = false;
      captureBtn.innerHTML = '<span class="capture-inner">Capture Now</span>';
      if (guideLine) guideLine.classList.add("hidden", "d-none");
      if (faceOverlay) {
        faceOverlay.classList.add("ready");
        faceOverlay.style.border = "none";
      }
    } else {
      captureBtn.disabled = true;
      captureBtn.innerHTML = '<span class="capture-inner">Capture Now</span>';
      if (guideLine) guideLine.classList.remove("hidden", "d-none");
      if (faceOverlay) {
        faceOverlay.classList.remove("ready");
        faceOverlay.style.border = "4px dashed rgba(255, 255, 255, 0.8)"
      }
    }
    updateSwitchCameraButtonVisibility();
  }

  function setControlsForLive() {
    captureBtn.classList.remove("hidden", "d-none");
    recaptureBtn.classList.add("hidden");
    confirmBtn.classList.add("hidden");
    if (uploadBtn) uploadBtn.classList.remove("hidden", "d-none");
    captureBtn.innerHTML = '<span class="capture-inner">Capture Now</span>';
    captureBtn.disabled = true;
    confirmBtn.disabled = true;
    if (guideLine) guideLine.classList.remove("hidden", "d-none");
    if (faceOverlay) {
      faceOverlay.classList.remove("ready");
      faceOverlay.style.border = "4px dashed rgba(255, 255, 255, 0.8)";
    }
    updateSwitchCameraButtonVisibility();
  }

  function setControlsForCaptured() {
    captureBtn.classList.add("hidden", "d-none");
    recaptureBtn.classList.remove("hidden");
    confirmBtn.classList.remove("hidden");
    if (uploadBtn) uploadBtn.classList.add("hidden", "d-none");
    confirmBtn.disabled = !capturedDataUrl;
    confirmBtn.innerHTML = 'Continue <img src="/static/light-arrow-left.svg" class="img-fluid" alt="arrow-left" />';
    captureBtn.disabled = true;
    if (guideLine) guideLine.classList.add("hidden", "d-none");
    updateSwitchCameraButtonVisibility();
  }

  function drawCurrentFrameToCanvas() {
    canvas.width = video.videoWidth || 1184;
    canvas.height = video.videoHeight || 864;

    ctx.save();
    if (currentFacingMode === "user") {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    ctx.restore();
  }

  function setVerifyingUI(isVerifying) {
    if (!captureBtn) return;
    captureBtn.classList.remove("hidden", "d-none");
    if (isVerifying) {
      captureBtn.disabled = true;
      captureBtn.innerHTML = '<span class="capture-inner">Verifying...</span>';
    } else {
      captureBtn.disabled = false;
      captureBtn.innerHTML = '<span class="capture-inner">Capture Now</span>';
    }
  }


  // NEW: On-click hard gate (validate the exact frame being captured)
  async function captureAndValidateNow() {
    drawCurrentFrameToCanvas();

    const data = await detectOnce(canvas);

    const conf =
      typeof data.conf === "number"
        ? data.conf
        : typeof data.confidence === "number"
          ? data.confidence
          : 0;

    const visible = !!data.visible;
    const threshold = getThreshold();

    if (!(visible && conf >= threshold)) {
      throw new Error(
        `Not smiling enough. Confidence ${conf.toFixed(2)} (need ${threshold}).`
      );
    }

    return {
      dataUrl: canvas.toDataURL("image/jpeg", 0.92),
      conf,
      visible,
    };
  }

  async function detectLoop() {
    running = true;

    while (running) {
      try {
        if (!video.srcObject || video.readyState < 2) {
          await new Promise((r) => setTimeout(r, 120));
          continue;
        }

        drawCurrentFrameToCanvas();

        // If detect API is confirmed offline, skip remote call and enable button directly
        if (detectOfflineMode) {
          if (!isCapturing && running) updateCaptureButtonState(true);
          await new Promise((r) => setTimeout(r, 500));
          continue;
        }

        const data = await detectOnce(canvas);

        // Reset failure counter on success
        detectFailCount = 0;

        if (!running) break;

        const conf =
          typeof data.conf === "number"
            ? data.conf
            : typeof data.confidence === "number"
              ? data.confidence
              : 0;

        const visible = !!data.visible;
        lastConf = conf;

        // ✅ store last detect snapshot time + visible
        lastVisible = visible;
        lastDetectAt = Date.now();

        const threshold = getThreshold();
        if (status) {
          status.textContent = `Confidence: ${conf.toFixed(2)} | Visible: ${visible} | Threshold: ${threshold}`;
        }

        // Optional: require freshness (small extra protection)
        const fresh = Date.now() - lastDetectAt <= DETECT_FRESH_MS;
        if (!isCapturing && running) {
          updateCaptureButtonState(fresh && visible && conf >= threshold);
        }
      } catch (e) {
        detectFailCount++;
        console.warn(`detectLoop error (${detectFailCount}/${DETECT_FAIL_LIMIT}):`, e.message || e);
        if (detectFailCount >= DETECT_FAIL_LIMIT && !detectOfflineMode) {
          detectOfflineMode = true;
          console.warn("[SmileAI] Detect API offline — enabling capture without remote validation.");
          if (status) status.textContent = "Detection offline — Capture enabled directly.";
          if (!isCapturing && running) updateCaptureButtonState(true);
        }
      }

      await new Promise((r) => setTimeout(r, 200));
    }
  }

  captureBtn.addEventListener("click", async () => {
    if (isCapturing) return;
    isCapturing = true;

    showError("");
    resetResult();
    setMessage("");

    // extra safety
    if (captureBtn.disabled) {
      isCapturing = false;
      return;
    }

    if (!video.srcObject || video.readyState < 2) {
      setMessage("Camera not ready. Please try again.", "error");
      isCapturing = false;
      return;
    }

    try {
      // ✅ Freeze the exact frame immediately
      drawCurrentFrameToCanvas();
      const snapDataUrl = canvas.toDataURL("image/jpeg", 0.92);

      freezeImg.src = snapDataUrl;
      showFreeze();

      // ✅ Show Verifying...
      setControlsForVerifying();
      setMessage("Please wait… your image is being verified.", "muted");

      let conf = 0.90;
      let visible = true;
      const threshold = getThreshold();

      // Only call detect if API is online
      if (!detectOfflineMode) {
        try {
          const data = await detectOnce(canvas);
          conf =
            typeof data.conf === "number"
              ? data.conf
              : typeof data.confidence === "number"
                ? data.confidence
                : 0;
          visible = !!data.visible;
        } catch (detectErr) {
          detectFailCount++;
          if (detectFailCount >= DETECT_FAIL_LIMIT) detectOfflineMode = true;
          console.warn("[SmileAI Capture] Detect failed — treating as offline pass.", detectErr);
          // Offline: treat as valid pass
          visible = true;
          conf = 0.90;
        }
      }

      // ❌ FAIL → back to live → Capture Now (disabled until smile again)
      if (!detectOfflineMode && !(visible && conf >= threshold)) {
        hideFreeze();
        setControlsForLive();
        setMessage("Verification failed ❌ Please smile and try again.", "error");

        // ensure detect loop runs to re-enable button
        if (!running) detectLoop();

        isCapturing = false;
        return;
      }

      // ✅ PASS → keep frozen → show Recapture + Continue
      setMessage("Verified ✅ Captured successfully.", "ok");

      capturedDataUrl = snapDataUrl;
      lastConf = conf;

      // backend capture save
      try {
        const saved = await saveCapture(capturedDataUrl, lastConf);
        if (saved && saved.ok) {
          captureNonce = saved.nonce || null;
        } else {
          // treat backend reject as FAIL
          hideFreeze();
          setControlsForLive();
          setMessage("Capture validation failed. Please try again.", "error");
          if (!running) detectLoop();
          isCapturing = false;
          return;
        }
      } catch (e) {
        hideFreeze();
        setControlsForLive();
        setMessage("Capture failed. Please try again.", "error");
        if (!running) detectLoop();
        isCapturing = false;
        return;
      }

      // stop camera only after PASS + saved
      running = false;
      stopCamera();

      setControlsForCaptured(); // ✅ Recapture + Continue
      isCapturing = false;
    } catch (e) {
      hideFreeze();
      setControlsForLive();
      setMessage("Verification failed ❌ Please try again.", "error");
      if (!running) detectLoop();
      isCapturing = false;
    }
  });

  // 📸 Handle Photo Upload 📸
  if (uploadBtn && uploadInput) {
    uploadBtn.addEventListener("click", () => {
      uploadInput.value = "";
      uploadInput.click();
    });

    uploadInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = async (ev) => {
        const rawDataUrl = ev.target.result;
        
        // We will draw it to canvas to normalize size
        const img = new Image();
        img.onload = async () => {
          // Normalize resolution
          canvas.width = 1184;
          canvas.height = 864;
          // Calculate scale to cover
          const scale = Math.max(canvas.width / img.width, canvas.height / img.height);
          const x = (canvas.width / 2) - (img.width / 2) * scale;
          const y = (canvas.height / 2) - (img.height / 2) * scale;
          
          ctx.fillStyle = "#000";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, x, y, img.width * scale, img.height * scale);
          
          const finalDataUrl = canvas.toDataURL("image/jpeg", 0.92);

          // Treat like a captured photo
          freezeImg.src = finalDataUrl;
          showFreeze();
          setControlsForVerifying();
          setMessage("Verifying uploaded image...", "muted");

          try {
            // Optional: run detection to see if face is visible
            let conf = 0.85;
            try {
              const data = await detectOnce(canvas);
              conf = typeof data.conf === "number" ? data.conf : (typeof data.confidence === "number" ? data.confidence : 0.85);
              
              if (data && data.visible === false) {
                 hideFreeze();
                 setControlsForLive();
                 setMessage("No face or smile detected in the uploaded photo. Please try another.", "error");
                 if (!running && video && video.srcObject) {
                   running = true;
                   detectLoop();
                 }
                 return;
              }
            } catch (detErr) {
              console.warn("Detect API notice during upload (proceeding with photo):", detErr);
            }

            setMessage("Verified ✅ Upload successful.", "ok");
            capturedDataUrl = finalDataUrl;
            lastConf = conf;

            const saved = await saveCapture(capturedDataUrl, lastConf);
            if (saved && saved.ok) {
              captureNonce = saved.nonce || null;
            } else {
              hideFreeze();
              setControlsForLive();
              setMessage(saved?.error || "Server rejected the image.", "error");
              if (!running && video && video.srcObject) {
                running = true;
                detectLoop();
              }
              return;
            }

            running = false;
            stopCamera();
            setControlsForCaptured();
          } catch(err) {
             console.error("Upload error:", err);
             hideFreeze();
             setControlsForLive();
             setMessage("Error verifying photo. Please try again.", "error");
             if (!running && video && video.srcObject) {
               running = true;
               detectLoop();
             }
          }
        };
        img.src = rawDataUrl;
      };
      reader.readAsDataURL(file);
      e.target.value = "";
    });
  }

  // Direct upload triggers from landing page
  const heroUploadBtn = document.getElementById("heroUploadBtn");
  const bottomUploadBtn = document.getElementById("bottomUploadBtn");

  function triggerDirectPhotoUpload() {
    const smileModalEl = document.getElementById("smileModal");
    if (smileModalEl) {
      const modal = bootstrap.Modal.getInstance(smileModalEl) || new bootstrap.Modal(smileModalEl);
      modal.show();
      setTimeout(() => {
        if (uploadInput) {
          uploadInput.value = "";
          uploadInput.click();
        }
      }, 450);
    }
  }

  heroUploadBtn?.addEventListener("click", triggerDirectPhotoUpload);
  bottomUploadBtn?.addEventListener("click", triggerDirectPhotoUpload);

  recaptureBtn.addEventListener("click", async () => {
    showError("");
    resetResult();
    setMessage("");

    capturedDataUrl = null;
    lastConf = 0;
    captureNonce = null;
    generationPromise = null;
    generationResult = null;

    hideFreeze();
    setControlsForLive();

    try {
      await startCamera();
      setMessage("Camera restarted. Smile to enable Capture.", "muted");
      setControlsForLive();
      detectLoop();
    } catch (e) {
      console.error(e);
      setMessage("Camera access failed: " + e.message, "error");
      showError("Allow camera access in browser, or upload your photo below.");
      const cameraDeniedOverlay = document.getElementById("cameraDeniedOverlay");
      if (cameraDeniedOverlay) cameraDeniedOverlay.classList.remove("d-none");
      if (uploadBtn) uploadBtn.classList.remove("hidden", "d-none");
    }
  });

  switchCameraBtn?.addEventListener("click", async () => {
    if (isCapturing || !running) return;

    setMessage("Switching camera...", "muted");

    currentFacingMode = currentFacingMode === "user" ? "environment" : "user";

    try {
      if (videoDevices && videoDevices.length > 1) {
        currentDeviceIndex = (currentDeviceIndex + 1) % videoDevices.length;
        const nextDevice = videoDevices[currentDeviceIndex];
        await startCamera(nextDevice.deviceId);
      } else {
        await startCamera();
      }
      setMessage("Camera switched.", "muted");
      if (!running) detectLoop();
    } catch (e) {
      console.error("Camera switch error:", e);
      try {
        await startCamera();
      } catch (err) {
        setMessage("Failed to switch camera: " + (e.message || "Unknown error"), "error");
        const cameraDeniedOverlay = document.getElementById("cameraDeniedOverlay");
        if (cameraDeniedOverlay) cameraDeniedOverlay.classList.remove("d-none");
      }
    }
  });

  confirmBtn.addEventListener("click", async () => {
    showError("");

    if (!capturedDataUrl) {
      setMessage("Please capture or upload an image first.", "error");
      return;
    }

    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Designing Your Smile...';
    setMessage("Designing your personalized smile preview…", "muted");

    try {
      const smileModalEl = document.getElementById("smileModal");
      const openLoader = () => {
        cleanupModalBackdrops();
        showPreviewLoader();
      };

      if (smileModalEl && smileModalEl.classList.contains("show")) {
        let transitioned = false;
        const onHidden = () => {
          if (transitioned) return;
          transitioned = true;
          smileModalEl.removeEventListener("hidden.bs.modal", onHidden);
          setTimeout(() => {
            openLoader();
          }, 40);
        };
        smileModalEl.addEventListener("hidden.bs.modal", onHidden, { once: true });
        const smileModal =
          bootstrap.Modal.getInstance(smileModalEl) ||
          bootstrap.Modal.getOrCreateInstance(smileModalEl);
        smileModal.hide();
        setTimeout(onHidden, 350);
      } else {
        openLoader();
      }
    } catch (e) {
      console.warn("Modal transition note:", e);
      cleanupModalBackdrops();
      showPreviewLoader();
    }


    if (!generationPromise) {
      generationPromise = (async () => {
        try {
          const result = await callGemini(capturedDataUrl);

          if (!result || !result.ok) {
            generationResult = {
              ok: false,
              error: result?.error || "Smile generation failed",
              done: true,
            };
            tryOpenPreviewInline();
            return generationResult;
          }

          generationResult = {
            ok: true,
            beforeUrl: result.beforeUrl,
            afterUrl: result.afterUrl,
            done: true,
          };

          if (resultWrap && resultStatus) {
            resultWrap.classList.remove("hidden");
            resultStatus.textContent = "Smile generated ✅";
          }

          tryOpenPreviewInline();
          return generationResult;
        } catch (e) {
          console.error("Gemini generation error:", e);
          generationResult = { ok: false, error: e.message || String(e), done: true };
          tryOpenPreviewInline();
          return generationResult;
        }
      })();
    } else {
      generationPromise.then(() => {
        tryOpenPreviewInline();
      });
    }

    confirmBtn.disabled = false;
  });

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  const csrftoken = getCookie("csrftoken");

  async function triggerWhatsappWebhook() {
    // Disabled by user request: Do not send generated smiles or data to WhatsApp or external webhooks
    return Promise.resolve({ ok: true, paused: true });
  }

  // ✅ UPDATED: prevents double call with whatsappInFlight
  async function tryTriggerWhatsapp() {
    // Disabled by user request: Do not send generated smiles or data to WhatsApp or external webhooks
    return;
  }


  if (leadForm) {
    leadForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      if (leadFormMsg) {
        leadFormMsg.textContent = "";
        leadFormMsg.style.color = "";
      }

      if (leadSubmitBtn) leadSubmitBtn.disabled = true;

      const payload = {
        name: leadName ? leadName.value.trim() : "",
        phone: leadPhone ? leadPhone.value.trim() : "",
        city: leadCity ? leadCity.value.trim() : "",
        email: leadEmail ? leadEmail.value.trim() : "",
        nonce: captureNonce,
      };

      try {
        const res = await fetch("/virtual-smile-try-on/api/smile-lead/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken || "",
          },
          body: JSON.stringify(payload),
        });

        let data = {};
        try {
          data = await res.json();
        } catch (jsonErr) {
          data = { ok: false, error: `Server response error (${res.status})` };
        }

        if (!res.ok || !data.ok) {
          leadFormMsg.style.color = "red";
          leadFormMsg.textContent = data?.error || "Form error. Please check fields.";
          return;
        }

        leadSubmitted = true;
        leadId = data.id || null;
        previewOpened = false;

        function showLeadLoader(text = "Your smile generation is in process…") {
          if (!leadFormMsg) return;
          leadFormMsg.style.color = "white";
          leadFormMsg.innerHTML = `
              <div class="d-flex align-items-center justify-content-center gap-2">
                <span class="spinner-border spinner-border-sm"></span>
                <span>${text}</span>
              </div>`;
        }

        showLeadLoader();

        tryOpenPreviewInline();
        tryTriggerWhatsapp(); // ✅ safe now
      } catch (err) {
        console.error("Lead submit error:", err);
        leadFormMsg.style.color = "red";
        leadFormMsg.textContent = err.message || "Network error. Please try again.";
      } finally {
        if (leadSubmitBtn) leadSubmitBtn.disabled = false;
      }
    });
  }

  const smileModalEl = document.getElementById("smileModal");

  if (smileModalEl) {
    smileModalEl.addEventListener("shown.bs.modal", async () => {
      currentFacingMode = "user";
      generationPromise = null;
      generationResult = null;
      capturedDataUrl = null;
      leadSubmitted = false;
      previewOpened = false;
      leadId = null;

      // ✅ reset WhatsApp flags for new session
      whatsappTriggered = false;
      whatsappInFlight = false;

      // ✅ reset detect state for new session
      detectFailCount = 0;
      detectOfflineMode = false;
      lastConf = 0;
      lastVisible = false;
      lastDetectAt = 0;

      const pBefore = document.getElementById("previewBeforeImg");
      const pAfter = document.getElementById("previewAfterImg");
      if (pBefore) pBefore.src = "";
      if (pAfter) pAfter.src = "";

      resetResult();
      hideFreeze();

      try {
        setControlsForLive();
        await startCamera();
        if (!running) detectLoop();
        setMessage(
          "Camera started. Smile and the Capture button will enable automatically.",
          "muted"
        );
      } catch (e) {
        console.error(e);
        setMessage("Camera access failed: " + e.message, "error");
        showError("Allow camera access in browser, or upload your photo below.");
        const cameraDeniedOverlay = document.getElementById("cameraDeniedOverlay");
        if (cameraDeniedOverlay) cameraDeniedOverlay.classList.remove("d-none");
        if (uploadBtn) uploadBtn.classList.remove("hidden", "d-none");
      }
    });

    smileModalEl.addEventListener("hidden.bs.modal", () => {
      currentFacingMode = "user";
      running = false;
      stopCamera();
      hideFreeze();
      // Keep generationPromise and capturedDataUrl alive for the contact and preview modals!
    });

    const contactModalEl = document.getElementById("contactModal");
    contactModalEl?.addEventListener("hidden.bs.modal", () => {
      // If generation is already completed and user closed contact modal, open preview
      if (!previewOpened && generationResult && generationResult.done === true && generationResult.ok) {
        tryOpenPreviewInline();
      }
    });

    const previewModalEl = document.getElementById("PreviewModal");
    if (previewModalEl) {
      previewModalEl.addEventListener("hidden.bs.modal", () => {
        previewOpened = false;
        generationPromise = null;
        generationResult = null;
        capturedDataUrl = null;
        setControlsForLive();
        hideFreeze();
        resetResult();

        const previewLoader = document.getElementById("previewLoader");
        const previewContent = document.getElementById("previewContent");
        const previewError = document.getElementById("previewError");
        if (previewLoader) {
          previewLoader.classList.add("d-none");
          previewLoader.style.display = "none";
        }
        if (previewContent) {
          previewContent.classList.add("d-none");
          previewContent.style.display = "none";
        }
        if (previewError) previewError.classList.add("d-none");

        cleanupModalBackdrops();
      });
    }
  }
})();