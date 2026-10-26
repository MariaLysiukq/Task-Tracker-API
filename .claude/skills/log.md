Trigger: At the conclusion of ANY coding task, test generation, or bug fix.
Action: Automatically append a new entry to docs/ai-log.md. 
The entry MUST include:   
Task/Request: What the user asked for.
Agent Actions: A brief summary of what you did.
Changed Files/Commit: The specific files modified.
Executed Checks: Note that pytest/pre-commit was run.
