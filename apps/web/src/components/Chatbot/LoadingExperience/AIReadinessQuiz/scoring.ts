import { GameHistory, QuizResult } from "./types";

export function computeResult(history: GameHistory): QuizResult {
  const counts = { ai: 0, digital: 0, manual: 0 };
  for (const c of history.choices) {
    if (c.type === "ai") counts.ai++;
    else if (c.type === "digital") counts.digital++;
    else counts.manual++;
  }

  // Score: weighted by choice type + bonus from remaining stats
  const choiceScore = counts.ai * 18 + counts.digital * 10 + counts.manual * 4;
  const statsAvg =
    (history.finalStats.time +
      history.finalStats.budget +
      history.finalStats.sanity) /
    3;
  const statsBonus = Math.round(statsAvg * 0.1); // 0-10 bonus
  const score = Math.min(100, choiceScore + statsBonus);

  // Archetype
  let archetype: string;
  let summary: string;

  if (counts.ai >= 4) {
    archetype = "AI Pioneer";
    summary =
      "You instinctively reach for AI-first solutions. You're ready to leverage automation across your entire operation.";
  } else if (counts.ai >= 3) {
    archetype = "Pragmatic Scaler";
    summary =
      "You blend AI with proven methods strategically. You adopt technology where it makes the biggest impact.";
  } else if (counts.digital >= 3) {
    archetype = "Digital Adapter";
    summary =
      "You're comfortable with digital tools but haven't fully embraced AI yet. The next leap could transform your efficiency.";
  } else if (counts.ai >= 2) {
    archetype = "Curious Innovator";
    summary =
      "You're open to AI but still rely heavily on traditional methods. Targeted AI adoption could save you significant time.";
  } else {
    archetype = "Traditionalist Explorer";
    summary =
      "You prefer hands-on approaches. There's massive untapped potential in automating your most time-consuming tasks.";
  }

  return { score, archetype, summary };
}
