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
from knowledge_base import PRODUCT_DATA

import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)

# --- CONFIGURATION ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ACCESS_CODE = os.getenv("ACCESS_CODE", "Hammer2025!")

# Configure Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- STYLING ---
COLOR_PRIMARY = (15, 23, 42)    # Navy
COLOR_ACCENT = (37, 99, 235)    # Blue
COLOR_TEXT = (51, 65, 85)       # Slate
FONT_FAMILY = 'Helvetica'

# --- UTILS ---
def sanitize_text(text):
    if not isinstance(text, str): return str(text)
    replacements = {'\u2013': '-', '\u2014': '--', '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u00a0': ' ', '\u2022': '*'}
    for char, rep in replacements.items(): text = text.replace(char, rep)
    return text.encode('latin-1', 'replace').decode('latin-1')

def get_tavily_context(client_name, client_url, industry):
    """Agent 2: The Researcher (Uses Tavily)"""
    if not TAVILY_API_KEY: return f"Standard {industry} challenges apply."
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        query = f"What are the top strategic priorities and recent news for {client_name} ({client_url}) in {industry} 2024-2025?"
        response = tavily.search(query=query, search_depth="basic", max_results=3)
        return "\n".join([f"- {r['content'][:200]}..." for r in response['results']])
    except:
        return "Standard industry operational pressure."

# --- GEMINI AGENT ENGINE ---
def run_gemini_agent(agent_role, model_name, prompt, beta_mode=False):
    """
    Generic handler for calling Gemini Models.
    """
    if beta_mode:
        return None # Skip execution in beta
        
    try:
        # Gemini 1.5 supports native JSON schemas, but for simplicity/robustness across versions, 
        # we'll use the prompt instruction + response_mime_type.
        model = genai.GenerativeModel(
            model_name,
            system_instruction=f"You are a specialized agent: {agent_role}. You output strictly valid JSON."
        )
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini Error ({agent_role}): {e}")
        return None

def generate_tailored_content(client_name, industry, project_type, context_text, problem_statement, selected_products, mode='live'):
    """
    The 3-Agent Chain:
    1. Triage (Gemini Flash) -> 2. Research (Tavily) -> 3. Analysis (Gemini Pro)
    """
    
    # Context Loading
    product_context_str = ""
    for prod in selected_products:
        if prod in PRODUCT_DATA:
            product_context_str += f"\nPRODUCT: {prod}\nDESC: {PRODUCT_DATA[prod]['tagline']}\n"

    # --- AGENT 1: TRIAGE DOCTOR (Gemini 1.5 Flash) ---
    # Task: Analyze the problem and pick the strategy.
    triage_prompt = f"""
    CLIENT: {client_name}
    PROBLEM: "{problem_statement}"
    PRODUCTS: {product_context_str}
    
    TASK: Analyze the USER PROBLEM. For each product, determine the best "ROI Archetype" (e.g., Labor Savings vs. Risk Avoidance).
    Output JSON: {{ "Product_Name": "Rationale for strategy..." }}
    """
    
    # --- AGENT 3: CFO ANALYST (Gemini 1.5 Pro) ---
    # Task: Do the detailed logic construction.
    cfo_prompt = f"""
    CLIENT: {client_name} ({industry})
    FOCUS: {project_type}
    PROBLEM: "{problem_statement}"
    CONTEXT: {context_text}
    PRODUCTS: {product_context_str}

    TASK:
    For each product, generate a JSON object with:
    1. "impact": 2-sentence strategic impact statement.
    2. "bullets": 3 Hard Savings bullet points.
    3. "math_variables": A specific financial scenario.
       - "scenario_title": Title of the calculation (e.g. "Cost of Downtime")
       - "metric_unit": Unit of measure
       - "cost_per_unit_label": e.g. "Avg Cost per Hour"
       - "cost_per_unit_value": (Number only)
       - "before_label": e.g. "Current Manual Process"
       - "before_qty": (Number only)
       - "after_label": e.g. "With Automation"
       - "after_qty": (Number only)

    Output pure JSON: {{ "ProductName": {{ "impact": "...", "bullets": [], "math_variables": {{...}} }} }}
    """

    # --- BETA MODE PREVIEW ---
    if mode == 'beta':
        debug_output = {}
        preview_text = (
            f"--- [AGENT 1: TRIAGE (Flash)] ---\n{triage_prompt}\n\n"
            f"--- [AGENT 3: CFO (Pro)] ---\n{cfo_prompt}"
        )
        for prod in selected_products:
            fallback = PRODUCT_DATA.get(prod, {}).get('math_variables', {})
            debug_output[prod] = {
                "impact": preview_text,
                "bullets": ["(Beta Mode)", "No API Cost"],
                "math_variables": fallback
            }
        return debug_output

    if not GOOGLE_API_KEY:
        return {prod: PRODUCT_DATA.get(prod, {}) for prod in selected_products}

    # Execute Chain
    # Note: We skip Agent 1 actual call for V1.5 efficiency and just feed the instructions directly 
    # to Agent 3 (Pro) which is smart enough to do both triage and calc in one shot. 
    # This saves latency.
    
    result = run_gemini_agent("CFO Analyst", "gemini-1.5-pro", cfo_prompt)
    
    if not result:
        return {prod: PRODUCT_DATA.get(prod, {}) for prod in selected_products}
        
    return result

# --- CALCULATOR (Python) ---
def calculate_roi(product_data, user_costs):
    results = {}
    total_investment = 0
    total_savings = 0

    for prod_name, ai_data in product_data.items():
        math = ai_data.get('math_variables', PRODUCT_DATA.get(prod_name, {}).get('math_variables'))
        if not math: continue

        cost_monthly = user_costs.get(prod_name, {}).get('cost', 0)
        term_months = user_costs.get(prod_name, {}).get('term', 12)
        investment = cost_monthly * term_months
        total_investment += investment

        term_years = term_months / 12.0
        unit_cost = math.get('cost_per_unit_value', 0)
        before_qty = math.get('before_qty', 0)
        after_qty = math.get('after_qty', 0)
        
        annual_savings = (unit_cost * before_qty) - (unit_cost * after_qty)
        term_savings = annual_savings * term_years

        results[prod_name] = {
            "investment": investment,
            "savings": term_savings,
            "math": math,
            "roi": ((term_savings - investment)/investment)*100 if investment > 0 else 0
        }
        total_savings += term_savings

    return results, total_investment, total_savings

# --- PDF GENERATOR (ProReportPDF) ---
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
        self.cell(0, 10, 'CONFIDENTIAL', ln=1, align='R')
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

    def draw_math_table(self, math_data, savings, investment):
        self.set_fill_color(248, 250, 252)
        self.rect(10, self.get_y(), 190, 35, 'F')
        
        self.set_xy(15, self.get_y()+5)
        self.set_font(FONT_FAMILY, 'B', 10)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 5, f"Scenario: {sanitize_text(math_data.get('scenario_title', 'ROI Analysis'))}", ln=True)
        
        col_1, col_2, y_base = 60, 100, self.get_y() + 2
        
        # Benchmark
        self.set_font(FONT_FAMILY, 'B', 9)
        self.set_text_color(100, 100, 100)
        self.set_xy(15, y_base)
        self.cell(col_1, 5, "Industry Benchmark:", ln=0)
        self.set_font(FONT_FAMILY, '', 9)
        self.set_text_color(0, 0, 0)
        self.cell(col_2, 5, f"${math_data.get('cost_per_unit_value', 0):,.2f} per {sanitize_text(math_data.get('metric_unit', 'Unit'))}", ln=1)
        
        # Status Quo
        self.set_xy(15, y_base + 6)
        self.set_font(FONT_FAMILY, 'B', 9)
        self.set_text_color(185, 28, 28)
        self.cell(col_1, 5, sanitize_text(math_data.get('before_label', 'Before')), ln=0)
        self.set_font(FONT_FAMILY, '', 9)
        self.set_text_color(0, 0, 0)
        val_before = math_data.get('cost_per_unit_value', 0) * math_data.get('before_qty', 0)
        self.cell(col_2, 5, f"{math_data.get('before_qty', 0)} units = ${val_before:,.0f}/yr Risk", ln=1)
        
        # Solution
        self.set_xy(15, y_base + 12)
        self.set_font(FONT_FAMILY, 'B', 9)
        self.set_text_color(22, 163, 74)
        self.cell(col_1, 5, sanitize_text(math_data.get('after_label', 'After')), ln=0)
        self.set_font(FONT_FAMILY, '', 9)
        self.set_text_color(0, 0, 0)
        val_after = math_data.get('cost_per_unit_value', 0) * math_data.get('after_qty', 0)
        self.cell(col_2, 5, f"{math_data.get('after_qty', 0)} units = ${val_after:,.0f}/yr Risk", ln=1)
        
        # Summary
        self.set_xy(130, y_base + 10)
        self.set_font(FONT_FAMILY, 'B', 12)
        self.set_text_color(*COLOR_ACCENT)
        self.cell(60, 10, f"Net Savings: ${savings:,.0f}", align='R')
        self.ln(20)

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

# --- CHART GENERATOR ---
def create_payback_chart(one_time_cost, recurring_cost):
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(7, 3.5))
    months = list(range(13))
    start_val = -1 * abs(float(one_time_cost or 50000))
    monthly_gain = (recurring_cost * 2.5) / 12 if recurring_cost > 0 else 5000
    cash_flow = []
    current = start_val
    for m in months:
        cash_flow.append(current)
        current += monthly_gain
    ax.plot(months, cash_flow, color='#2563EB', linewidth=3, marker='o', markersize=6)
    ax.axhline(0, color='#64748B', linewidth=1.5, linestyle='--')
    ax.set_title("Cumulative Cash Flow (Year 1)", fontsize=12, fontweight='bold', pad=15, color='#0F172A')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle=':', alpha=0.6)
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
    if request.form.get('access_code') != ACCESS_CODE: return "Invalid Access Code", 403

    mode = request.form.get('mode', 'live')
    client_name = sanitize_text(request.form.get('client_name'))
    industry = sanitize_text(request.form.get('industry'))
    project_type = sanitize_text(request.form.get('project_type'))
    problem_statement = sanitize_text(request.form.get('problem_statement'))
    selected_products = request.form.getlist('products')
    
    # Parse Costs
    user_costs = {}
    for prod in selected_products:
        try:
            cost = float(request.form.get(f'cost_{prod}', 0))
            term_str = request.form.get(f'term_{prod}', '12')
            term = float(request.form.get(f'term_custom_{prod}', 12)) if term_str == 'other' else float(term_str)
            user_costs[prod] = {'cost': cost, 'term': term}
        except:
            user_costs[prod] = {'cost': 0, 'term': 12}

    # Execute Agent Chain
    tavily_context = get_tavily_context(client_name, request.form.get('client_url'), industry)
    ai_content = generate_tailored_content(client_name, industry, project_type, tavily_context, problem_statement, selected_products, mode)
    
    # Python Calculator
    roi_data, total_inv, total_save = calculate_roi(ai_content, user_costs)

    # PDF Build
    pdf = ProReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Page 1: Executive Summary
    pdf.add_page()
    pdf.ln(5)
    pdf.set_font(FONT_FAMILY, 'B', 20)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(0, 10, f"Strategic ROI Analysis: {client_name}", ln=True)
    pdf.set_font(FONT_FAMILY, '', 12)
    pdf.set_text_color(*COLOR_TEXT)
    pdf.cell(0, 8, f"Focus: {project_type} | Problem: {problem_statement[:50]}...", ln=True)
    pdf.ln(10)
    
    # Scorecards
    y_start = pdf.get_y()
    card_w, card_h = 60, 25
    pdf.card_box("PROJECTED SAVINGS", f"${total_save:,.0f}", "Total Contract Value", 10, y_start, card_w, card_h)
    pdf.card_box("INVESTMENT", f"${total_inv:,.0f}", "Total Cost", 75, y_start, card_w, card_h)
    roi_pct = ((total_save - total_inv)/total_inv)*100 if total_inv > 0 else 0
    pdf.card_box("ROI %", f"{roi_pct:.0f}%", "Net Return", 140, y_start, card_w, card_h)
    
    pdf.set_y(y_start + card_h + 15)
    chart_img = create_payback_chart(total_inv/2, total_save/12) # Approximation for chart
    pdf.image(chart_img, x=10, w=180)

    # Product Pages
    for prod in selected_products:
        if prod not in ai_content: continue
        data = ai_content[prod]
        calc = roi_data.get(prod, {'savings':0, 'investment':0, 'math':{}})
        
        pdf.add_page()
        pdf.chapter_title(f"Analysis: {prod}")
        
        pdf.set_font(FONT_FAMILY, 'I', 10)
        pdf.set_text_color(50,50,50)
        pdf.multi_cell(0, 5, sanitize_text(data.get('impact', '')))
        pdf.ln(5)
        
        pdf.set_font(FONT_FAMILY, '', 10)
        pdf.set_text_color(*COLOR_TEXT)
        for bullet in data.get('bullets', []):
            pdf.set_x(15)
            pdf.cell(5, 5, "+", ln=0)
            pdf.multi_cell(170, 5, sanitize_text(bullet))
        pdf.ln(10)
        
        if 'math_variables' in data:
            pdf.draw_math_table(data['math_variables'], calc['savings'], calc['investment'])

    output_path = "generated_roi_report.pdf"
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
