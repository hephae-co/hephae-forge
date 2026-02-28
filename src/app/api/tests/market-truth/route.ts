import { NextRequest, NextResponse } from "next/server";
import { runEvaluations } from "@/tests/run_evals";

export const maxDuration = 300; // Let this long E2E test run up to 5 minutes

export async function GET(req: NextRequest) {
    try {
        console.log("🚀 Initializing E2E Market Truth (LLM-as-a-Judge) Test Suite via API...");
        const results = await runEvaluations();

        return NextResponse.json({
            success: true,
            message: "Test Suite Execution Complete. Report generated at src/tests/report.md",
            results
        });
    } catch (e: any) {
        console.error("❌ Fatal Error in E2E Market Truth Test Suite:", e);
        return NextResponse.json({ success: false, error: e.message }, { status: 500 });
    }
}
