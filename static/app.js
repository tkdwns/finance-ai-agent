window.setQuery = function(text) {
  const queryInput = document.getElementById("queryInput");
  if (queryInput) {
    queryInput.value = text;
    queryInput.focus();
  }
};

window.saveUserApiKey = function() {
  const input = document.getElementById("userApiKey");
  if (input && input.value.trim()) {
    sessionStorage.setItem("user_api_key", input.value.trim());
    alert("API Key가 브라우저 세션에 저장되었습니다.");
  } else {
    alert("API Key를 입력해주세요.");
  }
};

window.promptOwnerPin = async function() {
  const pin = prompt("소유자 관리자 핀코드를 입력하세요:");
  if (pin && pin.trim()) {
    try {
      const resp = await fetch(`/api/health?pin=${encodeURIComponent(pin.strip ? pin.strip() : pin)}`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.is_owner || data.is_pin_valid) {
          localStorage.setItem("admin_pin_code", pin.trim());
          const apiKeyBanner = document.getElementById("apiKeyBanner");
          if (apiKeyBanner) apiKeyBanner.style.display = "none";
          alert("소유자 인증에 성공했습니다! API 키 입력 바가 자동 숨김 처리됩니다.");
          return;
        }
      }
    } catch (e) {}
    alert("핀코드가 일치하지 않습니다. 다시 확인해주세요.");
  }
};

document.addEventListener("DOMContentLoaded", async () => {
  const queryInput = document.getElementById("queryInput");
  const btnRun = document.getElementById("btnRun");
  const apiKeyBanner = document.getElementById("apiKeyBanner");
  const userApiKeyInput = document.getElementById("userApiKey");

  // URL 파라미터 또는 localStorage에 저장된 핀코드 확인
  const urlParams = new URLSearchParams(window.location.search);
  const savedPin = urlParams.get("pin") || localStorage.getItem("admin_pin_code") || "";

  // 헬스 체크를 통한 소유자(로컬 환경 또는 핀코드 인증) 파악
  try {
    const healthResp = await fetch(`/api/health?pin=${encodeURIComponent(savedPin)}`);
    if (healthResp.ok) {
      const healthData = await healthResp.json();
      if (healthData.is_owner) {
        // 소유자 접속 시 API Key 입력 바 완전 자동 숨김!
        if (apiKeyBanner) apiKeyBanner.style.display = "none";
      } else {
        // 외부 방문자 접속 시 입력 바 표시
        if (apiKeyBanner) apiKeyBanner.style.display = "block";
        const savedKey = sessionStorage.getItem("user_api_key");
        if (savedKey && userApiKeyInput) userApiKeyInput.value = savedKey;
      }
    }
  } catch (e) {
    console.warn("Health check error:", e);
  }

  // 분석 실행 이벤트
  btnRun.addEventListener("click", async () => {
    const query = queryInput.value.trim();
    if (!query) {
      alert("분석할 기업명이나 금융질의를 입력하세요.");
      queryInput.focus();
      return;
    }

    const userKey = sessionStorage.getItem("user_api_key") || (userApiKeyInput ? userApiKeyInput.value.trim() : "");

    // UI 상태 업데이트
    btnRun.disabled = true;
    btnRun.querySelector("span").textContent = "분석 진행 중...";
    statusTimeline.style.display = "flex";
    reportPlaceholder.style.display = "none";
    reportViewer.style.display = "none";
    reportActions.style.display = "none";

    resetProcessSteps();
    startProcessProgress();

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query, api_key: userKey || null }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "서버 요청 처리 중 오류가 발생했습니다.");
      }

      const data = await response.json();
      const reportText = data.report || data.final_report || "보고서 내용을 가져올 수 없습니다.";

      finishProcessProgress();
      reportViewer.innerHTML = renderMarkdown(reportText);
      reportViewer.style.display = "block";
      reportActions.style.display = "block";

    } catch (err) {
      alert(`오류: ${err.message}`);
      reportPlaceholder.style.display = "flex";
      reportPlaceholder.innerHTML = `<p style="color: #dc2626;">분석 중 오류가 발생했습니다: ${err.message}</p>`;
    } finally {
      btnRun.disabled = false;
      btnRun.querySelector("span").textContent = "분석 보고서 생성";
    }
  });

  // 보고서 복사 기능
  btnCopy.addEventListener("click", () => {
    const textToCopy = reportViewer.innerText;
    navigator.clipboard.writeText(textToCopy).then(() => {
      alert("보고서 내용이 클립보드에 복사되었습니다.");
    });
  });

  // 감사 이력 모달
  menuAuditLog.addEventListener("click", (e) => {
    e.preventDefault();
    openAuditModal();
  });

  btnCloseModal.addEventListener("click", () => {
    auditModal.style.display = "none";
  });

  auditModal.addEventListener("click", (e) => {
    if (e.target === auditModal) {
      auditModal.style.display = "none";
    }
  });

  async function openAuditModal() {
    auditModal.style.display = "flex";
    auditList.innerHTML = "<p>감사 이력을 조회 중입니다...</p>";
    try {
      const res = await fetch("/api/history");
      const data = await res.json();
      renderAuditLogs(data.history || []);
    } catch (err) {
      auditList.innerHTML = `<p style="color: #dc2626;">감사 로그 조회의 실패했습니다: ${err.message}</p>`;
    }
  }

  // 프로세스 진행 상태 헬퍼 함수
  let progressTimer = null;

  function resetProcessSteps() {
    const steps = ["researcher", "analyst", "compliance", "writer"];
    steps.forEach(s => {
      const el = document.getElementById(`step-${s}`);
      if (el) el.className = "process-step";
    });
    progressBar.style.width = "0%";
    progressPercent.textContent = "0%";
  }

  function startProcessProgress() {
    const steps = [
      { id: "researcher", pct: 30 },
      { id: "analyst", pct: 65 },
      { id: "compliance", pct: 85 },
      { id: "writer", pct: 95 },
    ];
    let idx = 0;

    if (progressTimer) clearInterval(progressTimer);

    progressTimer = setInterval(() => {
      if (idx < steps.length) {
        if (idx > 0) {
          const prevEl = document.getElementById(`step-${steps[idx - 1].id}`);
          if (prevEl) prevEl.className = "process-step done";
        }
        const currEl = document.getElementById(`step-${steps[idx].id}`);
        if (currEl) currEl.className = "process-step active";

        progressBar.style.width = `${steps[idx].pct}%`;
        progressPercent.textContent = `${steps[idx].pct}%`;
        idx++;
      } else {
        clearInterval(progressTimer);
      }
    }, 1500);
  }

  function finishProcessProgress() {
    if (progressTimer) clearInterval(progressTimer);
    const steps = ["researcher", "analyst", "compliance", "writer"];
    steps.forEach(s => {
      const el = document.getElementById(`step-${s}`);
      if (el) el.className = "process-step done";
    });
    progressBar.style.width = "100%";
    progressPercent.textContent = "100%";
  }

  function renderAuditLogs(logs) {
    if (!logs || logs.length === 0) {
      auditList.innerHTML = "<p>저장된 감사 이력이 없습니다.</p>";
      return;
    }

    auditList.innerHTML = logs.slice().reverse().map(rec => `
      <div class="audit-item">
        <div class="audit-meta">
          <span>[${rec.role}] ${rec.action}</span>
          <span style="font-size: 11px; color: #71717a;">${new Date(rec.timestamp).toLocaleString()}</span>
        </div>
        <div style="color: #3f3f46; font-size: 12px; word-break: break-all;">
          ${JSON.stringify(rec.details)}
        </div>
      </div>
    `).join("");
  }

  function renderMarkdown(text) {
    if (!text) return "";
    if (typeof marked !== "undefined" && typeof marked.parse === "function") {
      return marked.parse(text);
    }
    // 마크다운 파서 폴백
    return text
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1 ↗</a>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }
});
