import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { api, RemoteSkillItem } from '../api';

// 커뮤니티 인기 Skills 소스 빠른 선택 목록
const COMMUNITY_SOURCES = [
  {
    label: 'obra/superpowers',
    emoji: '⚡',
    stars: '66.9k',
    desc: '완전한 개발 워크플로우 스킬 세트',
    skills: [
      { name: 'brainstorming', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/brainstorming/SKILL.md' },
      { name: 'test-driven-development', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/test-driven-development/SKILL.md' },
      { name: 'systematic-debugging', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/systematic-debugging/SKILL.md' },
      { name: 'subagent-driven-development', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/subagent-driven-development/SKILL.md' },
      { name: 'writing-plans', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/writing-plans/SKILL.md' },
      { name: 'executing-plans', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/executing-plans/SKILL.md' },
      { name: 'requesting-code-review', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/requesting-code-review/SKILL.md' },
      { name: 'root-cause-tracing', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/root-cause-tracing/SKILL.md' },
      { name: 'verification-before-completion', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/verification-before-completion/SKILL.md' },
      { name: 'dispatching-parallel-agents', url: 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/dispatching-parallel-agents/SKILL.md' },
    ],
  },
  {
    label: 'anthropics/skills',
    emoji: '🏛️',
    stars: '공식',
    desc: 'Anthropic 공식 스킬 라이브러리',
    skills: [
      { name: 'docx', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/docx/SKILL.md' },
      { name: 'pdf', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/pdf/SKILL.md' },
      { name: 'xlsx', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/xlsx/SKILL.md' },
      { name: 'pptx', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/pptx/SKILL.md' },
      { name: 'mcp-builder', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/mcp-builder/SKILL.md' },
      { name: 'frontend-design', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md' },
      { name: 'web-artifacts-builder', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/web-artifacts-builder/SKILL.md' },
      { name: 'webapp-testing', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/webapp-testing/SKILL.md' },
      { name: 'algorithmic-art', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/algorithmic-art/SKILL.md' },
      { name: 'canvas-design', url: 'https://raw.githubusercontent.com/anthropics/skills/main/skills/canvas-design/SKILL.md' },
    ],
  },
  {
    label: 'ComposioHQ/awesome-claude-skills',
    emoji: '🌐',
    stars: '39.2k',
    desc: '100+ 커뮤니티 엄선 스킬',
    skills: [
      { name: 'github-integration', url: 'https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/github-integration/SKILL.md' },
      { name: 'data-analysis', url: 'https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/data-analysis/SKILL.md' },
      { name: 'code-review', url: 'https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/code-review/SKILL.md' },
    ],
  },
];

export default function SkillsConfig() {
  const agentConfig = useStore((s) => s.agentConfig);
  const loadAgentConfig = useStore((s) => s.loadAgentConfig);
  const toast = useStore((s) => s.toast);

  // 로컬 스킬 상태
  const [skillModal, setSkillModal] = useState<{ agentId: string; name: string; content: string; path: string } | null>(null);
  const [addForm, setAddForm] = useState<{ agentId: string; agentLabel: string } | null>(null);
  const [formData, setFormData] = useState({ name: '', desc: '', trigger: '' });
  const [submitting, setSubmitting] = useState(false);

  // 메인 탭 전환
  const [activeTab, setActiveTab] = useState<'local' | 'remote'>('local');

  // 원격 스킬 상태
  const [remoteSkills, setRemoteSkills] = useState<RemoteSkillItem[]>([]);
  const [remoteLoading, setRemoteLoading] = useState(false);
  const [addRemoteForm, setAddRemoteForm] = useState(false);
  const [remoteFormData, setRemoteFormData] = useState({ agentId: '', skillName: '', sourceUrl: '', description: '' });
  const [remoteSubmitting, setRemoteSubmitting] = useState(false);
  const [updatingSkill, setUpdatingSkill] = useState<string | null>(null);
  const [removingSkill, setRemovingSkill] = useState<string | null>(null);
  const [quickPickSource, setQuickPickSource] = useState<(typeof COMMUNITY_SOURCES)[0] | null>(null);
  const [quickPickAgent, setQuickPickAgent] = useState('');

  useEffect(() => {
    loadAgentConfig();
  }, [loadAgentConfig]);

  useEffect(() => {
    if (activeTab === 'remote') loadRemoteSkills();
  }, [activeTab]);

  const loadRemoteSkills = async () => {
    setRemoteLoading(true);
    try {
      const r = await api.remoteSkillsList();
      if (r.ok) setRemoteSkills(r.remoteSkills || []);
    } catch {
      toast('원격 스킬 목록 로딩 실패', 'err');
    }
    setRemoteLoading(false);
  };

  const openSkill = async (agentId: string, skillName: string) => {
    setSkillModal({ agentId, name: skillName, content: '⟳ 로딩 중…', path: '' });
    try {
      const r = await api.skillContent(agentId, skillName);
      if (r.ok) {
        setSkillModal({ agentId, name: skillName, content: r.content || '', path: r.path || '' });
      } else {
        setSkillModal({ agentId, name: skillName, content: '❌ ' + (r.error || '읽기 실패'), path: '' });
      }
    } catch {
      setSkillModal({ agentId, name: skillName, content: '❌ 서버 연결 실패', path: '' });
    }
  };

  const openAddForm = (agentId: string, agentLabel: string) => {
    setAddForm({ agentId, agentLabel });
    setFormData({ name: '', desc: '', trigger: '' });
  };

  const submitAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addForm || !formData.name) return;
    setSubmitting(true);
    try {
      const r = await api.addSkill(addForm.agentId, formData.name, formData.desc, formData.trigger);
      if (r.ok) {
        toast(`✅ 스킬 ${formData.name}이(가) ${addForm.agentLabel}에 추가되었습니다`, 'ok');
        setAddForm(null);
        loadAgentConfig();
      } else {
        toast(r.error || '추가 실패', 'err');
      }
    } catch {
      toast('서버 연결 실패', 'err');
    }
    setSubmitting(false);
  };

  const submitAddRemote = async (e: React.FormEvent) => {
    e.preventDefault();
    const { agentId, skillName, sourceUrl, description } = remoteFormData;
    if (!agentId || !skillName || !sourceUrl) return;
    setRemoteSubmitting(true);
    try {
      const r = await api.addRemoteSkill(agentId, skillName, sourceUrl, description);
      if (r.ok) {
        toast(`✅ 원격 스킬 ${skillName}이(가) ${agentId}에 추가되었습니다`, 'ok');
        setAddRemoteForm(false);
        setRemoteFormData({ agentId: '', skillName: '', sourceUrl: '', description: '' });
        loadRemoteSkills();
        loadAgentConfig();
      } else {
        toast(r.error || '추가 실패', 'err');
      }
    } catch {
      toast('서버 연결 실패', 'err');
    }
    setRemoteSubmitting(false);
  };

  const handleUpdate = async (skill: RemoteSkillItem) => {
    const key = `${skill.agentId}/${skill.skillName}`;
    setUpdatingSkill(key);
    try {
      const r = await api.updateRemoteSkill(skill.agentId, skill.skillName);
      if (r.ok) {
        toast(`✅ 스킬 ${skill.skillName}이(가) 업데이트되었습니다`, 'ok');
        loadRemoteSkills();
      } else {
        toast(r.error || '업데이트 실패', 'err');
      }
    } catch {
      toast('서버 연결 실패', 'err');
    }
    setUpdatingSkill(null);
  };

  const handleRemove = async (skill: RemoteSkillItem) => {
    const key = `${skill.agentId}/${skill.skillName}`;
    setRemovingSkill(key);
    try {
      const r = await api.removeRemoteSkill(skill.agentId, skill.skillName);
      if (r.ok) {
        toast(`🗑️ 스킬 ${skill.skillName}이(가) 제거되었습니다`, 'ok');
        loadRemoteSkills();
        loadAgentConfig();
      } else {
        toast(r.error || '제거 실패', 'err');
      }
    } catch {
      toast('서버 연결 실패', 'err');
    }
    setRemovingSkill(null);
  };

  const handleQuickImport = async (skillUrl: string, skillName: string) => {
    if (!quickPickAgent) { toast('먼저 대상 Agent를 선택하세요', 'err'); return; }
    try {
      const r = await api.addRemoteSkill(quickPickAgent, skillName, skillUrl, '');
      if (r.ok) {
        toast(`✅ ${skillName} → ${quickPickAgent}`, 'ok');
        loadRemoteSkills();
        loadAgentConfig();
      } else {
        toast(r.error || '가져오기 실패', 'err');
      }
    } catch {
      toast('서버 연결 실패', 'err');
    }
  };

  if (!agentConfig?.agents) {
    return <div className="empty">로드할 수 없습니다</div>;
  }

  // ── 로컬 스킬 패널 ──
  const localPanel = (
    <div>
      <div className="skills-grid">
        {agentConfig.agents.map((ag) => (
          <div className="sk-card" key={ag.id}>
            <div className="sk-hdr">
              <span className="sk-emoji">{ag.emoji || '🏛️'}</span>
              <span className="sk-name">{ag.label}</span>
              <span className="sk-cnt">{(ag.skills || []).length} 스킬</span>
            </div>
            <div className="sk-list">
              {!(ag.skills || []).length ? (
                <div className="sk-empty">아직 Skills 없음</div>
              ) : (
                (ag.skills || []).map((sk) => (
                  <div className="sk-item" key={sk.name} onClick={() => openSkill(ag.id, sk.name)}>
                    <span className="si-name">📦 {sk.name}</span>
                    <span className="si-desc">{sk.description || '설명 없음'}</span>
                    <span className="si-arrow">›</span>
                  </div>
                ))
              )}
            </div>
            <div className="sk-add" onClick={() => openAddForm(ag.id, ag.label)}>
              ＋ 스킬 추가
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // ── 원격 스킬 패널 ──
  const remotePanel = (
    <div>
      {/* 작업 바 */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <button
          style={{ padding: '8px 18px', background: 'var(--acc)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13 }}
          onClick={() => { setAddRemoteForm(true); setQuickPickSource(null); }}
        >
          ＋ 원격 Skill 추가
        </button>
        <button
          style={{ padding: '8px 14px', background: 'transparent', color: 'var(--acc)', border: '1px solid var(--acc)', borderRadius: 8, cursor: 'pointer', fontSize: 12 }}
          onClick={loadRemoteSkills}
        >
          ⟳ 목록 새로고침
        </button>
        <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 4 }}>
          총 {remoteSkills.length}개 원격 스킬
        </span>
      </div>

      {/* 커뮤니티 빠른 선택 영역 */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', letterSpacing: '.06em', marginBottom: 10 }}>
          🌐 커뮤니티 스킬 출처 — 원클릭 가져오기
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {COMMUNITY_SOURCES.map((src) => (
            <div
              key={src.label}
              onClick={() => setQuickPickSource(quickPickSource?.label === src.label ? null : src)}
              style={{
                padding: '8px 14px',
                background: quickPickSource?.label === src.label ? '#0d1f45' : 'var(--panel)',
                border: `1px solid ${quickPickSource?.label === src.label ? 'var(--acc)' : 'var(--line)'}`,
                borderRadius: 10,
                cursor: 'pointer',
                fontSize: 12,
                transition: 'all .15s',
              }}
            >
              <span style={{ marginRight: 6 }}>{src.emoji}</span>
              <b style={{ color: 'var(--text)' }}>{src.label}</b>
              <span style={{ marginLeft: 6, color: '#f0b429', fontSize: 11 }}>★ {src.stars}</span>
              <span style={{ marginLeft: 8, color: 'var(--muted)' }}>{src.desc}</span>
            </div>
          ))}
        </div>

        {quickPickSource && (
          <div style={{ marginTop: 14, background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
              <span style={{ fontSize: 12, fontWeight: 600 }}>대상 Agent:</span>
              <select
                value={quickPickAgent}
                onChange={(e) => setQuickPickAgent(e.target.value)}
                style={{ padding: '6px 10px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--text)', fontSize: 12 }}
              >
                <option value="">— Agent 선택 —</option>
                {agentConfig.agents.map((ag) => (
                  <option key={ag.id} value={ag.id}>{ag.emoji} {ag.label} ({ag.id})</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 8 }}>
              {quickPickSource.skills.map((sk) => {
                const alreadyAdded = remoteSkills.some((r) => r.skillName === sk.name && r.agentId === quickPickAgent);
                return (
                  <div
                    key={sk.name}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 12px', background: 'var(--panel2)', borderRadius: 8,
                      border: '1px solid var(--line)',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>📦 {sk.name}</div>
                      <div style={{ fontSize: 10, color: 'var(--muted)', wordBreak: 'break-all', maxWidth: 180 }}>{sk.url.split('/').slice(-2).join('/')}</div>
                    </div>
                    {alreadyAdded ? (
                      <span style={{ fontSize: 10, color: '#4caf88', fontWeight: 600 }}>✓ 가져옴</span>
                    ) : (
                      <button
                        onClick={() => handleQuickImport(sk.url, sk.name)}
                        style={{ padding: '4px 10px', background: 'var(--acc)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 11, whiteSpace: 'nowrap' }}
                      >
                        가져오기
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 추가된 원격 스킬 목록 */}
      {remoteLoading ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13 }}>⟳ 로딩 중…</div>
      ) : remoteSkills.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', background: 'var(--panel)', borderRadius: 12, border: '1px dashed var(--line)' }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>🌐</div>
          <div style={{ fontSize: 14, color: 'var(--muted)' }}>아직 원격 스킬이 없습니다</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 6 }}>커뮤니티 스킬 출처에서 빠르게 가져오거나 URL 을 직접 추가하세요</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {remoteSkills.map((sk) => {
            const key = `${sk.agentId}/${sk.skillName}`;
            const isUpdating = updatingSkill === key;
            const isRemoving = removingSkill === key;
            const agInfo = agentConfig.agents.find((a) => a.id === sk.agentId);
            return (
              <div
                key={key}
                style={{
                  background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 12, padding: '14px 18px',
                  display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <span style={{ fontSize: 14, fontWeight: 700 }}>📦 {sk.skillName}</span>
                    <span style={{
                      fontSize: 10, padding: '2px 8px', borderRadius: 999,
                      background: sk.status === 'valid' ? '#0d3322' : '#3d1111',
                      color: sk.status === 'valid' ? '#4caf88' : '#ff5270',
                      fontWeight: 600,
                    }}>
                      {sk.status === 'valid' ? '✓ 유효' : '✗ 파일 누락'}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--panel2)', padding: '2px 8px', borderRadius: 6 }}>
                      {agInfo?.emoji} {agInfo?.label || sk.agentId}
                    </span>
                  </div>
                  {sk.description && (
                    <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>{sk.description}</div>
                  )}
                  <div style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                    <span>🔗 <a href={sk.sourceUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--acc)', textDecoration: 'none' }}>{sk.sourceUrl.length > 60 ? sk.sourceUrl.slice(0, 60) + '…' : sk.sourceUrl}</a></span>
                    <span>📅 {sk.lastUpdated ? sk.lastUpdated.slice(0, 10) : sk.addedAt?.slice(0, 10)}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    onClick={() => openSkill(sk.agentId, sk.skillName)}
                    style={{ padding: '6px 12px', background: 'transparent', color: 'var(--muted)', border: '1px solid var(--line)', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}
                  >
                    보기
                  </button>
                  <button
                    onClick={() => handleUpdate(sk)}
                    disabled={isUpdating}
                    style={{ padding: '6px 12px', background: 'transparent', color: 'var(--acc)', border: '1px solid var(--acc)', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}
                  >
                    {isUpdating ? '⟳' : '갱신'}
                  </button>
                  <button
                    onClick={() => handleRemove(sk)}
                    disabled={isRemoving}
                    style={{ padding: '6px 12px', background: 'transparent', color: '#ff5270', border: '1px solid #ff5270', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}
                  >
                    {isRemoving ? '⟳' : '삭제'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  return (
    <div>
      {/* 메인 탭 전환 */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--line)', paddingBottom: 0 }}>
        {[
          { key: 'local', label: '🏛️ 로컬 스킬', count: agentConfig.agents.reduce((n, a) => n + (a.skills?.length || 0), 0) },
          { key: 'remote', label: '🌐 원격 스킬', count: remoteSkills.length },
        ].map((t) => (
          <div
            key={t.key}
            onClick={() => setActiveTab(t.key as 'local' | 'remote')}
            style={{
              padding: '8px 18px', cursor: 'pointer', fontSize: 13, borderRadius: '8px 8px 0 0',
              fontWeight: activeTab === t.key ? 700 : 400,
              background: activeTab === t.key ? 'var(--panel)' : 'transparent',
              color: activeTab === t.key ? 'var(--text)' : 'var(--muted)',
              border: activeTab === t.key ? '1px solid var(--line)' : '1px solid transparent',
              borderBottom: activeTab === t.key ? '1px solid var(--panel)' : '1px solid transparent',
              position: 'relative', bottom: -1,
              transition: 'all .15s',
            }}
          >
            {t.label}
            {t.count > 0 && (
              <span style={{ marginLeft: 6, fontSize: 10, padding: '1px 6px', borderRadius: 999, background: '#1a2040', color: 'var(--acc)' }}>
                {t.count}
              </span>
            )}
          </div>
        ))}
      </div>

      {activeTab === 'local' ? localPanel : remotePanel}

      {/* Skill Content Modal */}
      {skillModal && (
        <div className="modal-bg open" onClick={() => setSkillModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setSkillModal(null)}>✕</button>
            <div className="modal-body">
              <div style={{ fontSize: 11, color: 'var(--acc)', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>
                {skillModal.agentId.toUpperCase()}
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 16 }}>📦 {skillModal.name}</div>
              <div className="sk-modal-body">
                <div className="sk-md" style={{ whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.7 }}>
                  {skillModal.content}
                </div>
                {skillModal.path && (
                  <div className="sk-path" style={{ fontSize: 10, color: 'var(--muted)', marginTop: 12 }}>
                    📂 {skillModal.path}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 로컬 Add Skill Form Modal */}
      {addForm && (
        <div className="modal-bg open" onClick={() => setAddForm(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setAddForm(null)}>✕</button>
            <div className="modal-body">
              <div style={{ fontSize: 11, color: 'var(--acc)', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>
                {addForm.agentLabel} 에 스킬 추가
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 18 }}>＋ Skill 신규 추가</div>

              <div
                style={{
                  background: 'var(--panel2)',
                  border: '1px solid var(--line)',
                  borderRadius: 10,
                  padding: 14,
                  marginBottom: 18,
                  fontSize: 12,
                  lineHeight: 1.7,
                  color: 'var(--muted)',
                }}
              >
                <b style={{ color: 'var(--text)' }}>📋 Skill 규격 안내</b>
                <br />
                • 스킬 이름은 <b style={{ color: 'var(--text)' }}>소문자 영문 + 하이픈</b> 사용
                <br />
                • 생성 후 SKILL.md 템플릿 파일이 만들어집니다
                <br />
                • 스킬은 agent 가 관련 작업을 받을 때 <b style={{ color: 'var(--text)' }}>자동 활성화</b> 됩니다
              </div>

              <form onSubmit={submitAdd} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    스킬 이름 <span style={{ color: '#ff5270' }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="예: data-analysis, code-review"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData((p) => ({ ...p, name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') }))
                    }
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>스킬 설명</label>
                  <input
                    type="text"
                    placeholder="용도를 한 문장으로 설명"
                    value={formData.desc}
                    onChange={(e) => setFormData((p) => ({ ...p, desc: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>트리거 조건 (선택)</label>
                  <input
                    type="text"
                    placeholder="이 스킬이 활성화되는 조건"
                    value={formData.trigger}
                    onChange={(e) => setFormData((p) => ({ ...p, trigger: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 4 }}>
                  <button type="button" className="btn btn-g" onClick={() => setAddForm(null)} style={{ padding: '8px 20px' }}>
                    취소
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    style={{ padding: '8px 20px', fontSize: 13, background: 'var(--acc)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}
                  >
                    {submitting ? '⟳ 생성 중…' : '📦 스킬 생성'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* 원격 Add Remote Skill Modal */}
      {addRemoteForm && (
        <div className="modal-bg open" onClick={() => setAddRemoteForm(false)}>
          <div className="modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setAddRemoteForm(false)}>✕</button>
            <div className="modal-body">
              <div style={{ fontSize: 11, color: '#a07aff', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>
                원격 스킬 관리
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 18 }}>🌐 원격 Skill 추가</div>

              <div style={{ background: 'var(--panel2)', border: '1px solid var(--line)', borderRadius: 10, padding: 12, marginBottom: 18, fontSize: 11, color: 'var(--muted)', lineHeight: 1.7 }}>
                GitHub Raw URL 지원, 예:<br />
                <code style={{ color: 'var(--acc)', fontSize: 10 }}>https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/brainstorming/SKILL.md</code>
              </div>

              <form onSubmit={submitAddRemote} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>대상 Agent <span style={{ color: '#ff5270' }}>*</span></label>
                  <select
                    required
                    value={remoteFormData.agentId}
                    onChange={(e) => setRemoteFormData((p) => ({ ...p, agentId: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}
                  >
                    <option value="">— Agent 선택 —</option>
                    {agentConfig.agents.map((ag) => (
                      <option key={ag.id} value={ag.id}>{ag.emoji} {ag.label} ({ag.id})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>스킬 이름 <span style={{ color: '#ff5270' }}>*</span></label>
                  <input
                    type="text"
                    required
                    placeholder="예: brainstorming, code-review"
                    value={remoteFormData.skillName}
                    onChange={(e) => setRemoteFormData((p) => ({ ...p, skillName: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>출처 URL <span style={{ color: '#ff5270' }}>*</span></label>
                  <input
                    type="url"
                    required
                    placeholder="https://raw.githubusercontent.com/..."
                    value={remoteFormData.sourceUrl}
                    onChange={(e) => setRemoteFormData((p) => ({ ...p, sourceUrl: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 12, outline: 'none' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 6 }}>설명 (선택)</label>
                  <input
                    type="text"
                    placeholder="용도를 한 문장으로 설명"
                    value={remoteFormData.description}
                    onChange={(e) => setRemoteFormData((p) => ({ ...p, description: e.target.value }))}
                    style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 13, outline: 'none' }}
                  />
                </div>
                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 4 }}>
                  <button type="button" className="btn btn-g" onClick={() => setAddRemoteForm(false)} style={{ padding: '8px 20px' }}>취소</button>
                  <button
                    type="submit"
                    disabled={remoteSubmitting}
                    style={{ padding: '8px 20px', fontSize: 13, background: '#a07aff', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}
                  >
                    {remoteSubmitting ? '⟳ 다운로드 중…' : '🌐 원격 스킬 추가'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
