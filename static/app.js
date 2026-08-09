/* Antigravity Financial Analytics Frontend Script (Pure Direct Agent Engine) */

window.setQuery = function(text) {
  const queryInput = document.getElementById("queryInput");
  if (queryInput) {
    queryInput.value = text;
    queryInput.focus();
  }
};

document.addEventListener("DOMContentLoaded", () => {
  const queryInput = document.getElementById("queryInput");
  const btnRun = document.getElementById("btnRun");

  const statusTimeline = document.getElementById("statusTimeline");
  const progressBar = document.getElementById("progressBar");
  const progressPercent = document.getElementById("progressPercent");

  const reportPlaceholder = document.getElementById("reportPlaceholder");
  const reportViewer = document.getElementById("reportViewer");
  const reportActions = document.getElementById("reportActions");
  const btnCopy = document.getElementById("btnCopy");

  const menuAuditLog = document.getElementById("menuAuditLog");
  const auditModal = document.getElementById("auditModal");
  const btnCloseModal = document.getElementById("btnCloseModal");
  const auditList = document.getElementById("auditList");

  // 분석 실행 이벤트 - 백엔드 파이썬 Multi-Agent 직접 호출
  btnRun.addEventListener("click", async () => {
    const query = queryInput.value.trim();
    if (!query) {
      alert("분석할 기업명이나 금융질의를 입력하세요.");
      queryInput.focus();
      return;
    }

    // UI 상태 업데이트
    btnRun.disabled = true;
    btnRun.querySelector("span").textContent = "Multi-Agent 자율 분석 진행 중...";
    statusTimeline.style.display = "flex";
    reportPlaceholder.style.display = "none";
    reportViewer.style.display = "none";
    reportActions.style.display = "none";

    resetProcessSteps();
    startProcessProgress();

    try {
      // 파이썬 FastAPI 백엔드 (/api/analyze) 직접 호출
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: "서버 응답 오류" }));
        throw new Error(errData.detail || "백엔드 API 요청 처리 중 오류가 발생했습니다.");
      }

      const data = await response.json();
      const reportText = data.report || data.final_report || "보고서 내용을 가져올 수 없습니다.";

      finishProcessProgress();
      reportViewer.innerHTML = renderMarkdown(reportText);
      reportViewer.style.display = "block";
      reportActions.style.display = "block";

    } catch (err) {
      reportPlaceholder.style.display = "flex";
      reportPlaceholder.innerHTML = `
        <div style="text-align: center; padding: 24px; color: #ef4444; max-width: 480px; margin: 0 auto;">
          <h3 style="font-size: 16px; margin-bottom: 8px;">⚠️ 파이썬 백엔드 에이전트 연결 필요</h3>
          <p style="font-size: 13px; color: #a1a1aa; line-height: 1.6; margin-bottom: 12px;">
            진짜 파이썬 Multi-Agent 백엔드 서버(<code>app.py</code>) 연결이 필요합니다.<br>
            터미널에서 <code>python app.py</code> 실행 후 <strong>http://localhost:8000</strong>으로 접속하시면 실시간 수집 및 자율 에이전트 분석이 100% 가동됩니다.
          </p>
        </div>
      `;
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
      if (res.ok) {
        const data = await res.json();
        renderAuditLogs(data.history || []);
      } else {
        auditList.innerHTML = "<p style='color:#dc2626;'>감사 로그 조회 실패</p>";
      }
    } catch (err) {
      auditList.innerHTML = `<p style="color: #dc2626;">감사 로그 연결 실패: ${err.message}</p>`;
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
    return text
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '## $1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1 ↗</a>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }
});
