import * as admin from 'firebase-admin';

if (!admin.apps.length) {
    try {
        admin.initializeApp({
            credential: admin.credential.applicationDefault(),
            projectId: 'hephae-co-dev',
        });
        console.log("[Firebase] Admin SDK Initialized correctly.");
    } catch (e: any) {
        console.error("[Firebase] Error initializing Admin SDK:", e.message);
    }
}

export const db = admin.firestore();
export const storage = admin.storage().bucket('everything-hephae');
