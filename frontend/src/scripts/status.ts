// 「行った」「たぶん行かない」ボタンの挙動（ISS-475）
//
// 真実の源は Google Sheets。読み書きは GAS の Web App（gas/Code.gs）経由。
// 静的サイトなのでページには状態が焼き込まれていない。開いたときに GAS から全件を取り、
// ボタンの見た目に反映する（別の端末で押した分もここで揃う）。
//
// 合言葉トークンは目隠し（ISS-518）を通った端末だけが持っている（localStorage の tg-token）。
// 公開HTMLには埋め込まない。
//
// 失敗は必ず画面に出す（黙って落とすと「押したのに次の週も出てきた」になる）。

type Status = 'visited' | 'skipped' | 'none';

const LABEL: Record<Status, string> = {
  visited: '行った',
  skipped: 'たぶん行かない',
  none: '未設定',
};

const state = new Map<string, Status>();
let initialized = false;

function apiUrl(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="tg-status-api"]')?.content.trim() ?? '';
}

function token(): string {
  const w = window as unknown as { __tgToken?: string };
  if (w.__tgToken) return w.__tgToken;
  try {
    return localStorage.getItem('tg-token') ?? '';
  } catch {
    return '';
  }
}

async function call(body: Record<string, unknown>): Promise<any> {
  const url = apiUrl();
  if (!url) throw new Error('状態APIが未設定です（status_api.json）');
  const t = token();
  if (!t) throw new Error('合言葉がありません。メールのリンクから開き直してください');
  // Content-Type を付けない（= text/plain）。application/json だとプリフライトになり GAS が応答できない
  const res = await fetch(url, { method: 'POST', body: JSON.stringify({ ...body, token: t }) });
  if (!res.ok) throw new Error(`状態APIの応答が異常です（HTTP ${res.status}）`);
  const data = await res.json();
  if (!data.ok) {
    if (data.error === 'forbidden') throw new Error('合言葉が一致しません。最新のメールのリンクから開き直してください');
    throw new Error(`状態APIがエラーを返しました（${data.error}）`);
  }
  return data;
}

function toast(message: string, kind: 'error' | 'info' = 'error') {
  let el = document.getElementById('tg-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'tg-toast';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.dataset.kind = kind;
  el.classList.add('show');
  clearTimeout((el as any)._timer);
  (el as any)._timer = setTimeout(() => el!.classList.remove('show'), kind === 'error' ? 6000 : 2500);
}

/** 同じ店のボタンは画面上に複数あり得る（アーカイブで別の週に再登場する）ので全部揃える */
function render(placeId: string, status: Status) {
  document.querySelectorAll<HTMLElement>(`.tg-status[data-place-id="${CSS.escape(placeId)}"]`).forEach((box) => {
    box.dataset.status = status;
    box.querySelectorAll<HTMLButtonElement>('.tg-status-btn').forEach((btn) => {
      btn.setAttribute('aria-pressed', String(btn.dataset.status === status));
    });
    box.closest('[data-tg-card]')?.classList.toggle('tg-excluded', status !== 'none');
  });
  document.dispatchEvent(new CustomEvent('tg-status-change', { detail: { placeId, status } }));
}

function setBusy(placeId: string, busy: boolean) {
  document.querySelectorAll<HTMLElement>(`.tg-status[data-place-id="${CSS.escape(placeId)}"] .tg-status-btn`).forEach((b) => {
    (b as HTMLButtonElement).disabled = busy;
  });
}

async function onClick(btn: HTMLButtonElement) {
  const box = btn.closest<HTMLElement>('.tg-status');
  if (!box) return;
  const placeId = box.dataset.placeId ?? '';
  const name = box.dataset.name ?? '';
  const clicked = btn.dataset.status as Status;
  const before = state.get(placeId) ?? 'none';
  // 同じボタンをもう一度押すと解除（永久除外・解除可）
  const next: Status = before === clicked ? 'none' : clicked;

  render(placeId, next); // 押した感触を先に返す
  setBusy(placeId, true);
  try {
    await call({ action: 'set', place_id: placeId, name, status: next });
    state.set(placeId, next);
    toast(next === 'none' ? `「${name}」の印を外しました` : `「${name}」を「${LABEL[next]}」にしました`, 'info');
  } catch (e) {
    render(placeId, before); // 見た目を戻す
    toast(`保存できませんでした: ${(e as Error).message}`);
  } finally {
    setBusy(placeId, false);
  }
}

let loading = false;
async function loadAll() {
  if (loading || !token()) return; // トークンは目隠しを通った瞬間に届く（tg-gate-unlocked）
  loading = true;
  try {
    const data = await call({ action: 'list' });
    for (const item of data.items as { place_id: string; status: string }[]) {
      const s = (['visited', 'skipped', 'none'].includes(item.status) ? item.status : 'none') as Status;
      state.set(item.place_id, s);
    }
    document.querySelectorAll<HTMLElement>('.tg-status').forEach((box) => {
      const id = box.dataset.placeId ?? '';
      render(id, state.get(id) ?? 'none');
    });
  } catch (e) {
    toast(`「行った/たぶん行かない」の状態を読み込めませんでした: ${(e as Error).message}`);
  } finally {
    loading = false;
  }
}

export function initStatusButtons() {
  if (initialized) return;
  initialized = true;
  document.addEventListener('click', (ev) => {
    const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>('.tg-status-btn');
    if (btn && !btn.disabled) onClick(btn);
  });
  document.addEventListener('tg-gate-unlocked', () => loadAll());
  loadAll();
}
