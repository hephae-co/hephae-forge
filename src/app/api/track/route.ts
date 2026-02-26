import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/firebase";
import * as admin from 'firebase-admin';

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { id, query, email } = body;

        // Route 1: Initial query logging
        if (!id && query) {
            const docRef = db.collection('hub_searches').doc();
            await docRef.set({
                query,
                timestamp: admin.firestore.FieldValue.serverTimestamp(),
                status: 'pending_email'
            });
            return NextResponse.json({ success: true, id: docRef.id });
        }

        // Route 2: Email update
        if (id && email) {
            const docRef = db.collection('hub_searches').doc(id);
            await docRef.update({
                email,
                email_captured_at: admin.firestore.FieldValue.serverTimestamp(),
                status: 'captured'
            });
            return NextResponse.json({ success: true });
        }

        return NextResponse.json({ error: "Invalid Request payload" }, { status: 400 });

    } catch (error: any) {
        console.error("[API/Track] Firestore failed:", error);
        return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
    }
}
