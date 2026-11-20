(() => {
  const slides = [...document.querySelectorAll('.slide')];
  const dots = document.getElementById('slide-dots');
  const progress = document.getElementById('progress-fill');
  const count = document.getElementById('slide-count');
  const previous = document.getElementById('prev');
  const next = document.getElementById('next');
  const fullscreen = document.getElementById('fullscreen');
  let current = 0;

  slides.forEach((slide) => {
    slide.querySelectorAll('.reveal').forEach((element, index) => {
      element.style.setProperty('--reveal-order', Math.min(index, 7));
    });
    slide.querySelectorAll('.mock-bars i').forEach((bar, index) => {
      bar.style.setProperty('--bar-order', index);
    });
  });

  const pad = (number) => String(number).padStart(2, '0');

  slides.forEach((slide, index) => {
    slide.setAttribute('aria-hidden', index === current ? 'false' : 'true');
    const dot = document.createElement('button');
    dot.type = 'button';
    dot.className = `dot-btn${index === current ? ' active' : ''}`;
    dot.setAttribute('aria-label', `Aller à la diapositive ${index + 1}`);
    dot.addEventListener('click', () => show(index));
    dots.append(dot);
  });

  function show(index) {
    const nextIndex = Math.max(0, Math.min(slides.length - 1, index));
    const direction = nextIndex >= current ? 'forward' : 'backward';
    current = nextIndex;
    slides.forEach((slide, slideIndex) => {
      const active = slideIndex === current;
      slide.classList.toggle('active', active);
      slide.classList.toggle('enter-forward', active && direction === 'forward');
      slide.classList.toggle('enter-backward', active && direction === 'backward');
      slide.setAttribute('aria-hidden', active ? 'false' : 'true');
    });
    [...dots.children].forEach((dot, dotIndex) => {
      dot.classList.toggle('active', dotIndex === current);
      dot.setAttribute('aria-current', dotIndex === current ? 'step' : 'false');
    });
    progress.style.width = `${((current + 1) / slides.length) * 100}%`;
    count.textContent = `${pad(current + 1)} / ${pad(slides.length)}`;
    previous.disabled = current === 0;
    next.disabled = current === slides.length - 1;
    if (location.protocol !== 'file:') history.replaceState(null, '', `#slide-${current + 1}`);
  }

  previous.addEventListener('click', () => show(current - 1));
  next.addEventListener('click', () => show(current + 1));
  fullscreen.addEventListener('click', async () => {
    try {
      if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
      else await document.exitFullscreen();
    } catch (error) {
      console.info('Le mode plein écran n’est pas disponible dans ce navigateur.', error);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (['ArrowRight', 'PageDown', ' '].includes(event.key)) {
      event.preventDefault();
      show(current + 1);
    } else if (['ArrowLeft', 'PageUp'].includes(event.key)) {
      event.preventDefault();
      show(current - 1);
    } else if (event.key === 'Home') {
      show(0);
    } else if (event.key === 'End') {
      show(slides.length - 1);
    } else if (event.key.toLowerCase() === 'f') {
      fullscreen.click();
    }
  });

  let touchStartX = null;
  document.addEventListener('touchstart', (event) => {
    touchStartX = event.changedTouches[0].screenX;
  }, { passive: true });
  document.addEventListener('touchend', (event) => {
    if (touchStartX === null) return;
    const distance = event.changedTouches[0].screenX - touchStartX;
    if (Math.abs(distance) > 65) show(current + (distance < 0 ? 1 : -1));
    touchStartX = null;
  }, { passive: true });

  const requestedSlide = Number(location.hash.match(/slide-(\d+)/)?.[1]);
  if (requestedSlide > 0 && requestedSlide <= slides.length) current = requestedSlide - 1;
  show(current);
})();
