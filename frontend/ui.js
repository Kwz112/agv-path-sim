/* ============================================================
   共享交互层（提示与确认弹窗）
   提供轻量提示/确认弹窗，替代原生 alert/confirm：
   - kwToast(msg, type, duration)  type: success(绿✓)/error(红✕)/info(深蓝)
   - kwConfirm(msg, opts) → Promise<boolean>
     opts: { title, okText, cancelText, danger }
     Esc/点遮罩=取消，Enter=确认
   自包含（自动注入样式），不依赖 ui.css，深浅色页面均可用
   ============================================================ */
(function () {
  'use strict';
  if (window.kwToast && window.kwConfirm) return;

  var CSS = [
    '.kw-toast-wrap{position:fixed;top:18px;left:50%;transform:translateX(-50%);z-index:99999;display:flex;flex-direction:column;align-items:center;gap:8px;pointer-events:none;max-width:min(92vw,560px)}',
    '.kw-toast{pointer-events:auto;display:flex;align-items:flex-start;gap:9px;background:#fff;color:#2b3648;font-size:13.5px;line-height:1.55;padding:10px 16px 10px 13px;border-radius:10px;box-shadow:0 12px 32px -10px rgba(18,29,46,.35),0 2px 8px rgba(18,29,46,.08);border:1px solid #e3e8ef;border-left:4px solid #1f3a5f;white-space:pre-line;word-break:break-word;animation:kwToastIn .22s cubic-bezier(.2,.9,.3,1.2)}',
    '.kw-toast.kw-success{border-left-color:#0e9f6e}.kw-toast.kw-success .kw-ico{color:#0e9f6e}',
    '.kw-toast.kw-error{border-left-color:#d14343}.kw-toast.kw-error .kw-ico{color:#d14343}',
    '.kw-toast.kw-info{border-left-color:#1f3a5f}.kw-toast.kw-info .kw-ico{color:#1f3a5f}',
    '.kw-toast .kw-ico{flex:none;font-weight:700;font-size:14px;line-height:1.5}',
    '.kw-toast.kw-out{animation:kwToastOut .18s ease-in forwards}',
    '@keyframes kwToastIn{from{opacity:0;transform:translateY(-10px) scale(.97)}to{opacity:1;transform:none}}',
    '@keyframes kwToastOut{to{opacity:0;transform:translateY(-8px) scale(.97)}}',
    '.kw-mask{position:fixed;inset:0;background:rgba(18,29,46,.45);z-index:99998;display:flex;align-items:center;justify-content:center;padding:20px;animation:kwFadeIn .16s ease-out}',
    '.kw-dialog{background:#fff;border-radius:14px;box-shadow:0 28px 64px -16px rgba(18,29,46,.4);width:100%;max-width:420px;padding:20px 22px 16px;animation:kwDialogIn .2s cubic-bezier(.2,.9,.3,1.15);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}',
    '.kw-dialog h3{margin:0 0 8px;font-size:15.5px;color:#16202e;font-weight:600}',
    '.kw-dialog .kw-msg{font-size:13.5px;line-height:1.65;color:#2b3648;white-space:pre-line;word-break:break-word;max-height:50vh;overflow:auto}',
    '.kw-dialog .kw-btns{display:flex;justify-content:flex-end;gap:10px;margin-top:18px}',
    '.kw-dialog button{font-family:inherit;font-size:13.5px;padding:8px 18px;border-radius:8px;cursor:pointer;border:1px solid transparent;transition:background .15s,box-shadow .15s,transform .1s}',
    '.kw-dialog button:active{transform:translateY(1px)}',
    '.kw-dialog .kw-cancel{background:#fff;color:#2b3648;border-color:#d2d9e3}',
    '.kw-dialog .kw-cancel:hover{background:#f3f6fa}',
    '.kw-dialog .kw-ok{background:#1f3a5f;color:#fff}',
    '.kw-dialog .kw-ok:hover{background:#2a4a72}',
    '.kw-dialog .kw-ok.kw-danger{background:#d14343}',
    '.kw-dialog .kw-ok.kw-danger:hover{background:#b93a3a}',
    '.kw-dialog button:focus-visible{outline:2px solid #2a4a72;outline-offset:2px}',
    '@keyframes kwFadeIn{from{opacity:0}to{opacity:1}}',
    '@keyframes kwDialogIn{from{opacity:0;transform:translateY(10px) scale(.97)}to{opacity:1;transform:none}}',
    '@media (prefers-reduced-motion:reduce){.kw-toast,.kw-toast.kw-out,.kw-mask,.kw-dialog{animation:none!important;transition:none!important}}'
  ].join('\n');

  function ensureStyle() {
    if (document.getElementById('kw-shared-style')) return;
    var st = document.createElement('style');
    st.id = 'kw-shared-style';
    st.textContent = CSS;
    (document.head || document.documentElement).appendChild(st);
  }

  var ICONS = { success: '✓', error: '✕', info: 'ℹ' };

  /* 原生 <dialog> showModal 处于 top layer，z-index 无法覆盖；
     弹窗/吐司需挂载到当前打开的 dialog 内才能可见 */
  function topHost() {
    var dlg = document.querySelector('dialog[open]');
    return dlg || document.body;
  }

  window.kwToast = function (msg, type, duration) {
    ensureStyle();
    type = (type === 'success' || type === 'error') ? type : 'info';
    duration = duration || 2600;
    var host = topHost();
    var wrap = host.querySelector('.kw-toast-wrap');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.className = 'kw-toast-wrap';
      host.appendChild(wrap);
    }
    var el = document.createElement('div');
    el.className = 'kw-toast kw-' + type;
    el.setAttribute('role', 'status');
    var ico = document.createElement('span');
    ico.className = 'kw-ico';
    ico.textContent = ICONS[type];
    var txt = document.createElement('span');
    txt.textContent = msg;
    el.appendChild(ico);
    el.appendChild(txt);
    wrap.appendChild(el);
    setTimeout(function () {
      el.classList.add('kw-out');
      setTimeout(function () { el.remove(); }, 200);
    }, duration);
  };

  window.kwConfirm = function (msg, opts) {
    ensureStyle();
    opts = opts || {};
    return new Promise(function (resolve) {
      var mask = document.createElement('div');
      mask.className = 'kw-mask';
      var dlg = document.createElement('div');
      dlg.className = 'kw-dialog';
      dlg.setAttribute('role', 'dialog');
      dlg.setAttribute('aria-modal', 'true');

      var h = document.createElement('h3');
      h.textContent = opts.title || '确认操作';
      var m = document.createElement('div');
      m.className = 'kw-msg';
      m.textContent = msg;
      var btns = document.createElement('div');
      btns.className = 'kw-btns';
      var cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'kw-cancel';
      cancel.textContent = opts.cancelText || '取消';
      var ok = document.createElement('button');
      ok.type = 'button';
      ok.className = 'kw-ok' + (opts.danger ? ' kw-danger' : '');
      ok.textContent = opts.okText || '确定';

      btns.appendChild(cancel);
      btns.appendChild(ok);
      dlg.appendChild(h);
      dlg.appendChild(m);
      dlg.appendChild(btns);
      mask.appendChild(dlg);
      topHost().appendChild(mask);

      function done(val) {
        document.removeEventListener('keydown', onKey, true);
        mask.remove();
        resolve(val);
      }
      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); done(false); }
        else if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); done(true); }
      }
      cancel.addEventListener('click', function () { done(false); });
      ok.addEventListener('click', function () { done(true); });
      mask.addEventListener('click', function (e) { if (e.target === mask) done(false); });
      document.addEventListener('keydown', onKey, true);
      ok.focus();
    });
  };
})();
