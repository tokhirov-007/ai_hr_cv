console.log("AI HR Admin v6.1 Loaded");
let adminLang = 'ru';

const adminTranslations = {
    ru: {
        title: "Кандидаты",
        subtitle: "Управление потоком найма",
        th_candidate: "Кандидат",
        th_phone: "Телефон",
        th_email: "Email",
        th_lang: "Язык",
        th_status: "Статус",
        th_score: "Баллы",
        th_actions: "Действия",
        view_cv: "Открыть CV",
        status_invited: "Приглашен",
        status_rejected: "Отклонен",
        status_review: "На проверке",
        status_pending: "Ожидание",
        update_success: "Статус успешно обновлен!"
    },
    uz: {
        title: "Nomzodlar",
        subtitle: "Yollash oqimini boshqarish",
        th_candidate: "Nomzod",
        th_phone: "Telefon",
        th_email: "Email",
        th_lang: "Til",
        th_status: "Holat",
        th_score: "Ball",
        th_actions: "Harakatlar",
        view_cv: "CV-ni ochish",
        status_invited: "Taklif etildi",
        status_rejected: "Rad etildi",
        status_review: "Ko'rib chiqilmoqda",
        status_pending: "Kutilmoqda",
        update_success: "Holat muvaffaqiyatli yangilandi!"
    }
};

function switchAdminLang(lang) {
    adminLang = lang;
    document.querySelectorAll('.lang-switcher button').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`btn-admin-${lang}`).classList.add('active');
    updateAdminUI();
}

function updateAdminUI() {
    const t = adminTranslations[adminLang];
    document.getElementById('admin-title').innerText = t.title;
    document.getElementById('admin-subtitle').innerText = t.subtitle;
    document.getElementById('th-candidate').innerText = t.th_candidate;
    document.getElementById('th-phone').innerText = t.th_phone;
    document.getElementById('th-email').innerText = t.th_email;
    document.getElementById('th-lang').innerText = t.th_lang;
    document.getElementById('th-status').innerText = t.th_status;
    document.getElementById('th-score').innerText = t.th_score;
    document.getElementById('th-actions').innerText = t.th_actions;

    loadCandidates();
}

let allCandidates = [];

async function loadCandidates() {
    try {
        const response = await fetch('/admin/sessions');
        const data = await response.json();
        allCandidates = data; // Store for modal access
        renderCandidates(data);
    } catch (error) {
        console.error("Failed to load candidates:", error);
    }
}

function renderCandidates(candidates) {
    const body = document.getElementById('candidates-body');
    const t = adminTranslations[adminLang];
    body.innerHTML = '';

    candidates.forEach(c => {
        const tr = document.createElement('tr');

        let statusClass = 'status-review';
        let statusText = t.status_review;

        if (c.status_public === 'INVITED') {
            statusClass = 'status-invited';
            statusText = t.status_invited;
        } else if (c.status_public === 'REJECTED') {
            statusClass = 'status-rejected';
            statusText = t.status_rejected;
        }

        const cvLink = c.cv_path ? `<a href="/uploads/${c.cv_path.replace(/\\/g, '/').split('/').pop()}" target="_blank" class="admin-btn btn-cv">📄 CV</a>` : 'No CV';

        tr.innerHTML = `
            <td><strong>${c.candidate_name}</strong></td>
            <td>${c.candidate_phone}</td>
            <td>${c.candidate_email}</td>
            <td>${(c.candidate_lang || 'en').toUpperCase()}</td>
            <td>${new Date(c.start_time).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td class="score-cell">${c.score !== null ? c.score : '-'}</td>
            <td>
                <div style="display:flex; gap:8px; align-items: center;">
                    ${cvLink}
                    <button onclick="showQA('${c.session_id}')" class="admin-btn btn-qa" title="View Q&A">💬 Q&A</button>
                    <button onclick="updateStatus('${c.session_id}', 'INVITED')" class="admin-btn btn-invite" title="Invite">✅</button>
                    <button onclick="updateStatus('${c.session_id}', 'REJECTED')" class="admin-btn btn-reject" title="Reject">❌</button>
                </div>
            </td>
        `;
        body.appendChild(tr);
    });
}

function showQA(sessionId) {
    const candidate = allCandidates.find(c => c.session_id === sessionId);
    if (!candidate) return;

    const content = document.getElementById('qa-content');
    content.innerHTML = '';

    if (!candidate.questions || candidate.questions.length === 0) {
        content.innerHTML = '<p style="text-align:center; padding: 20px; opacity: 0.6;">No questions found for this session.</p>';
    } else {
        candidate.questions.forEach((q, idx) => {
            const answer = (candidate.answers && candidate.answers[idx]) ? candidate.answers[idx].answer_text : '<i>No answer provided</i>';
            const qaItem = document.createElement('div');
            qaItem.className = 'qa-item';
            qaItem.innerHTML = `
                <div class="qa-q"><strong>Q${idx + 1}:</strong> ${q.question}</div>
                <div class="qa-a"><strong>A:</strong> ${answer}</div>
            `;
            content.appendChild(qaItem);
        });
    }

    document.getElementById('qa-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('qa-modal').classList.add('hidden');
}

async function updateStatus(sessionId, status) {
    const t = adminTranslations[adminLang];
    try {
        await fetch(`/update-session-status/${sessionId}?internal_status=${status}&public_status=${status}`, {
            method: 'POST'
        });
        alert(t.update_success);
        loadCandidates();
    } catch (error) {
        console.error("Failed to update status:", error);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updateAdminUI();
});
