# Hephae Skills: Industry Intelligence

The "Skills" layer is the knowledge base that allows Hephae Agents to be vertical-aware. It decouples the **Logic** (how to analyze) from the **Knowledge** (what to look for in a specific industry).

---

## 1. Concept: Config-Driven Intelligence

Instead of hardcoding rules for "Restaurants" into the SEO agent, we use a Skill Configuration (YAML). This allows us to scale to new industries (e.g., Barbers, Bakeries) by only adding a configuration file.

### What a Skill Defines:
- **Signal Weights**: How important is Instagram vs. a Website for this vertical?
- **Friction Keywords**: What words in a review indicate a "Pain Point" (e.g., "long wait" for barbers, "busy phone" for restaurants)?
- **Platform Lists**: Which CMS platforms are "High Maturity" for this vertical (e.g., Toast for food, Booksy for services)?
- **Capability Selection**: Which agents should run? (Barbers skip Margin Surgery but need Booking Analysis).

---

## 2. Directory Structure (`skills/`)

```
skills/
  └── industry_intelligence/
      ├── configs/
      │   ├── restaurants.yaml
      │   ├── barbers.yaml
      │   └── bakeries.yaml
      └── hephae_skills/
          ├── loader.py        # Loads YAML into Pydantic models
          ├── friction.py      # Regex logic for vertical-specific keywords
          └── calibration.py   # Logic for updating weights based on outcomes
```

---

## 3. The Compounding Loop

Skills are not static. The **CalibrationAgent** (see `docs/agents.md`) periodically reviews business outcomes in BigQuery.
- **Example**: If the data shows that 90% of "Successful" Barbers use a specific booking platform, the Calibration Agent will increase the "Digital Maturity" score for that platform in the `barbers.yaml` config.

---

## 4. Why this matters for Hephae

By moving vertical-specific logic into the Skills layer, we achieve:
1. **Zero-Code Scaling**: Launching a new industry requires zero Python changes.
2. **Global Learning**: Insights gained from bakeries in New Jersey can immediately be applied to bakeries in California.
3. **Targeted Outreach**: The outreach pitch automatically adjusts to the industry's most critical pain points.
