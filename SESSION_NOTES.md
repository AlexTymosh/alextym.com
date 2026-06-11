# SESSION_NOTES.md

## Текущий фокус

Закрыт этап наведения порядка в источниках данных для resume, RAG, fallback
retrieval и генерации embeddings.

Единственный источник истины для публичного resume и RAG-контента:

```text
content/public/resume.md
```

В `content/public/` сейчас должен находиться только `resume.md`.

---

## Ограничения

- Не пушить код.
- Не комитить код.
- Не выполнять команды для удаленных репозиториев.
- Не добавлять в `content/public/` документы кроме `resume.md` без отдельного решения.
- Не добавлять private biography, private contacts, health information,
  names of colleagues/friends/managers, secrets, private notes, or private
  chat logs.
- Не запускать paid/live RAG ingestion или paid evals без отдельного разрешения.

---

## Выполненный План

| Этап | Статус | Что сделано | Результат |
|---:|---|---|---|
| 1 | Завершен | Проверен текущий source/path usage | Найдены все активные resume/RAG/generated paths |
| 2 | Завершен | Canonical resume перенесен из `frontend/content/resume.md` в `content/public/resume.md` | Source больше не находится внутри frontend |
| 3 | Завершен | Обновлены backend fallback, RAG extraction, frontend parser, tests и docs | Активные пути читают `content/public/resume.md` |
| 4 | Завершен | Generated RAG artifact перенесен из `backend/knowledge` в `.tmp/rag` | `backend/knowledge` больше не рабочая папка pipeline |
| 5 | Завершен | Docker build переведен на repository root context | Backend image получает `content/public/resume.md` для fallback |
| 6 | Завершен | `backend/knowledge/` удалена | Legacy source folder больше не существует |
| 7 | Завершен | Бесплатные checks | `task ci:quick` и `task docker:build` прошли |

---

## Фактическая Цепочка Данных

- Canonical source: `content/public/resume.md`.
- Frontend resume parser читает `content/public/resume.md`.
- Structured RAG extraction читает `## RAG` и `### RAG` из canonical source.
- Generated artifact: `.tmp/rag/resume.generated.chunks.json`.
- Generated artifact не является источником истины и не хранит числовые embeddings.
- Embeddings создаются во время ingestion и отправляются в Qdrant.
- Runtime retrieval использует Qdrant при наличии конфигурации.
- Fallback retrieval строится из `content/public/resume.md`.
- `backend/knowledge/` удалена.

---

## Qdrant Cleanup Compatibility

Ingestion продолжает очищать старые payload source names, чтобы в Qdrant не
оставались дубликаты после миграции:

```text
content/public/resume.md
frontend/content/resume.md
resume.md
resume.generated.chunks.json
```

Это только имена старых payload/source записей в Qdrant. Это не означает, что
старые файлы читаются как источники данных.

---

## Проверки

Пройдено:

```text
task ci:quick
task docker:build
```

`task ci:quick` включал:

- backend sync, lint, format check, compile, pytest;
- frontend install, lint, resume parser check, production build, Playwright e2e;
- deterministic free RAG extraction and eval cycle.

Paid/live проверки не запускались:

```text
task rag:ingest
task rag:eval:paid
task rag:eval:generated
task rag:eval:retrieval
```

---

## Следующее Действие

После успешных checks можно перейти к следующему большому этапу:

```text
архитектура настроек проекта и вынос hardcoded configuration
```

Перед изменениями нужно отдельно обсудить стратегию для:

- публичной site/person config;
- SEO metadata;
- chat UI texts and assistant-facing copy;
- environment variables versus non-secret config;
- deploy-time settings.
