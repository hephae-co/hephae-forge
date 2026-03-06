import { Mission } from "./types";

export const MISSIONS: Mission[] = [
  {
    id: "customer_engagement",
    emoji: "\u{1F91D}",
    title: "Customer Engagement Crisis",
    description:
      "A loyal regular mentions they haven't heard from you in months. Your customer list is scattered across paper logs and old spreadsheets.",
    choices: [
      {
        id: "manual_reachout",
        text: "Call Top Customers Individually",
        type: "manual",
        effects: { time: -40, budget: 0, sanity: -20 },
      },
      {
        id: "email_template",
        text: "Send a standard email blast",
        type: "digital",
        effects: { time: -15, budget: -10, sanity: -5 },
      },
      {
        id: "ai_crm",
        text: "Deploy AI-driven CRM automation",
        type: "ai",
        effects: { time: -5, budget: -25, sanity: 15 },
      },
    ],
  },
  {
    id: "inventory_optimization",
    emoji: "\u{1F4CA}",
    title: "Hidden Profit Leakage",
    description:
      "You suspect you're over-ordering high-cost ingredients, but tracking waste is a nightmare with your current system.",
    choices: [
      {
        id: "manual_audit",
        text: "Conduct a 4-hour manual audit",
        type: "manual",
        effects: { time: -50, budget: 0, sanity: -30 },
      },
      {
        id: "excel_tracking",
        text: "Set up an advanced Excel tracker",
        type: "digital",
        effects: { time: -25, budget: -5, sanity: -10 },
      },
      {
        id: "ai_forecasting",
        text: "Use AI for predictive ordering",
        type: "ai",
        effects: { time: -10, budget: -20, sanity: 20 },
      },
    ],
  },
  {
    id: "content_marketing",
    emoji: "\u{1F4F8}",
    title: "Digital Presence Gap",
    description:
      "Your competitors are posting daily, but you don't have a dedicated marketing team to handle the constant content demands.",
    choices: [
      {
        id: "diy_content",
        text: "Spend your evenings creating posts",
        type: "manual",
        effects: { time: -30, budget: 0, sanity: -25 },
      },
      {
        id: "freelancer",
        text: "Hire a part-time freelancer",
        type: "digital",
        effects: { time: -5, budget: -40, sanity: 10 },
      },
      {
        id: "ai_creator",
        text: "Use AI content generation tools",
        type: "ai",
        effects: { time: -5, budget: -15, sanity: 15 },
      },
    ],
  },
  {
    id: "financial_health",
    emoji: "\u{1F4B0}",
    title: 'The Friday "Profit Panic"',
    description:
      "It's Friday night. You need to know your exact margin for the week to plan for next week's payroll, but receipts are everywhere.",
    choices: [
      {
        id: "calculator_crunch",
        text: "Crunch numbers with a calculator",
        type: "manual",
        effects: { time: -40, budget: 0, sanity: -40 },
      },
      {
        id: "bookkeeper",
        text: "Wait for your monthly bookkeeper",
        type: "digital",
        effects: { time: 0, budget: -30, sanity: -10 },
      },
      {
        id: "ai_finance",
        text: "Scan and analyze with AI Finance",
        type: "ai",
        effects: { time: -5, budget: -10, sanity: 25 },
      },
    ],
  },
  {
    id: "hiring_workflow",
    emoji: "\u{1F464}",
    title: "Critical Staffing Need",
    description:
      "You need to hire a new manager, but reviewing 100+ applications is taking time away from actually running the business.",
    choices: [
      {
        id: "read_every_resume",
        text: "Read every resume personally",
        type: "manual",
        effects: { time: -60, budget: 0, sanity: -50 },
      },
      {
        id: "job_board_filters",
        text: "Use basic job board filters",
        type: "digital",
        effects: { time: -20, budget: -15, sanity: 0 },
      },
      {
        id: "ai_screening",
        text: "Use AI for candidate screening",
        type: "ai",
        effects: { time: -5, budget: -10, sanity: 20 },
      },
    ],
  },
];
