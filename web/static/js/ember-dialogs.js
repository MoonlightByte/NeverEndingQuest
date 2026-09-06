/* Public HTML workbench modal presentation. Existing handlers exclusively own
 * operations/cancellation. No requests, game state, or action payloads here. */
(() => {
  const layers = [];
  const inertBefore = new Map();
  let overflowBefore = null;
  let labelSequence = 0;
  let help = null;
  let helpLeaveTimer = null;
  const visible = node => node.isConnected && !node.hidden && node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden';
  const available = node => visible(node) && !node.closest('[inert]') && !node.disabled;
  const controls = node => Array.from(node.querySelectorAll('button,input,select,textarea,a[href],video[controls],[tabindex]'))
    .filter(element => available(element) && element.tabIndex >= 0);
  const top = () => layers[layers.length - 1];
  function hideHelp() {
    clearTimeout(helpLeaveTimer); helpLeaveTimer = null;
    if (!help) return;
    help.trigger.removeAttribute('aria-describedby');
    help.trigger.setAttribute('aria-expanded', 'false');
    help.popup.remove(); help = null;
  }
  function showHelp(trigger, pinned = false) {
    clearTimeout(helpLeaveTimer); helpLeaveTimer = null;
    if (!available(trigger)) return;
    if (help?.trigger === trigger) { help.pinned = pinned || help.pinned; return; }
    hideHelp();
    const popup = document.createElement('div');
    popup.className = 'ember-help-popup'; popup.id = `ember-help-${++labelSequence}`;
    popup.setAttribute('role', 'tooltip'); popup.textContent = trigger.dataset.tooltip;
    (trigger.closest('[data-ember-modal]') || document.body).append(popup);
    trigger.setAttribute('aria-describedby', popup.id); trigger.setAttribute('aria-expanded', 'true');
    help = { trigger, popup, pinned };
    popup.addEventListener('pointerenter', () => { clearTimeout(helpLeaveTimer); helpLeaveTimer = null; });
    popup.addEventListener('pointerleave', () => leaveHelp(trigger));
    const anchor = trigger.getBoundingClientRect(); const box = popup.getBoundingClientRect();
    popup.style.left = `${Math.max(8, Math.min(anchor.left + anchor.width / 2 - box.width / 2, innerWidth - box.width - 8))}px`;
    const above = anchor.top - box.height - 8;
    popup.style.top = `${Math.max(8, Math.min(above >= 8 ? above : anchor.bottom + 8, innerHeight - box.height - 8))}px`;
  }
  function leaveHelp(trigger) {
    clearTimeout(helpLeaveTimer);
    helpLeaveTimer = setTimeout(() => {
      if (help?.trigger === trigger && !help.pinned && document.activeElement !== trigger) hideHelp();
    }, 180);
  }
  function enhanceHelp() {
    document.querySelectorAll('.ember-workbench .tooltip-trigger:not([data-ember-help])').forEach(original => {
      const trigger = document.createElement('button');
      for (const attribute of original.attributes) trigger.setAttribute(attribute.name, attribute.value);
      trigger.type = 'button'; trigger.textContent = original.textContent;
      const context = original.closest('h2,h3,h4,label')?.textContent.replace(/\?\s*$/, '').trim() || 'More information';
      trigger.setAttribute('aria-label', `Help: ${context}`); trigger.setAttribute('aria-expanded', 'false');
      trigger.dataset.emberHelp = ''; original.replaceWith(trigger);
      trigger.addEventListener('pointerenter', event => { if (event.pointerType !== 'touch') showHelp(trigger) });
      trigger.addEventListener('pointerleave', () => leaveHelp(trigger));
      trigger.addEventListener('focus', () => showHelp(trigger));
      trigger.addEventListener('blur', () => { if (help?.trigger === trigger) hideHelp() });
      trigger.addEventListener('click', event => {
        event.preventDefault(); event.stopPropagation();
        if (help?.trigger === trigger && help.pinned) hideHelp(); else showHelp(trigger, true);
      });
    });
  }
  const focusEntry = layer => {
    const cancel = layer.node.querySelector('[data-ember-dismiss]');
    const first = cancel && available(cancel) ? cancel : controls(layer.node)[0];
    (first || layer.node).focus({ preventScroll: true });
  };
  const dismiss = layer => {
    const cancel = layer?.node.querySelector('[data-ember-dismiss]');
    if (cancel && available(cancel)) cancel.click();
  };
  function sync() {
    enhanceHelp();
    const open = Array.from(document.querySelectorAll('[data-ember-modal]')).filter(visible);
    const removed = layers.filter(layer => !open.includes(layer.node));
    for (let index = layers.length - 1; index >= 0; index--) {
      if (!open.includes(layers[index].node)) {
        const [layer] = layers.splice(index, 1);
        layer.node.style.zIndex = layer.zIndex;
      }
    }
    const added = [];
    for (const node of open) {
      if (layers.some(layer => layer.node === node)) continue;
      const layer = { node, previousFocus: document.activeElement, zIndex: node.style.zIndex };
      const heading = node.querySelector('h1,h2,h3,h4');
      node.setAttribute('role', 'dialog');
      node.setAttribute('aria-modal', 'true');
      node.tabIndex = -1;
      if (heading) {
        if (!heading.id) heading.id = `ember-workbench-dialog-${++labelSequence}`;
        node.setAttribute('aria-labelledby', heading.id);
      }
      layers.push(layer); added.push(layer);
    }
    const current = top();
    if (help && (!available(help.trigger) || (current && !current.node.contains(help.trigger)))) hideHelp();
    const shouldBeInert = new Set(current ? Array.from(document.body.children)
      .filter(node => node !== current.node && !node.contains(current.node) && !['SCRIPT','STYLE','LINK'].includes(node.tagName)) : []);
    for (const [node, before] of inertBefore) {
      if (!shouldBeInert.has(node)) { node.inert = before; inertBefore.delete(node); }
    }
    for (const node of shouldBeInert) {
      if (!inertBefore.has(node)) inertBefore.set(node, node.inert);
      node.inert = true;
    }
    if (current && overflowBefore === null) { overflowBefore = document.body.style.overflow; document.body.style.overflow = 'hidden'; }
    if (!current && overflowBefore !== null) { document.body.style.overflow = overflowBefore; overflowBefore = null; }
    layers.forEach((layer, index) => {
      const zIndex = String(12000 + index);
      if (layer.node.style.zIndex !== zIndex) layer.node.style.zIndex = zIndex;
      // Progress notifications replace their content as they complete.
      const heading = layer.node.querySelector('h1,h2,h3,h4');
      if (heading) {
        if (!heading.id) heading.id = `ember-workbench-dialog-${++labelSequence}`;
        layer.node.setAttribute('aria-labelledby', heading.id);
      }
    });
    if (added.length) focusEntry(current);
    else if (removed.length) {
      const previous = removed[removed.length - 1].previousFocus;
      if (previous instanceof HTMLElement && previous !== document.body && available(previous) && (!current || current.node.contains(previous))) previous.focus({ preventScroll: true });
      else if (current) focusEntry(current);
      else (document.querySelector('.tabs .tab.active') || document.querySelector('.tabs .tab'))?.focus({ preventScroll: true });
    }
    else if (current && !current.node.contains(document.activeElement)) focusEntry(current);
  }
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && help) {
      event.preventDefault(); event.stopImmediatePropagation(); hideHelp(); return;
    }
    const layer = top();
    if (!layer) return;
    if (event.key === 'Escape') {
      event.preventDefault(); event.stopImmediatePropagation(); dismiss(layer);
    } else if (event.key === 'Tab') {
      const items = controls(layer.node);
      const index = items.indexOf(document.activeElement);
      if (!items.length || index < 0 || (event.shiftKey ? index === 0 : index === items.length - 1)) {
        event.preventDefault();
        (event.shiftKey ? items[items.length - 1] : items[0] || layer.node)?.focus();
      }
    }
  }, true);
  document.addEventListener('focusin', event => {
    const layer = top();
    if (layer && !layer.node.contains(event.target)) focusEntry(layer);
  }, true);
  document.addEventListener('click', event => {
    if (help && event.target !== help.trigger && !help.trigger.contains(event.target)) hideHelp();
    const layer = top();
    if (layer && event.target === layer.node && layer.node.classList.contains('modal')) dismiss(layer);
  });
  // Activate through the original click owner so each tab retains its existing
  // data loaders and Socket.IO request behavior, including on keyboard use.
  document.querySelectorAll('.ember-workbench [role="tablist"]').forEach(tablist => {
    const orientation = () => tablist.setAttribute('aria-orientation', getComputedStyle(tablist).flexDirection === 'column' ? 'vertical' : 'horizontal');
    orientation(); window.addEventListener('resize', orientation);
    tablist.addEventListener('keydown', event => {
      if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key)) return;
      const tabs = Array.from(tablist.querySelectorAll('[role="tab"]')).filter(available);
      const index = tabs.indexOf(document.activeElement);
      if (index < 0 || !tabs.length) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (['ArrowRight','ArrowDown'].includes(event.key) ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next].focus(); tabs[next].click();
    });
  });
  window.addEventListener('resize', hideHelp);
  document.addEventListener('scroll', hideHelp, true);
  // Existing HTML opens/hides static modals and appends/removes confirmations.
  // Observe that presentation lifecycle instead of wrapping operation handlers.
  const observer = new MutationObserver(sync);
  observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class', 'hidden'] });
  // Explicit, asynchronous presentation API. Callers must await confirmation
  // before performing their own operation; native browser globals stay intact.
  const prompts = [];
  let activePrompt = null;
  const desktopPrompts = () => window.matchMedia('(min-width: 1024px)').matches;
  function finishPrompt(value) {
    const current = activePrompt;
    if (!current) return;
    activePrompt = null;
    current.node.remove();
    sync(); // Restore the parent layer and opener before resolving the caller.
    current.resolve(current.kind === 'confirm' ? value : undefined);
    queueMicrotask(showNextPrompt);
  }
  function showNextPrompt() {
    if (activePrompt || !prompts.length) return;
    const request = prompts.shift();
    if (!desktopPrompts()) {
      try {
        request.resolve(request.kind === 'confirm' ? window.confirm(request.message) : window.alert(request.message));
      } catch (error) { request.reject(error); }
      queueMicrotask(showNextPrompt);
      return;
    }
    const node = document.createElement('div');
    node.className = 'modal ember-prompt'; node.dataset.emberModal = '';
    const settle = value => { if (activePrompt?.node === node) finishPrompt(value); };
    const card = document.createElement('div'); card.className = 'modal-content ember-prompt-card';
    const title = document.createElement('h2'); title.textContent = request.kind === 'confirm' ? 'Confirm action' : 'Notification';
    const message = document.createElement('p');
    message.id = `ember-prompt-message-${++labelSequence}`; message.className = 'ember-prompt-message';
    message.textContent = request.message; node.setAttribute('aria-describedby', message.id);
    const buttons = document.createElement('div'); buttons.className = 'ember-prompt-buttons';
    if (request.kind === 'confirm') {
      const cancel = document.createElement('button');
      cancel.type = 'button'; cancel.className = 'btn'; cancel.textContent = 'Cancel'; cancel.dataset.emberDismiss = '';
      cancel.addEventListener('click', () => settle(false)); buttons.append(cancel);
    }
    const accept = document.createElement('button');
    accept.type = 'button'; accept.className = 'btn btn-primary'; accept.textContent = request.kind === 'confirm' ? 'Continue' : 'OK';
    if (request.kind === 'alert') accept.dataset.emberDismiss = '';
    accept.addEventListener('click', () => settle(true)); buttons.append(accept);
    card.append(title, message, buttons); node.append(card);
    activePrompt = { ...request, node };
    document.body.append(node); sync();
  }
  function prompt(kind, message) {
    return new Promise((resolve, reject) => {
      prompts.push({ kind, message: String(message ?? ''), resolve, reject });
      showNextPrompt();
    });
  }
  window.EmberDialogs = Object.freeze({
    alert: message => prompt('alert', message),
    confirm: message => prompt('confirm', message),
  });
  // External removal of a prompt must never strand its unresolved Promise.
  new MutationObserver(() => {
    if (activePrompt && !activePrompt.node.isConnected) finishPrompt(false);
  }).observe(document.body, { childList: true });
  window.addEventListener('pagehide', () => {
    const pending = prompts.splice(0);
    if (activePrompt) finishPrompt(false);
    pending.forEach(request => request.resolve(request.kind === 'confirm' ? false : undefined));
  });
  sync();
})();
