export interface Choice {
  id: string;
  text: string;
  type: "manual" | "digital" | "ai";
  effects: { time: number; budget: number; sanity: number };
}

export interface Mission {
  id: string;
  emoji: string;
  title: string;
  description: string;
  choices: Choice[];
}

export interface GameHistory {
  choices: { missionId: string; choiceId: string; type: string }[];
  finalStats: { time: number; budget: number; sanity: number };
}

export interface QuizResult {
  score: number;
  archetype: string;
  summary: string;
}
