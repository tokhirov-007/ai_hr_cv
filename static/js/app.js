console.log("AI HR App v6.1 Loaded");
let sessionId = null;
let currentQuestionIndex = 0;
let questions = [];
let timerInterval = null;

const translations = {
    en: {
        loading: "Analyzing your CV...",
        final_title: "Thank You!",
        final_msg: "Your interview is complete. You will receive an email notification soon. Please check your Inbox and Spam folder within 10-15 minutes.",
        btn_start: "Start Interview",
        lbl_upload: "Select CV (PDF/DOCX)",
        answer_ph: "Type your answer here...",
        lbl_name: "Full Name:",
        lbl_phone: "Phone Number:",
        lbl_email: "Email Address:",
        no_file: "File not selected",
        file_chosen: "Uploaded file: "
    },
    ru: {
        loading: "Анализируем ваше CV...",
        final_title: "Спасибо!",
        final_msg: "Интервью успешно завершено. В ближайшее время вам придет уведомление на почту. Пожалуйста, проверьте папку «Входящие» и «Спам» в течение 10-15 минут.",
        btn_start: "Начать интервью",
        lbl_upload: "Выберите CV (PDF/DOCX)",
        answer_ph: "Введите ваш ответ здесь...",
        lbl_name: "ФИО:",
        lbl_phone: "Номер телефона:",
        lbl_email: "Email адрес:",
        no_file: "Файл не выбран",
        file_chosen: "Загружен файл: "
    },
    uz: {
        loading: "CV tahlil qilinmoqda...",
        final_title: "Rahmat!",
        final_msg: "Sizning intervyungiz muvaffaqiyatli yakunlandi. Tez orada elektron pochtangizga xabar keladi. Iltimos, 10-15 daqiqa ichida «Inboks» va «Spam» papkalarini tekshiring.",
        btn_start: "Intervyuni boshlash",
        lbl_upload: "CV-ni tanlang (PDF/DOCX)",
        answer_ph: "Javobingizni bu yerga yozing...",
        lbl_name: "F.I.SH.:",
        lbl_phone: "Telefon raqami:",
        lbl_email: "Email manzili:",
        no_file: "Fayl tanlanmagan",
        file_chosen: "Fayl yuklandi: "
    }
};

function updateUI() {
    const lang = document.getElementById('lang-select').value;
    const t = translations[lang];
    document.getElementById('loading-text').innerText = t.loading;
    document.getElementById('final-title').innerText = t.final_title;
    document.getElementById('final-msg').innerText = t.final_msg;
    document.getElementById('btn-start').innerText = t.btn_start;
    document.getElementById('lbl-upload').innerText = t.lbl_upload;
    document.getElementById('answer-text').placeholder = t.answer_ph;
    document.getElementById('lbl-name').innerText = t.lbl_name;
    document.getElementById('lbl-phone').innerText = t.lbl_phone;
    document.getElementById('lbl-email').innerText = t.lbl_email;

    // Refresh filename display
    const fileInput = document.getElementById('cv-file');
    const display = document.getElementById('file-name-display');
    if (fileInput.files.length > 0) {
        display.innerText = t.file_chosen + fileInput.files[0].name;
    } else {
        display.innerText = t.no_file;
    }
}

function handleFileSelect() {
    const fileInput = document.getElementById('cv-file');
    const display = document.getElementById('file-name-display');
    const lang = document.getElementById('lang-select').value;
    const t = translations[lang];

    if (fileInput.files.length > 0) {
        display.innerText = t.file_chosen + fileInput.files[0].name;
    } else {
        display.innerText = t.no_file;
    }
}

function validateUzPhone(phone) {
    const re = /^\+998\d{9}$/;
    return re.test(phone);
}

async function startProcessing() {
    const fileInput = document.getElementById('cv-file');
    const lang = document.getElementById('lang-select').value;
    const name = document.getElementById('candidate-name').value;
    const phone = document.getElementById('candidate-phone').value;
    const email = document.getElementById('candidate-email').value;

    if (!name || !phone || !email) {
        alert("Please fill in all fields (Name, Phone, Email)");
        return;
    }

    if (!validateUzPhone(phone)) {
        alert("Please enter a valid Uzbekistan phone number (+998XXXXXXXXX)");
        return;
    }

    if (fileInput.files.length === 0) {
        alert("Please upload your CV first");
        return;
    }

    showStep('step-loading');

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('name', name);
    formData.append('phone', phone);
    formData.append('email', email);

    try {
        // Step 1: Analyze CV
        const analyzeRes = await fetch('/analyze', { method: 'POST', body: formData });
        const cvResult = await analyzeRes.json();

        // Step 2: Detect Level
        const levelRes = await fetch('/detect-level', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ candidate_name: name, cv_result: cvResult })
        });
        const levelResult = await levelRes.json();

        // Step 3: Interview Plan
        await fetch('/interview-plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(levelResult)
        });

        // Step 4: Generate Questions
        const questionsRes = await fetch('/generate-questions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ level_result: levelResult, max_questions: 5, lang: lang })
        });
        const questionSet = await questionsRes.json();
        questions = questionSet.questions;

        // Step 5: Start Interview Session
        const sessionRes = await fetch('/start-interview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                candidate_id: Math.random().toString(36).substring(7),
                candidate_name: name || "Unknown",
                candidate_phone: phone || "",
                candidate_email: email || "",
                question_set: questionSet,
                lang: lang || "en",
                cv_path: (cvResult && cvResult.cv_path) ? cvResult.cv_path : ""
            })
        });
        const session = await sessionRes.json();
        sessionId = session.session_id;

        loadQuestion();
        showStep('step-interview');
    } catch (error) {
        console.error(error);
        alert("An error occurred. Please try again.");
        showStep('step-upload');
    }
}

function loadQuestion() {
    if (currentQuestionIndex >= questions.length) {
        finishInterview();
        return;
    }

    const q = questions[currentQuestionIndex];
    document.getElementById('question-text').innerText = q.question;
    document.getElementById('answer-text').value = "";
    document.getElementById('progress-fill').style.width = `${((currentQuestionIndex) / questions.length) * 100}%`;

    startTimer(120); // 2 minutes per question
}

async function submitAnswer() {
    const answer = document.getElementById('answer-text').value;
    if (!answer) {
        alert("Please type an answer");
        return;
    }

    clearInterval(timerInterval);

    try {
        await fetch(`/submit-answer/${sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(answer)
        });

        currentQuestionIndex++;
        loadQuestion();
    } catch (error) {
        console.error(error);
        alert("Failed to submit answer.");
    }
}

async function finishInterview() {
    showStep('step-loading');
    document.getElementById('loading-text').innerText = "Finalizing interview...";

    try {
        // Step 6 & 7: Integrity and Recommendation
        await fetch(`/analyze-integrity/${sessionId}`, { method: 'POST' });
        await fetch(`/generate-recommendation/${sessionId}`, { method: 'POST' });

        showStep('step-final');
    } catch (error) {
        console.error(error);
        showStep('step-final'); // Show final anyway
    }
}

function startTimer(seconds) {
    let timeLeft = seconds;
    const timerEl = document.getElementById('timer');

    timerInterval = setInterval(() => {
        const mins = Math.floor(timeLeft / 60) || 0;
        const secs = timeLeft % 60 || 0;
        timerEl.innerText = `Time Remaining: ${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            submitAnswer(); // Auto-submit on timeout
        }
        timeLeft--;
    }, 1000);
}

function showStep(stepId) {
    document.querySelectorAll('.step-card').forEach(el => el.classList.add('hidden'));
    document.getElementById(stepId).classList.remove('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
    updateUI();
});
