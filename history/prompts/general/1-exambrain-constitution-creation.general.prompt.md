---
id: 1
title: exambrain-constitution-creation
stage: general
date: 2026-07-19
surface: agent
model: deepseek-v4-flash-free
feature: constitution
branch: main
user: saifullah
command: /sp.constitution
labels: [constitution, governance, foundation, sdd]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .specify/memory/constitution.md
tests:
  - none
---

## Prompt

Run the /sp.constitution command and write the constitution for this project. Also add code quality constraints — docstrings, comments, no workarounds.

(Full context: The user asked to study constitution.md files from 8 sibling projects under /home/saifullah/projects/, then synthesize and write a constitution for prepplease (ExamBrain). Code quality constraints were specifically requested as an add-on.)

## Response snapshot

Wrote a comprehensive 10-principle constitution for ExamBrain to .specify/memory/constitution.md, covering:
- Spec-Driven Development (SDD)
- Zero-Cost Infrastructure Mandate
- Agent Isolation & Contract-First
- Async-First Everywhere
- LLM Provider Abstraction
- TDD on Critical Paths
- Repository Pattern & Data Integrity
- Code Quality & Standards (with no workarounds, Google-style docstrings, mypy strict, ruff+black, no dead code, minimal diffs)
- Security by Default
- Observability & Operations

Plus tech stack constraints table, development workflow, and governance section. Version 1.0.0 ratified 2026-07-19.

## Outcome

- ✅ Impact: Foundation governance document written for ExamBrain project
- 🧪 Tests: N/A
- 📁 Files: .specify/memory/constitution.md (written), history/prompts/general/ (created)
- 🔁 Next prompts: Feature specs, agent implementations, service scaffolding
- 🧠 Reflection: Constitution draws patterns from 8 sibling projects while adapting to ExamBrain's multi-agent, multi-cloud, async architecture. Code quality section emphasizes practical discipline over ceremony.

## Evaluation notes (flywheel)

- Failure modes observed: N/A
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
