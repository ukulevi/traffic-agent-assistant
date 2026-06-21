const slidesList = [
    'sections/00_00_cover.html',
    'sections/00_01_toc.html',
    'sections/01_00_chapter.html',
    'sections/01_01_gioi_thieu.html',
    'sections/01_02_muc_tieu.html',
    'sections/02_00_chapter.html',
    'sections/02_01_gcn_lstm.html',
    'sections/02_02_rag_sql.html',
    'sections/02_03_counterfactual_safety.html',
    'sections/03_00_chapter.html',
    'sections/03_01_kien_truc_4tang.html',
    'sections/03_02_e2e_flow.html',
    'sections/04_00_chapter.html',
    'sections/04_01_cctv_pipeline.html',
    'sections/04_02_tensor.html',
    'sections/05_00_chapter.html',
    'sections/05_01_gcn_lstm_model.html',
    'sections/05_02_surrogate_ensemble.html',
    'sections/06_00_chapter.html',
    'sections/06_01_vectordb.html',
    'sections/06_02_constrained_query.html',
    'sections/07_00_chapter.html',
    'sections/07_01_multiagent.html',
    'sections/07_02_safety_loop.html',
    'sections/08_00_chapter.html',
    'sections/08_01_gantt.html',
    'sections/09_00_chapter.html',
    'sections/09_01_kpi.html',
    'sections/10_00_chapter.html',
    'sections/10_01_rui_ro.html',
    'sections/99_00_thanks.html'
];

const wrapper = document.getElementById('slides_wrapper');
var currentSlide = 0;
var isPresenting = false;
let scaleObserver = null;

function initResizeObserver() {
    if (!scaleObserver) {
        scaleObserver = new ResizeObserver((entries) => {
            if (!isPresenting) return;
            for (let entry of entries) {
                if (entry.target.classList.contains('active')) {
                    recalculateScale(entry.target); break;
                }
            }
        });
    }
}

function recalculateScale(activeSlide) {
    let baseWidth = 1440, baseHeight = 900;
    if (activeSlide && activeSlide.scrollHeight > baseHeight) baseHeight = activeSlide.scrollHeight + 40;
    const sx = window.innerWidth / baseWidth;
    const sy = window.innerHeight / baseHeight;
    document.body.style.setProperty('--scale', Math.min(sx, sy));
}

function observeActiveSlide() {
    initResizeObserver();
    scaleObserver.disconnect();
    const activeSlide = document.querySelector('.slide-container.active');
    if (activeSlide) { scaleObserver.observe(activeSlide); recalculateScale(activeSlide); }
}

function updateOverviewZoom() {
    if (isPresenting) return;
    const zoom = Math.min(1, (window.innerWidth * 0.9) / 1440);
    document.documentElement.style.setProperty('--slide-zoom', zoom);
}
updateOverviewZoom();
window.addEventListener('resize', () => {
    if (isPresenting) {
        recalculateScale(document.querySelector('.slide-container.active'));
    } else { updateOverviewZoom(); }
});

async function loadSlides() {
    try {
        const promises = slidesList.map(url => fetch(url + '?v=20260621b').then(res => {
            if (!res.ok) throw new Error(`Could not load ${url}`);
            return res.text().then(html => ({ url, html }));
        }));
        const contents = await Promise.all(promises);
        let globalIndex = 0;
        contents.forEach((item) => {
            const div = document.createElement('div');
            div.innerHTML = item.html;
            const sourceName = item.url.split('/').pop();
            const subSlides = div.querySelectorAll('.slide-container');
            if (subSlides.length > 0) {
                subSlides.forEach(slide => {
                    slide.id = `slide-${globalIndex++}`;
                    slide.setAttribute('data-source', sourceName);
                    wrapper.appendChild(slide);
                });
            } else if (div.firstElementChild) {
                div.firstElementChild.id = `slide-${globalIndex++}`;
                div.firstElementChild.setAttribute('data-source', sourceName);
                wrapper.appendChild(div.firstElementChild);
            }
        });
        if (audioModeEnabled) document.getElementById('audio-hover-area').style.display = 'flex';
        document.getElementById('loading').style.display = 'none';
        updateCounter();
        if (window.MathJax && typeof MathJax.typesetPromise === 'function') {
            MathJax.typesetPromise().catch(err => console.log('MathJax error:', err));
        }
        return Promise.resolve();
    } catch (error) {
        console.error(error);
        document.getElementById('loading').innerHTML = `
            <div style="text-align:center;color:#ff6b6b;padding:20px;">
                <h1>Lỗi tải Slide!</h1><p><code>${error.message}</code></p>
            </div>`;
    }
}

function updateCounter() {
    const total = document.querySelectorAll('.slide-container').length;
    document.getElementById('counter').innerText = `${currentSlide + 1} / ${total}`;
}

function updateView() {
    const slides = document.querySelectorAll('.slide-container');
    updateCounter();
    if (isPresenting) {
        slides.forEach((s, i) => s.classList.toggle('active', i === currentSlide));
        observeActiveSlide();
        if (typeof playCurrentSlideAudio === 'function') playCurrentSlideAudio();
    } else {
        slides[currentSlide].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function nextSlide() {
    const total = document.querySelectorAll('.slide-container').length;
    if (currentSlide < total - 1) { currentSlide++; updateView(); }
}
function prevSlide() {
    if (currentSlide > 0) { currentSlide--; updateView(); }
}

let wasFullscreenAchieved = false;
function togglePresentation() {
    const slides = document.querySelectorAll('.slide-container');
    isPresenting = !isPresenting;
    document.body.classList.toggle('presentation-mode', isPresenting);
    if (isPresenting) {
        wasFullscreenAchieved = false;
        document.documentElement.requestFullscreen().then(() => { wasFullscreenAchieved = true; }).catch(() => {});
        updateView();
        const btnIcon = document.querySelector('#controls button:nth-child(2) i');
        if (btnIcon) { btnIcon.classList.remove('fa-play'); btnIcon.classList.add('fa-compress'); }
    } else {
        wasFullscreenAchieved = false;
        if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
        document.body.style.setProperty('--scale', 1);
        const audioArea = document.getElementById('audio-hover-area');
        if (audioArea) audioArea.style.display = 'none';
        if (typeof pauseSlideAudio === 'function') pauseSlideAudio();
        slides.forEach(s => s.classList.remove('active'));
        const btnIcon = document.querySelector('#controls button:nth-child(2) i');
        if (btnIcon) { btnIcon.classList.remove('fa-compress'); btnIcon.classList.add('fa-play'); }
        if (window.presentationTools) window.presentationTools.cleanup();
        setTimeout(() => slides[currentSlide].scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
    }
}

document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && isPresenting && wasFullscreenAchieved) togglePresentation();
});

document.addEventListener('keydown', (e) => {
    if (document.querySelector('#slide-jump-overlay.visible') || document.querySelector('#chapter-nav-overlay.visible')) return;
    if (document.querySelector('#blackout-overlay.visible')) return;
    if (e.key === 'ArrowRight') { if (!document.body.classList.contains('drawing-mode')) nextSlide(); }
    if (e.key === ' ') {
        e.preventDefault();
        if (!document.body.classList.contains('drawing-mode')) {
            if (isPresenting && audioModeEnabled && audioElement) {
                if (audioElement.paused) audioElement.play(); else audioElement.pause();
            } else nextSlide();
        }
    }
    if (e.key === 'ArrowLeft') { if (!document.body.classList.contains('drawing-mode')) prevSlide(); }
    if (e.key === 'f' || e.key === 'F' || e.key === 'p' || e.key === 'P') togglePresentation();
    if (e.key === 'Escape' && isPresenting && !wasFullscreenAchieved) {
        if (!document.body.classList.contains('drawing-mode')) togglePresentation();
    }
});

document.addEventListener('click', (e) => {
    if (isPresenting && !e.target.closest('#controls') && !e.target.closest('#pres-toolbar')
        && !e.target.closest('#context-menu') && !e.target.closest('#drawing-toolbar')
        && !document.body.classList.contains('drawing-mode')
        && !document.body.classList.contains('laser-mode')
        && !document.querySelector('#slide-jump-overlay.visible')
        && !document.querySelector('#chapter-nav-overlay.visible')) {
        nextSlide();
    }
});

const observer = new IntersectionObserver((entries) => {
    if (isPresenting) return;
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const index = parseInt(entry.target.id.replace('slide-', ''));
            if (!isNaN(index)) { currentSlide = index; updateCounter(); }
        }
    });
}, { threshold: 0.6 });

const audioElement = document.getElementById('slide-audio');
let audioModeEnabled = false, autoAdvanceTimer = null;

function toggleAudioMode() {
    audioModeEnabled = !audioModeEnabled;
    const btnIcon = document.querySelector('#btn-toggle-audio i');
    const audioArea = document.getElementById('audio-hover-area');
    if (audioModeEnabled) {
        btnIcon.classList.remove('fa-volume-xmark'); btnIcon.classList.add('fa-volume-high');
        btnIcon.parentElement.style.color = '#38bdf8';
        if (isPresenting) { audioArea.style.display = 'flex'; playCurrentSlideAudio(); }
    } else {
        btnIcon.classList.remove('fa-volume-high'); btnIcon.classList.add('fa-volume-xmark');
        btnIcon.parentElement.style.color = '';
        audioArea.style.display = 'none'; pauseSlideAudio();
    }
}

if (audioElement) {
    audioElement.addEventListener('ended', () => {
        if (audioModeEnabled && isPresenting) {
            const total = document.querySelectorAll('.slide-container').length;
            if (currentSlide < total - 1) autoAdvanceTimer = setTimeout(() => nextSlide(), 2000);
        }
    });
}

function playCurrentSlideAudio() {
    if (autoAdvanceTimer) clearTimeout(autoAdvanceTimer);
    if (!isPresenting || !audioElement || !audioModeEnabled) return;
    audioElement.src = `audio/slide_${currentSlide + 1}.mp3`;
    audioElement.play().catch(() => {});
}
function pauseSlideAudio() { if (audioElement) audioElement.pause(); }

loadSlides().then(() => {
    document.querySelectorAll('.slide-container').forEach(slide => observer.observe(slide));
});
