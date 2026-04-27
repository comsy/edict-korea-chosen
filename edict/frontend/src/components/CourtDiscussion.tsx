/**
 * 조정 의정 — 다수 관원 실시간 토론 시각화 컴포넌트
 *
 * nvwa 프로젝트의 스토리 극장 + 협업 워크숍 + 가상 생활에서 영감을 받음
 * 기능:
 *   - 조정 배치 시각화, 관원 위치
 *   - 실시간 그룹 채팅 토론, 관원이 각자 의견 개진
 *   - 임금(사용자)이 언제든 발언 참여
 *   - 천명 강림(상위 시점)으로 토론 흐름 변경
 *   - 운명 주사위: 무작위 이벤트로 재미 추가
 *   - 자동 진행 / 수동 진행
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useStore, DEPTS } from '../store';
import { api } from '../api';

// ── 상수 ──

const OFFICIAL_COLORS: Record<string, string> = {
  taizi: '#e8a040', zhongshu: '#a07aff', menxia: '#6a9eff', shangshu: '#2ecc8a',
  libu: '#f5c842', hubu: '#ff9a6a', bingbu: '#ff5270', xingbu: '#cc4444',
  gongbu: '#44aaff', libu_hr: '#9b59b6',
};

const EMOTION_EMOJI: Record<string, string> = {
  neutral: '', confident: '😏', worried: '😟', angry: '😤',
  thinking: '🤔', amused: '😄', happy: '😊',
};

const COURT_POSITIONS: Record<string, { x: number; y: number }> = {
  // 좌측 열
  zhongshu: { x: 15, y: 25 }, menxia: { x: 15, y: 45 }, shangshu: { x: 15, y: 65 },
  // 우측 열
  libu: { x: 85, y: 20 }, hubu: { x: 85, y: 35 }, bingbu: { x: 85, y: 50 },
  xingbu: { x: 85, y: 65 }, gongbu: { x: 85, y: 80 },
  // 중앙
  taizi: { x: 50, y: 20 }, libu_hr: { x: 50, y: 80 },
};

interface CourtMessage {
  type: string;
  content: string;
  official_id?: string;
  official_name?: string;
  emotion?: string;
  action?: string;
  timestamp?: number;
}

interface CourtSession {
  session_id: string;
  topic: string;
  officials: Array<{
    id: string;
    name: string;
    emoji: string;
    role: string;
    personality: string;
    speaking_style: string;
  }>;
  messages: CourtMessage[];
  round: number;
  phase: string;
}

export default function CourtDiscussion() {
  // Phase: setup | session
  const [phase, setPhase] = useState<'setup' | 'session'>('setup');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [topic, setTopic] = useState('');
  const [session, setSession] = useState<CourtSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoPlay, setAutoPlay] = useState(false);
  const autoPlayRef = useRef(false);

  // 임금 발언
  const [userInput, setUserInput] = useState('');
  // 천명 강림
  const [showDecree, setShowDecree] = useState(false);
  const [decreeInput, setDecreeInput] = useState('');
  const [decreeFlash, setDecreeFlash] = useState(false);
  // 운명 주사위
  const [diceRolling, setDiceRolling] = useState(false);
  const [diceResult, setDiceResult] = useState<string | null>(null);
  // 활성 발언 관원
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  // 관원 감정
  const [emotions, setEmotions] = useState<Record<string, string>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const toast = useStore((s) => s.toast);
  const liveStatus = useStore((s) => s.liveStatus);

  // 자동으로 맨 아래로 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages?.length]);

  // 자동 진행
  useEffect(() => {
    autoPlayRef.current = autoPlay;
  }, [autoPlay]);

  useEffect(() => {
    if (!autoPlay || !session || loading) return;
    const timer = setInterval(() => {
      if (autoPlayRef.current && !loading) {
        handleAdvance();
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [autoPlay, session, loading]);

  // ── 관원 선택 토글 ──
  const toggleOfficial = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 8) next.add(id);
      return next;
    });
  };

  // ── 의정 시작 ──
  const handleStart = async () => {
    if (!topic.trim() || selectedIds.size < 2 || loading) return;
    setLoading(true);
    try {
      const res = await api.courtDiscussStart(topic, Array.from(selectedIds));
      if (!res.ok) throw new Error(res.error || '시작 실패');
      setSession(res as unknown as CourtSession);
      setPhase('session');
    } catch (e: unknown) {
      toast((e as Error).message || '시작 실패', 'err');
    } finally {
      setLoading(false);
    }
  };

  // ── 토론 진행 ──
  const handleAdvance = useCallback(async (userMsg?: string, decree?: string) => {
    if (!session || loading) return;
    setLoading(true);

    try {
      const res = await api.courtDiscussAdvance(session.session_id, userMsg, decree);
      if (!res.ok) throw new Error(res.error || '진행 실패');

      // 세션 메시지 갱신 (새 메시지 추가)
      setSession((prev) => {
        if (!prev) return prev;
        const newMsgs: CourtMessage[] = [];

        if (userMsg) {
          newMsgs.push({ type: 'emperor', content: userMsg, timestamp: Date.now() / 1000 });
        }
        if (decree) {
          newMsgs.push({ type: 'decree', content: decree, timestamp: Date.now() / 1000 });
        }

        const aiMsgs = (res.new_messages || []).map((m: Record<string, string>) => ({
          type: 'official',
          official_id: m.official_id,
          official_name: m.name,
          content: m.content,
          emotion: m.emotion,
          action: m.action,
          timestamp: Date.now() / 1000,
        }));

        if (res.scene_note) {
          newMsgs.push({ type: 'scene_note', content: res.scene_note, timestamp: Date.now() / 1000 });
        }

        return {
          ...prev,
          round: res.round ?? prev.round + 1,
          messages: [...prev.messages, ...newMsgs, ...aiMsgs],
        };
      });

      // 애니메이션: 발언하는 관원 순차 강조
      const aiMsgs = res.new_messages || [];
      if (aiMsgs.length > 0) {
        const emotionMap: Record<string, string> = {};
        let idx = 0;
        const cycle = () => {
          if (idx < aiMsgs.length) {
            setSpeakingId(aiMsgs[idx].official_id);
            emotionMap[aiMsgs[idx].official_id] = aiMsgs[idx].emotion || 'neutral';
            idx++;
            setTimeout(cycle, 1200);
          } else {
            setSpeakingId(null);
          }
        };
        cycle();
        setEmotions((prev) => ({ ...prev, ...emotionMap }));
      }
    } catch {
      // silently
    } finally {
      setLoading(false);
    }
  }, [session, loading]);

  // ── 임금 발언 ──
  const handleEmperor = () => {
    const msg = userInput.trim();
    if (!msg) return;
    setUserInput('');
    handleAdvance(msg);
  };

  // ── 천명 강림 ──
  const handleDecree = () => {
    const msg = decreeInput.trim();
    if (!msg) return;
    setDecreeInput('');
    setShowDecree(false);
    setDecreeFlash(true);
    setTimeout(() => setDecreeFlash(false), 800);
    handleAdvance(undefined, msg);
  };

  // ── 운명 주사위 ──
  const handleDice = async () => {
    if (loading || diceRolling) return;
    setDiceRolling(true);
    setDiceResult(null);

    // 굴림 애니메이션
    let count = 0;
    const timer = setInterval(async () => {
      count++;
      setDiceResult('🎲 운명이 회전 중...');
      if (count >= 6) {
        clearInterval(timer);
        try {
          const res = await api.courtDiscussFate();
          const event = res.event || '변경 급보가 도착했습니다';
          setDiceResult(event);
          setDiceRolling(false);
          // 천명 강림으로 자동 주입
          handleAdvance(undefined, `【운명 주사위】${event}`);
        } catch {
          setDiceResult('운명의 힘이 잠시 닿지 않습니다');
          setDiceRolling(false);
        }
      }
    }, 200);
  };

  // ── 의정 종료 ──
  const handleConclude = async () => {
    if (!session) return;
    setLoading(true);
    try {
      const res = await api.courtDiscussConclude(session.session_id);
      if (res.summary) {
        setSession((prev) =>
          prev
            ? {
              ...prev,
              phase: 'concluded',
              messages: [
                ...prev.messages,
                { type: 'system', content: `📋 조정 의정 종료 — ${res.summary}`, timestamp: Date.now() / 1000 },
              ],
            }
            : prev,
        );
      }
      setAutoPlay(false);
    } catch {
      toast('종료 실패', 'err');
    } finally {
      setLoading(false);
    }
  };

  // ── 초기화 ──
  const handleReset = () => {
    if (session) {
      api.courtDiscussDestroy(session.session_id).catch(() => {});
    }
    setPhase('setup');
    setSession(null);
    setAutoPlay(false);
    setEmotions({});
    setSpeakingId(null);
    setDiceResult(null);
  };

  // ── 사전 설정 의제 (현재 지시에서 추출) ──
  const activeEdicts = (liveStatus?.tasks || []).filter(
    (t) => /^JJC-/i.test(t.id) && !['Done', 'Cancelled'].includes(t.state),
  );

  const presetTopics = [
    ...activeEdicts.slice(0, 3).map((t) => ({
      text: `지시 토론 ${t.id}: ${t.title}`,
      taskId: t.id,
      icon: '📜',
    })),
    { text: '시스템 아키텍처 최적화 방안 토론', taskId: '', icon: '🏗️' },
    { text: '현재 프로젝트 진행 현황 및 리스크 평가', taskId: '', icon: '📊' },
    { text: '다음 주 업무 계획 수립', taskId: '', icon: '📋' },
    { text: '긴급 사안: 운영 버그 조사 방안', taskId: '', icon: '🚨' },
  ];

  // ═══════════════════
  //     렌더링: 설정 화면
  // ═══════════════════

  if (phase === 'setup') {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="text-center py-4">
          <h2 className="text-xl font-bold bg-gradient-to-r from-amber-400 to-purple-400 bg-clip-text text-transparent">
            🏛 조정 의정
          </h2>
          <p className="text-xs text-[var(--muted)] mt-1">
            대신을 선택해 등정시키고 의제를 두고 토론합니다 · 임금께서는 언제든 발언하거나 천명을 내려 흐름을 바꿀 수 있습니다
          </p>
        </div>

        {/* 관원 선택 */}
        <div className="bg-[var(--panel)] rounded-xl p-4 border border-[var(--line)]">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm font-semibold">👔 참조 관원 선택</span>
            <span className="text-xs text-[var(--muted)]">({selectedIds.size}/8, 최소 2명)</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
            {DEPTS.map((d) => {
              const active = selectedIds.has(d.id);
              const color = OFFICIAL_COLORS[d.id] || '#6a9eff';
              return (
                <button
                  key={d.id}
                  onClick={() => toggleOfficial(d.id)}
                  className="p-2.5 rounded-lg border transition-all text-left"
                  style={{
                    borderColor: active ? color + '80' : 'var(--line)',
                    background: active ? color + '15' : 'var(--panel2)',
                    boxShadow: active ? `0 0 12px ${color}20` : 'none',
                  }}
                >
                  <div className="flex items-center gap-1.5">
                    <span className="text-lg">{d.emoji}</span>
                    <div>
                      <div className="text-xs font-semibold" style={{ color: active ? color : 'var(--text)' }}>
                        {d.label}
                      </div>
                      <div className="text-[10px] text-[var(--muted)]">{d.role}</div>
                    </div>
                    {active && (
                      <span
                        className="ml-auto w-4 h-4 rounded-full flex items-center justify-center text-[10px] text-white"
                        style={{ background: color }}
                      >
                        ✓
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* 의제 */}
        <div className="bg-[var(--panel)] rounded-xl p-4 border border-[var(--line)]">
          <div className="text-sm font-semibold mb-2">📜 의제 설정</div>
          {presetTopics.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {presetTopics.map((p, i) => (
                <button
                  key={i}
                  onClick={() => setTopic(p.text)}
                  className="text-xs px-2.5 py-1.5 rounded-lg border border-[var(--line)] hover:border-[var(--acc)] hover:text-[var(--acc)] transition-colors"
                  style={{
                    background: topic === p.text ? 'var(--acc)' + '18' : 'transparent',
                    borderColor: topic === p.text ? 'var(--acc)' : undefined,
                    color: topic === p.text ? 'var(--acc)' : undefined,
                  }}
                >
                  {p.icon} {p.text}
                </button>
              ))}
            </div>
          )}
          <textarea
            className="w-full bg-[var(--panel2)] rounded-lg p-3 text-sm border border-[var(--line)] focus:border-[var(--acc)] outline-none resize-none"
            rows={2}
            placeholder="또는 의제를 직접 입력..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </div>

        {/* 기능 특성 태그 */}
        <div className="flex flex-wrap gap-1.5">
          {[
            '👑 임금 발언', '⚡ 천명 강림', '🎲 운명 주사위',
            '🔄 자동 진행', '📜 토론 기록',
          ].map((tag) => (
            <span key={tag} className="text-[10px] px-2 py-1 rounded-full border border-[var(--line)] text-[var(--muted)]">
              {tag}
            </span>
          ))}
        </div>

        {/* 시작 버튼 */}
        <button
          onClick={handleStart}
          disabled={selectedIds.size < 2 || !topic.trim() || loading}
          className="w-full py-3 rounded-xl font-semibold text-sm transition-all border-0"
          style={{
            background:
              selectedIds.size >= 2 && topic.trim()
                ? 'linear-gradient(135deg, #6a9eff, #a07aff)'
                : 'var(--panel2)',
            color: selectedIds.size >= 2 && topic.trim() ? '#fff' : 'var(--muted)',
            opacity: loading ? 0.6 : 1,
            cursor: selectedIds.size >= 2 && topic.trim() && !loading ? 'pointer' : 'not-allowed',
          }}
        >
          {loading ? '소집 중...' : `🏛 의정 시작 (${selectedIds.size}명 등정)`}
        </button>
      </div>
    );
  }

  // ═══════════════════
  //   렌더링: 의정 진행 중
  // ═══════════════════

  const officials = session?.officials || [];
  const messages = session?.messages || [];

  return (
    <div className="space-y-3">
      {/* 상단 컨트롤바 */}
      <div className="flex items-center justify-between flex-wrap gap-2 bg-[var(--panel)] rounded-xl px-4 py-2 border border-[var(--line)]">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold">🏛 조정 의정</span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--acc)]20 text-[var(--acc)] border border-[var(--acc)]30">
            {session?.round || 0}회차
          </span>
          {session?.phase === 'concluded' && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-900/40 text-green-400 border border-green-800">
              종료됨
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setShowDecree(!showDecree)}
            className="text-xs px-2.5 py-1 rounded-lg border border-amber-600/40 text-amber-400 hover:bg-amber-900/20 transition"
            title="천명 강림 — 상위 시점 개입"
          >
            ⚡ 천명
          </button>
          <button
            onClick={handleDice}
            disabled={diceRolling || loading}
            className="text-xs px-2.5 py-1 rounded-lg border border-purple-600/40 text-purple-400 hover:bg-purple-900/20 transition"
            title="운명 주사위 — 무작위 이벤트"
          >
            🎲 {diceRolling ? '...' : '주사위'}
          </button>
          <button
            onClick={() => setAutoPlay(!autoPlay)}
            className={`text-xs px-2.5 py-1 rounded-lg border transition ${autoPlay
              ? 'border-green-600/40 text-green-400 bg-green-900/20'
              : 'border-[var(--line)] text-[var(--muted)] hover:text-[var(--text)]'
              }`}
          >
            {autoPlay ? '⏸ 일시정지' : '▶ 자동'}
          </button>
          {session?.phase !== 'concluded' && (
            <button
              onClick={handleConclude}
              className="text-xs px-2.5 py-1 rounded-lg border border-[var(--line)] text-[var(--muted)] hover:text-[var(--warn)] hover:border-[var(--warn)]40 transition"
            >
              📋 산조
            </button>
          )}
          <button
            onClick={handleReset}
            className="text-xs px-2 py-1 rounded-lg border border-red-900/40 text-red-400/70 hover:text-red-400 transition"
          >
            ✕
          </button>
        </div>
      </div>

      {/* 천명 강림 패널 */}
      {showDecree && (
        <div
          className="bg-gradient-to-br from-amber-950/40 to-purple-950/30 rounded-xl p-4 border border-amber-700/30"
          style={{ animation: 'fadeIn .3s' }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-bold text-amber-400">⚡ 천명 강림 — 상위 시점</span>
            <button onClick={() => setShowDecree(false)} className="text-xs text-[var(--muted)]">
              ✕
            </button>
          </div>
          <p className="text-[10px] text-amber-300/60 mb-2">
            천명을 내려 토론의 흐름을 바꾸면 모든 관원이 이에 반응합니다
          </p>
          <div className="flex gap-2">
            <input
              value={decreeInput}
              onChange={(e) => setDecreeInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleDecree()}
              placeholder="예: 갑자기 예산이 두 배로 늘어났습니다..."
              className="flex-1 bg-black/30 rounded-lg px-3 py-1.5 text-sm border border-amber-800/40 outline-none focus:border-amber-600"
            />
            <button
              onClick={handleDecree}
              disabled={!decreeInput.trim()}
              className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-amber-600 to-purple-600 text-white text-xs font-semibold disabled:opacity-40"
            >
              하지
            </button>
          </div>
        </div>
      )}

      {/* 운명 주사위 결과 */}
      {diceResult && (
        <div
          className="bg-purple-950/40 rounded-lg px-3 py-2 border border-purple-700/30 text-xs text-purple-300 flex items-center gap-2"
          style={{ animation: 'fadeIn .3s' }}
        >
          <span className="text-lg">🎲</span>
          {diceResult}
        </div>
      )}

      {/* 천명 강림 섬광 효과 */}
      {decreeFlash && (
        <div
          className="fixed inset-0 pointer-events-none z-50"
          style={{
            background: 'radial-gradient(circle, rgba(255,200,50,0.3), transparent 70%)',
            animation: 'fadeOut .8s forwards',
          }}
        />
      )}

      {/* 의제 */}
      <div className="text-xs text-center text-[var(--muted)] py-1">
        📜 {session?.topic || ''}
      </div>

      {/* 메인 콘텐츠: 조정 배치 + 채팅 기록 */}
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-3">
        {/* 좌측: 조정 시각화 */}
        <div className="bg-[var(--panel)] rounded-xl p-3 border border-[var(--line)] relative overflow-hidden min-h-[320px]">
          {/* 어좌 */}
          <div className="text-center mb-2">
            <div className="inline-block px-3 py-1 rounded-lg bg-gradient-to-b from-amber-800/40 to-amber-950/40 border border-amber-700/30">
              <span className="text-lg">👑</span>
              <div className="text-[10px] text-amber-400/80">어 좌</div>
            </div>
          </div>

          {/* 관원 위치 */}
          <div className="relative" style={{ minHeight: 250 }}>
            {/* 좌측 라벨 */}
            <div className="absolute left-0 top-0 text-[9px] text-[var(--muted)] opacity-50">3사</div>
            <div className="absolute right-0 top-0 text-[9px] text-[var(--muted)] opacity-50">6조</div>

            {officials.map((o) => {
              const pos = COURT_POSITIONS[o.id] || { x: 50, y: 50 };
              const color = OFFICIAL_COLORS[o.id] || '#6a9eff';
              const isSpeaking = speakingId === o.id;
              const emotion = emotions[o.id] || 'neutral';

              return (
                <div
                  key={o.id}
                  className="absolute transition-all duration-500"
                  style={{
                    left: `${pos.x}%`,
                    top: `${pos.y}%`,
                    transform: 'translate(-50%, -50%)',
                  }}
                >
                  {/* 발언 광원 */}
                  {isSpeaking && (
                    <div
                      className="absolute -inset-2 rounded-full"
                      style={{
                        background: `radial-gradient(circle, ${color}40, transparent)`,
                        animation: 'pulse 1s infinite',
                      }}
                    />
                  )}
                  {/* 아바타 */}
                  <div
                    className="relative w-10 h-10 rounded-full flex items-center justify-center text-lg border-2 transition-all"
                    style={{
                      borderColor: isSpeaking ? color : color + '40',
                      background: isSpeaking ? color + '30' : color + '10',
                      transform: isSpeaking ? 'scale(1.2)' : 'scale(1)',
                      boxShadow: isSpeaking ? `0 0 16px ${color}50` : 'none',
                    }}
                  >
                    {o.emoji}
                    {/* 감정 버블 */}
                    {EMOTION_EMOJI[emotion] && (
                      <span
                        className="absolute -top-1 -right-1 text-xs"
                        style={{ animation: 'bounceIn .3s' }}
                      >
                        {EMOTION_EMOJI[emotion]}
                      </span>
                    )}
                  </div>
                  {/* 이름 */}
                  <div
                    className="text-[9px] text-center mt-0.5 whitespace-nowrap"
                    style={{ color: isSpeaking ? color : 'var(--muted)' }}
                  >
                    {o.name}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 우측: 채팅 기록 */}
        <div className="bg-[var(--panel)] rounded-xl border border-[var(--line)] flex flex-col" style={{ maxHeight: 500 }}>
          {/* 메시지 목록 */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2" style={{ minHeight: 200 }}>
            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} officials={officials} />
            ))}
            {loading && (
              <div className="text-xs text-[var(--muted)] text-center py-2" style={{ animation: 'pulse 1.5s infinite' }}>
                🏛 군신들이 생각 중입니다...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 임금 입력란 */}
          {session?.phase !== 'concluded' && (
            <div className="border-t border-[var(--line)] p-2 flex gap-2">
              <input
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleEmperor()}
                placeholder="과인이 한 마디 하노라..."
                className="flex-1 bg-[var(--panel2)] rounded-lg px-3 py-1.5 text-sm border border-[var(--line)] outline-none focus:border-amber-600"
              />
              <button
                onClick={handleEmperor}
                disabled={!userInput.trim() || loading}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold border-0 disabled:opacity-40"
                style={{
                  background: userInput.trim() ? 'linear-gradient(135deg, #e8a040, #f5c842)' : 'var(--panel2)',
                  color: userInput.trim() ? '#000' : 'var(--muted)',
                }}
              >
                👑 발언
              </button>
              <button
                onClick={() => handleAdvance()}
                disabled={loading}
                className="px-3 py-1.5 rounded-lg text-xs border border-[var(--acc)]40 text-[var(--acc)] hover:bg-[var(--acc)]10 disabled:opacity-40 transition"
              >
                ▶ 다음 회차
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 메시지 버블 ──

function MessageBubble({
  msg,
  officials,
}: {
  msg: CourtMessage;
  officials: Array<{ id: string; name: string; emoji: string }>;
}) {
  const color = OFFICIAL_COLORS[msg.official_id || ''] || '#6a9eff';
  const official = officials.find((o) => o.id === msg.official_id);

  if (msg.type === 'system') {
    return (
      <div className="text-center text-[10px] text-[var(--muted)] py-1 border-b border-[var(--line)] border-dashed">
        {msg.content}
      </div>
    );
  }

  if (msg.type === 'scene_note') {
    return (
      <div className="text-center text-[10px] text-purple-400/80 py-1 italic">
        ✦ {msg.content} ✦
      </div>
    );
  }

  if (msg.type === 'emperor') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-gradient-to-br from-amber-900/40 to-amber-800/20 rounded-xl px-3 py-2 border border-amber-700/30">
          <div className="text-[10px] text-amber-400 mb-0.5">👑 임금</div>
          <div className="text-sm">{msg.content}</div>
        </div>
      </div>
    );
  }

  if (msg.type === 'decree') {
    return (
      <div className="text-center py-2">
        <div className="inline-block bg-gradient-to-r from-amber-900/30 via-purple-900/30 to-amber-900/30 rounded-lg px-4 py-2 border border-amber-600/30">
          <div className="text-xs text-amber-400 font-bold">⚡ 천명 강림</div>
          <div className="text-sm mt-0.5">{msg.content}</div>
        </div>
      </div>
    );
  }

  // 관원 메시지
  return (
    <div className="flex gap-2 items-start" style={{ animation: 'fadeIn .4s' }}>
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-sm flex-shrink-0 border"
        style={{ borderColor: color + '60', background: color + '15' }}
      >
        {official?.emoji || '💬'}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="text-[11px] font-semibold" style={{ color }}>
            {msg.official_name || '관원'}
          </span>
          {msg.emotion && EMOTION_EMOJI[msg.emotion] && (
            <span className="text-xs">{EMOTION_EMOJI[msg.emotion]}</span>
          )}
        </div>
        <div className="text-sm leading-relaxed">
          {msg.content?.split(/(\*[^*]+\*)/).map((part, i) => {
            if (part.startsWith('*') && part.endsWith('*')) {
              return (
                <span key={i} className="text-[var(--muted)] italic text-xs">
                  {part.slice(1, -1)}
                </span>
              );
            }
            return <span key={i}>{part}</span>;
          })}
        </div>
      </div>
    </div>
  );
}
