/* ============================================
   PRESENTATION TOOLS - Professional Features
   Laser Pointer, Drawing, Context Menu, Blackout
   ============================================ */

(function () {
    'use strict';

    // ─── Chapter definitions for navigation ───
    const chapters = [
        { num: 0, title: 'Trang bìa', color: '#005ce6', slideFile: '00_cover.html' },
        { num: 0, title: 'Mục lục', color: '#005ce6', slideFile: '00_toc.html' },
        { num: 1, title: 'Giới Thiệu Chung', color: '#005ce6', slideFile: '01_00_chapter.html' },
        { num: 2, title: 'Mạch Khả Kiểm', color: '#ef4444', slideFile: '02_00_chapter.html' },
        { num: 3, title: 'Chèn Điểm Kiểm Thử', color: '#10b981', slideFile: '03_00_chapter.html' },
        { num: 4, title: 'Kỹ Thuật Full Scan DFT', color: '#8b5cf6', slideFile: '04_00_chapter.html' },
        { num: 5, title: 'Các Kiến Trúc Scan', color: '#f59e0b', slideFile: '05_00_chapter.html' },
        { num: 6, title: 'Scan Mức RTL', color: '#0ea5e9', slideFile: '06_00_chapter.html' },
        { num: 7, title: 'Tổng kết & So sánh', color: '#6366f1', slideFile: '07_00_chapter.html' },
    ];

    // ─── State ───
    let laserActive = false;
    let drawingActive = false;
    let blackoutActive = false;
    let drawColor = '#ff0000';
    let drawSize = 3;
    let drawTool = 'pen'; // 'pen', 'highlighter', 'eraser'
    let isDrawing = false;
    let drawingData = {}; // per-slide drawings: { slideIndex: ImageData }
    let undoStack = {}; // per-slide undo stacks
    let redoStack = {}; // per-slide redo stacks

    // ─── DOM Elements (created dynamically) ───
    let laserDot, drawingCanvas, drawCtx;
    let contextMenu, slideJumpOverlay, chapterNavOverlay, blackoutOverlay;
    let drawingToolbar, presToolbar, modeIndicator;

    // ─── Initialize ───
    function init() {
        createDOMElements();
        bindEvents();
    }

    // ─── Create all DOM elements ───
    function createDOMElements() {
        // Laser dot
        laserDot = document.createElement('div');
        laserDot.className = 'laser-dot';
        document.body.appendChild(laserDot);

        // Drawing canvas
        drawingCanvas = document.createElement('canvas');
        drawingCanvas.id = 'drawing-canvas';
        document.body.appendChild(drawingCanvas);
        drawCtx = drawingCanvas.getContext('2d');
        resizeCanvas();

        // Drawing toolbar
        drawingToolbar = document.createElement('div');
        drawingToolbar.id = 'drawing-toolbar';
        drawingToolbar.innerHTML = `
            <button class="tool-btn active" data-tool="pen" title="Bút vẽ"><i class="fa-solid fa-pen"></i></button>
            <button class="tool-btn" data-tool="highlighter" title="Highlight chữ"><i class="fa-solid fa-highlighter"></i></button>
            <button class="tool-btn" data-tool="eraser" title="Tẩy"><i class="fa-solid fa-eraser"></i></button>
            <div class="separator"></div>
            <button class="color-btn active" data-color="#ff0000" style="background:#ff0000" title="Đỏ"></button>
            <button class="color-btn" data-color="#005ce6" style="background:#005ce6" title="Xanh dương"></button>
            <button class="color-btn" data-color="#10b981" style="background:#10b981" title="Xanh lá"></button>
            <button class="color-btn" data-color="#f59e0b" style="background:#f59e0b" title="Vàng"></button>
            <button class="color-btn" data-color="#ffffff" style="background:#ffffff" title="Trắng"></button>
            <div class="separator"></div>
            <button class="size-btn" data-size="2" title="Mảnh"><div class="size-dot" style="width:4px;height:4px"></div></button>
            <button class="size-btn active" data-size="3" title="Vừa"><div class="size-dot" style="width:7px;height:7px"></div></button>
            <button class="size-btn" data-size="6" title="Đậm"><div class="size-dot" style="width:11px;height:11px"></div></button>
            <div class="separator"></div>
            <button class="tool-btn" id="btn-undo" title="Hoàn tác (Ctrl+Z)"><i class="fa-solid fa-rotate-left"></i></button>
            <button class="tool-btn" id="btn-redo" title="Làm lại (Ctrl+Y)"><i class="fa-solid fa-rotate-right"></i></button>
            <div class="separator"></div>
            <button class="tool-btn" id="btn-clear-draw" title="Xóa nét vẽ"><i class="fa-solid fa-trash-can"></i></button>
            <button class="tool-btn" id="btn-clear-highlight" title="Xóa highlight"><i class="fa-solid fa-broom"></i></button>
            <div class="separator"></div>
            <button class="tool-btn close-draw-btn" id="btn-close-draw" title="Đóng bút vẽ (ESC)"><i class="fa-solid fa-xmark"></i></button>
        `;
        document.body.appendChild(drawingToolbar);

        // Context menu
        contextMenu = document.createElement('div');
        contextMenu.id = 'context-menu';
        contextMenu.innerHTML = `
            <button class="ctx-item" data-action="first-slide"><i class="fa-solid fa-house"></i> Về slide đầu <span class="shortcut">Home</span></button>
            <button class="ctx-item" data-action="last-slide"><i class="fa-solid fa-forward-fast"></i> Slide cuối <span class="shortcut">End</span></button>
            <button class="ctx-item" data-action="jump-slide"><i class="fa-solid fa-arrow-right-to-bracket"></i> Đến slide... <span class="shortcut">G</span></button>
            <button class="ctx-item" data-action="chapter-nav"><i class="fa-solid fa-list"></i> Danh sách Chương</button>
            <div class="ctx-separator"></div>
            <button class="ctx-item" data-action="toggle-laser"><i class="fa-solid fa-circle-dot"></i> Bật/tắt Laser <span class="shortcut">L</span></button>
            <button class="ctx-item" data-action="toggle-draw"><i class="fa-solid fa-pen"></i> Bật/tắt Bút vẽ <span class="shortcut">D</span></button>
            <button class="ctx-item" data-action="clear-draw"><i class="fa-solid fa-eraser"></i> Xóa nét vẽ</button>
            <div class="ctx-separator"></div>
            <button class="ctx-item" data-action="blackout"><i class="fa-solid fa-moon"></i> Màn hình đen <span class="shortcut">B</span></button>
            <button class="ctx-item" data-action="exit"><i class="fa-solid fa-xmark"></i> Thoát trình chiếu <span class="shortcut">Esc</span></button>
        `;
        document.body.appendChild(contextMenu);

        // Slide jump overlay (thumbnail grid)
        slideJumpOverlay = document.createElement('div');
        slideJumpOverlay.id = 'slide-jump-overlay';
        slideJumpOverlay.innerHTML = `
            <div id="slide-jump-header">
                <h3>🎯 Chọn slide</h3>
                <input type="number" id="slide-jump-input" min="1" placeholder="Nhập số slide">
            </div>
            <div id="slide-grid"></div>
        `;
        document.body.appendChild(slideJumpOverlay);

        // Chapter navigation overlay (card grid)
        chapterNavOverlay = document.createElement('div');
        chapterNavOverlay.id = 'chapter-nav-overlay';
        chapterNavOverlay.innerHTML = `<div id="chapter-nav-panel"><h3>📚 Danh sách Chương</h3><div id="chapter-grid"></div></div>`;
        document.body.appendChild(chapterNavOverlay);

        // Blackout overlay
        blackoutOverlay = document.createElement('div');
        blackoutOverlay.id = 'blackout-overlay';
        blackoutOverlay.innerHTML = '<div class="blackout-text">Nhấn phím bất kỳ để tiếp tục</div>';
        document.body.appendChild(blackoutOverlay);

        // Presentation toolbar (bottom)
        presToolbar = document.createElement('div');
        presToolbar.id = 'pres-toolbar';
        presToolbar.innerHTML = `
            <button class="toolbar-btn" data-action="toggle-laser" title="Laser"><i class="fa-solid fa-circle-dot"></i><span class="tooltip">Laser (L)</span></button>
            <button class="toolbar-btn" data-action="toggle-draw" title="Vẽ"><i class="fa-solid fa-pen"></i><span class="tooltip">Bút vẽ (D)</span></button>
            <div class="tb-separator"></div>
            <button class="toolbar-btn" data-action="blackout" title="Blackout"><i class="fa-solid fa-moon"></i><span class="tooltip">Màn hình đen (B)</span></button>
            <button class="toolbar-btn" data-action="chapter-nav" title="Chương"><i class="fa-solid fa-list"></i><span class="tooltip">Chương</span></button>
            <button class="toolbar-btn" data-action="jump-slide" title="Đến slide"><i class="fa-solid fa-arrow-right-to-bracket"></i><span class="tooltip">Đến slide (G)</span></button>
        `;
        document.body.appendChild(presToolbar);

        // Mode indicator
        modeIndicator = document.createElement('div');
        modeIndicator.id = 'mode-indicator';
        document.body.appendChild(modeIndicator);
    }

    // ─── Show mode indicator ───
    function showIndicator(text, className) {
        modeIndicator.textContent = text;
        modeIndicator.className = className + ' show';
        setTimeout(() => { modeIndicator.classList.remove('show'); }, 2000);
    }

    // ─── Laser Pointer ───
    function toggleLaser() {
        if (!window.isPresenting) return;
        laserActive = !laserActive;
        document.body.classList.toggle('laser-mode', laserActive);
        if (laserActive) {
            if (drawingActive) toggleDrawing(); // turn off drawing
            showIndicator('🔴 Laser ON', 'laser-ind');
        } else {
            showIndicator('Laser OFF', 'laser-ind');
        }
        updateToolbarState();
    }

    function updateLaserPosition(e) {
        if (!laserActive) return;
        laserDot.style.left = e.clientX + 'px';
        laserDot.style.top = e.clientY + 'px';
    }

    // ─── Drawing ───
    function toggleDrawing() {
        if (!window.isPresenting) return;
        drawingActive = !drawingActive;
        document.body.classList.toggle('drawing-mode', drawingActive);
        if (drawingActive) {
            if (laserActive) toggleLaser(); // turn off laser
            showIndicator('✏️ Bút vẽ ON', 'draw-ind');
            restoreDrawing();
        } else {
            showIndicator('Bút vẽ OFF', 'draw-ind');
            saveDrawing();
            // Exit highlight mode if active
            document.body.classList.remove('highlight-text-mode');
        }
        updateToolbarState();
    }

    function resizeCanvas() {
        drawingCanvas.width = window.innerWidth;
        drawingCanvas.height = window.innerHeight;
    }

    function startDraw(e) {
        if (!drawingActive) return;
        if (drawTool === 'highlighter') return; // highlight uses text selection, not canvas
        isDrawing = true;
        // Save state for undo before drawing
        pushUndo();
        drawCtx.beginPath();
        drawCtx.moveTo(e.clientX, e.clientY);

        if (drawTool === 'eraser') {
            drawCtx.globalCompositeOperation = 'destination-out';
            drawCtx.strokeStyle = 'rgba(0,0,0,1)';
            drawCtx.lineWidth = drawSize * 6;
        } else {
            drawCtx.globalCompositeOperation = 'source-over';
            drawCtx.strokeStyle = drawColor;
            drawCtx.lineWidth = drawSize;
        }
        drawCtx.lineCap = 'round';
        drawCtx.lineJoin = 'round';
    }

    function draw(e) {
        if (!isDrawing) return;
        drawCtx.lineTo(e.clientX, e.clientY);
        drawCtx.stroke();
    }

    function endDraw() {
        if (!isDrawing) return;
        isDrawing = false;
        drawCtx.closePath();
        drawCtx.globalCompositeOperation = 'source-over';
        saveDrawing();
    }

    function pushUndo() {
        const idx = currentSlide;
        if (!undoStack[idx]) undoStack[idx] = [];
        if (!redoStack[idx]) redoStack[idx] = [];
        undoStack[idx].push(drawCtx.getImageData(0, 0, drawingCanvas.width, drawingCanvas.height));
        // Limit undo history to 20 states
        if (undoStack[idx].length > 20) undoStack[idx].shift();
        // Clear redo when new drawing happens
        redoStack[idx] = [];
    }

    function undo() {
        const idx = currentSlide;
        if (!undoStack[idx] || undoStack[idx].length === 0) return;
        if (!redoStack[idx]) redoStack[idx] = [];
        // Save current state to redo
        redoStack[idx].push(drawCtx.getImageData(0, 0, drawingCanvas.width, drawingCanvas.height));
        // Restore previous state
        const prevState = undoStack[idx].pop();
        drawCtx.putImageData(prevState, 0, 0);
        saveDrawing();
    }

    function redo() {
        const idx = currentSlide;
        if (!redoStack[idx] || redoStack[idx].length === 0) return;
        if (!undoStack[idx]) undoStack[idx] = [];
        // Save current state to undo
        undoStack[idx].push(drawCtx.getImageData(0, 0, drawingCanvas.width, drawingCanvas.height));
        // Restore redo state
        const nextState = redoStack[idx].pop();
        drawCtx.putImageData(nextState, 0, 0);
        saveDrawing();
    }

    function saveDrawing() {
        if (typeof currentSlide !== 'undefined') {
            drawingData[currentSlide] = drawCtx.getImageData(0, 0, drawingCanvas.width, drawingCanvas.height);
        }
    }

    function restoreDrawing() {
        drawCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
        if (typeof currentSlide !== 'undefined' && drawingData[currentSlide]) {
            drawCtx.putImageData(drawingData[currentSlide], 0, 0);
        }
    }

    function clearCurrentDrawing() {
        drawCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
        if (typeof currentSlide !== 'undefined') {
            delete drawingData[currentSlide];
        }
    }

    // ─── Text Highlight ───
    function applyTextHighlight() {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed || sel.rangeCount === 0) return;

        const range = sel.getRangeAt(0);
        // Ensure selection is within a slide
        const slideEl = range.commonAncestorContainer.nodeType === 1
            ? range.commonAncestorContainer.closest('.slide-container')
            : range.commonAncestorContainer.parentElement?.closest('.slide-container');
        if (!slideEl) return;

        const mark = document.createElement('mark');
        mark.className = 'text-highlight';
        mark.style.setProperty('--hl-color', drawColor);
        try {
            range.surroundContents(mark);
        } catch (e) {
            // If range spans multiple elements, wrap contents differently
            const fragment = range.extractContents();
            mark.appendChild(fragment);
            range.insertNode(mark);
        }
        sel.removeAllRanges();
    }

    function clearCurrentHighlights() {
        const slides = document.querySelectorAll('.slide-container');
        const slide = slides[window.currentSlide];
        if (!slide) return;
        slide.querySelectorAll('mark.text-highlight').forEach(mark => {
            const parent = mark.parentNode;
            while (mark.firstChild) {
                parent.insertBefore(mark.firstChild, mark);
            }
            parent.removeChild(mark);
            parent.normalize(); // merge adjacent text nodes
        });
    }

    // ─── Blackout ───
    function toggleBlackout() {
        if (!window.isPresenting) return;
        blackoutActive = !blackoutActive;
        blackoutOverlay.classList.toggle('visible', blackoutActive);
    }

    // ─── Context Menu ───
    function showContextMenu(e) {
        e.preventDefault();
        hideAllOverlays();

        // Position menu
        const x = e.clientX;
        const y = e.clientY;
        contextMenu.style.left = x + 'px';
        contextMenu.style.top = y + 'px';
        contextMenu.classList.add('visible');

        // Adjust if overflowing
        requestAnimationFrame(() => {
            const rect = contextMenu.getBoundingClientRect();
            if (rect.right > window.innerWidth) {
                contextMenu.style.left = (window.innerWidth - rect.width - 8) + 'px';
            }
            if (rect.bottom > window.innerHeight) {
                contextMenu.style.top = (window.innerHeight - rect.height - 8) + 'px';
            }
        });
    }

    function hideContextMenu() {
        contextMenu.classList.remove('visible');
    }

    // ─── Slide Jump (thumbnail grid) ───
    function showSlideJump() {
        hideContextMenu();
        const slides = document.querySelectorAll('.slide-container');
        const grid = document.getElementById('slide-grid');
        const input = document.getElementById('slide-jump-input');

        grid.innerHTML = '';
        input.max = slides.length;
        input.placeholder = `1 — ${slides.length}`;
        input.value = '';

        slides.forEach((slide, i) => {
            const thumb = document.createElement('div');
            thumb.className = 'slide-thumb' + (i === window.currentSlide ? ' current' : '');

            // Create a mini preview by cloning the slide
            const preview = document.createElement('div');
            preview.className = 'thumb-preview';
            const clone = slide.cloneNode(true);
            clone.classList.remove('active');
            clone.style.position = 'absolute';
            clone.style.top = '0';
            clone.style.left = '0';
            clone.style.width = '1440px';
            clone.style.minHeight = '900px';
            clone.style.zoom = 'unset';
            // Scale the clone to fit the thumbnail
            const thumbWidth = 220;
            const scale = thumbWidth / 1440;
            clone.style.transform = `scale(${scale})`;
            clone.style.transformOrigin = 'top left';
            preview.appendChild(clone);

            const num = document.createElement('div');
            num.className = 'thumb-number';
            num.textContent = i + 1;

            thumb.appendChild(preview);
            thumb.appendChild(num);

            thumb.onclick = () => {
                if (drawingActive) saveDrawing();
                window.currentSlide = i;
                if (typeof updateView === 'function') updateView();
                if (drawingActive) restoreDrawing();
                hideSlideJump();
            };

            grid.appendChild(thumb);
        });

        slideJumpOverlay.classList.add('visible');
        setTimeout(() => input.focus(), 100);
    }

    function hideSlideJump() {
        slideJumpOverlay.classList.remove('visible');
    }

    function executeSlideJump() {
        const input = document.getElementById('slide-jump-input');
        const val = parseInt(input.value);
        const total = document.querySelectorAll('.slide-container').length;
        if (val >= 1 && val <= total) {
            if (drawingActive) saveDrawing();
            window.currentSlide = val - 1;
            if (typeof updateView === 'function') updateView();
            if (drawingActive) restoreDrawing();
            hideSlideJump();
        }
    }

    // ─── Chapter Navigation (card grid) ───
    function showChapterNav() {
        hideContextMenu();
        const grid = document.getElementById('chapter-grid');
        grid.innerHTML = '';

        const slideFiles = window.slidesList || [];

        chapters.forEach(ch => {
            const card = document.createElement('div');
            card.className = 'chapter-card';

            // Find slide index securely via DOM elements
            const allSlides = Array.from(document.querySelectorAll('.slide-container'));
            let slideIdx = allSlides.findIndex(s => s.getAttribute('data-source') === ch.slideFile);

            // Mark current chapter
            if (slideIdx >= 0 && typeof currentSlide !== 'undefined') {
                let nextChIdx = allSlides.length;
                for (let i = slideIdx + 1; i < allSlides.length; i++) {
                    const src = allSlides[i].getAttribute('data-source');
                    if (src && (src.includes('_00_chapter') || src.includes('00_cover') || src.includes('00_toc'))) {
                        nextChIdx = i;
                        break;
                    }
                }
                if (currentSlide >= slideIdx && currentSlide < nextChIdx) {
                    card.classList.add('current');
                }
            }

            const header = document.createElement('div');
            header.className = 'card-header';
            header.style.background = ch.color;
            header.style.color = 'white';
            header.textContent = ch.num > 0 ? `Chương ${ch.num}` : (ch.title === 'Trang bìa' ? '🏠 Bìa' : '📋 Mục lục');

            const title = document.createElement('div');
            title.className = 'card-title';
            title.textContent = ch.title;

            card.appendChild(header);
            card.appendChild(title);

            card.onclick = () => {
                if (slideIdx >= 0) {
                    if (drawingActive) saveDrawing();
                    window.currentSlide = slideIdx;
                    if (typeof updateView === 'function') updateView();
                    if (drawingActive) restoreDrawing();
                }
                hideChapterNav();
            };

            grid.appendChild(card);
        });

        chapterNavOverlay.classList.add('visible');
    }

    function hideChapterNav() {
        chapterNavOverlay.classList.remove('visible');
    }

    // ─── Hide all overlays ───
    function hideAllOverlays() {
        hideContextMenu();
        hideSlideJump();
        hideChapterNav();
    }

    // ─── Update toolbar button states ───
    function updateToolbarState() {
        presToolbar.querySelectorAll('.toolbar-btn').forEach(btn => {
            const action = btn.dataset.action;
            if (action === 'toggle-laser') btn.classList.toggle('active', laserActive);
            if (action === 'toggle-draw') btn.classList.toggle('active', drawingActive);
        });
    }

    // ─── Called when slide changes (hook into updateView) ───
    function onSlideChange() {
        if (drawingActive) {
            restoreDrawing();
        } else {
            drawCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
            if (typeof currentSlide !== 'undefined' && drawingData[currentSlide]) {
                drawCtx.putImageData(drawingData[currentSlide], 0, 0);
            }
        }
    }

    // ─── Bind Events ───
    function bindEvents() {
        // Mouse move for laser
        document.addEventListener('mousemove', updateLaserPosition);

        // Drawing canvas events
        drawingCanvas.addEventListener('mousedown', startDraw);
        drawingCanvas.addEventListener('mousemove', draw);
        drawingCanvas.addEventListener('mouseup', endDraw);
        drawingCanvas.addEventListener('mouseleave', endDraw);

        // Window resize
        window.addEventListener('resize', () => {
            resizeCanvas();
            if (drawingActive) restoreDrawing();
        });

        // Drawing toolbar click
        drawingToolbar.addEventListener('click', (e) => {
            const toolBtn = e.target.closest('[data-tool]');
            if (toolBtn) {
                drawTool = toolBtn.dataset.tool;
                drawingToolbar.querySelectorAll('[data-tool]').forEach(b => b.classList.remove('active'));
                toolBtn.classList.add('active');
                // Toggle highlight text mode: makes canvas transparent to pointer events
                document.body.classList.toggle('highlight-text-mode', drawTool === 'highlighter');
                return;
            }
            const colorBtn = e.target.closest('.color-btn');
            if (colorBtn) {
                drawColor = colorBtn.dataset.color;
                drawingToolbar.querySelectorAll('.color-btn').forEach(b => b.classList.remove('active'));
                colorBtn.classList.add('active');
                return;
            }
            const sizeBtn = e.target.closest('.size-btn');
            if (sizeBtn) {
                drawSize = parseInt(sizeBtn.dataset.size);
                drawingToolbar.querySelectorAll('.size-btn').forEach(b => b.classList.remove('active'));
                sizeBtn.classList.add('active');
                return;
            }
            if (e.target.closest('#btn-undo')) { undo(); return; }
            if (e.target.closest('#btn-redo')) { redo(); return; }
            if (e.target.closest('#btn-clear-draw')) {
                pushUndo();
                clearCurrentDrawing();
                return;
            }
            if (e.target.closest('#btn-clear-highlight')) {
                clearCurrentHighlights();
                return;
            }
            if (e.target.closest('#btn-close-draw')) {
                toggleDrawing();
                return;
            }
        });

        // Text highlight: listen for mouseup to apply highlight after text selection
        document.addEventListener('mouseup', (e) => {
            if (!drawingActive || drawTool !== 'highlighter') return;
            // Small delay to let the selection finalize
            setTimeout(() => applyTextHighlight(), 10);
        });

        // Context menu events
        document.addEventListener('contextmenu', (e) => {
            if (window.isPresenting && !drawingActive) {
                showContextMenu(e);
            } else if (drawingActive) {
                e.preventDefault(); // prevent default while drawing
            }
        });

        // Context menu item click
        contextMenu.addEventListener('click', (e) => {
            const item = e.target.closest('.ctx-item');
            if (!item) return;
            const action = item.dataset.action;
            hideContextMenu();

            switch (action) {
                case 'first-slide':
                    if (drawingActive) saveDrawing();
                    window.currentSlide = 0;
                    if (typeof updateView === 'function') updateView();
                    if (drawingActive) restoreDrawing();
                    break;
                case 'last-slide':
                    if (drawingActive) saveDrawing();
                    window.currentSlide = document.querySelectorAll('.slide-container').length - 1;
                    if (typeof updateView === 'function') updateView();
                    if (drawingActive) restoreDrawing();
                    break;
                case 'jump-slide':
                    showSlideJump();
                    break;
                case 'chapter-nav':
                    showChapterNav();
                    break;
                case 'toggle-laser':
                    toggleLaser();
                    break;
                case 'toggle-draw':
                    toggleDrawing();
                    break;
                case 'clear-draw':
                    clearCurrentDrawing();
                    break;
                case 'blackout':
                    toggleBlackout();
                    break;
                case 'exit':
                    if (typeof togglePresentation === 'function') togglePresentation();
                    break;
            }
        });

        // Toolbar click
        presToolbar.addEventListener('click', (e) => {
            const btn = e.target.closest('.toolbar-btn');
            if (!btn) return;
            e.stopPropagation(); // Don't trigger slide advance
            const action = btn.dataset.action;
            switch (action) {
                case 'toggle-laser': toggleLaser(); break;
                case 'toggle-draw': toggleDrawing(); break;
                case 'blackout': toggleBlackout(); break;
                case 'chapter-nav': showChapterNav(); break;
                case 'jump-slide': showSlideJump(); break;
            }
        });

        // Close overlays on click outside
        slideJumpOverlay.addEventListener('click', (e) => {
            if (e.target === slideJumpOverlay) hideSlideJump();
        });
        chapterNavOverlay.addEventListener('click', (e) => {
            if (e.target === chapterNavOverlay) hideChapterNav();
        });

        // Click anywhere hides context menu
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#context-menu')) hideContextMenu();
        });

        // Blackout click to dismiss
        blackoutOverlay.addEventListener('click', () => { toggleBlackout(); });

        // Slide jump input
        document.getElementById('slide-jump-input').addEventListener('keydown', (e) => {
            e.stopPropagation(); // don't trigger presentation controls
            if (e.key === 'Enter') executeSlideJump();
            if (e.key === 'Escape') hideSlideJump();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (!window.isPresenting) return;

            // If jump dialog or chapter nav is open
            if (slideJumpOverlay.classList.contains('visible')) return;
            if (chapterNavOverlay.classList.contains('visible')) {
                if (e.key === 'Escape') hideChapterNav();
                return;
            }

            // Blackout: any key dismisses
            if (blackoutActive) {
                e.preventDefault();
                toggleBlackout();
                return;
            }

            // Drawing mode: ESC exits, arrow keys navigate, Ctrl+Z/Y for undo/redo
            if (drawingActive) {
                if (e.key === 'Escape') { toggleDrawing(); return; }
                if (e.ctrlKey && e.key.toLowerCase() === 'z') { e.preventDefault(); undo(); return; }
                if (e.ctrlKey && e.key.toLowerCase() === 'y') { e.preventDefault(); redo(); return; }
                // Allow arrow key navigation while drawing
                if (e.key === 'ArrowRight') { saveDrawing(); nextSlide(); restoreDrawing(); return; }
                if (e.key === 'ArrowLeft') { saveDrawing(); prevSlide(); restoreDrawing(); return; }
                return; // Block all other keys in drawing mode
            }

            switch (e.key.toLowerCase()) {
                case 'l':
                    e.preventDefault();
                    toggleLaser();
                    break;
                case 'd':
                    e.preventDefault();
                    toggleDrawing();
                    break;
                case 'b':
                    e.preventDefault();
                    toggleBlackout();
                    break;
                case 'g':
                    e.preventDefault();
                    showSlideJump();
                    break;
                case 'home':
                    e.preventDefault();
                    if (drawingActive) saveDrawing();
                    window.currentSlide = 0;
                    if (typeof updateView === 'function') updateView();
                    if (drawingActive) restoreDrawing();
                    break;
                case 'end':
                    e.preventDefault();
                    if (drawingActive) saveDrawing();
                    window.currentSlide = document.querySelectorAll('.slide-container').length - 1;
                    if (typeof updateView === 'function') updateView();
                    if (drawingActive) restoreDrawing();
                    break;
            }
        });

        // Hook into slide changes by monkey-patching updateView
        const origUpdateView = window.updateView;
        if (origUpdateView) {
            window.updateView = function () {
                origUpdateView.call(this);
                onSlideChange();
            };
        }
    }

    // ─── Public API for cleanup ───
    window.presentationTools = {
        toggleLaser,
        toggleDrawing,
        toggleBlackout,
        showSlideJump,
        showChapterNav,
        clearCurrentDrawing,
        onSlideChange,
        cleanup: function () {
            laserActive = false;
            drawingActive = false;
            blackoutActive = false;
            document.body.classList.remove('laser-mode', 'drawing-mode');
            blackoutOverlay.classList.remove('visible');
            hideAllOverlays();
            updateToolbarState();
        }
    };

    // Init when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
