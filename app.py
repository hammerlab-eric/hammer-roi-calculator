import os
import io
import json
import logging
from flask import Flask, render_template, request, send_file
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from tavily import TavilyClient
import google.generativeai as genai
from knowledge_base import PRODUCT_DATA, PRODUCT_MANUALS

# Concurrency-safe plotting
import matplotlib
matplotlib.use('Agg')
import threading
plot_lock = threading.Lock()

app = Flask(__name__)

# --- CONFIGURATION ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ACCESS_CODE = os.getenv("ACCESS_CODE", "Hammer2025!")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- UTILS ---
def sanitize_text(text):
    if not isinstance(text, str): return str(text)
    replacements = {'\u2013': '-', '\u2014': '--', '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u00a0': ' ', '\u2022': '*'}
    for char, rep in replacements.items(): text = text.replace(char, rep)
    return text.encode('latin-1', 'replace').decode('latin-1')

def get_tavily_context(client_name, client_url, industry):
    """ Agent 2 (Parallel): The Researcher """
    if not TAVILY_API_KEY: return f"Standard {industry} challenges apply."
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        query = f"Strategic priorities and financial challenges for {client_name} ({client_url}) in {industry} 2025?"
        response = tavily.search(query=query, search_depth="basic", max_results=2)
        return "\n".join([f"- {r['content'][:200]}..." for r in response['results']])
    except:
        return "Standard industry context."

# --- GEMINI AGENT ENGINE ---
def run_gemini_agent(agent_role, primary_model, fallback_model, prompt, beta_mode=False):
    """
    Tries the Primary Model (e.g. 2.5). If 404/Error, falls back to Stable (e.g. 1.5).
    """
    if beta_mode: return None
    
    def try_generate(model_name):
        model = genai.GenerativeModel(
            model_name,
            system_instruction=f"You are a specialized agent: {agent_role}. Return strictly valid JSON."
        )
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"},
            request_options={"timeout": 90} # 90s timeout per agent
        )
        return json.loads(response.text)

    # Attempt 1: Primary (2.5)
    try:
        return try_generate(primary_model)
    except Exception as e:
        print(f"Gemini {primary_model} failed ({e}). Falling back to {fallback_model}...")
        
    # Attempt 2: Fallback (1.5)
    try:
        return try_generate(fallback_model)
    except Exception as e:
        print(f"Gemini Fallback {fallback_model} failed: {e}")
        return None

# --- AGENT 1: TRIAGE (Flash) ---
# Low Cost, High Speed, Massive Context
def agent_triage_doctor(client_name, problem_statement, product_name, beta_mode=False):
    full_manual = PRODUCT_MANUALS.get(product_name, "No manual found.")
    
    prompt = f"""
    CLIENT: {client_name}
    PROBLEM: "{problem_statement}"
    
    MANUAL: 
    {full_manual[:30000]} 
    
    TASK: 
    1. Read the Manual. 
    2. Select the ONE 'ROI Metric' or 'Usage Scenario' that best solves the User Problem.
    
    Output JSON ONLY: {{ "selected_scenario_name": "Name of scenario", "reasoning": "Why it fits" }}
    """
    
    if beta_mode: return {"selected_scenario_name": "BETA_PREVIEW", "prompt": prompt}

    # Primary: 2.5 Flash | Fallback: 1.5 Flash
    result = run_gemini_agent("Triage Doctor", "gemini-2.5-flash", "gemini-1.5-flash", prompt)
    
    return result if result else {"selected_scenario_name": "Standard ROI", "reasoning": "Default"}

# --- AGENT 2: CFO (Pro) ---
# High Intelligence, Reasoning, Math
def agent_cfo_analyst(client_name, industry, product_name, triage_result, context_text, beta_mode=False):
    full_manual = PRODUCT_MANUALS.get(product_name, "")
    scenario = triage_result.get("selected_scenario_name", "Standard ROI")
    
    prompt = f"""
    CLIENT: {client_name} ({industry})
    PRODUCT: {product_name}
    SCENARIO: {scenario}
    CONTEXT: {context_text}
    
    MANUAL SNIPPET (Relevant Logic):
    {full_manual[:20000]}
    
    TASK: Using the logic in the Manual for '{scenario}', generate a financial table.
    
    Output JSON: 
    {{
       "impact": "2-sentence impact statement.",
       "bullets": ["Bullet 1", "Bullet 2", "Bullet 3"],
       "math_variables": {{
           "scenario_title": "{scenario}",
           "metric_unit": "Unit (e.g. Hours/Year)",
           "cost_per_unit_label": "Label (e.g. Avg Cost)",
           "cost_per_unit_value": (Number),
           "before_label": "Current State",
           "before_qty": (Number),
           "after_label": "Future State",
           "after_qty": (Number)
       }}
    }}
    """
    if beta_mode: return prompt
    
    # Primary: 2.5 Pro | Fallback: 1.5 Pro
    return run_gemini_agent("CFO Analyst", "gemini-2.5-pro", "gemini-1.5-pro", prompt)

def generate_tailored_content(client_name, industry, project_type, context_text, problem_statement, selected_products, mode='live'):
    results = {}
    is_beta = (mode == 'beta')
    
    for prod in selected_products:
        # Step 1: Triage (Flash)
        triage = agent_triage_doctor(client_name, problem_statement, prod, beta_mode=is_beta)
        
        if is_beta:
            preview = f"--- AGENT 1 (FLASH) ---\n{triage['prompt']}\n\n--- AGENT 2 (PRO) ---\n(Dependent on Agent 1 output)"
            results[prod] = {
                "impact": preview, 
                "bullets": ["BETA MODE"], 
                "math_variables": {"scenario_title": "BETA", "cost_per_unit_value":0}
            }
        else:
            # Step 2: CFO (Pro)
            cfo = agent_cfo_analyst(client_name, industry, prod, triage, context_text)
            
            if cfo:
                results[prod] = cfo
            else:
                results[prod] = PRODUCT_DATA.get(prod, {})

    return results

# --- CALCULATOR ---
def calculate_roi(product_data, user_costs):
    results = {}
    total_inv = 0
    total_save = 0
    for prod, data in product_data.items():
        math = data.get('math_variables')
        if not math: continue
        
        cost = user_costs.get(prod, {}).get('cost', 0)
        term = user_costs.get(prod, {}).get('term', 12)
        inv = cost * term
        total_inv += inv
        
        term_years = term / 12.0
        unit = float(math.get('cost_per_unit_value', 0))
        before = float(math.get('before_qty', 0))
        after = float(math.get('after_qty', 0))
        
        save = (unit * before - unit * after) * term_years
        total_save += save
        
        results[prod] = {"investment": inv, "savings": save, "math": math}
        
    return results, total_inv, total_save

# --- PDF GENERATOR ---
class ProReportPDF(FPDF):
    def header(self):
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 20, 'F')
        self.set_y(5); self.set_font('Helvetica', 'B', 12); self.set_text_color(255, 255, 255)
        self.cell(10); self.cell(0, 10, 'STRATEGIC VALUE ANALYSIS', ln=0)
        self.ln(10)
    
    def footer(self):
        self.set_y(-15); self.set_font('Helvetica', 'I', 8); self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 16); self.set_text_color(15, 23, 42)
        self.cell(0, 8, sanitize_text(title), ln=True)
        self.line(10, self.get_y()+2, 200, self.get_y()+2); self.ln(10)

    def draw_math_table(self, math, save, inv):
        self.set_fill_color(248, 250, 252); self.rect(10, self.get_y(), 190, 35, 'F')
        self.set_xy(15, self.get_y()+5); self.set_font('Helvetica', 'B', 10); self.set_text_color(15, 23, 42)
        self.cell(0, 5, f"Scenario: {sanitize_text(math.get('scenario_title', 'ROI'))}", ln=True)
        
        y = self.get_y() + 2; col1=60; col2=100
        self.set_font('Helvetica', 'B', 9); self.set_text_color(100,100,100)
        self.set_xy(15, y); self.cell(col1, 5, "Benchmark:"); self.set_font('Helvetica', ''); self.set_text_color(0)
        self.cell(col2, 5, f"${math.get('cost_per_unit_value', 0):,.2f} / {sanitize_text(math.get('metric_unit', 'Unit'))}")
        
        self.set_xy(15, y+6); self.set_font('Helvetica', 'B', 9); self.set_text_color(185, 28, 28)
        self.cell(col1, 5, sanitize_text(math.get('before_label', 'Before'))); self.set_font('Helvetica', ''); self.set_text_color(0)
        val = math.get('cost_per_unit_value', 0) * math.get('before_qty', 0)
        self.cell(col2, 5, f"{math.get('before_qty', 0)} units = ${val:,.0f} Risk")
        
        self.set_xy(15, y+12); self.set_font('Helvetica', 'B', 9); self.set_text_color(22, 163, 74)
        self.cell(col1, 5, sanitize_text(math.get('after_label', 'After'))); self.set_font('Helvetica', ''); self.set_text_color(0)
        val = math.get('cost_per_unit_value', 0) * math.get('after_qty', 0)
        self.cell(col2, 5, f"{math.get('after_qty', 0)} units = ${val:,.0f} Risk")
        
        self.set_xy(130, y+10); self.set_font('Helvetica', 'B', 12); self.set_text_color(37, 99, 235)
        self.cell(60, 10, f"Net Savings: ${save:,.0f}", align='R'); self.ln(20)

    def card_box(self, label, value, subtext, x, y, w, h):
        self.set_xy(x, y); self.set_fill_color(248, 250, 252); self.rect(x, y, w, h, 'DF')
        self.set_xy(x, y+5); self.set_font('Helvetica', 'B', 14); self.set_text_color(37, 99, 235)
        self.cell(w, 10, sanitize_text(value), align='C', ln=1)
        self.set_xy(x, y+16); self.set_font('Helvetica', 'B', 9); self.set_text_color(51, 65, 85)
        self.cell(w, 5, sanitize_text(label), align='C', ln=1)
        self.set_xy(x, y+22); self.set_font('Helvetica', '', 7); self.set_text_color(100, 116, 139)
        self.cell(w, 5, sanitize_text(subtext), align='C')

def create_chart(inv, save):
    with plot_lock:
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(7, 3.5))
        months = list(range(13))
        start = -1 * abs(inv)
        monthly = (save / 12) if save > 0 else 1000
        flow = [start + (monthly * m) for m in months]
        ax.plot(months, flow, color='#2563EB', linewidth=3, marker='o'); ax.axhline(0, color='#64748B', linestyle='--')
        ax.set_title("Cash Flow (Year 1)", fontweight='bold'); ax.grid(True, linestyle=':')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        plt.close()
        buf.seek(0)
        return buf

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', products=PRODUCT_DATA.keys())

@app.route('/generate', methods=['POST'])
def generate_pdf():
    if request.form.get('access_code') != ACCESS_CODE: return "Invalid Code", 403
    
    # Inputs
    mode = request.form.get('mode', 'live')
    client = sanitize_text(request.form.get('client_name'))
    ind = sanitize_text(request.form.get('industry'))
    prob = sanitize_text(request.form.get('problem_statement'))
    prods = request.form.getlist('products')
    
    # Costs
    costs = {}
    for p in prods:
        try:
            c = float(request.form.get(f'cost_{p}', 0))
            t_str = request.form.get(f'term_{p}', '12')
            t = float(request.form.get(f'term_custom_{p}', 12)) if t_str == 'other' else float(t_str)
            costs[p] = {'cost': c, 'term': t}
        except: costs[p] = {'cost': 0, 'term': 12}
        
    # Execution
    tavily = get_tavily_context(client, request.form.get('client_url'), ind)
    ai_data = generate_tailored_content(client, ind, "", tavily, prob, prods, mode)
    roi, tot_inv, tot_save = calculate_roi(ai_data, costs)
    
    # PDF
    pdf = ProReportPDF()
    pdf.set_auto_page_break(True, 15); pdf.add_page()
    pdf.ln(5); pdf.set_font('Helvetica', 'B', 20); pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, f"Strategic ROI Analysis: {client}", ln=True)
    pdf.set_font('Helvetica', '', 12); pdf.set_text_color(51, 65, 85)
    pdf.cell(0, 8, f"Problem: {prob[:60]}...", ln=True); pdf.ln(10)
    
    y = pdf.get_y(); w, h = 60, 25
    pdf.card_box("SAVINGS", f"${tot_save:,.0f}", "Total Value", 10, y, w, h)
    pdf.card_box("INVESTMENT", f"${tot_inv:,.0f}", "Total Cost", 75, y, w, h)
    roi_pct = ((tot_save-tot_inv)/tot_inv)*100 if tot_inv > 0 else 0
    pdf.card_box("ROI", f"{roi_pct:.0f}%", "Return", 140, y, w, h)
    
    pdf.set_y(y + h + 15); chart = create_chart(tot_inv, tot_save)
    pdf.image(chart, x=10, w=180)
    
    for p in prods:
        if p not in ai_data: continue
        d = ai_data[p]; calc = roi.get(p, {'savings':0, 'investment':0, 'math':{}})
        pdf.add_page(); pdf.chapter_title(f"Analysis: {p}")
        pdf.set_font('Helvetica', 'I', 10); pdf.multi_cell(0, 5, sanitize_text(d.get('impact', ''))); pdf.ln(5)
        pdf.set_font('Helvetica', '', 10)
        for b in d.get('bullets', []):
            pdf.set_x(15); pdf.cell(5, 5, "+"); pdf.multi_cell(170, 5, sanitize_text(b))
        pdf.ln(10)
        if 'math_variables' in d: pdf.draw_math_table(d['math_variables'], calc['savings'], calc['investment'])
    
    try:
        pdf_out = pdf.output(dest='S').encode('latin-1') 
    except:
        pdf_out = bytes(pdf.output()) 

    return send_file(
        io.BytesIO(pdf_out),
        as_attachment=True,
        download_name="generated_roi_report.pdf",
        mimetype="application/pdf"
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
