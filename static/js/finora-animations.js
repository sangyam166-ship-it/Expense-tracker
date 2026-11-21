/**
 * FINORA - Motion & Cinematic Micro-Interactions (GSAP)
 */

document.addEventListener('DOMContentLoaded', () => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  if (typeof gsap === 'undefined') return;

  // Cinematic Entrance Animation
  const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

  tl.from('.finora-topbar', {
    y: -20,
    opacity: 0,
    duration: 0.6,
  })
  .from('.kpi-card', {
    y: 25,
    opacity: 0,
    duration: 0.5,
    stagger: 0.1,
  }, '-=0.3')
  .from('.finora-card-chart', {
    scale: 0.96,
    opacity: 0,
    duration: 0.5,
    stagger: 0.15,
  }, '-=0.2')
  .from('.finora-table-reveal tbody tr', {
    y: 15,
    opacity: 0,
    duration: 0.35,
    stagger: 0.05,
  }, '-=0.3');

  // Animated Number Counters for KPIs
  document.querySelectorAll('.animate-counter').forEach(el => {
    const rawVal = parseFloat(el.getAttribute('data-value') || '0');
    const prefix = el.getAttribute('data-prefix') || '';
    const decimals = parseInt(el.getAttribute('data-decimals') || '2', 10);

    const counterObj = { val: 0 };
    gsap.to(counterObj, {
      val: rawVal,
      duration: 1.2,
      ease: 'power2.out',
      onUpdate: () => {
        el.innerText = prefix + counterObj.val.toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals
        });
      }
    });
  });

  // 3D Perspective Card Tilt on Interactive & KPI Cards
  const tiltCards = document.querySelectorAll('.finora-card-interactive, .kpi-card');
  tiltCards.forEach(card => {
    let ticking = false;

    card.addEventListener('mousemove', (e) => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const rect = card.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const y = e.clientY - rect.top;
          const centerX = rect.width / 2;
          const centerY = rect.height / 2;
          const rotateX = ((y - centerY) / centerY) * -5;
          const rotateY = ((x - centerX) / centerX) * 5;

          card.style.transform = `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-4px)`;
          card.style.transition = 'transform 0.08s ease-out';
          ticking = false;
        });
        ticking = true;
      }
    });

    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
      card.style.transition = 'transform 0.35s ease-out';
    });
  });
});
