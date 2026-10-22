import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ai_client import stream_text
from db import get_conn

router = APIRouter()

PROJECT_ROOT = Path(__file__).parent.parent.parent


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    lesson_slug: str
    messages: list[Message]


def _lesson_context(slug: str) -> tuple[str, str | None]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT l.title, l.md_path FROM lessons l WHERE l.slug = ?", (slug,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return slug, None
    md_file = PROJECT_ROOT / row['md_path']
    if not md_file.exists():
        return row['title'], None
    text = md_file.read_text()
    if text.startswith('---'):
        try:
            end = text.index('---', 3)
            return row['title'], text[end + 3:].strip()
        except ValueError:
            pass
    return row['title'], text


@router.post('/ai/chat')
async def chat(request: ChatRequest):
    for m in request.messages:
        if m.role not in ('user', 'assistant'):
            raise HTTPException(status_code=400, detail=f"Invalid role: {m.role!r}. Must be 'user' or 'assistant'.")

    MAX_HISTORY = 10   # последние 5 обменов сообщениями
    LESSON_CHARS = 3000

    title, content = _lesson_context(request.lesson_slug)

    system = f"Ты — ИИ-наставник русскоязычного курса DevOps. Отвечай на русском языке, если пользователь явно не попросил другой язык. Тема занятия:\n\nУрок: {title}\n\n"
    if content:
        system += f"Содержание урока:\n{content[:LESSON_CHARS]}\n\n"
    system += (
        "Объясняй кратко, ясно и практично. Используй конкретные примеры и команды. "
        "Оставайся в рамках DevOps. Не выдумывай результаты выполнения команд; отмечай риски для production. Сохраняй имена команд, параметров и API без перевода."
    )

    trimmed = request.messages[-MAX_HISTORY:]

    async def stream_response():
        try:
            async for chunk in stream_text(
                system,
                [{'role': m.role, 'content': m.content} for m in trimmed],
            ):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'text': f'Ошибка: {e}'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
