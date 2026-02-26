import { SequentialAgent } from "@google/adk";
import { visionIntakeAgent } from "../visionIntake";
import { benchmarkerAgent } from "../benchmarker";
import { commodityWatchdogAgent } from "../commodityWatchdog";
import { surgeonAgent } from "../surgeon";
import { advisorAgent } from "../advisor";

export const marginSurgeryOrchestrator = new SequentialAgent({
    name: 'MarginSurgeryOrchestrator',
    description: 'Executes the full margin surgeon pipeline sequentially, taking the output of each agent and passing it to the next.',
    subAgents: [
        visionIntakeAgent,
        benchmarkerAgent,
        commodityWatchdogAgent,
        surgeonAgent,
        advisorAgent
    ]
});
