import streamlit as st
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="Auto-UX Evaluator", page_icon="🤖", layout="wide")
st.title("🤖 Auto-UX: AI Usability Tester")
st.markdown("Enter a website URL below to unleash an **AI Agent** that will evaluate its User Experience.")

# 2. SIDEBAR SETUP (API Key)
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter Google Gemini API Key", type="password")
    persona = st.selectbox("Select Agent Persona", ["Motor Impairment", "Color-Blind", "Neurodivergent"])
    st.info("Get your free key at: aistudio.google.com")

# 3. DEFINE THE BROWSER TOOL (Headless for Server)
def get_browser_content(url):
    options = Options()
    options.add_argument("--headless")  # Run invisible
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        time.sleep(3) # Wait for load
        
        # Take a screenshot for the report
        driver.save_screenshot("screenshot.png")
        
        # Get HTML
        html = driver.page_source[:20000] # Limit chars
        return html, "screenshot.png"
    except Exception as e:
        return None, None
    finally:
        driver.quit()

# 4. DEFINE THE AI ANALYSIS
def analyze_ux(html_content, persona_name, key):
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are a UX Testing Agent adopting the persona: {persona_name}.

Evaluate this website using the provided HTML (and any performance or interaction data supplied).

Perform analysis across the following dimensions:

1. Clickability & Interaction Testing  
   - Assess affordance clarity, button visibility, interactive element discoverability.  
   - Simulate execution of basic user tasks (e.g., navigation, form submission, clicking primary CTA).  
   - Identify potential interaction failures (dead links, hidden elements, ambiguous CTAs).

2. Visual Clarity  
   - Evaluate contrast, typography readability, layout hierarchy, spacing, and visual overload.

3. Accessibility (WCAG-Compliant Analysis)  
   - Assess alignment with WCAG 2.1/2.2 principles:
        • Perceivable (alt text, color contrast, semantic structure)
        • Operable (keyboard navigation, focus indicators)
        • Understandable (clear labels, predictable navigation)
        • Robust (proper semantic HTML usage)
   - Identify likely Level A / AA compliance issues.

4. Performance Benchmarking  
   - Infer potential performance concerns based on HTML structure:
        • Large scripts, inline styles, blocking resources
        • Excessive DOM depth
        • Unoptimized media
   - Estimate user-perceived performance impact (slow load, layout shift, interaction delay).

Provide:

- A Frustration Score (0–10) with a 1-sentence justification tied to persona tolerance.
- Exactly 3 major friction points.
- For each friction point, include:
    • Title  
    • Category (Interaction / Visual / Accessibility / Performance)  
    • Impact on Task Completion  
    • Why this persona is specifically affected  
    • Reference to relevant WCAG principle if applicable  

Base your reasoning strictly on the provided HTML and supplied data.
If data is insufficient for a category, explicitly state the limitation.
Format output as structured Markdown.
    
    HTML SNIPPET:
    {html_content}
    
    FORMAT OUTPUT AS MARKDOWN.
    """
    
    response = model.generate_content(prompt)
    return response.text

# 5. MAIN APP LOGIC
url_input = st.text_input("Website URL", "https://example.com")

if st.button("🚀 Run Evaluation"):
    if not api_key:
        st.error("Please enter an API Key in the sidebar first!")
    else:
        with st.status("🕵️ Agent is working...", expanded=True) as status:
            st.write("1. Launching headless browser...")
            html, img_path = get_browser_content(url_input)
            
            if html:
                st.write("2. Capturing site structure...")
                st.image(img_path, caption="Agent View of Website", width=500)
                
                st.write(f"3. {persona} is analyzing the experience...")
                report = analyze_ux(html, persona, api_key)
                
                status.update(label="✅ Evaluation Complete!", state="complete", expanded=False)
                
                # Display Results
                st.divider()
                st.subheader(f"📝 Evaluation Report ({persona})")
                st.markdown(report)
            else:
                status.update(label="❌ Failed to access site", state="error")
                st.error("Could not load the website. Check the URL.")
                