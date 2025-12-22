You are generating a PRP (Product Requirements Prompt) from the provided INITIAL.md.

Process:
1) Read the feature request carefully.
2) Inspect repository structure and existing docs/ and examples/ patterns.
3) Identify risks, missing context, and required clarifications; propose assumptions explicitly.
4) Produce a PRP with:
   - Objective / non-objectives
   - Functional requirements
   - Data contracts / schemas
   - Implementation plan broken into small, testable milestones
   - Validation gates (commands to run, checks)
   - Rollback plan
   - Confidence score and known unknowns

Output the PRP to PRPs/<feature_name>.md
