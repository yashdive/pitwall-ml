# docs/

**What this folder is:** the written record of the **system**: how it is built, why, and what comes next. (What we learned about the **data** is in `research/` instead.)

## Files

| File | What it is | Read it when |
|---|---|---|
| `ARCHITECTURE.md` | One diagram of the whole system and a short section per component: what it does, where its code is, what it reads and writes, how to run it | You want the big picture, or need to find where something lives |
| `DECISIONS.md` | Every design decision (D1, D2, …): what we decided, why, and what we did not choose | You wonder "why is it done this way?" before changing something |
| `ROADMAP.md` | The stages of the project with a checklist (✅ done, 🔨 in progress, ⬜ not started) | You want to know what is done and what is next |
| `CONCEPTS.md` | A glossary of ideas, written in our own words (idempotency, atomic writes, data leakage, …) | You meet a term you want to understand |
| `design/` | One detailed design note per component, written and approved before the code | You want the details of one component (see `design/README.md`) |

## Good to know
- Every folder of the project has its own `README.md` describing its files.
