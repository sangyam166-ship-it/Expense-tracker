/**
 * FINORA - Elevated 3D Ambient Kinetic Canvas (Three.js)
 * Clean undulating geometric financial grid & luminous particle lattice
 */

(function() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  const container = document.getElementById('finora-3d-bg');
  if (!container || typeof THREE === 'undefined') return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.set(0, 20, 75);
  camera.lookAt(0, 0, 0);

  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  container.appendChild(renderer.domElement);

  // 3D Kinetic Particle Plane
  const rows = 35;
  const cols = 55;
  const count = rows * cols;
  const spacing = 4.2;

  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);

  const colorBlue = new THREE.Color('#10B981');
  const colorPurple = new THREE.Color('#8B5CF6');
  const colorCyan = new THREE.Color('#06B6D4');

  let idx = 0;
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      const x = (j - cols / 2) * spacing;
      const z = (i - rows / 2) * spacing - 15;
      const y = 0;

      positions[idx * 3] = x;
      positions[idx * 3 + 1] = y;
      positions[idx * 3 + 2] = z;

      // Gradient color mapping
      const ratio = (j / cols) * 0.7 + (i / rows) * 0.3;
      let pColor = colorBlue.clone().lerp(colorPurple, ratio);
      if (Math.random() > 0.85) {
        pColor = colorCyan;
      }

      colors[idx * 3] = pColor.r;
      colors[idx * 3 + 1] = pColor.g;
      colors[idx * 3 + 2] = pColor.b;

      idx++;
    }
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 2.8,
    vertexColors: true,
    transparent: true,
    opacity: 0.55,
  });

  const particleMesh = new THREE.Points(geometry, material);
  particleMesh.rotation.x = 0.35;
  scene.add(particleMesh);

  // Mouse Parallax
  let mouseX = 0;
  let mouseY = 0;
  let targetX = 0;
  let targetY = 0;

  window.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX - window.innerWidth / 2) * 0.015;
    mouseY = (e.clientY - window.innerHeight / 2) * 0.015;
  });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  let isTabActive = true;
  document.addEventListener('visibilitychange', () => {
    isTabActive = !document.hidden;
  });

  let clock = 0;
  function animate() {
    requestAnimationFrame(animate);
    if (!isTabActive) return;

    clock += 0.018;

    targetX += (mouseX - targetX) * 0.04;
    targetY += (mouseY - targetY) * 0.04;

    const pos = geometry.attributes.position.array;
    let pIdx = 0;
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols; j++) {
        // Subtle undulating sine wave formula
        const wave = Math.sin(j * 0.25 + clock) * 2.2 + Math.cos(i * 0.3 + clock * 0.8) * 1.8;
        pos[pIdx * 3 + 1] = wave;
        pIdx++;
      }
    }
    geometry.attributes.position.needsUpdate = true;

    particleMesh.rotation.y = targetX * 0.15;
    camera.position.x = targetX * 12;
    camera.position.y = 20 - targetY * 8;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
  }

  animate();
})();
