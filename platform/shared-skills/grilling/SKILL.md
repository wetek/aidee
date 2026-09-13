---
name: grilling
description: Core interview protocol for tree-structured decision interrogation.
---

# Grilling

The foundational interview protocol for stress-testing plans, ideas, and system architectures before implementation.

## Protocol Structure

1. **Map the design tree:** Model the problem space as a tree where high-level decisions branch into downstream questions.
2. **Work in rounds:**
   - The **frontier** consists of all decisions whose prerequisite decisions are already settled.
   - Ask all questions on the frontier in one structured round.
   - For each question, provide context and a recommended default.
3. **Format question rounds:**

```markdown
❓ **Q1** - **[Question Title]**: [Detailed question body with choices and trade-offs]
➡️ [Recommended answer and rationale]

---

❓ **Q2** - **[Question Title]**: [Detailed question body with choices and trade-offs]
➡️ [Recommended answer and rationale]
```

4. **Separate facts from decisions:**
   - Finding facts is the agent's job (inspecting files, running commands, reading configs).
   - Making business and architectural choices belongs to the user.
5. **Completion:** The session is complete when the frontier is empty and all requirements are confirmed.
