import os
import io
import json
import logging
import concurrent.futures
from flask import Flask, render_template, request, send_file
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from tavily import TavilyClient
import google.generativeai as genai

# Import Data & Logic
from knowledge_base import PRODUCT_DATA, PRODUCT_MANUALS
import benchmarks 

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
    replacements = {'\u2013': '-', '\u2014': '--', '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u00a0': ' ', '\u2022': '+', '•': '+', '$': ''} 
    for char, rep in replacements.items(): text = text.replace(char, rep)
    return text.encode('latin-1', 'replace').decode('latin-1')

def format_currency(value):
    try:
        val = float(value)
        if val < 0: return f"(${abs(val):,.0f})"
        return f"${val:,.0f}"
    except: return "$0"

def get_tavily_context(client_name, client_url, industry):
    default_resp = {"context": f"Standard {industry} challenges.", "raw_search": ""}
    if not TAVILY_API_KEY: return default_resp
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        query = f"Annual revenue and strategic priorities for {client_name} ({client_url}) in {industry} 2024/2025?"
        response = tavily.search(query=query, search_depth="basic", max_results=3)
        text = "\n".join([f"- {r['content'][:300]}..." for r in response['results']])
        return {"context": text, "raw_search": text} 
    except:
        return default_resp

# --- GEMINI AGENT ---
def run_gemini_agent(agent_role, model_name, prompt, beta_mode=False):
    if beta_mode: return None
    try:
        model = genai.GenerativeModel(
            model_name,
            system_instruction=f"You are a specialized agent: {agent_role}. Return strictly valid JSON."
        )
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"},
            request_options={"timeout": 60} 
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"ERROR: {model_name} failed: {e}")
        return None

# --- REVENUE SCOUT ---
def extract_revenue_from_context(client_name, search_text):
    if not search_text: return None
    prompt = f"""
    CONTEXT: {search_text}
    TASK: Identify annual revenue for {client_name}. Return integer (e.g. 50000000). Return null if not found.
    OUTPUT JSON: {{ "annual_revenue": (Number or null) }}
    """
    result = run_gemini_agent("Revenue Scout", "gemini-2.5-flash", prompt)
    if result and result.get("annual_revenue"): return result["annual_revenue"]
    return None

# --- WORKER FUNCTION ---
def process_single_product(prod, client_name, industry, problem_statement, context_data, revenue_est, beta_mode):
    if beta_mode:
        return prod, {"impact": "BETA PREVIEW", "bullets": ["Beta"], "roi_components": []}

    profile_data, size_label, industry_key = benchmarks.get_benchmark_profile(industry, revenue_est)
    full_manual = PRODUCT_MANUALS.get(prod, "No manual found.")
    manual_snippet = full_manual[:20000]

    # Step 1: Triage (Identify Scenario)
    triage_prompt = f"""
    CLIENT: {client_name}
    PROBLEM: "{problem_statement}"
    MANUAL: {manual_snippet} 
    TASK: Select the ONE 'Usage Scenario' that best solves the User Problem.
    Output JSON ONLY: {{ "selected_scenario_name": "Name of scenario", "reasoning": "Why it fits" }}
    """
    triage_result = run_gemini_agent("Triage Doctor", "gemini-2.5-flash", triage_prompt)
    scenario = triage_result.get("selected_scenario_name", "Standard ROI") if triage_result else "Standard ROI"

    # Step 2: CFO (Multi-Factor Calculation)
    # We now ask for a LIST of savings components, not just one.
    cfo_prompt = f"""
    CLIENT: {client_name} ({industry_key} - {size_label})
    PRODUCT: {prod}
    SCENARIO: {scenario}
    BENCHMARK DATA: {json.dumps(profile_data, indent=2)}
    MANUAL SNIPPET: {manual_snippet}
    
    TASK: Calculate the Total Economic Impact.
    1. Identify the TOP 3-4 financial drivers relevant to this product from the Benchmark Data.
       (e.g., 'Reduced Downtime', 'Prevented Churn', 'Agent Productivity', 'DevOps Efficiency')
    2. For EACH driver, calculate the Annual Savings using the Benchmarks.
       - Logic: (Benchmark Cost * Quantity) * (Improvement Factor found in Manual or estimated)
    3. Be specific. If the product is "Hammer QA", focus on Dev/QA metrics. If "VoiceWatch", focus on Ops/Incidents.
    
    Output JSON Structure: 
    {{
       "impact": "2-sentence executive summary of value.",
       "bullets": ["Strategic Bullet 1", "Strategic Bullet 2", "Strategic Bullet 3"],
       "roi_components": [
           {{
               "label": "e.g. Reduction in P1 Incidents",
               "calculation_text": "e.g. 15 Incidents * $150k cost * 45% avoided",
               "savings_value": (Number)
           }},
           {{
               "label": "e.g. Automated Test Efficiency",
               "calculation_text": "e.g. 400 manual hours * $90/hr * 8 projects",
               "savings_value": (Number)
           }}
       ]
    }}
    """
    cfo_result = run_gemini_agent("CFO Analyst", "gemini-2.5-pro", cfo_prompt)
    return prod, (cfo_result if cfo_result else PRODUCT_DATA.get(prod, {}))

def generate_tailored_content(client_name, industry, project_type, context_data, problem_statement, selected_products, mode='live'):
    results = {}
    is_beta = (mode == 'beta')
    revenue_est = extract_revenue_from_context(client_name, context_data['raw_search'])
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_prod = {
            executor.submit(process_single_product, prod, client_name, industry, problem_statement, context_data, revenue_est, is_beta): prod 
            for prod in selected_products
        }
        for future in concurrent.futures.as_completed(future_to_prod):
            prod = future_to_prod[future]
            try:
                p_name, data = future.result()
                results[p_name] = data
            except Exception:
                results[prod] = PRODUCT_DATA.get(prod, {}) 

    return results

# --- CALCULATOR ---
def calculate_roi(product_data, user_costs):
    results = {}
    total_inv = 0
    total_save = 0
    for prod, data in product_data.items():
        components = data.get('roi_components', [])
        
        # Calculate Total Savings from all AI-identified components
        product_savings = sum([c.get('savings_value', 0) for c in components])
        
        # Calculate Cost
        cost_info = user_costs.get(prod, {'cost': 0, 'term': 12})
        investment = cost_info['cost'] * cost_info['term']
        
        # Annualize investment for chart matching (simplification) vs Total Term
        # For this report, we'll assume the savings are ANNUAL.
        # If term > 12 months, we scale savings to match term.
        term_years = cost_info['term'] / 12.0
        total_term_savings = product_savings * term_years
        
        total_inv += investment
        total_save += total_term_savings
        
        results[prod] = {"investment": investment, "savings": total_term_savings, "components": components}
        
    return results, total_inv, total_save

# --- PDF GENERATOR ---
class ProReportPDF(FPDF):
    def header(self):
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 25, 'F')
        self.set_y(8)
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(255, 255, 255)
        self.cell(10)
        self.cell(0, 10, 'STRATEGIC VALUE ANALYSIS', ln=0)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(200, 200, 200)
        self.cell(0, 10, 'CONFIDENTIAL PREVIEW', ln=1, align='R')
        self.ln(15)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(15, 23, 42)
        self.cell(0, 8, sanitize_text(title), ln=True)
        self.set_draw_color(37, 99, 235)
        self.set_line_width(0.8)
        self.line(10, self.get_y()+4, 200, self.get_y()+4)
        self.ln(12)

    def draw_financial_table(self, components, total_savings, investment):
        """ Draws a dynamic multi-row table for savings components """
        start_y = self.get_y()
        
        # 1. Table Header
        self.set_fill_color(241, 245, 249) # Light Gray
        self.rect(10, start_y, 190, 10, 'F')
        self.set_xy(15, start_y + 2)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(71, 85, 105)
        self.cell(90, 6, "Value Driver", ln=0)
        self.cell(60, 6, "Basis of Calculation", ln=0)
        self.cell(30, 6, "Annual Impact", align='R', ln=1)
        self.ln(4)
        
        # 2. Rows
        y = self.get_y()
        self.set_text_color(15, 23, 42)
        
        for comp in components:
            # Check for page break
            if self.get_y() > 250:
                self.add_page()
                y = 20
                self.set_y(y)
            
            label = sanitize_text(comp.get('label', 'Savings'))
            calcs = sanitize_text(comp.get('calculation_text', ''))
            val = comp.get('savings_value', 0)
            
            # Label (Col 1)
            self.set_xy(15, y)
            self.set_font('Helvetica', 'B', 9)
            self.multi_cell(85, 5, label, align='L')
            y_end_1 = self.get_y()
            
            # Calc Logic (Col 2)
            self.set_xy(105, y)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(100, 116, 139)
            self.multi_cell(55, 5, calcs, align='L')
            y_end_2 = self.get_y()
            
            # Value (Col 3)
            self.set_xy(160, y)
            self.set_font('Helvetica', 'B', 10)
            self.set_text_color(22, 163, 74) # Green
            self.cell(35, 5, format_currency(val), align='R')
            
            y = max(y_end_1, y_end_2) + 4
            self.set_draw_color(226, 232, 240)
            self.line(15, y-2, 195, y-2) # Separator line
            
        # 3. Summary Footer
        self.ln(5)
        self.set_xy(120, self.get_y())
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(15, 23, 42)
        self.cell(40, 8, "Total Benefits:", align='R')
        self.set_text_color(22, 163, 74)
        self.cell(35, 8, format_currency(total_savings), align='R', ln=1)
        
        self.set_xy(120, self.get_y())
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(100, 116, 139)
        self.cell(40, 6, "Less Investment:", align='R')
        self.set_text_color(185, 28, 28)
        self.cell(35, 6, f"({format_currency(investment)})", align='R', ln=1)
        
        # Net
        self.ln(2)
        self.set_xy(120, self.get_y())
        self.set_fill_color(240, 253, 244) # Green tint
        self.rect(120, self.get_y(), 75, 12, 'F')
        self.set_xy(120, self.get_y() + 2)
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(21, 128, 61)
        net = total_savings - investment
        self.cell(40, 8, "NET VALUE:", align='R')
        self.cell(35, 8, format_currency(net), align='R', ln=1)
        self.ln(15)

    def card_box(self, label, value, subtext, x, y, w, h):
        self.set_xy(x, y)
        self.set_fill_color(255, 255, 255)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.5)
        self.rect(x, y, w, h, 'DF')
        self.set_xy(x, y + 6)
        self.set_font('Helvetica', 'B', 14)
        if "ROI" in label or "SAVINGS" in label:
             if "(" in value or "-" in value: self.set_text_color(185, 28, 28)
             else: self.set_text_color(22, 163, 74)
        else: self.set_text_color(15, 23, 42)
        self.cell(w, 8, sanitize_text(value), align='C', ln=1)
        self.set_xy(x, y + 16)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(100, 116, 139)
        self.cell(w, 5, sanitize_text(label), align='C', ln=1)
        self.set_xy(x, y + 21)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(148, 163, 184)
        self.cell(w, 4, sanitize_text(subtext), align='C')

def create_chart(inv, save):
    with plot_lock:
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(8, 4))
        months = list(range(13))
        start = -1 * abs(inv)
        monthly = (save / 12) if save != 0 else 0
        flow = [start + (monthly * m) for m in months]
        ax.plot(months, flow, color='#2563EB', linewidth=3, marker='o', markersize=6)
        ax.axhline(0, color='#64748B', linestyle='--', linewidth=1.5)
        ax.set_title("Cumulative Cash Flow (Year 1)", fontsize=12, fontweight='bold', pad=15)
        ax.set_xlabel("Months", fontsize=9)
        ax.set_ylabel("Net Cash Position ($)", fontsize=9)
        fmt = '${x:,.0f}'
        tick = mtick.StrMethodFormatter(fmt)
        ax.yaxis.set_major_formatter(tick)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=200)
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
    
    mode = request.form.get('mode', 'live')
    client = sanitize_text(request.form.get('client_name'))
    ind = sanitize_text(request.form.get('industry'))
    prob = sanitize_text(request.form.get('problem_statement'))
    prods = request.form.getlist('products')
    
    costs = {}
    for p in prods:
        try:
            c = float(request.form.get(f'cost_{p}', 0))
            t_str = request.form.get(f'term_{p}', '12')
            t = float(request.form.get(f'term_custom_{p}', 12)) if t_str == 'other' else float(t_str)
            costs[p] = {'cost': c, 'term': t}
        except: costs[p] = {'cost': 0, 'term': 12}
        
    tavily_data = get_tavily_context(client, request.form.get('client_url'), ind)
    ai_data = generate_tailored_content(client, ind, "", tavily_data, prob, prods, mode)
    roi, tot_inv, tot_save = calculate_roi(ai_data, costs)
    
    pdf = ProReportPDF()
    pdf.set_auto_page_break(True, 15)
    
    pdf.add_page()
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 24)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, f"Strategic ROI Analysis", ln=True)
    pdf.set_font('Helvetica', '', 14)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 8, f"Prepared for: {client}", ln=True)
    pdf.ln(10)
    
    pdf.set_fill_color(241, 245, 249)
    pdf.rect(10, pdf.get_y(), 190, 25, 'F')
    pdf.set_xy(15, pdf.get_y()+5)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.set_text_color(71, 85, 105)
    pdf.multi_cell(180, 5, f"Focus: {prob}")
    pdf.ln(10)
    
    y = pdf.get_y()
    w, h = 60, 28
    pdf.card_box("PROJECTED SAVINGS", format_currency(tot_save), "Total Value Created", 10, y, w, h)
    pdf.card_box("TOTAL INVESTMENT", format_currency(tot_inv), "Software & Services", 75, y, w, h)
    roi_pct = ((tot_save-tot_inv)/tot_inv)*100 if tot_inv > 0 else 0
    pdf.card_box("ROI %", f"{roi_pct:.0f}%", "Return on Investment", 140, y, w, h)
    
    pdf.set_y(y + h + 20)
    chart = create_chart(tot_inv, tot_save)
    pdf.image(chart, x=10, w=190)
    
    for p in prods:
        if p not in ai_data: continue
        d = ai_data[p]
        calc = roi.get(p, {'savings':0, 'investment':0, 'components':[]})
        
        pdf.add_page()
        pdf.chapter_title(f"Analysis: {p}")
        
        pdf.set_font('Helvetica', 'I', 11)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(0, 6, sanitize_text(d.get('impact', '')))
        pdf.ln(8)
        
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        for b in d.get('bullets', []):
            pdf.set_x(15)
            pdf.cell(5, 6, "+", ln=0)
            pdf.multi_cell(170, 6, sanitize_text(b))
            pdf.ln(2)
        pdf.ln(5)
        
        # New Dynamic Table Draw
        if 'roi_components' in d:
             pdf.draw_financial_table(d['roi_components'], calc['savings'], calc['investment'])
    
    try:
        pdf_out = pdf.output(dest='S').encode('latin-1') 
    except:
        pdf_out = bytes(pdf.output()) 

    return send_file(
        io.BytesIO(pdf_out),
        as_attachment=True,
        download_name="Strategic_ROI_Analysis.pdf",
        mimetype="application/pdf"
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
