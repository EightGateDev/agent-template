# Personas — How to Create and Use

Personas let the agent switch behavioral modes based on context.
Each persona is a `.md` file in this directory with its own tone, rules, and focus area.

---

## How the system works

- **Active persona** is tracked in `personas/state.json`
- The agent reads the active persona file before responding
- After 2 hours of silence, the agent auto-resets to `default`
- `shared.md` rules ALWAYS apply, regardless of active persona

State machine: `personas/role.py`

```bash
# Check active persona
python personas/role.py get

# Switch to a persona
python personas/role.py set finance

# Extend session timeout (call this after each reply)
python personas/role.py touch

# Force back to default
python personas/role.py reset

# Full status with timing info
python personas/role.py status

# List available personas
python personas/role.py list
```

---

## Creating a new persona

1. Create a new file: `personas/<name>.md`
   Use only lowercase letters and hyphens. Examples: `finance.md`, `english-tutor.md`, `medical.md`

2. Structure it with these sections:

```markdown
# Persona: <Display Name> <optional emoji>

## Purpose
One sentence — what this persona is for.

## Tone
How this persona speaks. Adjustments to the default tone from shared.md.

## Triggers — switch to this persona when
Specific phrases, topics, or signals that should activate this persona.

## Behavior
What this persona does differently. Specific workflow patterns if relevant.

## Memory
What to read at the start of this persona's session.
What to write before switching away.

## Switch back to default when
Signals that this topic is closed and we should return.

## Visual marker (optional)
Emoji prefix or other identifier shown in responses during this mode.
```

3. Add it to `default.md` under the "Switch to specialized persona when" section

4. Tell the agent: "create a persona called X" — it will activate it automatically

---

## Example: a simple custom persona

`personas/work-focus.md`:
```markdown
# Persona: Work Focus 🎯

## Purpose
Deep work mode — help with professional tasks, project planning, and technical decisions.

## Tone
Precise, structured, no small talk. Bullet points and concrete actions.

## Triggers
"work mode", "let's focus", "project planning", explicit work task keywords.

## Behavior
- Skip pleasantries entirely
- Structure all responses as: summary → action items → blockers
- Keep sessions time-bounded: "what do you want to complete in this session?"
- Track session goal and remind if conversation drifts

## Switch back to default when
"done for today", "taking a break", casual non-work message after task completion.

## Visual marker
🎯 prefix on responses.
```

---

## Notes

- The `shared.md` file cannot be overridden by individual personas — its rules always apply
- Don't create personas for things the default persona handles well
- The `default.md` persona auto-loads when no other is active
- Persona files are just instructions — they don't change what skills are available
- File size: aim for 200–500 lines max. Longer files get less attention in context.
