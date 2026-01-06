import os
import io
import json
from flask import Flask, render_template, request, send_file
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from tavily import TavilyClient
import google.generativeai as genai
from knowledge_base import PRODUCT_DATA, PRODUCT_MANUALS

import matplotlib
matplotlib.use('Agg')

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
    if not TAVILY_API_KEY: return f"Standard {industry} challenges apply."
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        query = f"What are the top strategic priorities for {client_name} ({client_url}) in {industry}?"
        response = tavily.search(query=query, search_depth="basic", max_results=3)
        return "\n".join([f"- {r['content'][:200]}..." for r in response['results']])
    except:
        return "Standard industry context."

# --- GEMINI AGENTS ---
def run_gemini_agent(agent_role, model_name, prompt, beta_mode=False):
    if beta_mode: return None
    try:
        model = genai.GenerativeModel(
            model_name,
            system_instruction=f"You are a specialized agent: {agent_role}. Return valid JSON."
        )
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini Error ({agent_role}): {e}")
        return None

def agent_triage_doctor(client_name, problem_statement, product_name, beta_mode=False):
    """ Agent 1: Reads file -> Finds Scenario """
    manual_text = PRODUCT_MANUALS.get(product_name, "No manual found.")
    
    prompt = f"""
    CLIENT: {client_name}
    PROBLEM: "{problem_statement}"
    MANUAL: {manual_text[:50000]} 
    
    TASK: Read the manual. Identify the ONE 'Usage Scenario' or 'ROI Metric' that best solves the problem.
    Output JSON: {{ "selected_scenario_name": "Name of scenario", "reasoning": "Why it fits" }}
    """
    
    if beta_mode: return {"selected_scenario_name": "BETA_PREVIEW", "prompt": prompt}
    
    # Use Flash-001 (Fast/High Context)
    result = run_gemini_agent("Triage Doctor", "gemini-2.5-flash", prompt)
    return result if result else {"selected_scenario_name": "Standard ROI", "reasoning": "Default"}

def agent_cfo_analyst(client_name, industry, product_name, triage_result, context_text, beta_mode=False):
    """ Agent 3: Reads file -> Calculates Math """
    manual_text = PRODUCT_MANUALS.get(product_name, "")
    scenario = triage_result.get("selected_scenario_name", "Standard ROI")
    
    prompt = f"""
    CLIENT: {client_name} ({industry})
    PRODUCT: {product_name}
    SCENARIO: {scenario}
    CONTEXT: {context_text}
    MANUAL: {manual_text[:50000]}
    
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
    
    # Use Pro-001 (Reasoning)
    return run_gemini_agent("CFO Analyst", "gemini-2.5-pro", prompt)

def generate_tailored_content(client_name, industry, project_type, context_text, problem_statement, selected_products, mode='live'):
    results = {}
    is_beta = (mode == 'beta')
    
    for prod in selected_products:
        triage = agent_triage_doctor(client_name, problem_statement, prod, beta_mode=is_beta)
        
        if is_beta:
            preview = f"--- TRIAGE PROMPT ---\n{triage['prompt']}\n\n--- CFO PROMPT ---\n(Dependent on Triage Output)"
            results[prod] = {
                "impact": preview, 
                "bullets": ["BETA MODE"], 
                "math_variables": {"scenario_title": "BETA", "cost_per_unit_value":0}
            }
        else:
            cfo = agent_cfo_analyst(client_name, industry, prod, triage, context_text)
            results[prod] = cfo if cfo else PRODUCT_DATA.get(prod, {})

    return results

# --- CALCULATOR (Standard) ---
def calculate_roi(product_data, user_costs):
    results = {}
    total_inv = 0
    total_save = 0
    for prod, data in product_data.items():
        math = data.get('math_variables')
        if not math: continue
        
        # Cost
        cost = user_costs.get(prod, {}).get('cost', 0)
        term = user_costs.get(prod, {}).get('term', 12)
        inv = cost * term
        total_inv += inv
        
        # Savings
        term_years = term / 12.0
        unit = math.get('cost_per_unit_value', 0)
        save = (unit * math.get('before_qty', 0) - unit * math.get('after_qty', 0)) * term_years
        total_save += save
        
        results[prod] = {"investment": inv, "savings": save, "math": math}
        
    return results, total_inv, total_save

# --- PDF GENERATOR (Standard) ---
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
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(7, 3.5))
    months = list(range(13))
    start = -1 * abs(inv)
    monthly = (save / 12) if save > 0 else 1000
    flow = [start + (monthly * m) for m in months]
    ax.plot(months, flow, color='#2563EB', linewidth=3, marker='o'); ax.axhline(0, color='#64748B', linestyle='--')
    ax.set_title("Cash Flow (Year 1)", fontweight='bold'); ax.grid(True, linestyle=':')
    buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight', dpi=150); plt.close(); buf.seek(0)
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
        
    out = "report.pdf"; pdf.output(out)
    return send_file(out, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
