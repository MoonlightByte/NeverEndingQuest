/* Public HTML workbench modal presentation. Existing handlers exclusively own
 * operations/cancellation. No requests, game state, or action payloads here. */
(() => {
  const layers = [];
  const inertBefore = new Map();
  let overflowBefore = null;
  let labelSequence = 0;
  const visible = node => node.isConnected && !node.hidden && node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden';
  const available = node => visible(node) && !node.closest('[inert]') && !node.disabled;
  const controls = node => Array.from(node.querySelectorAll('button,input,select,textarea,a[href],video[controls],[tabindex]'))
    .filter(element => available(element) && element.tabIndex >= 0);
  const top = () => layers[layers.length - 1];
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
    const layer = top();
    if (layer && event.target === layer.node && layer.node.classList.contains('modal')) dismiss(layer);
  });
  // Existing HTML opens/hides static modals and appends/removes confirmations.
  // Observe that presentation lifecycle instead of wrapping operation handlers.
  const observer = new MutationObserver(sync);
  observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class', 'hidden'] });
  sync();
})();
