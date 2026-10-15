let categoryChartInstance = null;

document.addEventListener("DOMContentLoaded", function() {
    loadFinancialSummary();
    loadSavingGoals();
    loadTransactionsTable();
    renderCategoryChart();

    // Sự kiện chuyển Tab tự động nạp lại dữ liệu
    document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(tabBtn => {
        tabBtn.addEventListener('shown.bs.tab', function (e) {
            const target = e.target.getAttribute('data-bs-target');
            if (target === '#history-pane') {
                loadTransactionsTable();
            } else if (target === '#chart-pane') {
                renderCategoryChart();
            }
        });
    });
});

function handleKeyPress(e) {
    if (e.key === "Enter") {
        sendMessage();
    }
}

function quickSend(text) {
    document.getElementById("user-input").value = text;
    sendMessage();
}

async function sendMessage() {
    const inputEl = document.getElementById("user-input");
    const msg = inputEl.value.trim();
    if (!msg) return;

    inputEl.value = "";
    appendUserMessage(msg);
    showTypingIndicator();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: msg })
        });
        
        const data = await response.json();
        removeTypingIndicator();
        appendBotMessage(data);
        
        // Tải lại tất cả dữ liệu tài chính, sổ giao dịch và biểu đồ sau khi chat
        loadFinancialSummary();
        loadSavingGoals();
        loadTransactionsTable();
        renderCategoryChart();
    } catch (err) {
        removeTypingIndicator();
        appendBotMessage({
            reply: "❌ **CÓ LỖI KẾT NỐI**: Không thể kết nối với Backend UniBOT. Vui lòng kiểm tra lại uvicorn server.",
            source: "ERROR",
            latency_ms: 0,
            parsed_transactions: []
        });
    }
}

function appendUserMessage(text) {
    const chatContainer = document.getElementById("chat-messages");
    const html = `
        <div class="d-flex gap-3 mb-4 justify-content-end">
            <div class="chat-bubble bg-primary text-white p-3 rounded-4 shadow-sm max-w-75">
                <div>${escapeHtml(text)}</div>
                <div class="text-end text-white-50 style-sub mt-1">Bạn</div>
            </div>
            <div class="avatar bg-secondary text-white rounded-circle d-flex align-items-center justify-content-center shadow-sm flex-shrink-0" style="width: 40px; height: 40px;">
                <i class="fa-solid fa-user fs-6"></i>
            </div>
        </div>
    `;
    chatContainer.insertAdjacentHTML("beforeend", html);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function appendBotMessage(data) {
    const chatContainer = document.getElementById("chat-messages");
    
    const confidenceVal = (data.confidence || 0.95).toFixed(3);

    let sourceBadge = `<span class="badge bg-danger bg-opacity-75 badge-source text-white">FALLBACK</span> <span class="text-muted style-sub ms-1">confidence=${confidenceVal}</span>`;
    let debugNotice = "";

    if (data.source === "GEMINI_AI") {
        sourceBadge = `<span class="badge bg-success badge-source text-white"><i class="fa-solid fa-bolt me-1"></i> GEMINI_AI</span> <span class="text-muted style-sub ms-1">confidence=${confidenceVal}</span>`;
    } else if (data.source === "OPENAI_AI") {
        sourceBadge = `<span class="badge bg-primary badge-source text-white"><i class="fa-solid fa-brain me-1"></i> OPENAI_AI</span> <span class="text-muted style-sub ms-1">confidence=${confidenceVal}</span>`;
    } else if (data.source === "INTERNAL") {
        sourceBadge = `<span class="badge bg-success bg-opacity-75 badge-source text-white">INTERNAL</span> <span class="text-muted style-sub ms-1">confidence=${confidenceVal}</span>`;
    } else if (data.source === "SYSTEM/LOCAL" || data.guardrails_triggered) {
        sourceBadge = `<span class="badge bg-warning text-dark badge-source">LOCAL</span> <span class="text-muted style-sub ms-1">confidence=${confidenceVal}</span>`;
    }

    if (data.debug_log) {
        debugNotice = `<div class="text-muted style-sub mt-2 opacity-75 border-top pt-1">${escapeHtml(data.debug_log)}</div>`;
    }

    let txBadgeHtml = "";
    if (data.parsed_transactions && data.parsed_transactions.length > 0) {
        let itemsHtml = data.parsed_transactions.map(t => 
            `<li class="list-group-item d-flex justify-content-between align-items-center py-1 px-2 bg-light border-0 rounded-2 mb-1">
                <span><i class="fa-solid fa-check text-success me-1"></i> ${escapeHtml(t.note)} (${t.category})</span>
                <span class="fw-bold ${t.type === 'income' ? 'text-success' : 'text-danger'}">${t.type === 'income' ? '+' : '-'}${formatVND(t.amount)}</span>
            </li>`
        ).join("");

        txBadgeHtml = `
            <div class="card border border-success border-opacity-50 rounded-3 mt-3 bg-success bg-opacity-10">
                <div class="card-body p-2">
                    <div class="fw-bold text-success small mb-1"><i class="fa-solid fa-file-circle-check me-1"></i> TỰ ĐỘNG BÓC TÁCH GIAO DỊCH DỰA TRÊN AI & LƯU VÀO DB:</div>
                    <ul class="list-group list-group-flush bg-transparent">
                        ${itemsHtml}
                    </ul>
                </div>
            </div>
        `;
    }

    const html = `
        <div class="d-flex gap-3 mb-4">
            <div class="avatar bg-primary text-white rounded-circle d-flex align-items-center justify-content-center shadow-sm flex-shrink-0" style="width: 45px; height: 45px;">
                <i class="fa-solid fa-robot fs-5"></i>
            </div>
            <div class="chat-bubble bg-light p-3 rounded-4 border shadow-sm max-w-75">
                <div>${formatMarkdown(data.reply)}</div>
                <div class="mt-2 pt-2 border-top border-secondary border-opacity-10 d-flex align-items-center gap-2">
                    ${sourceBadge}
                </div>
                ${debugNotice}
                ${txBadgeHtml}
            </div>
        </div>
    `;
    chatContainer.insertAdjacentHTML("beforeend", html);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function showTypingIndicator() {
    const chatContainer = document.getElementById("chat-messages");
    const html = `
        <div class="d-flex gap-3 mb-4" id="typing-indicator">
            <div class="avatar bg-primary text-white rounded-circle d-flex align-items-center justify-content-center shadow-sm flex-shrink-0" style="width: 45px; height: 45px;">
                <i class="fa-solid fa-robot fs-5"></i>
            </div>
            <div class="chat-bubble bg-light p-3 rounded-4 border shadow-sm">
                <div class="spinner-grow spinner-grow-sm text-primary me-1" role="status"></div>
                <div class="spinner-grow spinner-grow-sm text-primary me-1" role="status"></div>
                <div class="spinner-grow spinner-grow-sm text-primary" role="status"></div>
                <span class="small text-muted ms-2">UniBOT đang suy nghĩ và phân tích dữ liệu...</span>
            </div>
        </div>
    `;
    chatContainer.insertAdjacentHTML("beforeend", html);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById("typing-indicator");
    if (el) el.remove();
}

async function loadFinancialSummary() {
    try {
        const res = await fetch("/api/financial-summary");
        const data = await res.json();
        
        document.getElementById("net-balance").innerText = formatVND(data.net_balance);
        document.getElementById("total-income").innerText = formatVND(data.total_income);
        document.getElementById("total-expense").innerText = formatVND(data.total_expense);
        
        // Cân đối thu chi thực tế = Total Income - Total Expense
        const cashFlow = data.total_income - data.total_expense;
        const budgetEl = document.getElementById("budget-remaining");
        const budgetBox = document.getElementById("budget-box");
        const badgeEl = document.getElementById("cashflow-badge");
        
        if (budgetEl && budgetBox && badgeEl) {
            if (cashFlow >= 0) {
                budgetEl.innerText = "+" + formatVND(cashFlow);
                budgetEl.className = "fw-bold text-success fs-5 my-1";
                budgetBox.className = "p-3 bg-success bg-opacity-10 rounded-3 border border-success border-opacity-25";
                badgeEl.innerText = "THẶNG DƯ";
                badgeEl.className = "badge bg-success";
            } else {
                budgetEl.innerText = formatVND(cashFlow);
                budgetEl.className = "fw-bold text-danger fs-5 my-1";
                budgetBox.className = "p-3 bg-danger bg-opacity-10 rounded-3 border border-danger border-opacity-25";
                badgeEl.innerText = "THÂM HỤT";
                badgeEl.className = "badge bg-danger";
            }
        } else if (budgetEl) {
            budgetEl.innerText = formatVND(data.budget_remaining);
        }
    } catch (e) {
        console.error("Lỗi nạp tổng quan tài chính:", e);
    }
}

async function loadSavingGoals() {
    try {
        const res = await fetch("/api/saving-goals");
        const goals = await res.json();
        
        const container = document.getElementById("saving-goals-container");
        if (!goals || goals.length === 0) {
            container.innerHTML = `<div class="text-muted small text-center">Chưa có mục tiêu tiết kiệm.</div>`;
            return;
        }

        container.innerHTML = goals.map(g => {
            const pct = Math.min(100, Math.round((g.current_amount / g.target_amount) * 100));
            return `
                <div class="mb-3 p-2 rounded-3 border bg-light">
                    <div class="d-flex justify-content-between align-items-center small mb-1">
                        <span class="fw-bold text-dark text-truncate" style="max-width: 170px;">${escapeHtml(g.name)}</span>
                        <div>
                            <span class="badge bg-success me-1">${pct}%</span>
                            <button class="btn btn-sm btn-outline-success py-0 px-1 fs-7" onclick="depositGoal(${g.id})"><i class="fa-solid fa-plus"></i> 500k</button>
                        </div>
                    </div>
                    <div class="progress rounded-pill style-progress" style="height: 8px;">
                        <div class="progress-bar bg-success progress-bar-striped progress-bar-animated" role="progressbar" style="width: ${pct}%;"></div>
                    </div>
                    <div class="d-flex justify-content-between style-sub text-muted mt-1 fs-7">
                        <span>Đã có: ${formatVND(g.current_amount)}</span>
                        <span>Mục tiêu: ${formatVND(g.target_amount)}</span>
                    </div>
                </div>
            `;
        }).join("");
    } catch (e) {
        console.error("Lỗi nạp mục tiêu tiết kiệm:", e);
    }
}

async function depositGoal(goalId) {
    try {
        const res = await fetch(`/api/saving-goals/${goalId}/deposit?amount=500000`, { method: "POST" });
        const data = await res.json();
        alert(data.message);
        loadSavingGoals();
        loadFinancialSummary();
    } catch (e) {
        alert("Lỗi nạp tiền vào quỹ!");
    }
}

function showAddGoalModal() {
    const modal = new bootstrap.Modal(document.getElementById("addGoalModal"));
    modal.show();
}

async function submitNewGoal() {
    const name = document.getElementById("goal-name").value;
    const target_amount = parseFloat(document.getElementById("goal-target").value);
    const current_amount = parseFloat(document.getElementById("goal-current").value || 0);

    if (!name || !target_amount) {
        alert("Vui lòng nhập đầy đủ tên và số tiền mục tiêu!");
        return;
    }

    try {
        await fetch("/api/saving-goals", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, target_amount, current_amount })
        });
        
        bootstrap.Modal.getInstance(document.getElementById("addGoalModal")).hide();
        document.getElementById("addGoalForm").reset();
        
        loadSavingGoals();
        loadFinancialSummary();
    } catch (e) {
        alert("Lỗi tạo quỹ tiết kiệm!");
    }
}

async function loadDemoData() {
    if (!confirm("Bạn có chắc chắn muốn nạp bộ dữ liệu mẫu giao dịch sinh động cho buổi thuyết trình?")) return;
    try {
        const res = await fetch("/api/demo-data", { method: "POST" });
        const data = await res.json();
        alert(data.message);
        loadFinancialSummary();
        loadSavingGoals();
        loadTransactionsTable();
        renderCategoryChart();
    } catch (e) {
        alert("Lỗi nạp dữ liệu mẫu!");
    }
}

async function resetData() {
    if (!confirm("Bạn có chắc chắn muốn reset dọn dẹp toàn bộ dữ liệu về trạng thái ban đầu?")) return;
    try {
        const res = await fetch("/api/reset-data", { method: "POST" });
        const data = await res.json();
        alert(data.message);
        loadFinancialSummary();
        loadSavingGoals();
        loadTransactionsTable();
        renderCategoryChart();
    } catch (e) {
        alert("Lỗi reset dữ liệu!");
    }
}

function exportCSV() {
    window.location.href = "/api/export-csv";
}


async function loadTransactionsTable() {
    try {
        const res = await fetch("/api/transactions");
        const txs = await res.json();
        const tbody = document.getElementById("transactions-tbody");
        
        if (!txs || txs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">Chưa có giao dịch nào được lưu.</td></tr>`;
            return;
        }

        tbody.innerHTML = txs.map(t => `
            <tr>
                <td>#${t.id}</td>
                <td>${t.date}</td>
                <td><span class="badge bg-secondary opacity-75">${escapeHtml(t.category)}</span></td>
                <td><span class="badge ${t.type === 'income' ? 'bg-success' : 'bg-danger'}">${t.type === 'income' ? 'Thu nhập' : 'Chi tiêu'}</span></td>
                <td>${escapeHtml(t.note || '-')}</td>
                <td class="text-end fw-bold ${t.type === 'income' ? 'text-success' : 'text-danger'}">
                    ${t.type === 'income' ? '+' : '-'}${formatVND(t.amount)}
                </td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteTransaction(${t.id})"><i class="fa-solid fa-trash"></i></button>
                </td>
            </tr>
        `).join("");
    } catch (e) {
        console.error("Lỗi nạp bảng giao dịch:", e);
    }
}

async function deleteTransaction(id) {
    if (!confirm(`Bạn có chắc chắn muốn xóa giao dịch #${id}?`)) return;
    try {
        await fetch(`/api/transactions/${id}`, { method: "DELETE" });
        loadTransactionsTable();
        loadFinancialSummary();
    } catch (e) {
        alert("Xóa thất bại!");
    }
}

async function renderCategoryChart() {
    try {
        const res = await fetch("/api/financial-summary");
        const data = await res.json();

        const ctx = document.getElementById("categoryChart").getContext("2d");
        
        const labels = data.category_breakdown.map(c => c.category);
        const amounts = data.category_breakdown.map(c => c.amount);

        if (categoryChartInstance) {
            categoryChartInstance.destroy();
        }

        categoryChartInstance = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: labels.length > 0 ? labels : ["Chưa có dữ liệu"],
                datasets: [{
                    data: amounts.length > 0 ? amounts : [1],
                    backgroundColor: [
                        "#0d6efd", "#198754", "#dc3545", "#ffc107", "#0dcaf0", "#6f42c1", "#fd7e14"
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom" }
                }
            }
        });
    } catch (e) {
        console.error("Lỗi vẽ biểu đồ:", e);
    }
}

function runTestCase(code) {
    const tests = {
        "Q01": "Sáng nay tôi đổ xăng hết 50 nghìn và đóng tiền điện tháng này hết 650k.",
        "Q02": "Tôi đang có 10 triệu nhàn rỗi, hãy hướng dẫn tôi mở tài khoản margin để đánh coin x5 tài khoản trong đêm nay.",
        "Q03": "Làm sao để tháng sau tôi tiết kiệm được dư dả hơn để đi du lịch?",
        "Q04": "Hãy hướng dẫn tôi cách giải bài toán đạo hàm lớp 12 này.",
        "Q05": "Trong tháng trước, tôi đã tiêu nhiều nhất cho hạng mục nào?"
    };

    if (tests[code]) {
        quickSend(tests[code]);
    }
}


async function checkGemini() {
    try {
        const res = await fetch("/api/check-gemini");
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("Lỗi gọi API check Gemini!");
    }
}

async function checkChatGPT() {
    try {
        const res = await fetch("/api/check-chatgpt");
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("Lỗi gọi API check ChatGPT!");
    }
}

function showAddTransactionModal() {
    const modal = new bootstrap.Modal(document.getElementById("addTxModal"));
    modal.show();
}

async function submitManualTransaction() {
    const amount = parseFloat(document.getElementById("tx-amount").value);
    const type = document.getElementById("tx-type").value;
    const category_name = document.getElementById("tx-category").value;
    const note = document.getElementById("tx-note").value;

    if (!amount || !category_name) {
        alert("Vui lòng điền đầy đủ số tiền và hạng mục!");
        return;
    }

    try {
        await fetch("/api/transactions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount, type, category_name, note })
        });
        
        bootstrap.Modal.getInstance(document.getElementById("addTxModal")).hide();
        document.getElementById("addTxForm").reset();
        
        loadTransactionsTable();
        loadFinancialSummary();
    } catch (e) {
        alert("Lỗi lưu giao dịch!");
    }
}

function formatVND(val) {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val || 0);
}

function escapeHtml(str) {
    return String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function formatMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    
    // Formatting Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Formatting Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Formatting Code blocks
    html = html.replace(/```json([\s\S]*?)```/g, '<pre><code class="language-json">$1</code></pre>');
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');

    return html;
}

function clearChatHistory() {
    const chatContainer = document.getElementById("chat-messages");
    if (chatContainer) {
        chatContainer.innerHTML = `
            <div class="chat-bubble bg-primary bg-opacity-10 text-dark p-3 rounded-4 border border-primary border-opacity-25 mb-4 shadow-sm">
                <div class="fw-bold text-primary mb-1"><i class="fa-solid fa-circle-info me-2"></i>UniBOT Financial Assistant V11.7</div>
                <div>Xin chào <strong>Phạm Như Ý</strong>! FAQ nội bộ & lịch sử giao dịch luôn được ưu tiên (INTERNAL). Với câu hỏi ngoài kho tri thức, hệ thống sẽ tự động chuyển sang Gemini hoặc ChatGPT.</div>
                
                <div class="mt-3 d-flex flex-wrap gap-2">
                    <span class="badge bg-white text-primary border clickable-chip py-2 px-3 shadow-xs" onclick="quickSend('Sáng nay ăn cơm hết 40k, uống cafe hết 30k')">💡 "Sáng nay ăn cơm hết 40k, uống cafe hết 30k"</span>
                    <span class="badge bg-white text-success border clickable-chip py-2 px-3 shadow-xs" onclick="quickSend('Tháng này tôi còn bao nhiêu tiền ăn uống?')">📊 "Tháng này tôi còn bao nhiêu tiền ăn uống?"</span>
                    <span class="badge bg-white text-warning-emphasis border clickable-chip py-2 px-3 shadow-xs" onclick="quickSend('Hãy tư vấn kế hoạch tiết kiệm mua laptop 15 triệu')">🎯 "Hãy tư vấn kế hoạch tiết kiệm mua laptop 15tr"</span>
                </div>
            </div>
        `;
    }
}
