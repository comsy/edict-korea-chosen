import { useState } from 'react';

interface Props {
  title: string;
  message: string;
  okLabel: string;
  okClass?: string;
  onOk: (reason: string) => void;
  onCancel: () => void;
}

export default function ConfirmDialog({ title, message, okLabel, okClass, onOk, onCancel }: Props) {
  const [reason, setReason] = useState('');

  return (
    <div className="confirm-bg open" onClick={onCancel}>
      <div className="confirm-box" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-title" dangerouslySetInnerHTML={{ __html: title }} />
        <div className="confirm-msg" dangerouslySetInnerHTML={{ __html: message }} />
        <textarea
          className="confirm-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="사유 입력 (선택)"
          rows={2}
        />
        <div className="confirm-btns">
          <button className="btn btn-g" onClick={onCancel}>취소</button>
          <button className={`btn btn-action ${okClass || ''}`} onClick={() => onOk(reason)}>
            {okLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
