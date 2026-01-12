import os
import io
import json
import logging
import concurrent.futures
import threading
import re

from flask import Flask, render_template, request, send_file, jsonify
from fpdf import FPDF
import matplotlib
# Set non-GUI backend to prevent server errors
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from tavily import TavilyClient
import google.generativeai as genai

# --- DATA IMPORTS ---
try:
    from knowledge_base import PRODUCT_DATA, PRODUCT_MANUALS
except ImportError:
    PRODUCT_DATA = {}
    PRODUCT_MANUALS = {}

import benchmarks 

app = Flask(__name__)

# --- CONFIGURATION ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ACCESS_CODE = os.getenv("ACCESS_CODE", "Hammer2025!")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Lock for thread-safe plotting
plot_lock = threading.Lock()

# --- STYLING CONSTANTS ---
COLOR_PRIMARY = (15, 23, 42)    # Navy
COLOR_ACCENT = (37, 99, 235)    # Blue
COLOR_TEXT = (51, 65, 85)       # Slate
FONT_FAMILY = 'Helvetica'

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

def extract_currency_value(text_value):
    """Defensive cleaner for AI outputs"""
    if not text_value: return 0.0
    clean_text = str(text_value).strip().replace('$', '').replace(',', '')
    multiplier = 1.0
    if clean_text.lower().endswith('k'): multiplier = 1000.0; clean_text = clean_text[:-1]
    elif clean_text.lower().endswith('m'): multiplier = 1000000.0; clean_text = clean_text[:-1]
    
    try:
        matches = re.findall(r"[-+]?\d*\.\d+|\d+", clean_text)
        if matches: return max([float(m) for m in matches]) * multiplier
        return 0.0
    except: return 0.0

# --- CHART GENERATOR ---
def create_payback_chart(investment, annual_savings):
    with plot_lock:
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(7, 3.5))
        
        months = list(range(13))
        start_val = -1 * abs(investment)
        monthly_gain = (annual_savings / 12.0) if annual_savings else 0
        
        cash_flow = []
        current = start_val
        for m in months:
            cash_flow.append(current)
            current += monthly_gain
            
        ax.plot(months, cash_flow, color='#2563EB', linewidth=3, marker='o', markersize=6)
        ax.axhline(0, color='#64748B', linewidth=1.5, linestyle='--')
        
        ax.set_title("Cumulative Cash Flow (Year 1)", fontsize=12, fontweight='bold', pad=15)
        ax.set_xlabel("Months", fontsize=9)
        ax.set_ylabel("Net Cash Position ($)", fontsize=9)
        
        # Format Y axis
        fmt = '${x:,.0f}'
        tick = mtick.StrMethodFormatter(fmt)
        ax.yaxis.set_major_formatter(tick)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        plt.close()
        buf.seek(0)
        return buf

# --- PDF CLASS ---
class ProReportPDF(FPDF):
    def header(self):
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, 210, 20, 'F')
        self.set_y(5)
        self.set_font(FONT_FAMILY, 'B', 12)
        self.set_text_color(255, 255, 255)
        self.cell(10)
        self.cell(0, 10, 'STRATEGIC VALUE ANALYSIS', ln=0, align='L')
        self.set_font(FONT_FAMILY, '', 9)
        self.cell(0, 10, 'CONFIDENTIAL PREVIEW', ln=1, align='R')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font(FONT_FAMILY, 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def chapter_title(self, title):
        self.set_font(FONT_FAMILY, 'B', 16)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 8, sanitize_text(title), ln=True, align='L')
        self.set_draw_color(*COLOR_ACCENT)
        self.set_line_width(0.5)
        self.line(10, self.get_y()+2, 200, self.get_y()+2)
        self.ln(10)

    def card_box(self, label, value, subtext, x, y, w, h):
        self.set_xy(x, y)
        self.set_fill_color(248, 250, 252)
        self.set_draw_color(226, 232, 240)
        self.rect(x, y, w, h, 'DF')
        self.set_xy(x, y + 5)
        self.set_font(FONT_FAMILY, 'B', 14)
        self.set_text_color(*COLOR_ACCENT)
        self.cell(w, 10, sanitize_text(value), align='C', ln=1)
        self.set_xy(x, y + 16)
        self.set_font(FONT_FAMILY, 'B', 9)
        self.set_text_color(*COLOR_TEXT)
        self.cell(w, 5, sanitize_text(label), align='C', ln=1)
        self.set_xy(x, y + 22)
        self.set_font(FONT_FAMILY, '', 7)
        self.set_text_color(100, 116, 139)
        self.cell(w, 5, sanitize_text(subtext), align='C')

    def draw_financial_table(self, components, total_savings, investment):
        start_y = self.get_y()
        self.set_fill_color(241, 245, 249)
        self.rect(10, start_y, 190, 10, 'F')
        self.set_xy(15, start_y + 2)
        self.set_font(FONT_FAMILY, 'B', 10)
        self.set_text_color(71, 85, 105)
        self.cell(90, 6, "Value Driver", ln=0)
        self.cell(60, 6, "Basis of Calculation", ln=0)
        self.cell(30, 6, "Annual Impact", align='R', ln=1)
        self.ln(4)
        
        y = self.get_y()
        self.set_text_color(15, 23, 42)
        
        for comp in components:
            if self.get_y() > 250:
                self.add_page()
                y = 20
                self.set_y(y)
            
            label = sanitize_text(comp.get('label', 'Savings'))
            calcs = sanitize_text(comp.get('calculation_text', ''))
            val = comp.get('savings_value', 0)
            
            self.set_xy(15, y)
            self.set_font(FONT_FAMILY, 'B', 9)
            self.multi_cell(85, 5, label, align='L')
            y_end_1 = self.get_y()
            
            self.set_xy(105, y)
            self.set_font(FONT_FAMILY, 'I', 8)
            self.set_text_color(100, 116, 139)
            self.multi_cell(55, 5, calcs, align='L')
            y_end_2 = self.get_y()
            
            self.set_xy(160, y)
            self.set_font(FONT_FAMILY, 'B', 10)
            self.set_text_color(22, 163, 74)
            self.cell(35, 5, format_currency(val), align='R')
            
            y = max(y_end_1, y_end_2) + 4
            self.set_draw_color(226, 232, 240)
            self.line(15, y-2, 195, y-2)
            
        self.ln(5)
        self.set_xy(120, self.get_y())
        self.set_font(FONT_FAMILY, 'B', 12)
        self.set_text_color(15, 23, 42)
        self.cell(40, 8, "Total Benefits:", align='R')
        self.set_text_color(22, 163, 74)
        self.cell(35, 8, format_currency(total_savings), align='R', ln=1)
        
        self.set_xy(120, self.get_y())
        self.set_font(FONT_FAMILY, 'B', 11)
        self.set_text_color(100, 116, 139)
        self.cell(40, 6, "Less Investment:", align='R')
        self.set_text_color(185, 28, 28)
        self.cell(35, 6, f"({format_currency(investment)})", align='R', ln=1)
        
        self.ln(2)
        self.set_xy(120, self.get_y())
        self.set_fill_color(240, 253, 244)
        self.rect(120, self.get_y(), 75, 12, 'F')
        self.set_xy(120, self.get_y() + 2)
        self.set_font(FONT_FAMILY, 'B', 14)
        self.set_text_color(21, 128, 61)
        net = total_savings - investment
        self.cell(40, 8, "NET VALUE:", align='R')
        self.cell(35, 8, format_currency(net), align='R', ln=1)
        self.ln(15)

# --- GEMINI AGENT ---
def run_gemini_agent(agent_role, model_name, prompt):
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

# --- SELECTOR LOGIC ---
SELECTOR_LOGIC = {
    "Hammer QA": {
        "Efficiency": {"label": "Regression Automation", "desc": "Eliminates manual UAT", "formula": "Manual_Test_Hours * Releases * Hourly_Rate"},
        "Risk":       {"label": "Shift-Left Detection", "desc": "Prevents defects via CI/CD", "formula": "Defects_Caught_Early * Cost_Difference_to_Fix"},
        "Strategic":  {"label": "Agile Velocity", "desc": "Parallel execution", "formula": "Project_Days_Saved * Daily_Revenue_per_Service"}
    },
    "Hammer VoiceExplorer": {
        "Efficiency": {"label": "Discovery Automation", "desc": "Maps legacy IVRs with 80% less effort", "formula": "Discovery_Hours_Saved * Consultant_Rate"},
        "Risk":       {"label": "Design Adherence", "desc": "Identifies navigation errors", "formula": "Logic_Gaps_Found * Rework_Cost_per_Gap"},
        "Strategic":  {"label": "Migration Assurance", "desc": "Prevents schedule creep", "formula": "Migration_Delay_Days * Daily_Project_Burn_Rate"}
    },
    "Hammer Performance": {
        "Efficiency": {"label": "Volume Validation", "desc": "Simulates peak traffic", "formula": "Testing_Hours * Hourly_Rate"},
        "Risk":       {"label": "Day 1 Outage Avoidance", "desc": "Validates cloud migrations", "formula": "Probability_of_Fail * Cost_of_Downtime"},
        "Strategic":  {"label": "Emergency Remediation", "desc": "Eliminates 'all-hands'", "formula": "War_Room_Hours * Senior_Eng_Rate * Staff_Count"}
    },
     "Hammer VoiceWatch": {
        "Efficiency": {"label": "MTTR Reduction", "desc": "Pinpoints faults", "formula": "MTTR_Reduction_Hours * Cost_of_Downtime"},
        "Risk":       {"label": "Outage Prevention", "desc": "Identifies errors pre-impact", "formula": "Major_Incidents_Prevented * Cost_of_Outage"},
        "Strategic":  {"label": "Silent Failure Detection", "desc": "24/7 monitoring", "formula": "Lost_Call_Volume * Avg_Customer_LTV"}
    },
    "Hammer Edge": {
        "Efficiency": {"label": "Mean Time to Innocence", "desc": "Proves fault domain", "formula": "Agent_Downtime * Hourly_Rate * Agent_Count"},
        "Risk":       {"label": "Hardware Lifecycle ROI", "desc": "Optimizes replacement", "formula": "Extension_of_PC_Life * Replacement_Cost"},
        "Strategic":  {"label": "VDI/CX Stability", "desc": "Ensures remote work stability", "formula": "CSAT_Improvement * Churn_Reduction_Value"}
    },
    "Ativa Enterprise": {
        "Efficiency": {"label": "Cross-Domain Correlation", "desc": "Unifies data", "formula": "Troubleshooting_Hours * Senior_Eng_Rate"},
        "Risk":       {"label": "Predictive Remediation", "desc": "AI/ML prevents incidents", "formula": "Predictive_Fixes * Major_Outage_Cost"},
        "Strategic":  {"label": "B2B Service Loyalty", "desc": "Multi-tenant portals", "formula": "B2B_Contract_Value * Churn_Rate_Reduction"}
    }
}

# --- WORKER FUNCTION ---
def process_single_product(prod, client_name, industry, problem_statement, profile_data, size_label, beta_mode):
    if beta_mode:
        return prod, {"impact": "BETA PREVIEW", "bullets": ["Beta"], "roi_components": []}

    # Match Logic
    product_rules = {}
    for key in SELECTOR_LOGIC.keys():
        if key.lower() in prod.lower():
            product_rules = SELECTOR_LOGIC[key]
            break
    if not product_rules: product_rules = SELECTOR_LOGIC["Hammer QA"]

    # Inject Manuals
    manual_text = PRODUCT_MANUALS.get(prod, "")
    if len(manual_text) > 3000: manual_text = manual_text[:3000] + "...(truncated)"

    # Step 1: Triage
    triage_prompt = f"""
    CLIENT: {client_name}
    PROBLEM: "{problem_statement}"
    TASK: Select the ONE 'Usage Scenario' name for {prod}.
    Output JSON ONLY: {{ "selected_scenario_name": "Name of scenario", "reasoning": "Why it fits" }}
    """
    triage_result = run_gemini_agent("Triage Doctor", "gemini-2.5-flash", triage_prompt)
    scenario = triage_result.get("selected_scenario_name", "Standard ROI") if triage_result else "Standard ROI"

    # Step 2: CFO
    cfo_prompt = f"""
    CLIENT: {client_name} ({industry} - {size_label})
    PRODUCT: {prod}
    SCENARIO: {scenario}
    
    PRODUCT MANUAL EXCERPT:
    "{manual_text}"
    
    BENCHMARK DATA (Use these values): 
    {json.dumps(profile_data, indent=2)}
    
    LOGIC RULES:
    {json.dumps(product_rules, indent=2)}
    
    TASK: Calculate Total Economic Impact.
    1. For each driver, calculate savings using the BENCHMARK DATA.
    2. Refer to the PRODUCT MANUAL to justify why the savings occur.
    
    Output JSON: 
    {{
       "impact": "2-sentence executive summary.",
       "bullets": ["Strategic Bullet 1", "Strategic Bullet 2", "Strategic Bullet 3"],
       "roi_components": [
           {{
               "label": "...",
               "calculation_text": "Show formula with numbers (e.g. 100 hrs * $50)",
               "savings_value": (Number)
           }}
       ]
    }}
    """
    cfo_result = run_gemini_agent("CFO Analyst", "gemini-2.5-pro", cfo_prompt)
    return prod, (cfo_result if cfo_result else PRODUCT_DATA.get(prod, {}))


# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', products=PRODUCT_DATA.keys())

@app.route('/research', methods=['POST'])
def research_client():
    """Step 1: Fetch Data for the Accordion"""
    client = request.form.get('client_name')
    url = request.form.get('client_url')
    ind = request.form.get('industry')
    
    # 1. Tavily Search
    tavily_resp = {"context": "", "revenue_est": None}
    if TAVILY_API_KEY:
        try:
            tavily = TavilyClient(api_key=TAVILY_API_KEY)
            query = f"Annual revenue and strategic priorities for {client} ({url}) in {ind}?"
            resp = tavily.search(query=query, search_depth="basic", max_results=3)
            text = "\n".join([f"- {r['content'][:300]}..." for r in resp['results']])
            
            # Extract Revenue
            rev_val = extract_revenue_from_context(client, text)
            tavily_resp = {"context": text, "revenue_est": rev_val}
        except Exception as e:
            print(f"Research Error: {e}")

    # 2. Get Benchmarks
    profile, size, _ = benchmarks.get_benchmark_profile(ind, tavily_resp['revenue_est'])
    
    # Flatten for frontend
    flat_benchmarks = {}
    for cat, metrics in profile.items():
        for k, v in metrics.items():
            flat_benchmarks[f"{cat}_{k}"] = v
            
    return jsonify({
        "success": True,
        "revenue": tavily_resp['revenue_est'],
        "size_label": size,
        "benchmarks": flat_benchmarks,
        "context": tavily_resp['context']
    })

@app.route('/generate', methods=['POST'])
def generate_pdf():
    # ... (Access Code check) ...
    if request.form.get('access_code') != ACCESS_CODE: return "Invalid Code", 403

    client = sanitize_text(request.form.get('client_name'))
    ind = sanitize_text(request.form.get('industry'))
    prob = sanitize_text(request.form.get('problem_statement'))
    prods = request.form.getlist('products')
    size_label = request.form.get('size_label', 'Medium')
    
    # 1. Reconstruct Profile from User Edits (The Accordion Data)
    custom_profile = {"ops": {}, "dev": {}, "incidents": {}, "cx": {}}
    for key, val in request.form.items():
        if key.startswith("bench_"):
            parts = key.replace("bench_", "").split("_", 1)
            if len(parts) == 2:
                category, metric = parts
                if category in custom_profile:
                    try: custom_profile[category][metric] = float(val)
                    except: custom_profile[category][metric] = val

    # 2. Run Analysis
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_prod = {
            executor.submit(process_single_product, p, client, ind, prob, custom_profile, size_label, False): p 
            for p in prods
        }
        for future in concurrent.futures.as_completed(future_to_prod):
            p = future_to_prod[future]
            try:
                p_name, data = future.result()
                results[p_name] = data
            except: results[p] = {}

    # 3. Calculate Totals
    costs = {}
    for p in prods:
        try:
            c = float(request.form.get(f'cost_{p}', 0))
            t = float(request.form.get(f'term_{p}', 12))
            costs[p] = {'cost': c, 'term': t}
        except: costs[p] = {'cost': 0, 'term': 12}

    roi_data = {}
    tot_inv = 0
    tot_save = 0
    for p, data in results.items():
        comps = data.get('roi_components', [])
        p_save = sum([extract_currency_value(c.get('savings_value', 0)) for c in comps])
        
        inv = costs[p]['cost'] * costs[p]['term']
        term_years = costs[p]['term'] / 12.0
        term_save = p_save * term_years
        
        tot_inv += inv
        tot_save += term_save
        roi_data[p] = {"investment": inv, "savings": term_save, "components": comps}

    # 4. Generate PDF
    pdf = ProReportPDF()
    pdf.set_auto_page_break(True, 15)
    
    pdf.add_page()
    pdf.ln(5)
    pdf.set_font(FONT_FAMILY, 'B', 24)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, f"Strategic ROI Analysis", ln=True)
    pdf.set_font(FONT_FAMILY, '', 14)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 8, f"Prepared for: {client}", ln=True)
    pdf.ln(10)
    
    pdf.set_fill_color(241, 245, 249)
    pdf.rect(10, pdf.get_y(), 190, 25, 'F')
    pdf.set_xy(15, pdf.get_y()+5)
    pdf.set_font(FONT_FAMILY, 'I', 10)
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
    # This call will now work because create_payback_chart is restored
    chart_img = create_payback_chart(tot_inv, tot_save)
    pdf.image(chart_img, x=10, w=190)
    
    for p in prods:
        if p not in results: continue
        d = results[p]
        calc = roi_data.get(p, {'savings':0, 'investment':0, 'components':[]})
        
        pdf.add_page()
        pdf.chapter_title(f"Analysis: {p}")
        
        pdf.set_font(FONT_FAMILY, 'I', 11)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(0, 6, sanitize_text(d.get('impact', '')))
        pdf.ln(8)
        
        pdf.set_font(FONT_FAMILY, '', 10)
        pdf.set_text_color(15, 23, 42)
        for b in d.get('bullets', []):
            pdf.set_x(15)
            pdf.cell(5, 6, "+", ln=0)
            pdf.multi_cell(170, 6, sanitize_text(b))
            pdf.ln(2)
        pdf.ln(5)
        
        if 'roi_components' in d:
             pdf.draw_financial_table(d['roi_components'], calc['savings'], calc['investment'])

    # --- NEW: ASSUMPTIONS APPENDIX ---
    pdf.add_page()
    pdf.chapter_title("Appendix: Financial Assumptions")
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 5, f"This analysis uses the following baseline metrics derived from the '{ind}' industry profile for a {size_label} organization:")
    pdf.ln(5)
    
    col_w = 90
    row_h = 8
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(col_w, row_h, "Metric", 1, 0, 'L', 1)
    pdf.cell(col_w, row_h, "Value Used", 1, 1, 'L', 1)
    pdf.set_font('Helvetica', '', 9)
    
    # Flatten custom_profile for table
    for cat, metrics in custom_profile.items():
        for k, v in metrics.items():
            label = k.replace("_", " ").title()
            val = f"${v:,.2f}" if "rate" in k or "cost" in k else str(v)
            pdf.cell(col_w, row_h, label, 1, 0)
            pdf.cell(col_w, row_h, val, 1, 1)

    try:
        pdf_out = pdf.output(dest='S').encode('latin-1') 
    except:
        pdf_out = bytes(pdf.output()) 

    return send_file(
        io.BytesIO(pdf_out),
        as_attachment=True,
        download_name=f"ROI_Analysis_{client}.pdf",
        mimetype="application/pdf"
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
