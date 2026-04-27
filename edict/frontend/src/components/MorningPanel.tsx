import { useEffect, useState, useRef } from 'react';
import { useStore } from '../store';
import { api } from '../api';
import type { SubConfig, MorningNewsItem } from '../api';

const CAT_META: Record<string, { icon: string; color: string; desc: string }> = {
  '정치': { icon: '🏛️', color: '#6a9eff', desc: '글로벌 정치 동향' },
  '군사': { icon: '⚔️', color: '#ff5270', desc: '군사 및 분쟁 동향' },
  '경제': { icon: '💹', color: '#2ecc8a', desc: '경제와 시장' },
  'AI 대형 모델': { icon: '🤖', color: '#a07aff', desc: 'AI 및 대형 모델 동향' },
};

const DEFAULT_CATS = ['정치', '군사', '경제', 'AI 대형 모델'];

export default function MorningPanel() {
  const morningBrief = useStore((s) => s.morningBrief);
  const subConfig = useStore((s) => s.subConfig);
  const loadMorning = useStore((s) => s.loadMorning);
  const loadSubConfig = useStore((s) => s.loadSubConfig);
  const toast = useStore((s) => s.toast);

  const [showConfig, setShowConfig] = useState(false);
  const [localConfig, setLocalConfig] = useState<SubConfig | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshLabel, setRefreshLabel] = useState('⟳ 즉시 수집');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadMorning();
  }, [loadMorning]);

  useEffect(() => {
    if (subConfig) setLocalConfig(JSON.parse(JSON.stringify(subConfig)));
  }, [subConfig]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const refreshNews = async () => {
    setRefreshing(true);
    setRefreshLabel('⟳ 수집 중…');
    let lastDate: string | null = null;
    try {
      lastDate = morningBrief?.generated_at || null;
    } catch { /* */ }

    try {
      await api.refreshMorning();
      toast('수집을 시작했습니다. 자동으로 갱신 여부를 확인합니다.', 'ok');
      let count = 0;
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        count++;
        if (count > 24) {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          setRefreshing(false);
          setRefreshLabel('⟳ 즉시 수집');
          toast('수집 시간이 초과되었습니다. 다시 시도하세요.', 'err');
          return;
        }
        try {
          const fresh = await api.morningBrief();
          if (fresh.generated_at && fresh.generated_at !== lastDate) {
            clearInterval(pollRef.current!);
            pollRef.current = null;
            setRefreshing(false);
            setRefreshLabel('⟳ 즉시 수집');
            loadMorning();
            toast('✅ 조보 요약이 업데이트되었습니다', 'ok');
          } else {
            setRefreshLabel(`⟳ 수집 중… (${count * 5}s)`);
          }
        } catch { /* */ }
      }, 5000);
    } catch {
      toast('요청 실패', 'err');
      setRefreshing(false);
      setRefreshLabel('⟳ 즉시 수집');
    }
  };

  // Config helpers
  const toggleCat = (name: string) => {
    if (!localConfig) return;
    const cats = [...(localConfig.categories || [])];
    const existing = cats.find((c) => c.name === name);
    if (existing) existing.enabled = !existing.enabled;
    else cats.push({ name, enabled: true });
    setLocalConfig({ ...localConfig, categories: cats });
  };

  const addKeyword = (kw: string) => {
    if (!localConfig || !kw) return;
    const kws = [...(localConfig.keywords || [])];
    if (!kws.includes(kw)) kws.push(kw);
    setLocalConfig({ ...localConfig, keywords: kws });
  };

  const removeKeyword = (i: number) => {
    if (!localConfig) return;
    const kws = [...(localConfig.keywords || [])];
    kws.splice(i, 1);
    setLocalConfig({ ...localConfig, keywords: kws });
  };

  const addFeed = (name: string, url: string, category: string) => {
    if (!localConfig || !name || !url) {
      toast('소스 이름과 URL을 입력하세요', 'err');
      return;
    }
    const feeds = [...(localConfig.custom_feeds || [])];
    feeds.push({ name, url, category });
    setLocalConfig({ ...localConfig, custom_feeds: feeds });
  };

  const removeFeed = (i: number) => {
    if (!localConfig) return;
    const feeds = [...(localConfig.custom_feeds || [])];
    feeds.splice(i, 1);
    setLocalConfig({ ...localConfig, custom_feeds: feeds });
  };

  const saveConfig = async () => {
    if (!localConfig) return;
    try {
      const r = await api.saveMorningConfig(localConfig);
      if (r.ok) {
        toast('구독 설정을 저장했습니다', 'ok');
        loadSubConfig();
      } else {
        toast(r.error || '저장 실패', 'err');
      }
    } catch {
      toast('서버 연결 실패', 'err');
    }
  };

  const enabledSet = localConfig
    ? new Set((localConfig.categories || []).filter((c) => c.enabled).map((c) => c.name))
    : new Set(DEFAULT_CATS);
  const userKws = (localConfig?.keywords || []).map((k) => k.toLowerCase());

  const cats = morningBrief?.categories || {};
  const dateStr = morningBrief?.date
    ? morningBrief.date.replace(/(\d{4})(\d{2})(\d{2})/, '$1년 $2월 $3일')
    : '';
  const totalNews = Object.values(cats).flat().length;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 4 }}>🌅 조보 요약</div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>
            {dateStr && `${dateStr} | `}
            {morningBrief?.generated_at && `수집 시각 ${morningBrief.generated_at} | `}
            총 {totalNews}건
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-g"
            onClick={() => setShowConfig(!showConfig)}
            style={{ fontSize: 12, padding: '6px 14px' }}
          >
            ⚙ 구독 설정
          </button>
          <button
            className="tpl-go"
            disabled={refreshing}
            onClick={refreshNews}
            style={{ fontSize: 12, padding: '6px 14px' }}
          >
            {refreshLabel}
          </button>
        </div>
      </div>

      {/* Subscription Config */}
      {showConfig && localConfig && (
        <SubConfigPanel
          config={localConfig}
          enabledSet={enabledSet}
          onToggleCat={toggleCat}
          onAddKeyword={addKeyword}
          onRemoveKeyword={removeKeyword}
          onAddFeed={addFeed}
          onRemoveFeed={removeFeed}
          onSave={saveConfig}
          onSetWebhook={(v) => setLocalConfig({ ...localConfig, feishu_webhook: v })}
        />
      )}

      {/* News */}
      {!Object.keys(cats).length ? (
        <div className="mb-empty">데이터가 없습니다. 오른쪽 상단의 "즉시 수집" 버튼으로 오늘 요약을 가져오세요.</div>
      ) : (
        <div className="mb-cats">
          {Object.entries(cats).map(([cat, items]) => {
            if (!enabledSet.has(cat)) return null;
            const meta = CAT_META[cat] || { icon: '📰', color: 'var(--acc)', desc: cat };
            const scored = (items as MorningNewsItem[])
              .map((item) => {
                const text = ((item.title || '') + (item.summary || '')).toLowerCase();
                const kwHits = userKws.filter((k) => text.includes(k)).length;
                return { ...item, _kwHits: kwHits };
              })
              .sort((a, b) => b._kwHits - a._kwHits);

            return (
              <div className="mb-cat" key={cat}>
                <div className="mb-cat-hdr">
                  <span className="mb-cat-icon">{meta.icon}</span>
                  <span className="mb-cat-name" style={{ color: meta.color }}>{cat}</span>
                  <span className="mb-cat-cnt">{scored.length}건</span>
                </div>
                <div className="mb-news-list">
                  {!scored.length ? (
                    <div className="mb-empty" style={{ padding: 16 }}>뉴스 없음</div>
                  ) : (
                    scored.map((item, i) => {
                      const hasImg = !!(item.image && item.image.startsWith('http'));
                      return (
                        <div
                          className="mb-card"
                          key={i}
                          onClick={() => window.open(item.link, '_blank')}
                        >
                          <div className="mb-img">
                            {hasImg ? (
                              <img
                                src={item.image}
                                onError={(e) => {
                                  (e.target as HTMLImageElement).style.display = 'none';
                                }}
                                loading="lazy"
                                alt=""
                              />
                            ) : (
                              <span>{meta.icon}</span>
                            )}
                          </div>
                          <div className="mb-info">
                            <div className="mb-headline">
                              {item.title}
                              {item._kwHits > 0 && (
                                <span
                                  style={{
                                    fontSize: 9,
                                    padding: '1px 5px',
                                    borderRadius: 999,
                                    background: '#a07aff22',
                                    color: '#a07aff',
                                    border: '1px solid #a07aff44',
                                    marginLeft: 4,
                                  }}
                                >
                                  ⭐ 관심
                                </span>
                              )}
                            </div>
                            <div className="mb-summary">{item.summary || item.desc || ''}</div>
                            <div className="mb-meta">
                              <span className="mb-source">📡 {item.source || ''}</span>
                              {item.pub_date && (
                                <span className="mb-time">{item.pub_date.substring(0, 16)}</span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SubConfigPanel({
  config,
  enabledSet,
  onToggleCat,
  onAddKeyword,
  onRemoveKeyword,
  onAddFeed,
  onRemoveFeed,
  onSave,
  onSetWebhook,
}: {
  config: SubConfig;
  enabledSet: Set<string>;
  onToggleCat: (name: string) => void;
  onAddKeyword: (kw: string) => void;
  onRemoveKeyword: (i: number) => void;
  onAddFeed: (name: string, url: string, cat: string) => void;
  onRemoveFeed: (i: number) => void;
  onSave: () => void;
  onSetWebhook: (v: string) => void;
}) {
  const [newKw, setNewKw] = useState('');
  const [feedName, setFeedName] = useState('');
  const [feedUrl, setFeedUrl] = useState('');
  const [feedCat, setFeedCat] = useState(DEFAULT_CATS[0]);

  const allCats = [...DEFAULT_CATS];
  (config.categories || []).forEach((c) => {
    if (!allCats.includes(c.name)) allCats.push(c.name);
  });

  return (
    <div className="sub-config" style={{ marginBottom: 20, padding: 16, background: 'var(--panel2)', borderRadius: 12, border: '1px solid var(--line)' }}>
      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>⚙ 구독 설정</div>

      {/* Categories */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>구독 카테고리</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {allCats.map((cat) => {
            const meta = CAT_META[cat] || { icon: '📰', color: 'var(--acc)', desc: cat };
            const on = enabledSet.has(cat);
            return (
              <div
                key={cat}
                className={`sub-cat ${on ? 'active' : ''}`}
                onClick={() => onToggleCat(cat)}
                style={{ cursor: 'pointer', padding: '6px 12px', borderRadius: 8, border: `1px solid ${on ? 'var(--acc)' : 'var(--line)'}`, display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <span>{meta.icon}</span>
                <span style={{ fontSize: 12 }}>{cat}</span>
                {on && <span style={{ fontSize: 10, color: 'var(--ok)' }}>✓</span>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Keywords */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>관심 키워드</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
          {(config.keywords || []).map((kw, i) => (
            <span key={i} className="sub-kw" style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: 'var(--bg)', border: '1px solid var(--line)' }}>
              {kw}
              <span style={{ cursor: 'pointer', marginLeft: 4, color: 'var(--danger)' }} onClick={() => onRemoveKeyword(i)}>✕</span>
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            type="text"
            value={newKw}
            onChange={(e) => setNewKw(e.target.value)}
            placeholder="키워드 입력"
            onKeyDown={(e) => { if (e.key === 'Enter') { onAddKeyword(newKw.trim()); setNewKw(''); } }}
            style={{ flex: 1, padding: '6px 10px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--text)', fontSize: 12, outline: 'none' }}
          />
          <button className="btn btn-g" onClick={() => { onAddKeyword(newKw.trim()); setNewKw(''); }} style={{ fontSize: 11, padding: '4px 12px' }}>
            추가
          </button>
        </div>
      </div>

      {/* Custom Feeds */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>사용자 지정 소스</div>
        {(config.custom_feeds || []).map((f, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4, fontSize: 11 }}>
            <span style={{ fontWeight: 600 }}>{f.name}</span>
            <span style={{ color: 'var(--muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.url}</span>
            <span style={{ color: 'var(--acc)' }}>{f.category}</span>
            <span style={{ cursor: 'pointer', color: 'var(--danger)' }} onClick={() => onRemoveFeed(i)}>✕</span>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
          <input placeholder="소스 이름" value={feedName} onChange={(e) => setFeedName(e.target.value)}
            style={{ width: 100, padding: '6px 8px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--text)', fontSize: 11, outline: 'none' }} />
          <input placeholder="RSS / URL" value={feedUrl} onChange={(e) => setFeedUrl(e.target.value)}
            style={{ flex: 1, padding: '6px 8px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--text)', fontSize: 11, outline: 'none' }} />
          <select value={feedCat} onChange={(e) => setFeedCat(e.target.value)}
            style={{ padding: '6px 8px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--text)', fontSize: 11, outline: 'none' }}>
            {allCats.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <button className="btn btn-g" onClick={() => { onAddFeed(feedName, feedUrl, feedCat); setFeedName(''); setFeedUrl(''); }} style={{ fontSize: 11, padding: '4px 12px' }}>
            추가
          </button>
        </div>
      </div>

      {/* Feishu Webhook */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>피슈 Webhook</div>
        <input
          type="text"
          value={config.feishu_webhook || ''}
          onChange={(e) => onSetWebhook(e.target.value)}
          placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
          style={{ width: '100%', padding: '8px 10px', background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 6, color: 'var(--text)', fontSize: 12, outline: 'none' }}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button className="tpl-go" onClick={onSave} style={{ fontSize: 12, padding: '6px 16px' }}>
          💾 설정 저장
        </button>
      </div>
    </div>
  );
}
