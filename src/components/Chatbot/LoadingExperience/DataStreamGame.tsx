"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";

/**
 * DataStreamGame — hephae.co-style data stream grid animation with click-to-collect scoring.
 *
 * Colored data dots flow along grid lines. Players click dots to collect them.
 * Three tiers: blue (10pts, common), green (25pts, uncommon), purple (50pts, rare).
 * Burst particle + floating score text on collect.
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
  points: number;
  color: string;
  life: number;
}

interface DataStreamGameProps {
  active: boolean;
  accentColor?: string;
  className?: string;
}

const GRID_SPACING = 60;
const DOT_SPAWN_INTERVAL = 600;
const MAX_DOTS = 18;
const TRAIL_LENGTH = 8;

const TIERS = {
  blue: { color: "#3b82f6", glow: "rgba(59,130,246,0.4)", points: 10, speed: 1.8, radius: 5, weight: 0.60 },
  green: { color: "#10b981", glow: "rgba(16,185,129,0.4)", points: 25, speed: 1.4, radius: 6.5, weight: 0.28 },
  purple: { color: "#8b5cf6", glow: "rgba(139,92,246,0.5)", points: 50, speed: 1.0, radius: 8, weight: 0.12 },
} as const;

let nextDotId = 0;

export default function DataStreamGame({ active, className = "" }: DataStreamGameProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dotsRef = useRef<DataDot[]>([]);
  const burstRef = useRef<BurstParticle[]>([]);
  const floatsRef = useRef<FloatingText[]>([]);
  const animRef = useRef<number>(0);
  const spawnRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [score, setScore] = useState(0);
  const [hasCollected, setHasCollected] = useState(false);
  const sizeRef = useRef({ w: 0, h: 0 });

  const rollTier = useCallback((): DataDot["tier"] => {
    const r = Math.random();
    if (r < TIERS.purple.weight) return "purple";
    if (r < TIERS.purple.weight + TIERS.green.weight) return "green";
    return "blue";
  }, []);

  const spawnDot = useCallback(() => {
    if (dotsRef.current.length >= MAX_DOTS) return;
    const { w, h } = sizeRef.current;
    if (w === 0 || h === 0) return;

    const tier = rollTier();
    const cfg = TIERS[tier];

    // Pick a random grid line to start from an edge
    const horizontal = Math.random() > 0.5;
    let x: number, y: number, vx: number, vy: number;

    if (horizontal) {
      // Travel along a horizontal grid line
      const gridY = Math.floor(Math.random() * Math.floor(h / GRID_SPACING)) * GRID_SPACING + GRID_SPACING / 2;
      const fromLeft = Math.random() > 0.5;
      x = fromLeft ? -10 : w + 10;
      y = gridY;
      vx = (fromLeft ? 1 : -1) * (cfg.speed + Math.random() * 0.5);
      vy = 0;
    } else {
      // Travel along a vertical grid line
      const gridX = Math.floor(Math.random() * Math.floor(w / GRID_SPACING)) * GRID_SPACING + GRID_SPACING / 2;
      const fromTop = Math.random() > 0.5;
      x = gridX;
      y = fromTop ? -10 : h + 10;
      vx = 0;
      vy = (fromTop ? 1 : -1) * (cfg.speed + Math.random() * 0.5);
    }

    dotsRef.current.push({
      id: ++nextDotId,
      x, y, vx, vy,
      radius: cfg.radius,
      color: cfg.color,
      glowColor: cfg.glow,
      tier,
      points: cfg.points,
      opacity: 0,
      trail: [],
      age: 0,
      alive: true,
    });
  }, [rollTier]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !active) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const w = parent.offsetWidth;
      const h = parent.offsetHeight;
      sizeRef.current = { w, h };
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();

    // Seed a few dots immediately
    for (let i = 0; i < 6; i++) {
      const tier = rollTier();
      const cfg = TIERS[tier];
      const { w, h } = sizeRef.current;
      dotsRef.current.push({
        id: ++nextDotId,
        x: GRID_SPACING + Math.random() * (w - GRID_SPACING * 2),
        y: GRID_SPACING + Math.random() * (h - GRID_SPACING * 2),
        vx: (Math.random() - 0.5) * cfg.speed * 2,
        vy: (Math.random() - 0.5) * cfg.speed * 2,
        radius: cfg.radius,
        color: cfg.color,
        glowColor: cfg.glow,
        tier,
        points: cfg.points,
        opacity: 1,
        trail: [],
        age: 30,
        alive: true,
      });
    }

    spawnRef.current = setInterval(spawnDot, DOT_SPAWN_INTERVAL);

    const animate = () => {
      const { w, h } = sizeRef.current;
      ctx.clearRect(0, 0, w, h);

      // Draw subtle grid
      ctx.strokeStyle = "rgba(148, 163, 184, 0.06)";
      ctx.lineWidth = 1;
      for (let x = GRID_SPACING / 2; x < w; x += GRID_SPACING) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = GRID_SPACING / 2; y < h; y += GRID_SPACING) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // Draw grid intersection dots
      ctx.fillStyle = "rgba(148, 163, 184, 0.08)";
      for (let x = GRID_SPACING / 2; x < w; x += GRID_SPACING) {
        for (let y = GRID_SPACING / 2; y < h; y += GRID_SPACING) {
          ctx.beginPath();
          ctx.arc(x, y, 1.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // Update & draw data dots
      const dots = dotsRef.current;
      for (let i = dots.length - 1; i >= 0; i--) {
        const d = dots[i];
        if (!d.alive) {
          dots.splice(i, 1);
          continue;
        }

        d.age++;

        // Fade in
        if (d.age < 20) d.opacity = Math.min(1, d.opacity + 0.06);

        // Move
        d.x += d.vx;
        d.y += d.vy;

        // Trail
        d.trail.push({ x: d.x, y: d.y });
        if (d.trail.length > TRAIL_LENGTH) d.trail.shift();

        // Remove if off-screen (with margin)
        if (d.x < -30 || d.x > w + 30 || d.y < -30 || d.y > h + 30) {
          dots.splice(i, 1);
          continue;
        }

        // Draw trail
        if (d.trail.length > 1) {
          for (let t = 0; t < d.trail.length - 1; t++) {
            const alpha = (t / d.trail.length) * 0.3 * d.opacity;
            const trailRadius = d.radius * (t / d.trail.length) * 0.6;
            ctx.beginPath();
            ctx.arc(d.trail[t].x, d.trail[t].y, trailRadius, 0, Math.PI * 2);
            ctx.fillStyle = d.color + Math.round(alpha * 255).toString(16).padStart(2, "0");
            ctx.fill();
          }
        }

        // Draw glow
        const glowGrad = ctx.createRadialGradient(d.x, d.y, 0, d.x, d.y, d.radius * 3);
        glowGrad.addColorStop(0, d.glowColor);
        glowGrad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.radius * 3, 0, Math.PI * 2);
        ctx.fillStyle = glowGrad;
        ctx.globalAlpha = d.opacity * 0.6;
        ctx.fill();
        ctx.globalAlpha = 1;

        // Draw dot
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.radius, 0, Math.PI * 2);
        ctx.fillStyle = d.color;
        ctx.globalAlpha = d.opacity;
        ctx.fill();
        ctx.globalAlpha = 1;

        // Inner highlight
        ctx.beginPath();
        ctx.arc(d.x - d.radius * 0.25, d.y - d.radius * 0.25, d.radius * 0.35, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${0.5 * d.opacity})`;
        ctx.fill();

        // Point label for green/purple
        if (d.tier !== "blue" && d.opacity > 0.5) {
          ctx.font = `bold ${d.radius * 1.1}px system-ui, sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillStyle = `rgba(255,255,255,${d.opacity * 0.9})`;
          ctx.fillText(`${d.points}`, d.x, d.y + 0.5);
        }
      }

      // Update & draw burst particles
      const bursts = burstRef.current;
      for (let i = bursts.length - 1; i >= 0; i--) {
        const p = bursts[i];
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.08; // gravity
        p.life--;
        if (p.life <= 0) {
          bursts.splice(i, 1);
          continue;
        }
        const alpha = p.life / p.maxLife;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * alpha, 0, Math.PI * 2);
        ctx.fillStyle = p.color + Math.round(alpha * 255).toString(16).padStart(2, "0");
        ctx.fill();
      }

      // Update & draw floating score texts
      const floats = floatsRef.current;
      for (let i = floats.length - 1; i >= 0; i--) {
        const f = floats[i];
        f.y -= 1.2;
        f.life--;
        if (f.life <= 0) {
          floats.splice(i, 1);
          continue;
        }
        const alpha = f.life / 60;
        ctx.font = "bold 16px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = f.color + Math.round(alpha * 255).toString(16).padStart(2, "0");
        ctx.fillText(`+${f.points}`, f.x, f.y);
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);
    window.addEventListener("resize", resize);

    return () => {
      cancelAnimationFrame(animRef.current);
      if (spawnRef.current) clearInterval(spawnRef.current);
      window.removeEventListener("resize", resize);
      dotsRef.current = [];
      burstRef.current = [];
      floatsRef.current = [];
    };
  }, [active, spawnDot, rollTier]);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;

    const dots = dotsRef.current;
    for (let i = dots.length - 1; i >= 0; i--) {
      const d = dots[i];
      if (!d.alive) continue;
      const dx = cx - d.x;
      const dy = cy - d.y;
      const hitRadius = Math.max(d.radius * 2.5, 18); // generous hit area
      if (dx * dx + dy * dy <= hitRadius * hitRadius) {
        d.alive = false;
        setScore((s) => s + d.points);
        if (!hasCollected) setHasCollected(true);

        // Spawn burst particles
        for (let p = 0; p < 10; p++) {
          const angle = (p / 10) * Math.PI * 2 + Math.random() * 0.3;
          const speed = 2 + Math.random() * 3;
          burstRef.current.push({
            x: d.x,
            y: d.y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed - 1,
            radius: 2 + Math.random() * 2.5,
            color: d.color,
            life: 25 + Math.random() * 15,
            maxLife: 40,
          });
        }

        // Floating score text
        floatsRef.current.push({
          id: d.id,
          x: d.x,
          y: d.y - 10,
          points: d.points,
          color: d.color,
          life: 60,
        });

        break;
      }
    }
  }, [hasCollected]);

  return (
    <div className={`relative w-full h-full ${className}`}>
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        className="absolute inset-0 w-full h-full cursor-pointer"
        style={{ zIndex: 1 }}
      />

      {/* Score display */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 pointer-events-none">
        {!hasCollected ? (
          <div className="bg-white/90 backdrop-blur-sm rounded-full px-4 py-1.5 shadow-md border border-gray-200/80 flex items-center gap-2 animate-pop-in">
            <span className="text-lg">&#x1F3AF;</span>
            <span className="text-sm font-bold text-gray-700">Catch the data streams!</span>
          </div>
        ) : (
          <div className="bg-white/90 backdrop-blur-sm rounded-full px-4 py-1.5 shadow-md border border-gray-200/80 animate-scale-in">
            <span className="text-sm font-bold text-gray-700">
              {score < 50 ? "Keep going!" : score < 150 ? "Nice catch!" : score < 300 ? "Data wizard!" : "Stream master!"}{" "}
              <span className="text-xs font-medium text-gray-500">{score} pts</span>
            </span>
          </div>
        )}
      </div>

      {/* Tier legend — bottom right */}
      <div className="absolute bottom-3 right-3 z-10 pointer-events-none flex gap-2 opacity-60">
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-blue-500" />
          <span className="text-[10px] text-gray-500 font-medium">10</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
          <span className="text-[10px] text-gray-500 font-medium">25</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full bg-purple-500" />
          <span className="text-[10px] text-gray-500 font-medium">50</span>
        </div>
      </div>
    </div>
  );
}
