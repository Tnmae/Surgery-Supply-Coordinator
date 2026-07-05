import React, { useMemo, useRef, useCallback } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

/* ── Helix Parameters ──────────────────────────────────────────────── */
const NUM_DOTS_PER_STRAND = 260;     // Dense strand points
const NUM_RUNGS = 50;                 // Cross-connections
const DOTS_PER_RUNG = 6;             // Dots per rung
const RADIUS = 3.5;
const HEIGHT = 30;
const COILS = 4.5;
const SCATTER = 0.2;                 // Subtle scatter for organic feel

// Repulsion
const REPULSE_RADIUS = 4.0;
const REPULSE_STRENGTH = 5.0;
const RETURN_SPEED = 2.5;

// Muted palette
const COLORS = [
  new THREE.Color('#6ea8c0'),  // Muted Cyan
  new THREE.Color('#c07890'),  // Muted Rose
  new THREE.Color('#a0a0a0'),  // Soft Gray
  new THREE.Color('#9070b8'),  // Soft Violet
];

const LINE_COLOR = new THREE.Color('#584080');

/* ── Build helix data ──────────────────────────────────────────────── */
function buildHelixData() {
  const totalDots = (NUM_DOTS_PER_STRAND * 2) + (NUM_RUNGS * DOTS_PER_RUNG);
  const restPositions = new Float32Array(totalDots * 3);
  const colorArray = new Float32Array(totalDots * 3);
  const lineIndices = [];
  let offset = 0;

  const addDot = (x, y, z) => {
    const idx = offset;
    restPositions[idx * 3 + 0] = x + (Math.random() - 0.5) * SCATTER;
    restPositions[idx * 3 + 1] = y + (Math.random() - 0.5) * SCATTER;
    restPositions[idx * 3 + 2] = z + (Math.random() - 0.5) * SCATTER;
    const c = COLORS[Math.floor(Math.random() * COLORS.length)];
    colorArray[idx * 3 + 0] = c.r;
    colorArray[idx * 3 + 1] = c.g;
    colorArray[idx * 3 + 2] = c.b;
    offset++;
    return idx;
  };

  const strand1Start = 0;
  const strand2Start = NUM_DOTS_PER_STRAND;

  for (let i = 0; i < NUM_DOTS_PER_STRAND; i++) {
    const t = i / NUM_DOTS_PER_STRAND;
    const angle = t * Math.PI * 2 * COILS;
    const y = (t - 0.5) * HEIGHT;
    addDot(Math.cos(angle) * RADIUS, y, Math.sin(angle) * RADIUS);
  }
  for (let i = 0; i < NUM_DOTS_PER_STRAND; i++) {
    const t = i / NUM_DOTS_PER_STRAND;
    const angle = t * Math.PI * 2 * COILS;
    const y = (t - 0.5) * HEIGHT;
    addDot(Math.cos(angle + Math.PI) * RADIUS, y, Math.sin(angle + Math.PI) * RADIUS);
  }

  // Connect consecutive strand dots
  for (let i = 0; i < NUM_DOTS_PER_STRAND - 1; i++) {
    lineIndices.push(strand1Start + i, strand1Start + i + 1);
    lineIndices.push(strand2Start + i, strand2Start + i + 1);
  }

  // Rungs
  const rungStart = NUM_DOTS_PER_STRAND * 2;
  for (let r = 0; r < NUM_RUNGS; r++) {
    const t = r / NUM_RUNGS;
    const angle = t * Math.PI * 2 * COILS;
    const y = (t - 0.5) * HEIGHT;
    const x1 = Math.cos(angle) * RADIUS;
    const z1 = Math.sin(angle) * RADIUS;
    const x2 = Math.cos(angle + Math.PI) * RADIUS;
    const z2 = Math.sin(angle + Math.PI) * RADIUS;
    const nearestS1 = strand1Start + Math.round(t * (NUM_DOTS_PER_STRAND - 1));
    const nearestS2 = strand2Start + Math.round(t * (NUM_DOTS_PER_STRAND - 1));

    const rungDotIndices = [];
    for (let j = 0; j < DOTS_PER_RUNG; j++) {
      const lerpT = (j + 1) / (DOTS_PER_RUNG + 1);
      const cx = x1 + (x2 - x1) * lerpT;
      const cz = z1 + (z2 - z1) * lerpT;
      rungDotIndices.push(addDot(cx, y, cz));
    }
    lineIndices.push(nearestS1, rungDotIndices[0]);
    for (let j = 0; j < rungDotIndices.length - 1; j++) {
      lineIndices.push(rungDotIndices[j], rungDotIndices[j + 1]);
    }
    lineIndices.push(rungDotIndices[rungDotIndices.length - 1], nearestS2);
  }

  return { restPositions, colorArray, lineIndices: new Uint16Array(lineIndices), totalDots };
}


/* ── Helix Scene ───────────────────────────────────────────────────── */
function HelixScene() {
  const meshRef = useRef();
  const linesRef = useRef();
  const groupRef = useRef();
  const mouseWorld = useRef(new THREE.Vector3(0, 100, 0));
  const { camera, size } = useThree();

  const raycaster = useMemo(() => new THREE.Raycaster(), []);
  const mousePlane = useMemo(() => new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), []);
  const mouseNDC = useRef(new THREE.Vector2(0, 0));

  const { restPositions, colorArray, lineIndices, totalDots } = useMemo(() => buildHelixData(), []);
  const currentPositions = useRef(new Float32Array(restPositions.length));
  useMemo(() => { currentPositions.current.set(restPositions); }, [restPositions]);

  const dummy = useMemo(() => new THREE.Object3D(), []);
  const linePositions = useRef(new Float32Array(lineIndices.length * 3));

  // Dot scales
  const dotScales = useRef(new Float32Array(totalDots));

  React.useLayoutEffect(() => {
    if (!meshRef.current) return;
    for (let i = 0; i < totalDots; i++) {
      dummy.position.set(restPositions[i * 3], restPositions[i * 3 + 1], restPositions[i * 3 + 2]);
      // Bumped up dot size slightly
      const scale = 0.35 + Math.random() * 0.5;
      dotScales.current[i] = scale;
      dummy.scale.set(scale, scale, scale);
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
      const color = new THREE.Color(colorArray[i * 3], colorArray[i * 3 + 1], colorArray[i * 3 + 2]);
      meshRef.current.setColorAt(i, color);
    }
    meshRef.current.instanceMatrix.needsUpdate = true;
    if (meshRef.current.instanceColor) meshRef.current.instanceColor.needsUpdate = true;
  }, [totalDots, restPositions, colorArray, dummy]);

  // Track mouse globally (works even with pointer-events: none on canvas container)
  const onPointerMove = useCallback((e) => {
    mouseNDC.current.set(
      (e.clientX / window.innerWidth) * 2 - 1,
      -(e.clientY / window.innerHeight) * 2 + 1
    );
  }, []);

  React.useEffect(() => {
    window.addEventListener('pointermove', onPointerMove, { passive: true });
    return () => window.removeEventListener('pointermove', onPointerMove);
  }, [onPointerMove]);

  // Reusable temp vectors to avoid GC pressure
  const _intersect = useMemo(() => new THREE.Vector3(), []);
  const _invMatrix = useMemo(() => new THREE.Matrix4(), []);

  useFrame((state, delta) => {
    if (!meshRef.current || !groupRef.current) return;

    groupRef.current.rotation.y += delta * 0.1;
    groupRef.current.position.y = Math.sin(state.clock.elapsedTime * 0.35) * 0.3;

    // Project mouse into group's local space
    raycaster.setFromCamera(mouseNDC.current, camera);
    if (raycaster.ray.intersectPlane(mousePlane, _intersect)) {
      _invMatrix.copy(groupRef.current.matrixWorld).invert();
      _intersect.applyMatrix4(_invMatrix);
      mouseWorld.current.copy(_intersect);
    }

    const cur = currentPositions.current;
    const dt = Math.min(delta, 0.05);

    for (let i = 0; i < totalDots; i++) {
      const ix = i * 3;
      const iy = i * 3 + 1;
      const iz = i * 3 + 2;

      const dx = cur[ix] - mouseWorld.current.x;
      const dy = cur[iy] - mouseWorld.current.y;
      const dz = cur[iz] - mouseWorld.current.z;
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

      let fx = 0, fy = 0, fz = 0;
      if (dist < REPULSE_RADIUS && dist > 0.01) {
        const strength = (1 - dist / REPULSE_RADIUS) * REPULSE_STRENGTH;
        fx = (dx / dist) * strength;
        fy = (dy / dist) * strength;
        fz = (dz / dist) * strength;
      }

      const sx = (restPositions[ix] - cur[ix]) * RETURN_SPEED;
      const sy = (restPositions[iy] - cur[iy]) * RETURN_SPEED;
      const sz = (restPositions[iz] - cur[iz]) * RETURN_SPEED;

      cur[ix] += (fx + sx) * dt;
      cur[iy] += (fy + sy) * dt;
      cur[iz] += (fz + sz) * dt;

      dummy.position.set(cur[ix], cur[iy], cur[iz]);
      const s = dotScales.current[i];
      dummy.scale.set(s, s, s);
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
    }
    meshRef.current.instanceMatrix.needsUpdate = true;

    // Update line positions
    if (linesRef.current) {
      const lp = linePositions.current;
      for (let l = 0; l < lineIndices.length; l++) {
        const dotIdx = lineIndices[l];
        lp[l * 3 + 0] = cur[dotIdx * 3 + 0];
        lp[l * 3 + 1] = cur[dotIdx * 3 + 1];
        lp[l * 3 + 2] = cur[dotIdx * 3 + 2];
      }
      linesRef.current.geometry.setAttribute('position', new THREE.Float32BufferAttribute(lp, 3));
      linesRef.current.geometry.attributes.position.needsUpdate = true;
    }
  });

  return (
    <group ref={groupRef} position={[-4, 0, 0]} rotation={[0.3, 0, -0.4]}>
      <instancedMesh ref={meshRef} args={[null, null, totalDots]}>
        <sphereGeometry args={[0.07, 6, 6]} />
        <meshBasicMaterial toneMapped={false} transparent opacity={0.65} />
      </instancedMesh>

      <lineSegments ref={linesRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            array={new Float32Array(lineIndices.length * 3)}
            count={lineIndices.length}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial color={LINE_COLOR} transparent opacity={0.25} />
      </lineSegments>
    </group>
  );
}

export default function DNAHelix() {
  return (
    <div className="canvas-container" aria-hidden="true">
      <Canvas camera={{ position: [0, 0, 14], fov: 52 }}>
        <fog attach="fog" args={['#110b1a', 10, 26]} />
        <HelixScene />
      </Canvas>
    </div>
  );
}
