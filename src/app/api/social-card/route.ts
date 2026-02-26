import { NextRequest, NextResponse } from "next/server";
import { generateSocialCard } from "@/lib/agents/visualizer";

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { businessName, totalLeakage, topItem } = body;

        if (!businessName) {
            return NextResponse.json({ error: "Missing data" }, { status: 400 });
        }

        const imageBuffer = await generateSocialCard(businessName, totalLeakage || 0, topItem || "Optimization");

        return new NextResponse(new Blob([new Uint8Array(imageBuffer)]), {
            headers: {
                "Content-Type": "image/png",
                "Content-Disposition": `attachment; filename="MenuSurgeon-Report.png"`
            }
        });

    } catch (error) {
        console.error("Social Card Generation Failed:", error);
        return NextResponse.json({ error: "Generation Failed" }, { status: 500 });
    }
}
