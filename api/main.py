import os
import textwrap
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from jinja2 import Template
from dotenv import load_dotenv

import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# ---- Config ----
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    # On Vercel, set the environment variable in the dashboard
    # Locally, put it in a .env and `export $(cat .env | xargs)`
    raise RuntimeError("GEMINI_API_KEY is not set")

genai.configure(api_key=GEMINI_API_KEY)

# Choose a fast, inexpensive model for responsive UX
# You can swap to 'gemini-1.5-pro' if you want higher quality/cost.
model = genai.GenerativeModel("gemini-1.5-flash")

app = FastAPI(title="Story Agent (Prompt → Story)")

# ---- HTML (simple, no build step) ----
INDEX_HTML = Template("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Story Agent — Prompt ➜ Story</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', Arial; margin: 0; padding: 24px; max-width: 900px; }
    h1 { margin: 0 0 8px; font-size: 1.6rem; }
    .muted { color: #777; margin-bottom: 16px; }
    textarea, input, select { width: 100%; padding: 12px; margin: 8px 0 12px; font-size: 1rem; }
    button { padding: 10px 16px; font-size: 1rem; cursor: pointer; border-radius: 8px; border: 1px solid #444; background: transparent; }
    button.primary { background: #111; color: #fff; border-color: #111; }
    .row { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: start; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 16px; margin-top: 12px; }
    .story { white-space: pre-wrap; line-height: 1.6; }
    .hidden { display:none; }
    .controls { display:flex; gap:8px; flex-wrap:wrap; }
    .label { font-weight:600; margin-top:8px; }
    .small { font-size: .9rem; color: #666; }
  </style>
</head>
<body>
  <h1>Story Agent</h1>
  <div class="muted">Prompt ➜ complete, polished short story. Then tweak a transition/twist if you don’t like it.</div>

  <form id="gen-form" class="card" onsubmit="return false;">
    <div class="label">Your inspiration (e.g., “a beautiful life story”, “a horror story in an old cabin”, “a genius scientist’s journey”)</div>
    <textarea id="inspiration" rows="3" placeholder="Type your idea..."></textarea>

    <div class="row">
      <div>
        <label class="label">Tone</label>
        <select id="tone">
          <option value="neutral">Neutral (genre-aware)</option>
          <option value="warm">Warm</option>
          <option value="dark">Dark</option>
          <option value="whimsical">Whimsical</option>
          <option value="dramatic">Dramatic</option>
        </select>
      </div>
      <div style="align-self:end;">
        <button class="primary" id="btn-generate">Generate Story</button>
      </div>
    </div>
    <div class="small">~600–800 words. The agent embeds hidden markers to enable precise rewrites later.</div>
  </form>

  <div id="story-card" class="card hidden">
    <div class="label">Title</div>
    <div id="title"></div>

    <div class="label" style="margin-top:12px;">Story</div>
    <div id="story" class="story"></div>

    <div class="label" style="margin-top:16px;">Don’t like a transition/twist?</div>
    <textarea id="feedback" rows="3" placeholder="e.g., Skip the college phase; have them directly enter a research university." ></textarea>
    <div class="controls">
      <button id="btn-revise">Apply Change</button>
      <button id="btn-reset">Start Over</button>
    </div>

    <!-- We keep the canon + markers here; not shown to user -->
    <textarea id="rawStory" class="hidden"></textarea>
  </div>

<script>
const genBtn = document.getElementById('btn-generate');
const reviseBtn = document.getElementById('btn-revise');
const resetBtn = document.getElementById('btn-reset');

async function generateStory(){
  const inspiration = document.getElementById('inspiration').value.trim();
  const tone = document.getElementById('tone').value;
  if(!inspiration){ alert('Give me some inspiration.'); return; }
  genBtn.disabled = true; genBtn.textContent = 'Generating...';

  const res = await fetch('/generate', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ inspiration, tone })
  });
  const data = await res.json();
  genBtn.disabled = false; genBtn.textContent = 'Generate Story';

  if(data.error){ alert(data.error); return; }

  document.getElementById('title').textContent = data.title || '(untitled)';
  document.getElementById('story').textContent = data.story_clean;
  document.getElementById('rawStory').value = data.story_raw;
  document.getElementById('story-card').classList.remove('hidden');
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

async function reviseStory(){
  const feedback = document.getElementById('feedback').value.trim();
  const rawStory = document.getElementById('rawStory').value;
  if(!feedback){ alert('Tell me what to change.'); return; }
  reviseBtn.disabled = true; reviseBtn.textContent='Revising...';

  const res = await fetch('/revise', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ feedback, original_story: rawStory })
  });
  const data = await res.json();
  reviseBtn.disabled = false; reviseBtn.textContent='Apply Change';

  if(data.error){ alert(data.error); return; }

  document.getElementById('title').textContent = data.title || '(untitled)';
  document.getElementById('story').textContent = data.story_clean;
  document.getElementById('rawStory').value = data.story_raw;
  document.getElementById('feedback').value = '';
}

function resetAll(){
  document.getElementById('story-card').classList.add('hidden');
  document.getElementById('inspiration').value = '';
  document.getElementById('feedback').value = '';
  document.getElementById('title').textContent = '';
  document.getElementById('story').textContent = '';
  document.getElementById('rawStory').value = '';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

genBtn.onclick = generateStory;
reviseBtn.onclick = reviseStory;
resetBtn.onclick = resetAll;
</script>
</body>
</html>
""")

# ---- Pydantic Schemas ----
class GenerateRequest(BaseModel):
    inspiration: str
    tone: str = "neutral"

class ReviseRequest(BaseModel):
    feedback: str
    original_story: str

# ---- Prompt Templates ----
def story_prompt(inspiration: str, tone: str) -> str:
    # Neutral narrator, genre-aware. Mark transitions with [TWIST#] to allow surgical rewrites.
    return textwrap.dedent(f"""
    You are a skilled storyteller. Write a complete, cohesive short story based on the user's inspiration.

    Requirements:
    - Narration: Neutral narrator that adapts to the implied genre/tone. Requested tone hint: "{tone}".
    - Length: ~600–800 words. Make it feel polished and intentional.
    - Structure: Clear beginning, middle, and resolution. 2–4 natural transitions or twists.
    - IMPORTANT: Insert bracket markers at major transitions to enable later editing, exactly like:
        [TWIST1] ... (text continues) ...
        [TWIST2] ... (text continues) ...
      Keep these markers embedded only around transitions you’d reasonably rewrite later.
    - Consistency: Maintain character names, setting logic, and timeline continuity.
    - Output strictly in the following format:

    Title: <concise, evocative title>

    Story:
    <the full story body including [TWIST#] markers where appropriate>

    User inspiration: "{inspiration}"
    """)

def revision_prompt(original_story: str, feedback: str) -> str:
    return textwrap.dedent(f"""
    You will revise the story below to implement the user's requested change(s) without breaking continuity.

    Instructions:
    - Read the user's feedback and adjust the most relevant transition(s) marked with [TWIST#].
    - Keep character names, setting facts, and tone consistent.
    - Prefer minimal rewrite: change the targeted transition plus any sentences needed for coherence.
    - Keep the [TWIST#] markers in place (they help future edits), but you may add or remove one if it improves structure.
    - Length should remain similar to the original (roughly 600–800 words).
    - Output strictly in the same format:

    Title: <title>

    Story:
    <full revised story body including [TWIST#] markers>

    User feedback: "{feedback}"

    Original story:
    {original_story}
    """)

# ---- Helpers ----
def call_gemini(prompt: str) -> str:
    """Call Gemini API with error handling and rate limiting awareness"""
    try:
        # Single-turn generation for determinism & cheapness
        resp = model.generate_content(prompt)
        # google-generativeai returns text in resp.text
        return (resp.text or "").strip()
    except Exception as e:
        error_msg = str(e)
        if "RATE_LIMIT_EXCEEDED" in error_msg or "429" in error_msg:
            raise Exception("API quota exceeded. Please check your Google AI Studio quota limits or try again later.")
        elif "PERMISSION_DENIED" in error_msg or "403" in error_msg:
            raise Exception("API key doesn't have permission. Please check your API key in Google AI Studio.")
        elif "INVALID_ARGUMENT" in error_msg or "400" in error_msg:
            raise Exception("Invalid API request. Please check your API key configuration.")
        else:
            raise Exception(f"Gemini API error: {error_msg}")

def parse_gemini_output(text: str) -> tuple[str, str]:
    """
    Parse:
      Title: ...
      Story:
      ...
    Returns (title, story_raw).
    """
    title = ""
    story = ""

    # Very lightweight parsing; model is instructed to follow this format
    lines = text.splitlines()
    mode = None
    for ln in lines:
        if ln.strip().lower().startswith("title:"):
            title = ln.split(":", 1)[1].strip()
            mode = None
            continue
        if ln.strip().lower().startswith("story:"):
            mode = "story"
            continue
        if mode == "story":
            story += ln + "\n"

    # Clean trailing
    story = story.strip()
    return title, story

def strip_markers(story: str) -> str:
    # Show a clean story to readers; keep the raw version (with markers) hidden for surgical edits
    return story.replace("[TWIST1]", "").replace("[TWIST2]", "").replace("[TWIST3]", "").replace("[TWIST4]", "").strip()

# ---- Routes ----
@app.get("/", response_class=HTMLResponse)
async def index(_: Request):
    return INDEX_HTML.render()

@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        prompt = story_prompt(req.inspiration, req.tone)
        out = call_gemini(prompt)
        if not out:
            return JSONResponse({"error": "Empty response from model"}, status_code=500)

        title, story_raw = parse_gemini_output(out)
        if not story_raw:
            # Fallback: treat everything as story if format missed
            story_raw = out
        story_clean = strip_markers(story_raw)
        return {"title": title, "story_raw": story_raw, "story_clean": story_clean}
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)

@app.post("/revise")
async def revise(req: ReviseRequest):
    try:
        prompt = revision_prompt(req.original_story, req.feedback)
        out = call_gemini(prompt)
        if not out:
            return JSONResponse({"error": "Empty response from model"}, status_code=500)

        title, story_raw = parse_gemini_output(out)
        if not story_raw:
            story_raw = out
        story_clean = strip_markers(story_raw)
        return {"title": title, "story_raw": story_raw, "story_clean": story_clean}
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)
