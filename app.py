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
from knowledge_base import PRODUCT_DATA, ROI_ARCHETYPES

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

def agent_triage_doctor(client_name, problem_statement, product_name, beta_mode=False):
    """
    Agent 1: Diagnoses the problem and selects the best ROI Archetype.
    """
    # 1. Get the Menu for this product
    menu = ROI_ARCHETYPES.get(product_name, {})
    if not menu:
        return "default"

    # 2. Construct the "Menu Card" for the AI
    menu_str = json.dumps(menu, indent=2)

    # 3. The Prompt
    prompt = f"""
    You are a Triage Agent. 
    CLIENT: {client_name}
    USER PROBLEM: "{problem_statement}"
    
    AVAILABLE ROI MODELS (The Menu):
    {menu_str}
    
    TASK: 
    Compare the USER PROBLEM to the "logic" in the Menu.
    Select the single best "key" (e.g., 'outage_avoidance' or 'labor_savings') that solves their specific pain.
    
    Output JSON ONLY: {{ "selected_key": "..." }}
    """
    
    if beta_mode:
        return {"selected_key": "BETA_PREVIEW", "prompt": prompt}

    # 4. Call Gemini Flash (Fast & Cheap)
    result = run_gemini_agent("Triage Doctor", "gemini-1.5-flash", prompt)
    if result and "selected_key" in result:
        # Validate the key actually exists in the menu
        if result["selected_key"] in menu:
            return result["selected_key"]
    
    # Fallback: Return the first key in the menu if AI fails or picks invalid key
    return list(menu.keys())[0] if menu else "default"

def agent_cfo_analyst(client_name, industry, product_name, selected_key, context_text, beta_mode=False):
    """
    Agent 3: Constructs the math based on the specific archetype selected.
    """
    # 1. Get the specific logic definition
    archetype_data = ROI_ARCHETYPES.get(product_name, {}).get(selected_key, {})
    
    prompt = f"""
    You are a Financial Analyst.
    CLIENT: {client_name} ({industry})
    PRODUCT: {product_name}
    SELECTED STRATEGY: {archetype_data.get('title', 'ROI Analysis')}
    STRATEGY LOGIC: {archetype_data.get('logic', 'Standard Savings')}
    INDUSTRY CONTEXT: {context_text}
    
    TASK:
    Generate a JSON object for a Financial Table.
    Use realistic estimates for {industry}.
    
    Required JSON Structure:
    {{
       "impact": "2-sentence strategic impact statement.",
       "bullets": ["Bullet 1", "Bullet 2", "Bullet 3"],
       "math_variables": {{
           "scenario_title": "{archetype_data.get('title', 'ROI Analysis')}",
           "metric_unit": "e.g., Hours/Year or Incidents/Year",
           "cost_per_unit_label": "e.g., Avg Hourly Cost",
           "cost_per_unit_value": (Number),
           "before_label": "Current Status",
           "before_qty": (Number - High),
           "after_label": "Future Status",
           "after_qty": (Number - Low)
       }}
    }}
    """
    
    if beta_mode:
        return prompt # Return the prompt string for preview
    
    # Call Gemini Pro (Smart Reasoning)
    return run_gemini_agent("CFO Analyst", "gemini-1.5-pro", prompt)


def generate_tailored_content(client_name, industry, project_type, context_text, problem_statement, selected_products, mode='live'):
    """
    The 3-Agent Chain Orchestrator
    """
    results = {}
    is_beta = (mode == 'beta')
    
    for prod in selected_products:
        # 1. Agent 1: Triage (Selects the Strategy Key)
        triage_result = agent_triage_doctor(client_name, problem_statement, prod, beta_mode=is_beta)
        
        if is_beta:
            # In Beta, triage_result is a dict with the prompt
            selected_key = "BETA_PREVIEW"
            triage_prompt_preview = triage_result['prompt']
        else:
            selected_key = triage_result
        
        # 2. Agent 3: CFO (Uses the key from Agent 1)
        cfo_result = agent_cfo_analyst(client_name, industry, prod, selected_key, context_text, beta_mode=is_beta)
        
        if is_beta:
             # In Beta, cfo_result is just the prompt string
             fallback = PRODUCT_DATA.get(prod, {}).get('math_variables', {})
             preview_text = (
                 f"--- [AGENT 1: TRIAGE (Flash)] ---\n{triage_prompt_preview}\n\n"
                 f"--- [AGENT 3: CFO (Pro)] ---\n{cfo_result}"
             )
             results[prod] = {
                 "impact": preview_text,
                 "bullets": ["(Beta Mode)", "No API Cost"],
                 "math_variables": fallback
             }
        else:
             # In Live, cfo_result is the JSON
             if cfo_result:
                 results[prod] = cfo_result
             else:
                 # Fallback if Gemini fails
                 results[prod] = PRODUCT_DATA.get(prod, {})

    return results

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

# --- PDF GENERATOR ---
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
