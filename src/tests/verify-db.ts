import * as admin from 'firebase-admin';

async function verify() {
    try {
        admin.initializeApp({
            credential: admin.credential.applicationDefault(),
            projectId: 'hephae-co',
        });
        const db = admin.firestore();
        const snap = await db.collection('discovered_businesses').limit(5).get();
        console.log(`✅ SUCCESS: Found ${snap.size} documents in 'discovered_businesses'`);
        snap.forEach(doc => {
            console.log(`   -> Document ID: ${doc.id}`);
            const data = doc.data();
            console.log(`      Name: ${data.name}`);
            console.log(`      Menu Size: ${data.menu_items?.length || 0}`);
            console.log(`      Competitors Found: ${data.competitors?.length || 0}`);
        });
    } catch (e: any) {
        console.error("❌ Firebase Check Failed:", e.message);
    }
}

verify();
