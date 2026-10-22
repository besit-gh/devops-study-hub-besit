import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { localizeScore } from '../utils/localization'
import { fetchInterviewQuestions, evaluateAnswerWithSrs, fetchInterviewReviewQueue, selfGradeInterview } from '../store/curriculumStore'



const SCORE_STYLE = {
  Strong: 'text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950 border-emerald-300 dark:border-emerald-700',
  Adequate: 'text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950 border-amber-300 dark:border-amber-700',
  Weak: 'text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-950 border-red-300 dark:border-red-700',
}

export default function InterviewPrep({ modules, onXpEarned, interviewQueue: queueProp = null }) {
  const { moduleSlug: urlSlug } = useParams()

  const initialSlug = urlSlug && modules.find(m => m.slug === urlSlug)
    ? urlSlug
    : modules.length
      ? modules[Math.floor(Math.random() * modules.length)].slug
      : ''

  // Main session state
  const [selectedSlug, setSelectedSlug] = useState(initialSlug)
  const [mode, setMode] = useState('ai') // ai | flashcard
  const [phase, setPhase] = useState('idle') // idle | loading | active | evaluating | reviewed | done
  const [questions, setQuestions] = useState([])
  const [qIndex, setQIndex] = useState(0)
  const [answer, setAnswer] = useState('')
  const [evaluation, setEvaluation] = useState(null)
  const [results, setResults] = useState([])
  const [modelOpen, setModelOpen] = useState(false)
  const [error, setError] = useState(null)

  // Review session state
  const [reviewQueue, setReviewQueue] = useState(queueProp) // null = loading, [] = empty
  const [reviewPhase, setReviewPhase] = useState('idle') // idle | active | submitting | reviewed_card | done
  const [reviewIndex, setReviewIndex] = useState(0)
  const [reviewAnswer, setReviewAnswer] = useState('')
  const [reviewEval, setReviewEval] = useState(null)
  const [reviewModelOpen, setReviewModelOpen] = useState(false)
  const [reviewResults, setReviewResults] = useState([])

  const selectedModule = modules.find(m => m.slug === selectedSlug)
  const topRef = useRef(null)
  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true
    return () => { isMounted.current = false }
  }, [])

  // Sync when App's isolated fetch completes (queueProp transitions null → loaded)
  useEffect(() => {
    if (reviewQueue === null && queueProp !== null) setReviewQueue(queueProp)
  }, [queueProp])

  useEffect(() => {
    if ((phase === 'reviewed' || reviewPhase === 'reviewed_card') && topRef.current) {
      const main = topRef.current.closest('main')
      if (main) main.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }, [phase, reviewPhase])

  // ---- Main session handlers -----------------------------------------------

  const start = async (startMode = mode) => {
    setMode(startMode)
    setPhase('loading')
    setError(null)
    try {
      const qs = await fetchInterviewQuestions(selectedSlug)
      setQuestions(qs)
      setQIndex(0)
      setAnswer('')
      setEvaluation(null)
      setResults([])
      setPhase('active')
    } catch {
      setError('Не удалось загрузить вопросы. Убедись, что backend запущен.')
      setPhase('idle')
    }
  }

  const reveal = () => setPhase('reviewed')

  const selfRate = async (score) => {
    try {
      const ev = await selfGradeInterview(selectedSlug, questions[qIndex].id, score)
      if (!isMounted.current) return
      setEvaluation(ev)
      if (ev.xp_earned > 0 && onXpEarned) onXpEarned(ev.xp_total)
    } catch {
      if (!isMounted.current) return
      setError('Не удалось сохранить оценку. Попробуй ещё раз.')
    }
  }

  const submit = async () => {
    if (!answer.trim()) return
    setPhase('evaluating')
    try {
      const ev = await evaluateAnswerWithSrs(selectedSlug, questions[qIndex].id, questions[qIndex].question, answer)
      if (!isMounted.current) return
      setEvaluation(ev)
      setModelOpen(false)
      setPhase('reviewed')
      if (ev.xp_earned > 0 && onXpEarned) onXpEarned(ev.xp_total)
    } catch (err) {
      if (!isMounted.current) return
      setError(err?.message?.includes('504') ? 'Время ожидания оценки истекло — попробуй ещё раз.' : 'Не удалось оценить ответ. Попробуй ещё раз.')
      setPhase('active')
    }
  }

  const advance = () => {
    const newResults = [...results, { question: questions[qIndex].question, answer, ...evaluation }]
    if (qIndex + 1 >= questions.length) {
      setResults(newResults)
      setPhase('done')
    } else {
      setResults(newResults)
      setQIndex(i => i + 1)
      setAnswer('')
      setEvaluation(null)
      setPhase('active')
    }
  }

  const reset = () => {
    setMode('ai')
    setPhase('idle')
    setQuestions([])
    setQIndex(0)
    setAnswer('')
    setEvaluation(null)
    setResults([])
    setError(null)
  }

  // ---- Review session handlers ---------------------------------------------

  const startReview = () => {
    setReviewIndex(0)
    setReviewAnswer('')
    setReviewEval(null)
    setReviewModelOpen(false)
    setReviewResults([])
    setReviewPhase('active')
  }

  const submitReview = async () => {
    if (!reviewAnswer.trim()) return
    setReviewPhase('submitting')
    const card = reviewQueue[reviewIndex]
    try {
      const ev = await evaluateAnswerWithSrs(card.module_slug, card.id, card.question, reviewAnswer)
      if (!isMounted.current) return
      setReviewEval(ev)
      setReviewModelOpen(false)
      setReviewPhase('reviewed_card')
      if (ev.xp_earned > 0 && onXpEarned) onXpEarned(ev.xp_total)
    } catch (err) {
      if (!isMounted.current) return
      setError(err?.message?.includes('504') ? 'Время ожидания оценки истекло — попробуйте ещё раз.' : 'Не удалось оценить ответ. Попробуйте ещё раз.')
      setReviewPhase('active')
    }
  }

  const advanceReview = () => {
    const newResults = [...reviewResults, { question: reviewQueue[reviewIndex].question, answer: reviewAnswer, ...reviewEval }]
    if (reviewIndex + 1 >= reviewQueue.length) {
      setReviewResults(newResults)
      setReviewPhase('done')
    } else {
      setReviewResults(newResults)
      setReviewIndex(i => i + 1)
      setReviewAnswer('')
      setReviewEval(null)
      setReviewModelOpen(false)
      setReviewPhase('active')
    }
  }

  const exitReview = () => {
    setReviewPhase('idle')
    setReviewAnswer('')
    setReviewEval(null)
    setReviewResults([])
    setError(null)
    fetchInterviewReviewQueue()
      .then(q => setReviewQueue(q))
      .catch(() => setReviewQueue([]))
  }

  // ---- Review session renders ----------------------------------------------

  if (reviewPhase === 'done') {
    const counts = { Strong: 0, Adequate: 0, Weak: 0 }
    reviewResults.forEach(r => { if (r.score in counts) counts[r.score]++ })
    return (
      <div className="p-6 max-w-2xl">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100 mb-1">Повторение завершено</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Повторено вопросов: {reviewQueue.length}
          </p>
        </div>
        <div className="flex gap-3 mb-6">
          {Object.entries(counts).map(([score, n]) => (
            <div key={score} className={`flex-1 text-center py-3 rounded-lg border text-sm font-medium ${SCORE_STYLE[score]}`}>
              <div className="text-2xl font-bold">{n}</div>
              <div>{localizeScore(score)}</div>
            </div>
          ))}
        </div>
        <div className="space-y-3 mb-6">
          {reviewResults.map((r, i) => (
            <div key={i} className="p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              <div className="flex items-start justify-between gap-2 mb-1">
                <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">{r.question}</p>
                <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full border font-medium ${SCORE_STYLE[r.score]}`}>
                  {localizeScore(r.score)}
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">{r.feedback}</p>
            </div>
          ))}
        </div>
        <button
          onClick={exitReview}
          className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors"
        >
          Назад к подготовке к собеседованию
        </button>
      </div>
    )
  }

  if (reviewPhase !== 'idle') {
    const card = reviewQueue[reviewIndex]
    return (
      <div ref={topRef} className="p-6 max-w-2xl">
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">{card.module_title} · К повторению</p>
            <h1 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
              Вопрос {reviewIndex + 1} из {reviewQueue.length}
            </h1>
          </div>
          <div className="flex items-center gap-3">
          <button
            onClick={exitReview}
            className="text-xs text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 underline"
          >
            Exit review
          </button>
          <div className="flex gap-1.5">
            {reviewQueue.map((_, i) => (
              <div
                key={i}
                className={`w-2 h-2 rounded-full ${
                  i < reviewResults.length
                    ? 'bg-emerald-500'
                    : i === reviewIndex
                      ? 'bg-gray-400 dark:bg-gray-500'
                      : 'bg-gray-200 dark:bg-gray-700'
                }`}
              />
            ))}
          </div>
          </div>
        </div>

        <p className="text-gray-800 dark:text-gray-100 text-base leading-relaxed mb-5">{card.question}</p>

        {(reviewPhase === 'active' || reviewPhase === 'submitting') && (
          <>
            <textarea
              value={reviewAnswer}
              onChange={e => setReviewAnswer(e.target.value)}
              disabled={reviewPhase === 'submitting'}
              placeholder="Введите свой ответ…"
              rows={6}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 mb-3"
            />
            {error && <p className="text-sm text-red-500 mb-2">{error}</p>}
            <button
              onClick={submitReview}
              disabled={!reviewAnswer.trim() || reviewPhase === 'submitting'}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {reviewPhase === 'submitting' ? 'Оцениваю…' : 'Отправить ответ'}
            </button>
          </>
        )}

        {reviewPhase === 'reviewed_card' && reviewEval && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${SCORE_STYLE[reviewEval.score]}`}>
                {localizeScore(reviewEval.score)}
              </div>
              {reviewEval.xp_earned > 0 && (
                <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">+{reviewEval.xp_earned} XP</span>
              )}
            </div>

            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Ваш ответ</p>
              <p className="text-sm text-gray-600 dark:text-gray-400 italic leading-relaxed">{reviewAnswer}</p>
            </div>

            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Обратная связь</p>
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{reviewEval.feedback}</p>
            </div>

            <div>
              <button
                onClick={() => setReviewModelOpen(o => !o)}
                className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline"
              >
                {reviewModelOpen ? '▼ Скрыть эталонный ответ' : '▶ Показать эталонный ответ'}
              </button>
              {reviewModelOpen && (
                <p className="mt-2 text-sm text-gray-700 dark:text-gray-300 leading-relaxed border-l-2 border-emerald-400 pl-3">
                  {reviewEval.model_answer}
                </p>
              )}
            </div>

            <button
              onClick={advanceReview}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors"
            >
              {reviewIndex + 1 >= reviewQueue.length ? 'Завершить повторение' : 'Следующий вопрос'}
            </button>
          </div>
        )}
      </div>
    )
  }

  // ---- Main session renders -----------------------------------------------

  if (phase === 'idle' || phase === 'loading') return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100 mb-1">Подготовка к собеседованию</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
        Тренируйтесь отвечать на реальные вопросы DevOps-собеседований. ИИ оценит ответ и покажет пример сильного ответа.
      </p>

      {reviewQueue !== null && reviewQueue.length > 0 && (
        <div className="mb-6 p-4 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950">
          <p className="text-sm font-medium text-amber-800 dark:text-amber-300 mb-1">
            К повторению: {reviewQueue.length} вопросов
          </p>
          <p className="text-xs text-amber-600 dark:text-amber-400 mb-3">
            Повторите их, чтобы не сбить расписание интервального повторения.
          </p>
          <button
            onClick={startReview}
            className="px-4 py-2 rounded-lg bg-amber-500 text-white text-sm font-medium hover:bg-amber-600 transition-colors"
          >
            Повторить сейчас
          </button>
        </div>
      )}

      {modules.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Модули пока недоступны.</p>
      ) : (
        <>
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">
              Модуль
            </label>
            <select
              value={selectedSlug}
              onChange={e => setSelectedSlug(e.target.value)}
              disabled={phase === 'loading'}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              {modules.map(m => (
                <option key={m.slug} value={m.slug}>{m.title}</option>
              ))}
            </select>
          </div>
          {error && <p className="text-sm text-red-500 mb-3">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => start('ai')}
              disabled={!selectedSlug || phase === 'loading'}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {phase === 'loading' ? 'Загрузка…' : 'Start Session'}
            </button>
            <button
              onClick={() => start('flashcard')}
              disabled={!selectedSlug || phase === 'loading'}
              className="px-4 py-2 rounded-lg border border-emerald-600 text-emerald-600 dark:text-emerald-400 dark:border-emerald-500 text-sm font-medium hover:bg-emerald-50 dark:hover:bg-emerald-950/30 disabled:opacity-50 transition-colors"
              title="Показать эталонные ответы и оценить себя — без вызова ИИ"
            >
              Быстрое повторение
            </button>
          </div>
        </>
      )}
    </div>
  )

  if (phase === 'done') {
    const counts = { Strong: 0, Adequate: 0, Weak: 0 }
    results.forEach(r => { if (r.score in counts) counts[r.score]++ })

    return (
      <div className="p-6 max-w-2xl">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100 mb-1">
            {mode === 'flashcard' ? 'Повторение завершено' : 'Сессия завершена'}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">{selectedModule?.title}</p>
        </div>

        <div className="flex gap-3 mb-6">
          {Object.entries(counts).map(([score, n]) => (
            <div key={score} className={`flex-1 text-center py-3 rounded-lg border text-sm font-medium ${SCORE_STYLE[score]}`}>
              <div className="text-2xl font-bold">{n}</div>
              <div>{localizeScore(score)}</div>
            </div>
          ))}
        </div>

        <div className="space-y-3 mb-6">
          {results.map((r, i) => (
            <div key={i} className="p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              <div className="flex items-start justify-between gap-2 mb-1">
                <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">{r.question}</p>
                <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full border font-medium ${SCORE_STYLE[r.score]}`}>
                  {localizeScore(r.score)}
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">{r.feedback}</p>
            </div>
          ))}
        </div>

        <button
          onClick={reset}
          className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors"
        >
          Новая сессия
        </button>
      </div>
    )
  }

  // Active / Evaluating / Reviewed / Mock-Reviewed ---------------------------
  const q = questions[qIndex]
  return (
    <div ref={topRef} className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">{selectedModule?.title}</p>
          <h1 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
            Вопрос {qIndex + 1} из {questions.length}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={reset}
            className="text-xs text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 underline"
          >
            Выйти из сессии
          </button>
        </div>
        <div className="flex gap-1.5">
          {questions.map((_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full ${
                i < results.length
                  ? 'bg-emerald-500'
                  : i === qIndex
                    ? 'bg-gray-400 dark:bg-gray-500'
                    : 'bg-gray-200 dark:bg-gray-700'
              }`}
            />
          ))}
        </div>
      </div>

      <p className="text-gray-800 dark:text-gray-100 text-base leading-relaxed mb-5">{q.question}</p>

      {(phase === 'active' || phase === 'evaluating') && (
        <>
          {mode === 'flashcard' ? (
            <>
              {error && <p className="text-sm text-red-500 mb-2">{error}</p>}
              <button
                onClick={reveal}
                className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors"
              >
                Показать ответ
              </button>
            </>
          ) : (
            <>
              <textarea
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                disabled={phase === 'evaluating'}
                placeholder="Введите свой ответ…"
                rows={6}
                className="w-full px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 mb-3"
              />
              {error && <p className="text-sm text-red-500 mb-2">{error}</p>}
              <button
                onClick={submit}
                disabled={!answer.trim() || phase === 'evaluating'}
                className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
              >
                {phase === 'evaluating' ? 'Оцениваю…' : 'Отправить ответ'}
              </button>
            </>
          )}
        </>
      )}

      {phase === 'reviewed' && mode === 'flashcard' && (
        <div className="space-y-4">
          <div>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Эталонный ответ</p>
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed border-l-2 border-emerald-400 pl-3">
              {q.model_answer || <span className="italic text-gray-400">Эталонный ответ пока не добавлен.</span>}
            </p>
          </div>
          {!evaluation ? (
            <>
              <p className="text-xs text-gray-500 dark:text-gray-400">Насколько хорошо вы знали ответ?</p>
              {error && <p className="text-sm text-red-500 mb-1">{error}</p>}
              <div className="flex gap-2">
                {(['Strong', 'Adequate', 'Weak']).map(score => (
                  <button
                    key={score}
                    onClick={() => selfRate(score)}
                    className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${SCORE_STYLE[score]} hover:opacity-80`}
                  >
                    {localizeScore(score)}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${SCORE_STYLE[evaluation.score]}`}>
                  {localizeScore(evaluation.score)}
                </div>
                {evaluation.xp_earned > 0 && (
                  <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">+{evaluation.xp_earned} XP</span>
                )}
              </div>
              <button
                onClick={advance}
                className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors"
              >
                {qIndex + 1 >= questions.length ? 'Завершить сессию' : 'Следующий вопрос'}
              </button>
            </>
          )}
        </div>
      )}

      {phase === 'reviewed' && mode === 'ai' && evaluation && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${SCORE_STYLE[evaluation.score]}`}>
              {localizeScore(evaluation.score)}
            </div>
            {evaluation.xp_earned > 0 && (
              <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">+{evaluation.xp_earned} XP</span>
            )}
            <button
              onClick={() => { setEvaluation(null); setPhase('active') }}
              className="ml-auto text-xs text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 underline"
            >
              Изменить ответ
            </button>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Ваш ответ</p>
            <p className="text-sm text-gray-600 dark:text-gray-400 italic leading-relaxed">{answer}</p>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Обратная связь</p>
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{evaluation.feedback}</p>
          </div>

          <div>
            <button
              onClick={() => setModelOpen(o => !o)}
              className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline"
            >
              {modelOpen ? '▼ Скрыть эталонный ответ' : '▶ Показать эталонный ответ'}
            </button>
            {modelOpen && (
              <p className="mt-2 text-sm text-gray-700 dark:text-gray-300 leading-relaxed border-l-2 border-emerald-400 pl-3">
                {evaluation.model_answer}
              </p>
            )}
          </div>

          <button
            onClick={advance}
            className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors"
          >
            {qIndex + 1 >= questions.length ? 'Завершить сессию' : 'Следующий вопрос'}
          </button>
        </div>
      )}
    </div>
  )
}
