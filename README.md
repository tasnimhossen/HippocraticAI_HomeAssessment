# Bedtime Story Teller — Solution

## How to run

```bash
# 1. Install dependency
pip install openai

# 2. Set your OpenAI key (do NOT commit this)
export OPENAI_API_KEY="sk-..."

# 3. Run
python main.py
```

You'll be prompted to describe the story you want.  
The pipeline will print its progress and then display the final story.

---

## System Design

The system is a **multi-agent pipeline** with three LLM roles and an automated revision loop:

```
USER → CATEGORISER → STORY GENERATOR → LLM JUDGE → (score ≥ 4?) → OUTPUT
                                            ↑               |
                                       STORY REVISER ← NO, revise (≤2×)
```

See `diagram.html` for a full block diagram (open in any browser).

### Agents

| Agent | Role | Prompt strategy |
|---|---|---|
| **Categoriser** | Classifies the request into one of 6 genres (Adventure, Friendship, Magic, Animals, Mystery, Family) | Zero-shot classification; temp=0 for determinism |
| **Story Generator** | Writes a 350–500 word bedtime story tailored to the genre | Category-specific structural strategy injected into system prompt; temp=0.85 for creativity |
| **LLM Judge** | Scores 5 criteria (age-appropriateness, engagement, structure, bedtime tone, lesson) on a 1–5 scale and produces actionable suggestions | Strict output format enforced; temp=0.2 for consistency |
| **Story Reviser** | Rewrites the story incorporating judge feedback | Receives original story + bullet suggestions; temp=0.75 |

### Control flow

1. Classify the user's request.  
2. Generate a first draft.  
3. Judge scores the draft. If the average is ≥ 4.0, deliver it. Otherwise, revise and re-judge (max 2 revision cycles to avoid infinite loops).

---

## What I would build next (given 2 more hours)

*(Also written in `main.py`)*

1. **User feedback loop** — after the story is delivered, ask for a rating and specific change requests, then feed them into a targeted revision pass.  
2. **Explicit lesson card** — extract the story's moral and print it as a "What did we learn today?" section for parents and educators.  
3. **Web front-end** — wrap the pipeline in a small FastAPI service + HTML page so it can be used without a terminal.
