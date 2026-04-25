import os
import openai

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

I would have added a user-feedback loop after the final story is delivered — asking the child (or parent)
to rate the story and request changes ("make it funnier", "add a dragon"), then feeding that feedback into
a revision pass. I would also have extracted the story's moral/lesson explicitly and offered to print it as
a separate "What did we learn today?" card, making the tool useful for parents and educators. Finally, I'd
package it as a small FastAPI web service with a simple HTML front-end so it can be used from a browser
without any CLI knowledge.
"""


# ─────────────────────────────────────────────
# Core LLM wrapper (model unchanged per spec)
# ─────────────────────────────────────────────

def call_model(prompt: str, max_tokens: int = 3000, temperature: float = 0.7) -> str:
    openai.api_key = os.getenv("OPENAI_API_KEY")  # please use your own openai api key here.
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message["content"]  # type: ignore


# ─────────────────────────────────────────────
# Step 1: Categorise the request
# ─────────────────────────────────────────────

CATEGORISE_PROMPT = """\
You are a children's story librarian. A child has asked for a bedtime story.
Read the request carefully and classify it into ONE of these categories:

  ADVENTURE  – quests, journeys, brave heroes
  FRIENDSHIP – bonds between characters, helping others
  MAGIC      – wizards, fairies, enchanted objects
  ANIMALS    – talking animals, wildlife, pets
  MYSTERY    – gentle puzzles, hidden treasures
  FAMILY     – siblings, parents, home life

Respond with ONLY the single category word (e.g. ADVENTURE).

Child's request: {request}
"""

def categorise(request: str) -> str:
    category = call_model(CATEGORISE_PROMPT.format(request=request), max_tokens=10, temperature=0.0).strip().upper()
    valid = {"ADVENTURE", "FRIENDSHIP", "MAGIC", "ANIMALS", "MYSTERY", "FAMILY"}
    return category if category in valid else "ADVENTURE"


# ─────────────────────────────────────────────
# Step 2: Generate a first-draft story
# ─────────────────────────────────────────────

STORY_SYSTEM = {
    "ADVENTURE":  "Use a classic three-act arc: a call to adventure, a challenge overcome through courage, and a triumphant return home.",
    "FRIENDSHIP": "Focus on characters helping each other through a problem; end with a warm moment of connection.",
    "MAGIC":      "Introduce a magical object or creature early; let its magic create both the problem and the solution.",
    "ANIMALS":    "Give each animal a distinct personality quirk; use simple nature imagery kids love.",
    "MYSTERY":    "Plant one small clue in the first paragraph that pays off at the end; keep the tone cosy, never scary.",
    "FAMILY":     "Show a relatable everyday moment; let the child character take the lead in solving a home problem.",
}

STORY_PROMPT = """\
You are a warm, creative children's story author. Write a bedtime story for children aged 5–10.

Story category: {category}
Storytelling strategy: {strategy}

Guidelines:
- Length: 350–500 words
- Language: simple vocabulary a 5-year-old can follow, but engaging enough for a 10-year-old
- Structure: clear beginning, middle, and end
- Tone: cosy, gentle, positive — perfect for winding down at bedtime
- End with a satisfying conclusion and a subtle lesson (do NOT state the moral explicitly)
- NO scary content, NO violence, NO adult themes

Child's story request: {request}

Write the story now:
"""

def generate_story(request: str, category: str) -> str:
    strategy = STORY_SYSTEM[category]
    prompt = STORY_PROMPT.format(category=category, strategy=strategy, request=request)
    return call_model(prompt, max_tokens=700, temperature=0.85)


# ─────────────────────────────────────────────
# Step 3: LLM Judge — score and critique
# ─────────────────────────────────────────────

JUDGE_PROMPT = """\
You are a strict but fair children's literature editor. Your job is to evaluate a bedtime story
for children aged 5–10 and provide structured feedback.

Score the story on each criterion from 1 (poor) to 5 (excellent):
  - AGE_APPROPRIATE : vocabulary and themes suit ages 5–10
  - ENGAGEMENT      : the story holds attention; interesting characters and plot
  - STRUCTURE       : clear beginning, middle, end
  - BEDTIME_TONE    : calming, positive, safe for bedtime
  - LESSON          : a gentle moral is present but not preachy

Then write 2–3 specific, actionable suggestions for improvement.

Respond ONLY in this exact format (no extra text):
SCORES: AGE_APPROPRIATE=X ENGAGEMENT=X STRUCTURE=X BEDTIME_TONE=X LESSON=X
SUGGESTIONS:
- <suggestion 1>
- <suggestion 2>
- <suggestion 3 (optional)>

Story to evaluate:
\"\"\"
{story}
\"\"\"
"""

def judge_story(story: str) -> tuple[dict, list[str]]:
    """Returns (scores_dict, suggestions_list). Falls back gracefully on parse errors."""
    raw = call_model(JUDGE_PROMPT.format(story=story), max_tokens=300, temperature=0.2)

    scores: dict = {}
    suggestions: list[str] = []

    try:
        lines = raw.strip().splitlines()
        score_line = next(l for l in lines if l.startswith("SCORES:"))
        for part in score_line.replace("SCORES:", "").split():
            key, val = part.split("=")
            scores[key.strip()] = int(val.strip())

        in_suggestions = False
        for line in lines:
            if line.startswith("SUGGESTIONS:"):
                in_suggestions = True
                continue
            if in_suggestions and line.strip().startswith("-"):
                suggestions.append(line.strip().lstrip("- ").strip())
    except Exception:
        # Graceful fallback — don't crash if the judge output is malformed
        scores = {k: 3 for k in ["AGE_APPROPRIATE", "ENGAGEMENT", "STRUCTURE", "BEDTIME_TONE", "LESSON"]}
        suggestions = ["Ensure vocabulary is simple.", "Add more sensory details.", "Strengthen the ending."]

    return scores, suggestions


def average_score(scores: dict) -> float:
    if not scores:
        return 0.0
    return sum(scores.values()) / len(scores)


# ─────────────────────────────────────────────
# Step 4: Revise the story using judge feedback
# ─────────────────────────────────────────────

REVISION_PROMPT = """\
You are a children's story author revising your own work based on an editor's feedback.

Original story:
\"\"\"
{story}
\"\"\"

Editor's suggestions:
{suggestions}

Rewrite the story, addressing all suggestions while keeping it 350–500 words,
cosy in tone, and appropriate for ages 5–10. Output ONLY the revised story.
"""

def revise_story(story: str, suggestions: list[str]) -> str:
    bullet_list = "\n".join(f"- {s}" for s in suggestions)
    prompt = REVISION_PROMPT.format(story=story, suggestions=bullet_list)
    return call_model(prompt, max_tokens=700, temperature=0.75)


# ─────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────

SCORE_THRESHOLD = 4.0   # Accept the story if avg judge score >= this
MAX_REVISIONS   = 2     # Never loop more than this many revision cycles

def run_pipeline(request: str, verbose: bool = True) -> str:
    def log(msg: str):
        if verbose:
            print(msg)

    log("\n📚 Categorising your story request…")
    category = categorise(request)
    log(f"   Category detected: {category}")

    log("\n✍️  Writing a first draft…")
    story = generate_story(request, category)

    for iteration in range(1, MAX_REVISIONS + 2):   # +2 so we judge even after final revision
        log(f"\n🧑‍⚖️  Judge reviewing story (iteration {iteration})…")
        scores, suggestions = judge_story(story)
        avg = average_score(scores)

        log(f"   Scores: {scores}")
        log(f"   Average: {avg:.1f}/5.0")

        if avg >= SCORE_THRESHOLD or iteration > MAX_REVISIONS:
            if avg >= SCORE_THRESHOLD:
                log(f"\n✅  Story accepted by judge (score {avg:.1f} ≥ {SCORE_THRESHOLD})")
            else:
                log(f"\n⚠️  Max revisions reached — delivering best version (score {avg:.1f})")
            break

        log(f"\n🔄  Revising story based on judge feedback…")
        log(f"   Suggestions: {suggestions}")
        story = revise_story(story, suggestions)

    return story


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

example_requests = "A story about a girl named Alice and her best friend Bob, who happens to be a cat."

def main():
    print("🌙 Welcome to the Bedtime Story Teller!\n")
    user_input = input("What kind of story do you want to hear?\n> ").strip()

    if not user_input:
        print(f"No input given — using example: {example_requests}")
        user_input = example_requests

    story = run_pipeline(user_input, verbose=True)

    print("\n" + "═" * 60)
    print("🌟  YOUR BEDTIME STORY")
    print("═" * 60)
    print(story)
    print("═" * 60)
    print("\nGoodnight! 🌙")


if __name__ == "__main__":
    main()
