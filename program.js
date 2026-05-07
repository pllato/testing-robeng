/* ─────────────────────────────────────────────────────────────────
   Программа (70 уроков): чек-лист по ученику + ссылка на материал
   + отправка в WhatsApp.
   Зависимости из index.html (глобалы):
     - S.students[]              — массив учеников {id,name,phone,parent,parentPhone,subjId}
     - S.enrollments[]           — связи (для фильтра по teacherId)
     - currentRole, currentTeacherId
     - fbDb (firebase.database())
   Хранилище в RTDB:
     eduSchedule/programProgress/{studentId}/{lessonNum}
       = { done: true, date: ISO, teacherId, note? }
   ───────────────────────────────────────────────────────────────── */

(function () {
  const CURRICULUM_URL = 'https://pub-4a4bf55405d74fe58e817b5fb86955d4.r2.dev/curriculum.json';
  // База URL для родителя: пока локальное превью, позже сменим на elc-kids.kz
  const LESSON_PUBLIC_BASE = 'http://127.0.0.1:8800';
  const LS_CURRICULUM = 'pg_curriculum_v1';
  const LS_TTL_MIN = 60;

  const state = {
    curriculum: null,
    progress: {},          // { studentId: { lessonNum: {done, date, ...} } }
    progressUnsub: null,   // для off()
    selectedStudentId: null,
    studentFilter: '',
  };

  // ── Curriculum loading (с кэшем в localStorage на час) ────────
  async function loadCurriculum() {
    if (state.curriculum) return state.curriculum;
    try {
      const raw = localStorage.getItem(LS_CURRICULUM);
      if (raw) {
        const c = JSON.parse(raw);
        const ageMin = (Date.now() - c._cachedAt) / 60000;
        if (ageMin < LS_TTL_MIN && c.lessons) { state.curriculum = c; return c; }
      }
    } catch {}
    const r = await fetch(CURRICULUM_URL, { cache: 'no-cache' });
    if (!r.ok) throw new Error('Не удалось загрузить программу: HTTP ' + r.status);
    const c = await r.json();
    c._cachedAt = Date.now();
    try { localStorage.setItem(LS_CURRICULUM, JSON.stringify(c)); } catch {}
    state.curriculum = c;
    return c;
  }

  // ── Helpers ───────────────────────────────────────────────────
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function visibleStudents() {
    const all = (window.S && Array.isArray(S.students)) ? S.students : [];
    let list = all;
    // Если роль teacher — показываем только тех, у кого есть enrollment с этим teacherId
    if (currentRole === 'teacher' && currentTeacherId != null && Array.isArray(S.enrollments)) {
      const myStudIds = new Set(
        S.enrollments.filter(e => e.teacherId === currentTeacherId).map(e => e.studentId)
      );
      list = list.filter(s => myStudIds.has(s.id));
    }
    const q = state.studentFilter.trim().toLowerCase();
    if (q) list = list.filter(s => (s.name || '').toLowerCase().includes(q));
    return list.slice().sort((a, b) => (a.name || '').localeCompare(b.name || '', 'ru'));
  }

  function progressForStudent(studentId) {
    return state.progress[studentId] || {};
  }
  function doneCount(studentId) {
    const p = progressForStudent(studentId);
    return Object.values(p).filter(x => x && x.done).length;
  }

  // ── RTDB subscription для выбранного ученика ──────────────────
  function subscribeProgress(studentId) {
    if (state.progressUnsub) { state.progressUnsub(); state.progressUnsub = null; }
    if (!studentId || !window.fbDb) return;
    const ref = fbDb.ref('eduSchedule/programProgress/' + studentId);
    const handler = ref.on('value', (snap) => {
      state.progress[studentId] = snap.val() || {};
      renderDetail();
      // обновим счётчик в списке
      const el = document.querySelector('.pg-stu[data-sid="' + studentId + '"] .pg-progress');
      if (el) el.textContent = doneCount(studentId) + '/70';
    });
    state.progressUnsub = () => ref.off('value', handler);
  }

  async function toggleLesson(studentId, lessonNum) {
    const cur = progressForStudent(studentId)[lessonNum];
    const ref = fbDb.ref(`eduSchedule/programProgress/${studentId}/${lessonNum}`);
    if (cur && cur.done) {
      await ref.remove();
    } else {
      await ref.set({
        done: true,
        date: new Date().toISOString(),
        teacherId: currentTeacherId || null,
        teacherEmail: (window.fbAuth && fbAuth.currentUser && fbAuth.currentUser.email) || null,
      });
    }
  }

  // ── WhatsApp ─────────────────────────────────────────────────
  function cleanPhone(p) { return String(p || '').replace(/[^\d]/g, ''); }

  function sendToWhatsApp(student, lesson) {
    const phone = cleanPhone(student.parentPhone || student.phone);
    if (!phone) { alert('У ученика не указан номер родителя/ученика'); return; }
    const url = `${LESSON_PUBLIC_BASE}/lesson.html?n=${lesson.lesson}`;
    const wordsLine = (lesson.words || []).join(', ');
    const text =
      `Здравствуйте! Сегодня прошли урок ${lesson.lesson}: ${lesson.topic || ''}.\n` +
      (wordsLine ? `Слова: ${wordsLine}\n` : '') +
      `Материал для повторения: ${url}`;
    window.open(`https://wa.me/${phone}?text=${encodeURIComponent(text)}`, '_blank');
  }

  // ── Rendering ─────────────────────────────────────────────────
  function renderProgramRoot() {
    const root = document.getElementById('panel-program');
    if (!root) return;
    if (!root.dataset.inited) {
      root.innerHTML = `
        <div class="pg-wrap">
          <div class="pg-students">
            <input type="text" id="pg-search" placeholder="Поиск ученика…"/>
            <div id="pg-stu-list"></div>
          </div>
          <div class="pg-detail" id="pg-detail">
            <div class="pg-empty">← Выберите ученика, чтобы увидеть программу.</div>
          </div>
        </div>`;
      root.dataset.inited = '1';
      const inp = document.getElementById('pg-search');
      inp.addEventListener('input', (e) => {
        state.studentFilter = e.target.value;
        renderStudentsList();
      });
    }
  }

  function renderStudentsList() {
    const wrap = document.getElementById('pg-stu-list');
    if (!wrap) return;
    const list = visibleStudents();
    if (!list.length) {
      wrap.innerHTML = '<div class="pg-empty" style="padding:20px">Учеников не найдено.</div>';
      return;
    }
    wrap.innerHTML = list.map(s => {
      const done = doneCount(s.id);
      const active = s.id === state.selectedStudentId ? ' active' : '';
      return `<div class="pg-stu${active}" data-sid="${s.id}">
        <span>${esc(s.name || '—')}</span>
        <span class="pg-progress">${done}/70</span>
      </div>`;
    }).join('');
    wrap.querySelectorAll('.pg-stu').forEach(el => {
      el.addEventListener('click', () => {
        state.selectedStudentId = parseInt(el.dataset.sid, 10);
        renderStudentsList();
        subscribeProgress(state.selectedStudentId);
        renderDetail();
      });
    });
  }

  function renderDetail() {
    const root = document.getElementById('pg-detail');
    if (!root) return;
    const sid = state.selectedStudentId;
    if (!sid) { root.innerHTML = '<div class="pg-empty">← Выберите ученика, чтобы увидеть программу.</div>'; return; }
    const stu = (S.students || []).find(x => x.id === sid);
    if (!stu) { root.innerHTML = '<div class="pg-empty">Ученик не найден.</div>'; return; }
    const c = state.curriculum;
    if (!c) { root.innerHTML = '<div class="pg-loading">Загружаем программу…</div>'; return; }
    const prog = progressForStudent(sid);
    const done = doneCount(sid);

    const cardsHtml = c.lessons.map(L => {
      const p = prog[L.lesson];
      const isDone = !!(p && p.done);
      const dateStr = isDone && p.date ? new Date(p.date).toLocaleDateString('ru-RU') : '';
      return `<div class="pg-card${isDone ? ' done' : ''}">
        <div class="pg-num">Урок ${L.lesson}</div>
        <div class="pg-topic">${esc(L.topic || '')}</div>
        ${dateStr ? `<div class="pg-meta">проведён ${esc(dateStr)}</div>` : ''}
        <div class="pg-actions">
          <button class="pg-btn pg-mark ${isDone ? 'is-done' : ''}" data-act="mark" data-n="${L.lesson}">${isDone ? '✓ Проведён' : 'Отметить'}</button>
          <button class="pg-btn pg-wa" data-act="wa" data-n="${L.lesson}" title="Отправить материал в WhatsApp">WA</button>
        </div>
      </div>`;
    }).join('');

    root.innerHTML = `
      <div class="pg-head">
        <h3>${esc(stu.name || '')}</h3>
        <span class="pg-stat">пройдено ${done} из 70</span>
      </div>
      <div class="pg-grid">${cardsHtml}</div>`;

    root.querySelectorAll('.pg-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const n = parseInt(btn.dataset.n, 10);
        const lesson = c.lessons.find(L => L.lesson === n);
        if (!lesson) return;
        if (btn.dataset.act === 'mark') {
          btn.disabled = true;
          try { await toggleLesson(sid, n); } catch (e) { alert('Ошибка: ' + e.message); }
          btn.disabled = false;
        } else if (btn.dataset.act === 'wa') {
          sendToWhatsApp(stu, lesson);
        }
      });
    });
  }

  // ── Public entry ──────────────────────────────────────────────
  window.renderProgram = async function () {
    renderProgramRoot();
    renderStudentsList();
    try {
      await loadCurriculum();
    } catch (e) {
      const root = document.getElementById('pg-detail');
      if (root) root.innerHTML = `<div class="pg-empty" style="color:var(--rd)">${esc(e.message)}</div>`;
      return;
    }
    if (state.selectedStudentId) {
      subscribeProgress(state.selectedStudentId);
      renderDetail();
    }
  };
})();
