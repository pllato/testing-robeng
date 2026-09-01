# ELC Kids — настройка перед запуском

Превью-папка `curriculum/preview/` содержит:

| Файл | Назначение |
|---|---|
| `index.html` | Список 70 уроков |
| `lesson.html` | Страница одного урока (слова + грамматика + диалог) |
| `play.html` | Тренировка / игра с родителем |
| `translations.json` | RU-перевод 640 слов |
| `image_dupes.json` | Слова с картинками-дублями (отчёт perceptual hash) |
| `_serve.py` | Локальный dev-сервер (порт 8800) |

Эта папка деплоится как один static-сайт на любой хостинг (Cloudflare Pages / GitHub Pages / nginx). Никакого билда не требуется.

---

## 1. Правила Firebase RTDB

Игра пишет результат в новый путь `eduSchedule/programGameResults/{studentId}/{lessonNum}/{mode}`. Чтобы запись прошла, **нужно добавить правило в RTDB**.

В Firebase Console → Realtime Database → Rules:

```json
{
  "rules": {
    "eduSchedule": {
      "programGameResults": {
        "$studentId": {
          "$lessonNum": {
            "$mode": {
              ".read":  "auth != null",
              ".write": "auth != null && (newData.child('lessonNum').val() == $lessonNum)"
            }
          }
        }
      }
    }
  }
}
```

Что это даёт:
- **Чтение** — только для авторизованных (учитель в CRM, который в любом случае залогинен)
- **Запись** — для авторизованных (включая anonymous-сессии, которые открывает `play.html`). Дополнительно проверяем что `lessonNum` в payload совпадает с путём — защита от случайной записи не туда

Если ты не хочешь пускать anonymous, можно временно поставить `.write: true` на этот путь — данные нечувствительные (счёт игры).

После применения правил — игра автоматически начнёт синхронизироваться, в CRM в карточках уроков появятся бейджи 🎯 N% (зелёный/жёлтый/красный по результату).

Пока правило не добавлено, результат сохраняется только в `localStorage` устройства ребёнка/родителя.

---

## 2. Публичный URL

В `program.js` (для WhatsApp ссылок) и `parent.html` (для кабинета родителя) указан:

```js
const LESSON_PUBLIC_BASE = 'http://127.0.0.1:8800';
const LESSON_BASE        = 'http://127.0.0.1:8800';
```

После выкладки на продакшен (Cloudflare Pages, например) — поменять на боевой URL вида:

```js
const LESSON_PUBLIC_BASE = 'https://kids.elc-kids.kz';
const LESSON_BASE        = 'https://kids.elc-kids.kz';
```

С одного места пробрасывается и в WhatsApp-сообщения, и в кабинет родителя.

---

## 3. Передача `studentId`

WhatsApp-сообщение из CRM теперь добавляет `&sid=<studentId>` к ссылкам игры:

```
https://kids.elc-kids.kz/play.html?n=5&mode=self&sid=42
```

Если ребёнок откроет игру без `sid`, она будет работать, но результат сохранится только локально.
