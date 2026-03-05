"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";

/**
 * DataStreamGame — Interactive mini-game with 4 rotating phases every 15 seconds.
 *
 * Phase 1: Data Streams — dots flow along grid lines
 * Phase 2: Meteor Shower — dots rain diagonally, fast, warm colors
 * Phase 3: Bonus Round — big slow high-value dots, 2x multiplier
 * Phase 4: Chaos Drift — dots wander randomly, zigzag paths
 */

interface DataDot {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  glowColor: string;
  tier: "blue" | "green" | "purple";
  points: number;
  opacity: number;
  trail: { x: number; y: number }[];
  age: number;
  alive: boolean;
  wobblePhase?: number;
}

interface BurstParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  life: number;
  maxLife: number;
}

interface FloatingText {
  id: number;
  x: number;
  y: number;
  text: string;
  color: string;
  life: number;
}

interface DataStreamGameProps {
  active: boolean;
  accentColor?: string;
  className?: string;
}

const GRID_SPACING = 60;
const MAX_DOTS = 20;
const TRAIL_LENGTH = 10;
const PHASE_DURATION_MS = 15_000;

interface PhaseConfig {
  name: string;
  emoji: string;
  spawnMs: number;
  sizeMultiplier: number;
  speedMultiplier: number;
  scoreMultiplier: number;
  tierWeights: { purple: number; green: number };
  gridVisible: boolean;
  spawnPattern: "grid" | "rain" | "edges" | "random";
  wobble: boolean;
}

const PHASES: PhaseConfig[] = [
  {
    name: "Data Streams",
    emoji: "📡",
    spawnMs: 500,
    sizeMultiplier: 1,
    speedMultiplier: 1,
    scoreMultiplier: 1,
    tierWeights: { purple: 0.10, green: 0.25 },
    gridVisible: true,
    spawnPattern: "grid",
    wobble: false,
  },
  {
    name: "Meteor Shower",
    emoji: "☄️",
    spawnMs: 300,
    sizeMultiplier: 0.9,
    speedMultiplier: 1.8,
    scoreMultiplier: 1,
    tierWeights: { purple: 0.08, green: 0.22 },
    gridVisible: false,
    spawnPattern: "rain",
    wobble: false,
  },
  {
    name: "Bonus Round",
    emoji: "⭐",
    spawnMs: 700,
    sizeMultiplier: 1.6,
    speedMultiplier: 0.6,
    scoreMultiplier: 2,
    tierWeights: { purple: 0.25, green: 0.40 },
    gridVisible: true,
    spawnPattern: "edges",
    wobble: false,
  },
  {
    name: "Chaos Drift",
    emoji: "🌀",
    spawnMs: 400,
    sizeMultiplier: 1.1,
    speedMultiplier: 1.2,
    scoreMultiplier: 1,
    tierWeights: { purple: 0.12, green: 0.28 },
    gridVisible: false,
    spawnPattern: "random",
    wobble: true,
  },
];

const BASE_TIERS = {
  blue:   { color: "#3b82f6", glow: "rgba(59,130,246,0.4)",  points: 10, speed: 1.6, radius: 9 },
  green:  { color: "#10b981", glow: "rgba(16,185,129,0.4)",  points: 25, speed: 1.2, radius: 11 },
  purple: { color: "#8b5cf6", glow: "rgba(139,92,246,0.5)",  points: 50, speed: 0.9, radius: 14 },
} as const;

let nextDotId = 0;

export default function DataStreamGame({ active, className = "" }: DataStreamGameProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dotsRef = useRef<DataDot[]>([]);
  const burstRef = useRef<BurstParticle[]>([]);
  const floatsRef = useRef<FloatingText[]>([]);
  const animRef = useRef<number>(0);
  const spawnRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const phaseRef = useRef(0);
  const phaseStartRef = useRef(Date.now());
  const [score, setScore] = useState(0);
  const [hasCollected, setHasCollected] = useState(false);
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [phaseFlash, setPhaseFlash] = useState(false);
  const sizeRef = useRef({ w: 0, h: 0 });
  const scoreRef = useRef(0);

  const getPhase = useCallback(() => PHASES[phaseRef.current % PHASES.length], []);

  const rollTier = useCallback((): DataDot["tier"] => {
    const phase = getPhase();
    const r = Math.random();
    if (r < phase.tierWeights.purple) return "purple";
    if (r < phase.tierWeights.purple + phase.tierWeights.green) return "green";
    return "blue";
  }, [getPhase]);

  const spawnDot = useCallback(() => {
    if (dotsRef.current.length >= MAX_DOTS) return;
    const { w, h } = sizeRef.current;
    if (w === 0 || h === 0) return;

    const phase = getPhase();
    const tier = rollTier();
    const base = BASE_TIERS[tier];
    const radius = base.radius * phase.sizeMultiplier;
    const speed = base.speed * phase.speedMultiplier;

    let x: number, y: number, vx: number, vy: number;

    switch (phase.spawnPattern) {
      case "grid": {
        const horizontal = Math.random() > 0.5;
        if (horizontal) {
          const gridY = Math.floor(Math.random() * Math.floor(h / GRID_SPACING)) * GRID_SPACING + GRID_SPACING / 2;
          const fromLeft = Math.random() > 0.5;
          x = fromLeft ? -15 : w + 15;
          y = gridY;
          vx = (fromLeft ? 1 : -1) * (speed + Math.random() * 0.4);
          vy = 0;
        } else {
          const gridX = Math.floor(Math.random() * Math.floor(w / GRID_SPACING)) * GRID_SPACING + GRID_SPACING / 2;
          const fromTop = Math.random() > 0.5;
          x = gridX;
          y = fromTop ? -15 : h + 15;
          vx = 0;
          vy = (fromTop ? 1 : -1) * (speed + Math.random() * 0.4);
        }
        break;
      }
      case "rain": {
        x = Math.random() * w;
        y = -15;
        const angle = (Math.PI / 4) + (Math.random() - 0.5) * 0.6;
        vx = Math.cos(angle) * speed * 1.5;
        vy = Math.sin(angle) * speed * 1.5;
        break;
      }
      case "edges": {
        const edge = Math.floor(Math.random() * 4);
        if (edge === 0) { x = -15; y = Math.random() * h; vx = speed; vy = (Math.random() - 0.5) * speed * 0.5; }
        else if (edge === 1) { x = w + 15; y = Math.random() * h; vx = -speed; vy = (Math.random() - 0.5) * speed * 0.5; }
        else if (edge === 2) { x = Math.random() * w; y = -15; vx = (Math.random() - 0.5) * speed * 0.5; vy = speed; }
        else { x = Math.random() * w; y = h + 15; vx = (Math.random() - 0.5) * speed * 0.5; vy = -speed; }
        break;
      }
      case "random":
      default: {
        const edge2 = Math.floor(Math.random() * 4);
        if (edge2 === 0) { x = -15; y = Math.random() * h; }
        else if (edge2 === 1) { x = w + 15; y = Math.random() * h; }
        else if (edge2 === 2) { x = Math.random() * w; y = -15; }
        else { x = Math.random() * w; y = h + 15; }
        const angle = Math.atan2(h / 2 - y, w / 2 - x) + (Math.random() - 0.5) * 1.5;
        vx = Math.cos(angle) * speed;
        vy = Math.sin(angle) * speed;
        break;
      }
    }

    dotsRef.current.push({
      id: ++nextDotId,
      x, y, vx, vy,
      radius,
      color: base.color,
      glowColor: base.glow,
      tier,
      points: base.points * phase.scoreMultiplier,
      opacity: 0,
      trail: [],
      age: 0,
      alive: true,
      wobblePhase: phase.wobble ? Math.random() * Math.PI * 2 : undefined,
    });
  }, [rollTier, getPhase]);

  // Phase rotation
  useEffect(() => {
    if (!active) return;
    const interval = setInterval(() => {
      phaseRef.current = (phaseRef.current + 1) % PHASES.length;
      phaseStartRef.current = Date.now();
      setPhaseIndex(phaseRef.current);
      setPhaseFlash(true);
      setTimeout(() => setPhaseFlash(false), 2000);

      // Restart spawn interval with new phase's spawn rate
      if (spawnRef.current) clearInterval(spawnRef.current);
      spawnRef.current = setInterval(spawnDot, PHASES[phaseRef.current].spawnMs);
    }, PHASE_DURATION_MS);
    return () => clearInterval(interval);
  }, [active, spawnDot]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !active) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    let seeded = false;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const w = parent.offsetWidth;
      const h = parent.offsetHeight;
      if (w === 0 || h === 0) return;
      sizeRef.current = { w, h };
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      if (!seeded) {
        seeded = true;
        for (let i = 0; i < 8; i++) {
          const tier = rollTier();
          const base = BASE_TIERS[tier];
          dotsRef.current.push({
            id: ++nextDotId,
            x: GRID_SPACING + Math.random() * (w - GRID_SPACING * 2),
            y: GRID_SPACING + Math.random() * (h - GRID_SPACING * 2),
            vx: (Math.random() - 0.5) * base.speed * 2,
            vy: (Math.random() - 0.5) * base.speed * 2,
            radius: base.radius,
            color: base.color,
            glowColor: base.glow,
            tier,
            points: base.points,
            opacity: 1,
            trail: [],
            age: 30,
            alive: true,
          });
        }
      }
    };

    resize();
    const observer = new ResizeObserver(() => resize());
    if (canvas.parentElement) observer.observe(canvas.parentElement);

    spawnRef.current = setInterval(spawnDot, PHASES[0].spawnMs);

    const animate = () => {
      const { w, h } = sizeRef.current;
      if (w === 0 || h === 0) {
        animRef.current = requestAnimationFrame(animate);
        return;
      }
      ctx.clearRect(0, 0, w, h);

      const phase = getPhase();

      // Draw grid (only in grid-visible phases)
      if (phase.gridVisible) {
        ctx.strokeStyle = "rgba(148, 163, 184, 0.06)";
        ctx.lineWidth = 1;
        for (let gx = GRID_SPACING / 2; gx < w; gx += GRID_SPACING) {
          ctx.beginPath();
          ctx.moveTo(gx, 0);
          ctx.lineTo(gx, h);
          ctx.stroke();
        }
        for (let gy = GRID_SPACING / 2; gy < h; gy += GRID_SPACING) {
          ctx.beginPath();
          ctx.moveTo(0, gy);
          ctx.lineTo(w, gy);
          ctx.stroke();
        }
        ctx.fillStyle = "rgba(148, 163, 184, 0.08)";
        for (let gx = GRID_SPACING / 2; gx < w; gx += GRID_SPACING) {
          for (let gy = GRID_SPACING / 2; gy < h; gy += GRID_SPACING) {
            ctx.beginPath();
            ctx.arc(gx, gy, 1.5, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }

      // Update & draw dots
      const dots = dotsRef.current;
      for (let i = dots.length - 1; i >= 0; i--) {
        const d = dots[i];
        if (!d.alive) { dots.splice(i, 1); continue; }

        d.age++;
        if (d.age < 15) d.opacity = Math.min(1, d.opacity + 0.08);

        // Wobble for chaos phase
        if (d.wobblePhase !== undefined) {
          d.wobblePhase += 0.08;
          d.vx += Math.sin(d.wobblePhase) * 0.15;
          d.vy += Math.cos(d.wobblePhase * 0.7) * 0.1;
        }

        d.x += d.vx;
        d.y += d.vy;

        d.trail.push({ x: d.x, y: d.y });
        if (d.trail.length > TRAIL_LENGTH) d.trail.shift();

        if (d.x < -40 || d.x > w + 40 || d.y < -40 || d.y > h + 40) {
          dots.splice(i, 1);
          continue;
        }

        // Trail
        for (let t = 0; t < d.trail.length - 1; t++) {
          const alpha = (t / d.trail.length) * 0.3 * d.opacity;
          const tr = d.radius * (t / d.trail.length) * 0.5;
          ctx.beginPath();
          ctx.arc(d.trail[t].x, d.trail[t].y, tr, 0, Math.PI * 2);
          ctx.fillStyle = d.color + Math.round(alpha * 255).toString(16).padStart(2, "0");
          ctx.fill();
        }

        // Glow
        const gg = ctx.createRadialGradient(d.x, d.y, 0, d.x, d.y, d.radius * 2.5);
        gg.addColorStop(0, d.glowColor);
        gg.addColorStop(1, "rgba(0,0,0,0)");
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.radius * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = gg;
        ctx.globalAlpha = d.opacity * 0.7;
        ctx.fill();
        ctx.globalAlpha = 1;

        // Dot body
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.radius, 0, Math.PI * 2);
        ctx.fillStyle = d.color;
        ctx.globalAlpha = d.opacity;
        ctx.fill();
        ctx.globalAlpha = 1;

        // Highlight
        ctx.beginPath();
        ctx.arc(d.x - d.radius * 0.2, d.y - d.radius * 0.2, d.radius * 0.3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${0.55 * d.opacity})`;
        ctx.fill();

        // Point label
        if (d.tier !== "blue" && d.opacity > 0.5) {
          ctx.font = `bold ${Math.max(10, d.radius * 0.9)}px system-ui, sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillStyle = `rgba(255,255,255,${d.opacity * 0.9})`;
          ctx.fillText(`${d.points}`, d.x, d.y + 0.5);
        }
      }

      // Burst particles
      const bursts = burstRef.current;
      for (let i = bursts.length - 1; i >= 0; i--) {
        const p = bursts[i];
        p.x += p.vx; p.y += p.vy; p.vy += 0.08; p.life--;
        if (p.life <= 0) { bursts.splice(i, 1); continue; }
        const a = p.life / p.maxLife;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * a, 0, Math.PI * 2);
        ctx.fillStyle = p.color + Math.round(a * 255).toString(16).padStart(2, "0");
        ctx.fill();
      }

      // Floating texts
      const floats = floatsRef.current;
      for (let i = floats.length - 1; i >= 0; i--) {
        const f = floats[i];
        f.y -= 1.2; f.life--;
        if (f.life <= 0) { floats.splice(i, 1); continue; }
        const a = f.life / 60;
        ctx.font = "bold 18px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = f.color + Math.round(a * 255).toString(16).padStart(2, "0");
        ctx.fillText(f.text, f.x, f.y);
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);
    window.addEventListener("resize", resize);

    return () => {
      cancelAnimationFrame(animRef.current);
      if (spawnRef.current) clearInterval(spawnRef.current);
      observer.disconnect();
      window.removeEventListener("resize", resize);
      dotsRef.current = [];
      burstRef.current = [];
      floatsRef.current = [];
    };
  }, [active, spawnDot, rollTier, getPhase]);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const phase = getPhase();

    const dots = dotsRef.current;
    for (let i = dots.length - 1; i >= 0; i--) {
      const d = dots[i];
      if (!d.alive) continue;
      const dx = cx - d.x;
      const dy = cy - d.y;
      const hitRadius = Math.max(d.radius * 2.2, 22);
      if (dx * dx + dy * dy <= hitRadius * hitRadius) {
        d.alive = false;
        const pts = d.points;
        scoreRef.current += pts;
        setScore(scoreRef.current);
        if (!hasCollected) setHasCollected(true);

        for (let p = 0; p < 12; p++) {
          const angle = (p / 12) * Math.PI * 2 + Math.random() * 0.3;
          const speed = 2.5 + Math.random() * 3;
          burstRef.current.push({
            x: d.x, y: d.y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed - 1.5,
            radius: 2.5 + Math.random() * 2.5,
            color: d.color,
            life: 28 + Math.random() * 15,
            maxLife: 43,
          });
        }

        const label = phase.scoreMultiplier > 1 ? `+${pts} ×${phase.scoreMultiplier}` : `+${pts}`;
        floatsRef.current.push({
          id: d.id, x: d.x, y: d.y - 12,
          text: label, color: d.color, life: 60,
        });
        break;
      }
    }
  }, [hasCollected, getPhase]);

  const currentPhase = PHASES[phaseIndex];

  return (
    <div className={`relative w-full h-full ${className}`}>
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        className="absolute inset-0 w-full h-full cursor-pointer"
        style={{ zIndex: 1 }}
      />

      {/* Score display — removed, now handled by parent LoadingOverlay */}

      {/* Phase indicator — bottom left */}
      <div className={`absolute bottom-3 left-3 z-10 pointer-events-none transition-all duration-500 ${phaseFlash ? "scale-110" : "scale-100"}`}>
        <div className={`bg-white/90 backdrop-blur-sm rounded-lg px-3 py-1.5 shadow-sm border border-gray-200/80 flex items-center gap-2 ${phaseFlash ? "ring-2 ring-indigo-300" : ""}`}>
          <span className="text-sm">{currentPhase.emoji}</span>
          <span className="text-xs font-bold text-gray-700">{currentPhase.name}</span>
          {currentPhase.scoreMultiplier > 1 && (
            <span className="text-[10px] font-bold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full">
              {currentPhase.scoreMultiplier}x
            </span>
          )}
        </div>
      </div>

      {/* Score — bottom right */}
      <div className="absolute bottom-3 right-3 z-10 pointer-events-none">
        <div className="bg-white/90 backdrop-blur-sm rounded-lg px-3 py-1.5 shadow-sm border border-gray-200/80">
          <span className="text-xs font-bold text-gray-700">
            {score < 50 ? "🎯" : score < 200 ? "🔥" : "⚡"}{" "}
            {score} pts
          </span>
        </div>
      </div>

      {/* Phase transition announcement */}
      {phaseFlash && (
        <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none animate-fade-in">
          <div className="bg-white/90 backdrop-blur-md rounded-2xl px-8 py-4 shadow-xl border border-gray-200 animate-scale-in">
            <div className="text-center">
              <span className="text-3xl">{currentPhase.emoji}</span>
              <div className="text-lg font-bold text-gray-800 mt-1">{currentPhase.name}</div>
              {currentPhase.scoreMultiplier > 1 && (
                <div className="text-sm font-bold text-amber-600 mt-0.5">Points ×{currentPhase.scoreMultiplier}!</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
