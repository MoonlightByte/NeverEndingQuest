/**
 * Legacy-interface glue for the Map tab (Task 8). Plain-script (non-module)
 * so it can sit alongside game_interface.html's classic inline `<script>`
 * without an import graph; the vendored mapper lib itself is loaded as an
 * ES module by a separate `<script type="module">` block that assigns
 * `window.NeqMap.createMap`.
 *
 * Pure helpers here (structuralKey/diffReveals/computeAutoFitViewBox/
 * clampViewBox/zoomPercent/applyCurrentMarker) are ports of the React Map
 * tab's proven implementation in
 * web/frontend/src/components/sheet/useMapPanZoom.ts (itself ported from
 * demo/neq-rail.html) -- kept in sync deliberately, not copy-drifted.
 *
 * `createMapController` is the stateful orchestration piece: unlike the React
 * component, the legacy interface has exactly one map instance for the whole
 * page lifetime (no mount/unmount), so there's no per-mount cache object --
 * the controller instance itself holds what MapTab.tsx split across refs and
 * a module-level cache.
 *
 * Exposed as `window.NeqMapGlue` (attached at the bottom of this file) so the
 * inline script in game_interface.html, and the static smoke-test harness,
 * can both reach it without a module import.
 */
(function () {
  'use strict';

  /** The full 1200x900 map canvas, in mapper-lib's fixed coordinate space. */
  var FULL_VB = { x: 0, y: 0, w: 1200, h: 900 };

  /**
   * A key that changes exactly when the map's rendered structure needs to be
   * rebuilt: a different area, a different room set, or a room whose
   * id/name/type/connections changed (including a redacted room gaining its
   * name+type on first reveal). Connections are sorted so their storage
   * order never affects the key. Rooms are likewise sorted by id so
   * reordering the server's room array alone never triggers a rebuild.
   */
  function structuralKey(payload) {
    var rooms = payload.map.rooms
      .map(function (r) {
        var conns = (r.connections || []).slice().sort().join(',');
        return [r.id, r.name || '', r.type || '', conns].join('|');
      })
      .sort()
      .join(';');
    return payload.areaId + ':' + rooms;
  }

  /** Ids present in `next` but not in `prev`, in `next`'s order. Additions only. */
  function diffReveals(prev, next) {
    var seen = {};
    for (var i = 0; i < prev.length; i++) seen[prev[i]] = true;
    return next.filter(function (id) { return !seen[id]; });
  }

  function cssEscape(id) {
    if (typeof CSS !== 'undefined' && CSS.escape) return CSS.escape(id);
    return String(id).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  }

  /**
   * Bounding box of the given revealed room ids (queried from the rendered
   * [data-room] groups), padded, aspect-locked to 4:3, and clamped to a sane
   * minimum so a single room isn't absurdly zoomed in.
   *
   * Anchors on each room's icon/label cluster via `markerAnchorBBox` (the
   * same outlier-filtered anchor used for the current-room marker and
   * notes-row focus) rather than the raw union of the full `[data-room]`
   * group bbox. At labelScale:2 the clamped/de-collided label text can be
   * large and, on dense maps, pushed well past its room's icon -- unioning
   * the whole group let a handful of oversized/offset labels skew the
   * computed fit. Anchoring on icon centers keeps the fit tied to where the
   * rooms actually are. (Ported from useMapPanZoom.ts::computeAutoFitViewBox.)
   */
  function computeAutoFitViewBox(svg, revealedIds) {
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (var i = 0; i < revealedIds.length; i++) {
      var groups = svg.querySelectorAll('[data-room="' + cssEscape(revealedIds[i]) + '"]');
      var anchor = markerAnchorBBox(groups);
      if (!anchor) continue;
      minX = Math.min(minX, anchor.x);
      minY = Math.min(minY, anchor.y);
      maxX = Math.max(maxX, anchor.x + anchor.width);
      maxY = Math.max(maxY, anchor.y + anchor.height);
    }
    if (!isFinite(minX)) return { x: FULL_VB.x, y: FULL_VB.y, w: FULL_VB.w, h: FULL_VB.h };

    var PAD = 170;
    minX -= PAD; minY -= PAD; maxX += PAD; maxY += PAD;
    var w = maxX - minX;
    var h = maxY - minY;

    var ASPECT = 4 / 3;
    if (w / h > ASPECT) h = w / ASPECT; else w = h * ASPECT;

    var MIN_W = 400;
    var MAX_W = 1200;
    if (w < MIN_W) { w = MIN_W; h = w / ASPECT; }
    if (w > MAX_W) { w = MAX_W; h = w / ASPECT; }

    var cx = (minX + maxX) / 2;
    var cy = (minY + maxY) / 2;
    var x = cx - w / 2;
    var y = cy - h / 2;
    x = Math.min(FULL_VB.w - w, Math.max(0, x));
    y = Math.min(FULL_VB.h - h, Math.max(0, y));
    return { x: x, y: y, w: w, h: h };
  }

  function setViewBox(svg, vb) {
    svg.setAttribute('viewBox', vb.x + ' ' + vb.y + ' ' + vb.w + ' ' + vb.h);
  }

  function zoomPercent(vb) {
    return Math.round((FULL_VB.w / vb.w) * 100);
  }

  /**
   * Fix round (Task 8/9 re-review): the current-room pulse marker was
   * landing on blank parchment, offset ~90px from the room's actual glyph,
   * on overland maps -- confirmed NOT a "currentLocationId missing from
   * revealed[]" data problem (the server-projected payload always includes
   * it; measured directly against a real payload where it did). Root cause:
   * the vendored mapper's overland renderer (render.js) nests each room's
   * nearest-neighbor-assigned decorative terrain glyphs (planFlavor's
   * scattered moss/tree/reed marks) inside the SAME `<g data-room="id">` as
   * that room's actual icon+label. Those decorations can span a bbox 50-300x
   * larger in area than the icon, because "nearest room" assignment scatters
   * them across whatever empty map area is closest -- not tightly around
   * the glyph. Unioning the *whole* `[data-room]` group's bbox (the original
   * approach here, ported verbatim from the React Map tab's
   * useMapPanZoom.ts::applyCurrentMarker, which has this identical latent
   * bug for the same reason) puts the computed center wherever that
   * lopsided union happens to fall, not on the glyph.
   *
   * This computes the union bbox of each matched group's *direct children*
   * instead, dropping any child whose area is a large outlier relative to
   * the smallest sibling. Measured on a real payload: glyph icon ~420px^2,
   * name label ~4000px^2, type tag ~430px^2, decoration group ~118,000px^2
   * (280x the icon) -- a wide, deliberately generous OUTLIER_MULTIPLE
   * cleanly separates "icon + labels" from "scattered decorations" without
   * hardcoding anything about the vendored renderer's internal filter IDs
   * or child ordering. Interior-mode rooms have no such decorations
   * (planFlavor only runs for overland maps -- render.js passes `decos =
   * interior ? [] : planFlavor(...)`), so every interior child bbox is
   * already room-sized and comparable; nothing gets dropped there, which
   * preserves the original whole-room-bbox behavior interior mode wants.
   *
   * `groups` is the live NodeList/array of one-or-more `[data-room]`
   * elements for the current room (one for overland, two -- walls + floor
   * -- for interior).
   */
  function markerAnchorBBox(groups) {
    var OUTLIER_MULTIPLE = 15;
    var boxes = [];
    for (var i = 0; i < groups.length; i++) {
      var kids = groups[i].children;
      if (kids.length === 0) {
        try {
          var own = groups[i].getBBox();
          if (own.width > 0 || own.height > 0) boxes.push(own);
        } catch (e) {
          // jsdom / not-yet-laid-out SVG: skip, marker circle just won't be placed
        }
        continue;
      }
      for (var j = 0; j < kids.length; j++) {
        try {
          var b = kids[j].getBBox();
          if (b.width > 0 || b.height > 0) boxes.push(b);
        } catch (e) {
          // jsdom / not-yet-laid-out SVG: skip this child
        }
      }
    }
    if (boxes.length === 0) return null;

    if (boxes.length > 1) {
      var minArea = Infinity;
      for (var m = 0; m < boxes.length; m++) minArea = Math.min(minArea, boxes[m].width * boxes[m].height);
      if (minArea > 0) {
        var kept = boxes.filter(function (b) { return (b.width * b.height) <= minArea * OUTLIER_MULTIPLE; });
        if (kept.length > 0) boxes = kept;
      }
    }

    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (var k = 0; k < boxes.length; k++) {
      minX = Math.min(minX, boxes[k].x);
      minY = Math.min(minY, boxes[k].y);
      maxX = Math.max(maxX, boxes[k].x + boxes[k].width);
      maxY = Math.max(maxY, boxes[k].y + boxes[k].height);
    }
    if (!isFinite(minX)) return null;
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }

  /**
   * Marks the current-location room group(s) with `.neq-map-here` (interior
   * mode renders two [data-room] groups per room -- walls and floor -- fog.js
   * treats them as a pair, so this does too) and drops a pulsing ring/dot
   * marker at a bbox center computed by `markerAnchorBBox` below.
   */
  function applyCurrentMarker(svg, currentLocationId) {
    var prevHere = svg.querySelectorAll('.neq-map-here');
    for (var k = 0; k < prevHere.length; k++) prevHere[k].classList.remove('neq-map-here');
    var prevMarker = svg.querySelector('.neq-map-here-marker');
    if (prevMarker) prevMarker.remove();
    if (!currentLocationId) return;

    var groups = svg.querySelectorAll('[data-room="' + cssEscape(currentLocationId) + '"]');
    if (groups.length === 0) return;
    for (var g = 0; g < groups.length; g++) groups[g].classList.add('neq-map-here');

    var anchor = markerAnchorBBox(groups);
    if (!anchor) return;

    var cx = anchor.x + anchor.width / 2;
    var cy = anchor.y + anchor.height / 2;
    var ns = 'http://www.w3.org/2000/svg';
    var marker = document.createElementNS(ns, 'g');
    marker.setAttribute('class', 'neq-map-here-marker');
    var ring = document.createElementNS(ns, 'circle');
    ring.setAttribute('class', 'neq-map-here-ring');
    ring.setAttribute('cx', String(cx));
    ring.setAttribute('cy', String(cy));
    ring.setAttribute('r', '15');
    var dot = document.createElementNS(ns, 'circle');
    dot.setAttribute('class', 'neq-map-here-dot');
    dot.setAttribute('cx', String(cx));
    dot.setAttribute('cy', String(cy));
    dot.setAttribute('r', '9');
    marker.appendChild(ring);
    marker.appendChild(dot);
    svg.appendChild(marker);
  }

  var FOCUS_PAD = 175;
  var FOCUS_MIN_W = 300;

  /**
   * Explorer's Notes row click -> tight pan/zoom to a single room. Ported
   * from the React Map tab's useMapPanZoom.ts::focusRoom (itself ported from
   * demo/neq-notes.js::panToRoom), centered on the room's icon/label cluster
   * via `markerAnchorBBox` -- the same anchor already used by the
   * current-room marker, so both always agree on where a room's "center" is.
   */
  function focusRoom(svg, roomId, onChange) {
    var groups = svg.querySelectorAll('[data-room="' + cssEscape(roomId) + '"]');
    if (groups.length === 0) return;
    var anchor = markerAnchorBBox(groups);
    if (!anchor) return;

    var cx = anchor.x + anchor.width / 2;
    var cy = anchor.y + anchor.height / 2;

    var ASPECT = 4 / 3;
    var w = FOCUS_PAD * 2;
    var h = FOCUS_PAD * 2;
    if (w / h > ASPECT) h = w / ASPECT; else w = h * ASPECT;

    if (w < FOCUS_MIN_W) { w = FOCUS_MIN_W; h = w / ASPECT; }
    if (w > FULL_VB.w) { w = FULL_VB.w; h = w / ASPECT; }

    var x = cx - w / 2;
    var y = cy - h / 2;
    x = Math.min(FULL_VB.w - w, Math.max(0, x));
    y = Math.min(FULL_VB.h - h, Math.max(0, y));

    var vb = { x: x, y: y, w: w, h: h };
    setViewBox(svg, vb);
    if (onChange) onChange(vb);
  }

  var PAN_MIN_W = 240;
  var PAN_MAX_W = 1200;

  /** Clamps a candidate pan/zoom viewBox to the pan-zoom width band and keeps it inside the full 1200x900 canvas. */
  function clampViewBox(vb) {
    var w = Math.min(PAN_MAX_W, Math.max(PAN_MIN_W, vb.w));
    var h = w * (FULL_VB.h / FULL_VB.w);
    var x = Math.min(FULL_VB.w - w, Math.max(0, vb.x));
    var y = Math.min(FULL_VB.h - h, Math.max(0, vb.y));
    return { x: x, y: y, w: w, h: h };
  }

  /**
   * Wheel-zoom + drag-pan on `stage`, mutating the current SVG's viewBox
   * directly. Returns a cleanup function that removes all listeners; safe to
   * call multiple times.
   */
  function wirePanZoom(stage, getSvg, onChange) {
    var dragging = null;

    function getViewBox() {
      var svg = getSvg();
      if (!svg) return null;
      var vb = svg.viewBox.baseVal;
      return { x: vb.x, y: vb.y, w: vb.width, h: vb.height };
    }

    function onWheel(e) {
      var svg = getSvg();
      var vb = getViewBox();
      var ctm = svg && svg.getScreenCTM();
      if (!svg || !vb || !ctm) return;
      e.preventDefault();
      var pt = svg.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      var loc = pt.matrixTransform(ctm.inverse());
      var factor = Math.exp(e.deltaY * 0.001);
      var newW = vb.w * factor;
      var clamped = clampViewBox({
        x: loc.x - (loc.x - vb.x) * (newW / vb.w),
        y: loc.y - (loc.y - vb.y) * (newW / vb.w),
        w: newW,
        h: 0,
      });
      setViewBox(svg, clamped);
      onChange(clamped);
    }

    function onPointerDown(e) {
      var vb = getViewBox();
      if (!vb) return;
      dragging = { startX: e.clientX, startY: e.clientY, vbx: vb.x, vby: vb.y, w: vb.w };
      stage.setPointerCapture(e.pointerId);
    }

    function onPointerMove(e) {
      if (!dragging) return;
      var svg = getSvg();
      if (!svg) return;
      var scale = dragging.w / svg.clientWidth;
      var clamped = clampViewBox({
        x: dragging.vbx - (e.clientX - dragging.startX) * scale,
        y: dragging.vby - (e.clientY - dragging.startY) * scale,
        w: dragging.w,
        h: 0,
      });
      setViewBox(svg, clamped);
      onChange(clamped);
    }

    function onPointerUp(e) {
      dragging = null;
      if (stage.hasPointerCapture(e.pointerId)) stage.releasePointerCapture(e.pointerId);
    }

    function onPointerCancel() {
      dragging = null;
    }

    stage.addEventListener('wheel', onWheel, { passive: false });
    stage.addEventListener('pointerdown', onPointerDown);
    stage.addEventListener('pointermove', onPointerMove);
    stage.addEventListener('pointerup', onPointerUp);
    stage.addEventListener('pointercancel', onPointerCancel);
    stage.addEventListener('lostpointercapture', onPointerCancel);

    return function () {
      stage.removeEventListener('wheel', onWheel);
      stage.removeEventListener('pointerdown', onPointerDown);
      stage.removeEventListener('pointermove', onPointerMove);
      stage.removeEventListener('pointerup', onPointerUp);
      stage.removeEventListener('pointercancel', onPointerCancel);
      stage.removeEventListener('lostpointercapture', onPointerCancel);
    };
  }

  /**
   * Stateful controller wrapping one map instance for the page's lifetime.
   * `createMapFn` is `NeqMap.createMap` (the vendored lib's `createMap`),
   * injected rather than imported so this file stays a plain script and is
   * trivially testable with a stub.
   *
   * `onZoomChange(pct)` is called whenever the effective zoom % changes
   * (auto-fit, reset, full, or live pan/zoom) so the caller can update a
   * "NN%" indicator.
   */
  function createMapController(stageEl, createMapFn, onZoomChange, notesEls) {
    var handle = null;
    var key = '';
    var revealed = [];
    var viewBox = FULL_VB;
    var userTouched = false;
    var panZoomCleanup = null;
    var focusedRowId = null;
    var notesPrevCurrentId = undefined;
    var notesPrevDiscoveredCount = -1;

    function reportZoom(vb) {
      if (onZoomChange) onZoomChange(zoomPercent(vb));
    }

    function destroy() {
      if (panZoomCleanup) { panZoomCleanup(); panZoomCleanup = null; }
      if (handle) { handle.destroy(); handle = null; }
    }

    /**
     * Explorer's Notes panel (ported from demo/neq-notes.js::buildNotesPanel
     * and the React Map tab's MapTab.tsx render). Rebuilds the discovered-
     * rooms list from scratch on every payload -- id order, name+type only
     * for rooms the server chose to name (see mapper-glue.js's module doc /
     * MapRoom's SECURITY NOTE: unrevealed rooms never carry name/type) -- and
     * re-marks the current room with the pulsing dot + emphasis.
     *
     * A row click focuses the map on that room (`focusRoom`) and counts as a
     * user-touched view exactly like a manual pan/zoom, via the same
     * userTouched/viewBox/reportZoom the wheel-zoom/drag-pan handler updates.
     *
     * Manual scrollTop math, not scrollIntoView (dragging the overflow:
     * hidden card ancestor along with it would hide the pinned header) --
     * see demo/neq-notes.js's comment on the same logic. Only runs when the
     * current room or discovered count actually changed, so re-rendering the
     * same payload (e.g. an unrelated tab refresh) doesn't fight a scroll
     * position the user set by hand.
     */
    function renderNotes(payload) {
      if (!notesEls || !notesEls.wrap || !notesEls.progress || !notesEls.scroll) return;

      if (!payload) {
        notesEls.wrap.style.display = 'none';
        notesPrevCurrentId = undefined;
        notesPrevDiscoveredCount = -1;
        return;
      }
      notesEls.wrap.style.display = '';

      var rooms = payload.map.rooms;
      var discovered = rooms
        .filter(function (r) { return !!r.name; })
        .slice()
        .sort(function (a, b) { return a.id < b.id ? -1 : a.id > b.id ? 1 : 0; });
      var totalCount = rooms.length;
      // discovered.length so "N of M" + this line always sum to M (mockup parity).
      var undiscoveredCount = totalCount - discovered.length;

      notesEls.progress.textContent = discovered.length + ' of ' + totalCount + ' places discovered';

      var scroll = notesEls.scroll;
      var prevScrollTop = scroll.scrollTop;
      scroll.innerHTML = '';

      var list = document.createElement('div');
      list.className = 'map-notes-list';
      var currentRow = null;

      discovered.forEach(function (room) {
        var isCurrent = room.id === payload.currentLocationId;
        var row = document.createElement('button');
        row.type = 'button';
        var cls = 'map-notes-row';
        if (isCurrent) cls += ' is-current';
        if (focusedRowId === room.id) cls += ' is-focused';
        row.className = cls;
        row.dataset.roomId = room.id;

        var main = document.createElement('span');
        main.className = 'map-notes-row-main';
        if (isCurrent) {
          var dot = document.createElement('span');
          dot.className = 'map-notes-dot';
          dot.setAttribute('aria-hidden', 'true');
          main.appendChild(dot);
        }
        var name = document.createElement('span');
        name.className = 'map-notes-row-name';
        name.textContent = room.name;
        main.appendChild(name);

        var type = document.createElement('span');
        type.className = 'map-notes-row-type';
        type.textContent = room.type || '';

        row.appendChild(main);
        row.appendChild(type);
        row.addEventListener('click', function () {
          focusedRowId = room.id;
          var prevFocused = scroll.querySelectorAll('.map-notes-row.is-focused');
          for (var i = 0; i < prevFocused.length; i++) prevFocused[i].classList.remove('is-focused');
          row.classList.add('is-focused');
          if (handle) {
            focusRoom(handle.svg, room.id, function (vb) {
              userTouched = true;
              viewBox = vb;
              reportZoom(vb);
            });
          }
        });

        if (isCurrent) currentRow = row;
        list.appendChild(row);
      });
      scroll.appendChild(list);

      if (undiscoveredCount > 0) {
        var undiscovered = document.createElement('div');
        undiscovered.className = 'map-notes-undiscovered';
        var plural = undiscoveredCount === 1 ? 'place' : 'places';
        undiscovered.textContent = '…and ' + undiscoveredCount + ' ' + plural + ' yet undiscovered.';
        scroll.appendChild(undiscovered);
      }

      if (payload.area && payload.area.areaDescription) {
        var rule = document.createElement('hr');
        rule.className = 'map-notes-excerpt-rule';
        scroll.appendChild(rule);

        var excerpt = document.createElement('div');
        excerpt.className = 'map-notes-excerpt';
        excerpt.textContent = payload.area.areaDescription;
        scroll.appendChild(excerpt);
      }

      var shouldAutoScroll = payload.currentLocationId !== notesPrevCurrentId ||
        discovered.length !== notesPrevDiscoveredCount;
      notesPrevCurrentId = payload.currentLocationId;
      notesPrevDiscoveredCount = discovered.length;

      scroll.scrollTop = prevScrollTop;
      if (currentRow && shouldAutoScroll) {
        var targetRow = currentRow;
        requestAnimationFrame(function () {
          var bottom = targetRow.offsetTop + targetRow.offsetHeight;
          var view = scroll.clientHeight;
          if (bottom > scroll.scrollTop + view) {
            scroll.scrollTop = bottom - view + 8;
          } else if (targetRow.offsetTop < scroll.scrollTop) {
            scroll.scrollTop = targetRow.offsetTop - 8;
          }
        });
      }
    }

    /**
     * Apply a `map_data_response`'s `data` payload (or null for "no map").
     * Mirrors MapTab.tsx's effect: rebuild on structural change (or a
     * missing handle), reveal-diff or full setRevealed on shrink, current-
     * room marker, and auto-fit only while the user hasn't manually
     * panned/zoomed.
     */
    function update(payload) {
      if (!payload) {
        destroy();
        key = '';
        revealed = [];
        renderNotes(null);
        return;
      }

      // F9 (defensive): a payload missing `.map`/`.revealed` would otherwise
      // throw out of structuralKey/reveal handling and propagate out of the
      // socket handler. The server contract guarantees this shape today;
      // guard it anyway so a malformed payload no-ops instead of crashing.
      if (!payload.map || !payload.map.rooms || !payload.revealed) return;

      var structural = structuralKey(payload);
      if (structural !== key || !handle) {
        var sameArea = key.indexOf(payload.areaId + ':') === 0;
        // Only an area change invalidates the row-focus highlight (room ids
        // can recur across areas/modules); a same-area structural change
        // (e.g. discovering a new room) leaves an already-focused row's id
        // still valid, so the highlight survives it.
        if (!sameArea) focusedRowId = null;
        var prevRevealed = sameArea ? (handle ? handle.revealed() : revealed) : [];
        if (handle) handle.destroy();
        handle = createMapFn(stageEl, payload.map, payload.area, { uid: 'neqmap', fontCss: false, quiet: true, labelScale: 2 });
        handle.setRevealed(prevRevealed.filter(function (id) { return payload.revealed.indexOf(id) !== -1; }));
        key = structural;
        if (!sameArea) {
          userTouched = false;
          viewBox = FULL_VB;
        } else if (userTouched) {
          setViewBox(handle.svg, viewBox);
          reportZoom(viewBox);
        }
      }

      if (!handle) return;

      var currentRevealed = handle.revealed();
      var shrunk = currentRevealed.some(function (id) { return payload.revealed.indexOf(id) === -1; });
      if (shrunk) {
        handle.setRevealed(payload.revealed);
      } else {
        diffReveals(currentRevealed, payload.revealed).forEach(function (id) { handle.reveal(id); });
      }
      revealed = handle.revealed();

      // React#7 (defensive): only draw the "you are here" marker when the
      // current room is actually in the revealed set -- prevents a position
      // leak on a fogged room if the server invariant ever slipped.
      var currentIsRevealed = !!payload.currentLocationId && payload.revealed.indexOf(payload.currentLocationId) !== -1;
      applyCurrentMarker(handle.svg, currentIsRevealed ? payload.currentLocationId : null);

      if (!userTouched) {
        var fit = computeAutoFitViewBox(handle.svg, payload.revealed);
        viewBox = fit;
        setViewBox(handle.svg, fit);
        reportZoom(fit);
      }

      if (!panZoomCleanup) {
        panZoomCleanup = wirePanZoom(
          stageEl,
          function () { return handle ? handle.svg : null; },
          function (vb) {
            userTouched = true;
            viewBox = vb;
            reportZoom(vb);
          }
        );
      }

      renderNotes(payload);
    }

    /** Recompute auto-fit fresh from the current revealed set (button: reset). */
    function reset(lastPayload) {
      if (!handle || !lastPayload) return;
      var fit = computeAutoFitViewBox(handle.svg, lastPayload.revealed);
      viewBox = fit;
      userTouched = false;
      setViewBox(handle.svg, fit);
      reportZoom(fit);
    }

    /** Show the whole 1200x900 canvas and persist that as the user's chosen view (button: full). */
    function full() {
      if (!handle) return;
      userTouched = true;
      viewBox = FULL_VB;
      setViewBox(handle.svg, FULL_VB);
      reportZoom(FULL_VB);
    }

    return {
      update: update,
      reset: reset,
      full: full,
      destroy: destroy,
      hasHandle: function () { return !!handle; },
    };
  }

  window.NeqMapGlue = {
    FULL_VB: FULL_VB,
    structuralKey: structuralKey,
    diffReveals: diffReveals,
    computeAutoFitViewBox: computeAutoFitViewBox,
    setViewBox: setViewBox,
    zoomPercent: zoomPercent,
    markerAnchorBBox: markerAnchorBBox,
    applyCurrentMarker: applyCurrentMarker,
    clampViewBox: clampViewBox,
    wirePanZoom: wirePanZoom,
    focusRoom: focusRoom,
    createMapController: createMapController,
  };
})();
