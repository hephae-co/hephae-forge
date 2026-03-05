"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { BUBBLE_CONFIG } from "./loadingConfig";

interface Bubble {
  id: number;
  x: number;
  y: number;
  radius: number;
  color: string;
  symbol: string;
  vy: number;
  phase: number;
  popping: boolean;
  popProgress: number;
  age: number; // frames since spawn — used for entrance bounce
}

interface FloatingScore {
  id: number;
  x: number;
  y: number;
  opacity: number;
  created: number;
}

interface BubblePopGameProps {
  active: boolean;
  accentColor?: string;
  className?: string;
}

let nextBubbleId = 0;

export default function BubblePopGame({ active, accentColor = "#0052CC", className = "" }: BubblePopGameProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const bubblesRef = useRef<Bubble[]>([]);
  const animFrameRef = useRef<number>(0);
  const spawnTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [score, setScore] = useState(0);
  const [floatingScores, setFloatingScores] = useState<FloatingScore[]>([]);
  const [hasPopped, setHasPopped] = useState(false);

  const spawnBubble = useCallback((width: number, height: number, startY?: number) => {
    if (bubblesRef.current.length >= BUBBLE_CONFIG.maxBubbles) return;
    const cfg = BUBBLE_CONFIG;
    const radius = cfg.minRadius + Math.random() * (cfg.maxRadius - cfg.minRadius);
    bubblesRef.current.push({
      id: ++nextBubbleId,
      x: radius + Math.random() * (width - radius * 2),
      y: startY ?? height + radius,
      radius,
      color: cfg.colors[Math.floor(Math.random() * cfg.colors.length)],
      symbol: cfg.symbols[Math.floor(Math.random() * cfg.symbols.length)],
      vy: cfg.riseSpeed.min + Math.random() * (cfg.riseSpeed.max - cfg.riseSpeed.min),
      phase: Math.random() * Math.PI * 2,
      popping: false,
      popProgress: 0,
      age: 0,
    });
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !active) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    let width = 0;
    let height = 0;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      width = parent.offsetWidth;
      height = parent.offsetHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();

    // Spawn 5 bubbles immediately across the visible area so it looks full
    for (let i = 0; i < 5; i++) {
      const startY = height * 0.25 + Math.random() * height * 0.55;
      spawnBubble(width, height, startY);
    }

    // Continue spawning
    spawnTimerRef.current = setInterval(() => spawnBubble(width, height), BUBBLE_CONFIG.spawnIntervalMs);

    const animate = () => {
      ctx.clearRect(0, 0, width, height);
      const bubbles = bubblesRef.current;

      for (let i = bubbles.length - 1; i >= 0; i--) {
        const b = bubbles[i];
        b.age++;

        if (b.popping) {
          b.popProgress += 0.05;
          if (b.popProgress >= 1) {
            bubbles.splice(i, 1);
            continue;
          }
          const expandR = b.radius * (1 + b.popProgress * 1.2);
          const alpha = 1 - b.popProgress;

          // Burst particles
          for (let p = 0; p < 8; p++) {
            const angle = (p / 8) * Math.PI * 2 + b.phase;
            const dist = b.popProgress * b.radius * 2.5;
            const px = b.x + Math.cos(angle) * dist;
            const py = b.y + Math.sin(angle) * dist;
            const pSize = (1 - b.popProgress) * 4;
            ctx.beginPath();
            ctx.arc(px, py, pSize, 0, Math.PI * 2);
            ctx.fillStyle = b.color + Math.round(alpha * 255).toString(16).padStart(2, "0");
            ctx.fill();
          }

          // Expanding ring
          ctx.beginPath();
          ctx.arc(b.x, b.y, expandR, 0, Math.PI * 2);
          ctx.strokeStyle = b.color + Math.round(alpha * 200).toString(16).padStart(2, "0");
          ctx.lineWidth = 2.5;
          ctx.stroke();
          continue;
        }

        // Physics: rise + wobble
        b.y -= b.vy;
        b.phase += 0.025;
        b.x += Math.sin(b.phase) * BUBBLE_CONFIG.wobbleAmplitude;

        // Remove if off-screen
        if (b.y + b.radius < -10) {
          bubbles.splice(i, 1);
          continue;
        }

        // Entrance bounce: scale up in the first 20 frames
        const entranceScale = b.age < 20 ? 0.5 + 0.5 * Math.min(b.age / 15, 1) * (1 + 0.15 * Math.sin(b.age * 0.5)) : 1;
        // Gentle breathing pulse
        const pulse = 1 + Math.sin(b.age * 0.04) * 0.03;
        const drawRadius = b.radius * entranceScale * pulse;

        // Draw solid, opaque bubble
        const gradient = ctx.createRadialGradient(
          b.x - drawRadius * 0.3, b.y - drawRadius * 0.35, drawRadius * 0.05,
          b.x, b.y, drawRadius,
        );
        gradient.addColorStop(0, b.color + "EE");
        gradient.addColorStop(0.6, b.color + "CC");
        gradient.addColorStop(1, b.color + "99");

        ctx.beginPath();
        ctx.arc(b.x, b.y, drawRadius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();

        // Prominent border
        ctx.beginPath();
        ctx.arc(b.x, b.y, drawRadius, 0, Math.PI * 2);
        ctx.strokeStyle = b.color + "DD";
        ctx.lineWidth = 2;
        ctx.stroke();

        // Glass shine highlight
        ctx.beginPath();
        ctx.arc(b.x - drawRadius * 0.2, b.y - drawRadius * 0.25, drawRadius * 0.25, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.fill();

        // Symbol — large and clear
        ctx.font = `${drawRadius * 0.8}px serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(b.symbol, b.x + 1, b.y + 2);
      }

      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);
    window.addEventListener("resize", resize);

    return () => {
      cancelAnimationFrame(animFrameRef.current);
      if (spawnTimerRef.current) clearInterval(spawnTimerRef.current);
      window.removeEventListener("resize", resize);
      bubblesRef.current = [];
    };
  }, [active, spawnBubble]);

  // Clean up floating scores
  useEffect(() => {
    if (floatingScores.length === 0) return;
    const timer = setTimeout(() => {
      setFloatingScores((prev) => prev.filter((s) => Date.now() - s.created < 700));
    }, 750);
    return () => clearTimeout(timer);
  }, [floatingScores]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;

    const bubbles = bubblesRef.current;
    for (let i = bubbles.length - 1; i >= 0; i--) {
      const b = bubbles[i];
      if (b.popping) continue;
      const dx = cx - b.x;
      const dy = cy - b.y;
      if (dx * dx + dy * dy <= b.radius * b.radius * 1.2) {
        b.popping = true;
        b.popProgress = 0;
        setScore((s) => s + 1);
        if (!hasPopped) setHasPopped(true);
        setFloatingScores((prev) => [
          ...prev,
          { id: b.id, x: b.x, y: b.y, opacity: 1, created: Date.now() },
        ]);
        break;
      }
    }
  };

  return (
    <div className={`relative w-full h-full ${className}`}>
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        className="absolute inset-0 w-full h-full cursor-pointer"
        style={{ zIndex: 1 }}
      />

      {/* Header prompt — large and obvious */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 pointer-events-none">
        {!hasPopped ? (
          <div className="bg-white/90 backdrop-blur-sm rounded-full px-4 py-1.5 shadow-md border border-gray-200/80 flex items-center gap-2 animate-pop-in">
            <span className="text-lg">&#x1F449;</span>
            <span className="text-sm font-bold text-gray-700">Pop the bubbles!</span>
          </div>
        ) : (
          <div className="bg-white/90 backdrop-blur-sm rounded-full px-4 py-1.5 shadow-md border border-gray-200/80 animate-scale-in">
            <span className="text-sm font-bold text-gray-700">
              {score < 5 ? "Keep going!" : score < 15 ? "Nice! \u{1F389}" : "Bubble master! \u{1F525}"}{" "}
              <span className="text-xs font-medium text-gray-500">{score} popped</span>
            </span>
          </div>
        )}
      </div>

      {/* Floating +1 scores */}
      {floatingScores.map((fs) => {
        const age = Date.now() - fs.created;
        const opacity = Math.max(0, 1 - age / 700);
        const offsetY = (age / 700) * 40;
        return (
          <div
            key={fs.id}
            className="absolute z-10 text-base font-extrabold pointer-events-none"
            style={{
              left: fs.x,
              top: fs.y - offsetY,
              opacity,
              color: accentColor,
              transform: "translate(-50%, -50%)",
              transition: "none",
              textShadow: "0 1px 3px rgba(0,0,0,0.15)",
            }}
          >
            +1
          </div>
        );
      })}
    </div>
  );
}
