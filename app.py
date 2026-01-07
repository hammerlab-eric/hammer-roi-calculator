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
    """ 
    Searches for strategic context AND revenue data.
    """
    default_resp = {"context": f"Standard {industry} challenges.", "raw_search": ""}
    
    if not TAVILY_API_KEY: return default_resp
    
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        # Explicitly ask for revenue to ensure the data is in the text for the AI to find
        query = f"Annual revenue and strategic priorities for {client_name} ({client_url}) in {industry} 2024/2025?"
        response = tavily.search(query=query, search_depth="basic", max_results=3)
        
        # Combine snippets into one text block
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

# --- NEW: REVENUE SCOUT AGENT ---
def extract_revenue_from_context(client_name, search_text):
    """
    Uses Gemini Flash to read the Tavily search results and extract a single integer for revenue.
    """
    if not search_text: return None
    
    prompt = f"""
    CONTEXT:
    {search_text}
    
    TASK: Identify the annual revenue for {client_name} from the context above.
    If a range is given, use the lower bound.
    If no revenue is found, return null.
    
    OUTPUT JSON: {{ "annual_revenue": (Number or null) }}
    """
    
    # Quick, cheap call
    result = run_gemini_agent("Revenue Scout", "gemini-2.5-flash", prompt)
    if result and result.get("annual_revenue"):
        return result["annual_revenue"]
    return None

# --- WORKER FUNCTION ---
def process_single_product(prod, client_name, industry, problem_statement, context_data, revenue_est, beta_mode):
    if beta_mode:
        return prod, {"impact": "BETA PREVIEW", "bullets": ["Beta"], "math_variables": {"scenario_title": "Beta", "cost_per_unit_value":0}}

    # 1. Get Benchmarks using the AI-extracted Revenue
    profile_data, size_label, industry_key = benchmarks.get_benchmark_profile(industry, revenue_est)
    
    full_manual = PRODUCT_MANUALS.get(prod, "No manual found.")
    manual_snippet = full_manual[:15000]

    # Step 2: Triage
    triage_prompt = f"""
    CLIENT: {client_name}
    PROBLEM: "{problem_statement}"
    MANUAL: {manual_snippet} 
    TASK: Select the ONE 'ROI Metric' or 'Usage Scenario' that best solves the User Problem.
    Output JSON ONLY: {{ "selected_scenario_name": "Name of scenario", "reasoning": "Why it fits" }}
    """
    triage_result = run_gemini_agent("Triage Doctor", "gemini-2.5-flash", triage_prompt)
    scenario = triage_result.get("selected_scenario_name", "Standard ROI") if triage_result else "Standard ROI"

    # Step 3: CFO (Injected with Benchmarks)
    cfo_prompt = f"""
    CLIENT: {client_name} ({industry_key} - {size_label} Business)
    PRODUCT: {prod}
    SCENARIO: {scenario}
    CONTEXT: {context_data['context']}
    MANUAL SNIPPET: {manual_snippet}
    
    BENCHMARK DATA (Truth Source):
    {json.dumps(profile_data, indent=2)}
    
    TASK: Generate a financial ROI table.
    
    CRITICAL RULES:
    1. Use the "BENCHMARK DATA" for cost basis (e.g. agent_hourly_rate).
    2. Automation must REDUCE the quantity (e.g. Hours, Incidents).
    3. DO NOT hallucinate costs. Use the provided benchmarks.
    
    Output JSON: 
    {{
       "impact": "2-sentence impact statement.",
       "bullets": ["Bullet 1", "Bullet 2", "Bullet 3"],
       "math_variables": {{
           "scenario_title": "{scenario}",
           "metric_unit": "Unit (e.g. Hours, Incidents)",
           "cost_per_unit_label": "Rate Label (e.g. Hourly Cost)",
           "cost_per_unit_value": (Number from Benchmarks),
           "before_label": "Current State",
           "before_qty": (Number),
           "after_label": "Future State",
           "after_qty": (Number)
       }}
    }}
    """
    cfo_result = run_gemini_agent("CFO Analyst", "gemini-2.5-pro", cfo_prompt)
    return prod, (cfo_result if cfo_result else PRODUCT_DATA.get(prod, {}))

def generate_tailored_content(client_name, industry, project_type, context_data, problem_statement, selected_products, mode='live'):
    results = {}
    is_beta = (mode == 'beta')
    
    # 1. Extract Revenue ONCE (Efficiency)
    revenue_est = extract_revenue_from_context(client_name, context_data['raw_search'])
    
    # 2. Parallel Process Products
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_prod = {
            executor.submit(
                process_single_product, 
                prod, 
                client_name, 
                industry, 
                problem_statement, 
                context_data, 
                revenue_est,  # Pass the extracted revenue down
                is_beta
            ): prod 
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
        math = data.get('math_variables')
        if not math: continue
        
        cost_info = user_costs.get(prod, {'cost': 0, 'term': 12})
        investment = cost_info['cost'] * cost_info['term']
        total_inv += investment
        
        unit = float(math.get('cost_per_unit_value', 0))
        before = float(math.get('before_qty', 0))
        after = float(math.get('after_qty', 0))
        
        annual_savings = (unit * before) - (unit * after)
        term_years = cost_info['term'] / 12.0
        
        total_term_savings = annual_savings * term_years
        total_save += total_term_savings
        
        results[prod] = {"investment": investment, "savings": total_term_savings, "math": math}
        
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

    def smart_row(self, c1_text, c2_text, c3_text, c1_color=(0,0,0), c3_color=(0,0,0)):
        x_start = 15
        col_widths = [95, 30, 50] 
        y_start = self.get_y()
        
        self.set_xy(x_start, y_start)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(*c1_color)
        self.multi_cell(col_widths[0], 6, sanitize_text(c1_text), align='L')
        y_end_1 = self.get_y()
        
        self.set_xy(x_start + col_widths[0], y_start)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(col_widths[1], 6, sanitize_text(c2_text), align='C')
        y_end_2 = self.get_y()
        
        self.set_xy(x_start + col_widths[0] + col_widths[1], y_start)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(*c3_color)
        self.multi_cell(col_widths[2], 6, sanitize_text(c3_text), align='R')
        y_end_3 = self.get_y()
        
        self.set_y(max(y_end_1, y_end_2, y_end_3) + 4)

    def draw_math_table(self, math, save, inv):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(15, 23, 42)
        scenario = sanitize_text(math.get('scenario_title', 'ROI Analysis'))
        self.cell(0, 8, f"Scenario: {scenario}", ln=True)
        self.ln(2)
        
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(100, 100, 100)
        unit_cost = math.get('cost_per_unit_value', 0)
        unit_name = sanitize_text(math.get('metric_unit', 'Unit'))
        self.cell(0, 6, f"Benchmark: {format_currency(unit_cost)} per {unit_name}", ln=True)
        self.ln(4)
        
        qty_before = math.get('before_qty', 0)
        val_before = unit_cost * qty_before
        self.smart_row(
            c1_text=math.get('before_label', 'Before'),
            c2_text=f"{qty_before:,.0f}",
            c3_text=f"= {format_currency(val_before)} Risk",
            c1_color=(185, 28, 28)
        )
        
        qty_after = math.get('after_qty', 0)
        val_after = unit_cost * qty_after
        self.smart_row(
            c1_text=math.get('after_label', 'After'),
            c2_text=f"{qty_after:,.0f}",
            c3_text=f"= {format_currency(val_after)} Risk",
            c1_color=(22, 163, 74)
        )
        
        self.ln(2)
        self.set_draw_color(200, 200, 200)
        self.line(120, self.get_y(), 200, self.get_y())
        self.ln(2)
        
        is_positive = save > 0
        color = (22, 163, 74) if is_positive else (185, 28, 28)
        self.set_text_color(*color)
        self.set_font('Helvetica', 'B', 14)
        label = "Net Benefit" if is_positive else "Net Cost"
        
        self.set_x(120)
        self.cell(80, 10, f"{label}: {format_currency(save)}", align='R', ln=1)
        self.ln(10)

    def card_box(self, label, value, subtext, x, y, w, h):
        self.set_xy(x, y)
        self.set_fill_color(255, 255, 255)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.5)
        self.rect(x, y, w, h, 'DF')
        
        self.set_xy(x, y + 6)
        self.set_font('Helvetica', 'B', 14)
        
        if "ROI" in label or "SAVINGS" in label:
             if "(" in value or "-" in value:
                 self.set_text_color(185, 28, 28)
             else:
                 self.set_text_color(22, 163, 74)
        else:
            self.set_text_color(15, 23, 42)

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
        calc = roi.get(p, {'savings':0, 'investment':0, 'math':{}})
        
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
        
        if 'math_variables' in d:
             pdf.draw_math_table(d['math_variables'], calc['savings'], calc['investment'])
    
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
