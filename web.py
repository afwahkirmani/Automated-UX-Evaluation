import streamlit as st
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from PIL import Image
import tempfile, os, json, re

# ── 1. PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Auto-UX Evaluator", page_icon="🤖", layout="wide")

st.markdown("""
<style>
  .metric-card {
    background: #1e1e2e;
    border: 1px solid #2e2e3e;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
  }
  .metric-label {
    font-size: 13px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
  }
  .metric-value {
    font-size: 42px;
    font-weight: 700;
    line-height: 1;
  }
  .metric-sub {
    font-size: 12px;
    color: #666;
    margin-top: 4px;
  }
  .score-bar-bg {
    background: #2e2e3e;
    border-radius: 999px;
    height: 10px;
    width: 100%;
    margin-top: 6px;
  }
  .score-bar-fill {
    height: 10px;
    border-radius: 999px;
  }
  .friction-card {
    background: #1a1a2a;
    border-left: 4px solid;
    border-radius: 0 10px 10px 0;
    padding: 16px 20px;
    margin-bottom: 14px;
  }
  .friction-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 10px;
  }
  .friction-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    margin-bottom: 6px;
    font-size: 14px;
  }
  .friction-key {
    color: #888;
    min-width: 120px;
    flex-shrink: 0;
  }
  .badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 500;
  }
  .win-card {
    background: #0f2a1a;
    border: 1px solid #1a4a2a;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
    font-size: 14px;
    color: #7ecf9a;
  }
  .section-title {
    font-size: 18px;
    font-weight: 600;
    margin: 28px 0 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid #2e2e3e;
  }
</style>
""", unsafe_allow_html=True)

st.title("🤖 Auto-UX Evaluator")
st.caption("AI-powered usability testing through the lens of accessibility personas")

# ── 2. PERSONAS ────────────────────────────────────────────────────────────────
PERSONAS = {
    "Motor Impairment": (
        "You have limited fine motor control. You rely entirely on keyboard navigation "
        "(Tab, Enter, arrow keys). You cannot hover, drag, or use a mouse. You need click "
        "targets of at least 44×44px. Time-limited interactions, carousels, and hover-only "
        "menus are inaccessible to you."
    ),
    "Color-Blind": (
        "You have deuteranopia (red-green color blindness), the most common form. "
        "You cannot distinguish red from green and struggle with low-contrast text. "
        "You rely on labels, icons, and contrast ratios — never color alone — to understand "
        "UI state (errors, success, warnings, links)."
    ),
    "Neurodivergent": (
        "You have ADHD and are sensitive to visual noise. Animations, auto-playing media, "
        "and busy layouts break your focus. You need clear visual hierarchy, consistent "
        "navigation, and unambiguous labels. Dense walls of text, jargon, and unpredictable "
        "UI patterns cause significant cognitive load."
    ),
}

# ── 3. SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Google Gemini API Key", type="password")
    persona = st.selectbox("Agent Persona", list(PERSONAS.keys()))
    st.info("Get a free key at aistudio.google.com")

# ── 4. HELPERS ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_driver_path():
    return ChromeDriverManager().install()

def get_browser_content(url):
    driver = None
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,900")
        driver = webdriver.Chrome(service=Service(get_driver_path()), options=options)
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img_path = tmp.name
        tmp.close()
        driver.save_screenshot(img_path)
        return driver.page_source, img_path
    except Exception as e:
        st.warning(f"Browser error: {e}")
        return None, None
    finally:
        if driver:
            driver.quit()

def extract_html_summary(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    title    = soup.title.string.strip() if soup.title else "None"
    lang     = soup.find("html").get("lang", "missing") if soup.find("html") else "missing"
    headings = [f"{h.name.upper()}: {h.get_text(strip=True)}" for h in soup.find_all(["h1","h2","h3"])[:15]]
    links    = soup.find_all("a")
    images   = soup.find_all("img")
    inputs   = soup.find_all(["input","button","select","textarea"])
    missing_alt       = [i.get("src","?")[-40:] for i in images if not i.get("alt")]
    unlabelled_inputs = [str(i)[:80] for i in inputs if not i.get("aria-label") and not i.get("id")]
    lines = [
        f"Page title: {title}",
        f"Language attribute: {lang}",
        f"Total links: {len(links)} | Total images: {len(images)} | Total form elements: {len(inputs)}",
        f"Images missing alt text ({len(missing_alt)}): {missing_alt[:5]}",
        f"Inputs missing label/aria-label ({len(unlabelled_inputs)}): {unlabelled_inputs[:3]}",
        "", "Heading structure:",
        *([f"  {h}" for h in headings] or ["  (none found)"]),
    ]
    return "\n".join(lines)

# ── 5. PROMPT (returns JSON) ───────────────────────────────────────────────────
def build_prompt(html_content, persona_name):
    return f"""
You are an expert UX auditor evaluating a website from the perspective of this specific user:

PERSONA — {persona_name}:
{PERSONAS[persona_name]}

You have been given two inputs:
1. A screenshot of the page (the image provided)
2. A structured HTML summary (below)

Use BOTH. The screenshot reveals visual issues — contrast, whitespace, layout density, font sizes.
The HTML reveals semantic issues — missing alt text, heading order, unlabelled fields, ARIA misuse.

STRUCTURED HTML SUMMARY:
{extract_html_summary(html_content)}

YOUR TASK:
Return ONLY a valid JSON object — no markdown fences, no explanation, just raw JSON.

The JSON must follow this exact schema:
{{
  "frustration_score": <integer 0-10>,
  "overall_grade": <"A"|"B"|"C"|"D"|"F">,
  "summary": "<one sentence summary of the overall UX for this persona>",
  "category_scores": {{
    "interaction": <integer 0-10>,
    "visual": <integer 0-10>,
    "accessibility": <integer 0-10>,
    "performance": <integer 0-10>
  }},
  "friction_points": [
    {{
      "title": "<short title>",
      "category": "<Interaction|Visual|Accessibility|Performance>",
      "severity": "<High|Medium|Low>",
      "observed": "<specific thing seen in screenshot or HTML>",
      "persona_impact": "<why this persona is specifically affected>",
      "wcag": "<WCAG reference or N/A>",
      "fix": "<concrete fix in 1-2 sentences>"
    }}
  ],
  "wins": ["<thing 1 that works well>", "<thing 2 that works well>"]
}}

Rules:
- friction_points must have exactly 3 items
- wins must have exactly 2 items
- Every field is required
- Be specific — cite actual elements from the screenshot or HTML
- Do NOT wrap the JSON in ```json or any other formatting
""".strip()

# ── 6. AI ANALYSIS ─────────────────────────────────────────────────────────────
def analyze_ux(html_content, img_path, persona_name, key):
    genai.configure(api_key=key)
    model    = genai.GenerativeModel("gemini-2.5-flash")
    prompt   = build_prompt(html_content, persona_name)
    screenshot = Image.open(img_path)
    response = model.generate_content([screenshot, prompt])
    raw = response.text.strip()
    # Strip accidental markdown fences if Gemini adds them
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)

# ── 7. DASHBOARD RENDERER ──────────────────────────────────────────────────────
def render_dashboard(data, persona_name, img_path):

    # ── Grade & score colour helpers
    def grade_color(g):
        return {"A":"#22c55e","B":"#84cc16","C":"#eab308","D":"#f97316","F":"#ef4444"}.get(g,"#888")

    def score_color(s):
        if s <= 3: return "#22c55e"
        if s <= 5: return "#eab308"
        if s <= 7: return "#f97316"
        return "#ef4444"

    def severity_color(s):
        return {"High":"#ef4444","Medium":"#f97316","Low":"#eab308"}.get(s,"#888")

    def category_icon(c):
        return {"Interaction":"🖱️","Visual":"👁️","Accessibility":"♿","Performance":"⚡"}.get(c,"📌")

    # ── TOP ROW: grade + frustration + summary ─────────────────────────────────
    col_grade, col_score, col_summary = st.columns([1, 1, 3])
    grade = data["overall_grade"]
    fscore = data["frustration_score"]

    with col_grade:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">Overall Grade</div>
          <div class="metric-value" style="color:{grade_color(grade)}">{grade}</div>
          <div class="metric-sub">for {persona_name}</div>
        </div>""", unsafe_allow_html=True)

    with col_score:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">Frustration Score</div>
          <div class="metric-value" style="color:{score_color(fscore)}">{fscore}<span style="font-size:20px;color:#555">/10</span></div>
          <div class="metric-sub">{'Low 🟢' if fscore<=3 else 'Moderate 🟡' if fscore<=6 else 'High 🔴'}</div>
        </div>""", unsafe_allow_html=True)

    with col_summary:
        st.markdown(f"""
        <div class="metric-card" style="text-align:left;height:100%;display:flex;flex-direction:column;justify-content:center">
          <div class="metric-label">Summary</div>
          <div style="font-size:15px;color:#ccc;line-height:1.6;margin-top:4px">{data['summary']}</div>
        </div>""", unsafe_allow_html=True)

    # ── CATEGORY SCORES ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">📊 Category Scores</div>', unsafe_allow_html=True)
    cats = data["category_scores"]
    icons = {"interaction":"🖱️","visual":"👁️","accessibility":"♿","performance":"⚡"}
    cols = st.columns(4)
    for i, (key, val) in enumerate(cats.items()):
        color = score_color(val)
        bar_width = int((val / 10) * 100)
        with cols[i]:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">{icons.get(key,'')} {key.title()}</div>
              <div class="metric-value" style="color:{color};font-size:32px">{val}<span style="font-size:14px;color:#555">/10</span></div>
              <div class="score-bar-bg">
                <div class="score-bar-fill" style="width:{bar_width}%;background:{color}"></div>
              </div>
            </div>""", unsafe_allow_html=True)

    # ── SCREENSHOT + FRICTION ──────────────────────────────────────────────────
    st.markdown('<div class="section-title">🔍 Friction Points</div>', unsafe_allow_html=True)
    col_img, col_friction = st.columns([2, 3])

    with col_img:
        st.image(img_path, caption="Agent's view of the page", use_column_width=True)

    with col_friction:
        for fp in data["friction_points"]:
            sev_color   = severity_color(fp["severity"])
            cat_icon    = category_icon(fp["category"])
            st.markdown(f"""
            <div class="friction-card" style="border-color:{sev_color}">
              <div class="friction-title">{fp['title']}
                <span class="badge" style="background:{sev_color}22;color:{sev_color};margin-left:8px">{fp['severity']}</span>
                <span class="badge" style="background:#ffffff11;color:#aaa;margin-left:4px">{cat_icon} {fp['category']}</span>
              </div>
              <div class="friction-row"><span class="friction-key">Observed</span><span>{fp['observed']}</span></div>
              <div class="friction-row"><span class="friction-key">Persona impact</span><span>{fp['persona_impact']}</span></div>
              <div class="friction-row"><span class="friction-key">WCAG</span><span style="color:#888">{fp['wcag']}</span></div>
              <div class="friction-row"><span class="friction-key">Fix</span><span style="color:#7ec8e3">{fp['fix']}</span></div>
            </div>""", unsafe_allow_html=True)

    # ── WHAT WORKS WELL ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">✅ What Works Well</div>', unsafe_allow_html=True)
    for win in data["wins"]:
        st.markdown(f'<div class="win-card">✓ {win}</div>', unsafe_allow_html=True)

    # ── DOWNLOAD ───────────────────────────────────────────────────────────────
    report_md = f"""# UX Evaluation Report — {persona_name}

**Overall Grade:** {grade}  
**Frustration Score:** {fscore}/10  
**Summary:** {data['summary']}

## Category Scores
| Category | Score |
|---|---|
{"".join(f"| {k.title()} | {v}/10 |\n" for k,v in cats.items())}

## Friction Points
{"".join(f'''
### {fp['title']} ({fp['severity']})
- **Category:** {fp['category']}
- **Observed:** {fp['observed']}
- **Persona impact:** {fp['persona_impact']}
- **WCAG:** {fp['wcag']}
- **Fix:** {fp['fix']}
''' for fp in data['friction_points'])}

## What Works Well
{"".join(f"- {w}\n" for w in data['wins'])}
"""
    st.download_button(
        "⬇️ Download Report",
        data=report_md,
        file_name=f"ux_report_{persona_name.lower().replace(' ','_')}.md",
        mime="text/markdown"
    )

# ── 8. MAIN ────────────────────────────────────────────────────────────────────
url_input = st.text_input("Website URL", "https://example.com")

if st.button("🚀 Run Evaluation", type="primary"):
    if not api_key:
        st.error("Enter a Gemini API key in the sidebar first.")
        st.stop()

    parsed = urlparse(url_input)
    if parsed.scheme not in ("http","https") or not parsed.netloc:
        st.error("Please enter a valid URL starting with http:// or https://")
        st.stop()

    with st.status("🕵️ Agent is working...", expanded=True) as status:
        st.write("1. Launching headless browser...")
        html, img_path = get_browser_content(url_input)

        if not html:
            status.update(label="❌ Failed to access site", state="error")
            st.stop()

        st.write(f"2. Analysing as: {persona}...")
        try:
            data = analyze_ux(html, img_path, persona, api_key)
        except json.JSONDecodeError as e:
            st.error(f"Failed to parse AI response as JSON: {e}")
            st.stop()

        status.update(label="✅ Done!", state="complete", expanded=False)

    st.divider()
    render_dashboard(data, persona, img_path)

    try:
        os.unlink(img_path)
    except OSError:
        pass
