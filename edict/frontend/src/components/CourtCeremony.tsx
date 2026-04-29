import { useEffect, useState } from 'react';
import { useStore, isEdict } from '../store';

export default function CourtCeremony() {
  const liveStatus = useStore((s) => s.liveStatus);
  const [show, setShow] = useState(false);
  const [out, setOut] = useState(false);

  useEffect(() => {
    const lastOpen = localStorage.getItem('openclaw_court_date');
    const today = new Date().toISOString().substring(0, 10);
    const pref = JSON.parse(localStorage.getItem('openclaw_court_pref') || '{"enabled":true}');
    if (!pref.enabled || lastOpen === today) return;
    localStorage.setItem('openclaw_court_date', today);
    setShow(true);
    const timer = setTimeout(() => skip(), 3500);
    return () => clearTimeout(timer);
  }, []);

  const skip = () => {
    setOut(true);
    setTimeout(() => setShow(false), 500);
  };

  if (!show) return null;

  const tasks = liveStatus?.tasks || [];
  const jjc = tasks.filter(isEdict);
  const pending = jjc.filter((t) => !['Completed', 'Cancelled'].includes(t.state)).length;
  const done = jjc.filter((t) => t.state === 'Completed').length;
  const overdue = jjc.filter(
    (t) => t.state !== 'Completed' && t.state !== 'Cancelled' && t.eta && new Date(t.eta.replace(' ', 'T')) < new Date()
  ).length;

  const d = new Date();
  const days = ['일', '월', '화', '수', '목', '금', '토'];
  const dateStr = `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 · ${days[d.getDay()]}요일`;

  return (
    <div className={`ceremony-bg${out ? ' out' : ''}`} onClick={skip}>
      <div className="crm-glow" />
      <div className="crm-line1 in">🏛 조회 시작</div>
      <div className="crm-line2 in">보고할 사안은 올리고, 없으면 정무를 마칩니다</div>
      <div className="crm-line3 in">
        진행 대기 {pending}건 · 완료 {done}건{overdue > 0 && ` · ⚠ 지연 ${overdue}건`}
      </div>
      <div className="crm-date in">{dateStr}</div>
      <div className="crm-skip">아무 곳이나 클릭해 건너뛰기</div>
    </div>
  );
}
