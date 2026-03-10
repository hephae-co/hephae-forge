# Review: Human-in-the-Loop Evaluation Strategy

This review analyzes the current "Add to Eval" (`save-fixture`) flow and provides recommendations for how this data should be used to improve your LLMs.

---

## 1. Current State: "Manual Fixture Collection"
The system currently allows an Admin to click a button that:
1.  Takes the current business state (identity, latest outputs).
2.  Saves it to a `fixtures` collection in Firestore.
3.  Registers it with the `hephae_db.eval.grounding` pipeline.

**The Gap:** This data is currently "Static." It is stored for future testing, but it isn't actively "Feeding" the agents to make them smarter in real-time.

---

## 2. Recommendation: The "Closed-Loop Grounding" Flow
To truly improve the LLMs, we must move from "Saving Test Data" to **"Active Grounding."**

### P0 Action: Dynamic Few-Shot Injection
*   **The Logic:** When an agent (e.g., `SEOAuditor`) runs, it should first query the `fixtures` collection for the **3 most relevant "Gold Standard" examples** for that sector.
*   **Implementation:** 
    1.  Update the agent's prompt to include a `{{few_shot_examples}}` block.
    2.  The runner pulls verified fixtures where `score > 90` and `adminNotes` indicate "Perfect Run."
*   **Benefit:** The LLM learns the "Hephae Tone" and "Precision" from your manual approvals without you having to re-train the model.

### P1 Action: "Hallucination Delta" Analysis
*   **The Logic:** When an Admin "Corrects" a data point (e.g., fixing a phone number or removing a hallucinated competitor), the system should save **Both** the "Hallucination" and the "Correction."
*   **Benefit:** This creates a **Negative-Positive pair**. During your eval runs, you can specifically test if new models still make the "Old Hallucination."

---

## 3. Improving the "Add to Eval" Workflow

| Feature | Current Flow | Recommended Update |
| :--- | :--- | :--- |
| **Data Scope** | Entire business doc | **Field-level tagging.** Allow Admin to mark *specific* fields as "Verified" or "Hallucinated." |
| **Metadata** | Notes string | **"Reason for Eval" tags.** (e.g., `edge_case`, `hallucination_fixed`, `high_quality`). |
| **Usage** | Manual Test Runs | **Grounding Memory Service.** Automatic injection into prompt context. |

---

## 4. Technical Roadmap: "The Eval Moat"

1.  **Stage 1 (Immediate):** Update `save_fixture_from_business` to include a `is_gold_standard` boolean. 
2.  **Stage 2 (Short-term):** Implement a `GroundingMemoryService` that uses vector search to find "Gold Standard" fixtures based on the current business's sector and location.
3.  **Stage 3 (Future):** Automated Fine-Tuning. Periodically export the "Correction Pairs" to Vertex AI for supervised fine-tuning of Gemini Flash models.

---

## 5. Conclusion
Your manual review process is your **proprietary data engine**. By field-level tagging and using these verified results as **Dynamic Grounding**, you ensure that your human QC doesn't just "Fix one business," but **"Fixes the Agent"** for every future business.

**Would you like me to start by updating the `fixtures.py` schema to support "Gold Standard" tagging and "Correction" pairs?**
