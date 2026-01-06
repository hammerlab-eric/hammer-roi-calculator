import os
import io
import json
from flask import Flask, render_template, request, send_file
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from tavily import TavilyClient
from openai import OpenAI
from knowledge_base import PRODUCT_DATA

import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)

# --- CONFIGURATION ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ACCESS_CODE = os.getenv("ACCESS_CODE", "Hammer2025!") 

# --- STYLING ---
COLOR_PRIMARY = (15, 23, 42)    # Navy
COLOR_ACCENT = (37, 99, 235)    # Blue
COLOR_TEXT = (51, 65, 85)       # Slate
COLOR_LIGHT = (241, 245, 249)   # Light Gray
FONT_FAMILY = 'Helvetica'

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
        query = f"What are the top strategic priorities and recent news for {client_name} ({client_url}) in {industry} 2024-2025?"
        response = tavily.search(query=query, search_depth="basic", max_results=3)
        return "\n".join([f"- {r['content'][:200]}..." for r in response['results']])
    except:
        return "Standard industry operational pressure."

# --- AI ENGINE ---
def generate_tailored_content(client_name, industry, project_type, context_text, problem_statement, selected_products, mode='live'):
    """
    Asks AI for Math Variables (Benchmarks), not final Savings.
    """
    product_context_str = ""
    for prod in selected_products:
        if prod in PRODUCT_DATA:
            product_context_str += f"\nPRODUCT: {prod}\nDESC: {PRODUCT_DATA[prod]['tagline']}\n"

    system_prompt = "You are a Senior Solutions Engineer. You provide quantitative data for business cases."
    user_prompt = f"""
    CLIENT: {client_name} ({industry})
    FOCUS: {project_type}
    PROBLEM: "{problem_statement}"
    CONTEXT: {context_text}

    PRODUCTS: {product_context_str}

    TASK:
    For each product, generate a JSON object with:
    1. "impact": 2-sentence strategic impact statement tailored to the problem.
    2. "bullets": 3 Hard Savings bullet points.
    3. "math_variables": A specific financial scenario ESTIMATING ANNUAL IMPACT.
       - "scenario_title": e.g., "Cost of Downtime Reduction"
       - "metric_unit": e.g., "Hours of Downtime/Year"
       - "cost_per_unit_label": e.g., "Avg Cost per Hour (Healthcare)"
       - "cost_per_unit_value": (Number only, e.g., 45000)
       - "before_label": e.g., "Current Manual Process"
       - "before_qty": (Number only, estimated annual hours/units)
       - "after_label": e.g., "With Automation"
       - "after_qty": (Number only, estimated annual hours/units)

    Output pure JSON: {{ "ProductName": {{ "impact": "...", "bullets": [], "math_variables": {{...}} }} }}
    """

    if mode == 'beta':
        debug_output = {}
        prompt_preview = f"--- BETA PREVIEW ---\n\n[USER PROMPT]:\n{user_prompt}"
        for prod in selected_products:
            # Use Fallback Math for Beta Preview so tables render
            fallback_math = PRODUCT_DATA[prod]['math_variables']
            debug_output[prod] = {
                "impact": prompt_preview,
                "bullets": ["(Beta Mode)", "Review Prompt Above"],
                "math_variables": fallback_math
            }
        return debug_output

    if not OPENAI_API_KEY:
        # Fallback to static
        return {prod: PRODUCT_DATA[prod] for prod in selected_products if prod in PRODUCT_DATA}

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return {prod: PRODUCT_DATA[prod] for prod in selected_products if prod in PRODUCT_DATA}

# --- CALCULATOR ---
def calculate_roi(product_data, user_costs):
    """
    Merges AI Benchmarks with User Pricing to calculate Savings.
    """
    results = {}
    total_investment = 0
    total_savings = 0

    for prod_name, ai_data in product_data.items():
        # Get Math Variables
        math = ai_data.get('math_variables', PRODUCT_DATA.get(prod_name, {}).get('math_variables'))
        if not math: continue

        # Get User Costs
        cost_monthly = user_costs.get(prod_name, {}).get('cost', 0)
        term_months = user_costs.get(prod_name, {}).get('term', 12)
        
        # Calculate Investment
        investment = cost_monthly * term_months
        total_investment += investment

        # Calculate Savings (Annualized Logic normalized to Term)
        # Note: AI gives Annual figures. We adjust to Term Length.
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
        """Renders the Financial Logic Table"""
        self.set_fill_color(248, 250, 252)
        self.rect(10, self.get_y(), 190, 35, 'F')
        
        # Title
        self.set_xy(15, self.get_y()+5)
        self.set_font(FONT_FAMILY, 'B', 10)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 5, f"Scenario: {sanitize_text(math_data['scenario_title'])}", ln=True)
        
        # Columns
        col_1 = 60
        col_2 = 100
        y_base = self.get_y() + 2
        
        # Row 1: Benchmark
        self.set_font(FONT_FAMILY, 'B', 9)
        self.set_text_color(100, 100, 100)
        self.set_xy(15, y_base)
        self.cell(col_1, 5, "Industry Benchmark:", ln=0)
        self.set_font(FONT_FAMILY, '', 9)
        self.set_text_color(0, 0, 0)
        self.cell(col_2, 5, f"${math_data['cost_per_unit_value']:,.2f} per {sanitize_text(math_data['metric_unit'])}", ln=1)
        
        # Row 2: Status Quo
        self.set_xy(15, y_base + 6)
        self.set_font(FONT_FAMILY, 'B', 9)
        self.set_text_color(185, 28, 28) # Red
        self.cell(col_1, 5, sanitize_text(math_data['before_label']), ln=0)
        self.set_font(FONT_FAMILY, '', 9)
        self.set_text_color(0, 0, 0)
        val_before = math_data['cost_per_unit_value'] * math_data['before_qty']
        self.cell(col_2, 5, f"{math_data['before_qty']} units x Cost = ${val_before:,.0f}/yr Risk", ln=1)
        
        # Row 3: Solution
        self.set_xy(15, y_base + 12)
        self.set_font(FONT_FAMILY, 'B', 9)
        self.set_text_color(22, 163, 74) # Green
        self.cell(col_1, 5, sanitize_text(math_data['after_label']), ln=0)
        self.set_font(FONT_FAMILY, '', 9)
        self.set_text_color(0, 0, 0)
        val_after = math_data['cost_per_unit_value'] * math_data['after_qty']
        self.cell(col_2, 5, f"{math_data['after_qty']} units x Cost = ${val_after:,.0f}/yr Risk", ln=1)
        
        # Row 4: Summary
        self.set_xy(130, y_base + 10)
        self.set_font(FONT_FAMILY, 'B', 12)
        self.set_text_color(*COLOR_ACCENT)
        self.cell(60, 10, f"Net Savings: ${savings:,.0f}", align='R')
        
        self.ln(20)


@app.route('/')
def index():
    return render_template('index.html', products=PRODUCT_DATA.keys())

@app.route('/generate', methods=['POST'])
def generate_pdf():
    # 0. Security
    if request.form.get('access_code') != ACCESS_CODE: return "Invalid Access Code", 403

    # 1. Inputs
    mode = request.form.get('mode', 'live')
    client_name = sanitize_text(request.form.get('client_name'))
    industry = sanitize_text(request.form.get('industry'))
    project_type = sanitize_text(request.form.get('project_type'))
    problem_statement = sanitize_text(request.form.get('problem_statement'))
    selected_products = request.form.getlist('products')
    
    # 2. Parse Dynamic Pricing
    user_costs = {}
    for prod in selected_products:
        # The HTML names are likely 'cost_Hammer VoiceWatch' -> need to handle spaces
        # Easier trick: iterate form keys
        p_key = prod # Assuming the checkbox value is safe
        try:
            cost = float(request.form.get(f'cost_{prod}', 0))
            term_str = request.form.get(f'term_{prod}', '12')
            
            if term_str == 'other':
                term = float(request.form.get(f'term_custom_{prod}', 12))
            else:
                term = float(term_str)
            
            user_costs[prod] = {'cost': cost, 'term': term}
        except ValueError:
            user_costs[prod] = {'cost': 0, 'term': 12}

    # 3. AI & Math
    tavily_context = get_tavily_context(client_name, request.form.get('client_url'), industry)
    ai_content = generate_tailored_content(client_name, industry, project_type, tavily_context, problem_statement, selected_products, mode)
    
    roi_data, total_inv, total_save = calculate_roi(ai_content, user_costs)

    # 4. PDF Generation
    pdf = ProReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Executive Summary
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
    pdf.set_fill_color(240, 248, 255)
    y = pdf.get_y()
    pdf.rect(10, y, 60, 25, 'F')
    pdf.set_xy(10, y+5)
    pdf.set_font(FONT_FAMILY, 'B', 14)
    pdf.cell(60, 5, f"${total_save:,.0f}", align='C', ln=1)
    pdf.set_font(FONT_FAMILY, '', 8)
    pdf.cell(60, 5, "Total Projected Value", align='C')
    
    pdf.set_xy(75, y)
    pdf.rect(75, y, 60, 25, 'F')
    pdf.set_xy(75, y+5)
    pdf.set_font(FONT_FAMILY, 'B', 14)
    pdf.cell(60, 5, f"${total_inv:,.0f}", align='C', ln=1)
    pdf.set_font(FONT_FAMILY, '', 8)
    pdf.cell(60, 5, "Total Investment", align='C')
    
    pdf.set_xy(140, y)
    pdf.rect(140, y, 60, 25, 'F')
    pdf.set_xy(140, y+5)
    pdf.set_font(FONT_FAMILY, 'B', 14)
    roi_pct = ((total_save - total_inv)/total_inv)*100 if total_inv > 0 else 0
    pdf.cell(60, 5, f"{roi_pct:.0f}%", align='C', ln=1)
    pdf.set_font(FONT_FAMILY, '', 8)
    pdf.cell(60, 5, "Return on Investment", align='C')
    
    pdf.ln(20)

    # Product Pages
    for prod in selected_products:
        if prod not in ai_content: continue
        data = ai_content[prod]
        calc = roi_data.get(prod, {'savings':0, 'investment':0, 'math':{}})
        
        pdf.add_page()
        pdf.chapter_title(f"Analysis: {prod}")
        
        # Strategic Impact
        pdf.set_font(FONT_FAMILY, 'I', 10)
        pdf.multi_cell(0, 5, sanitize_text(data['impact']))
        pdf.ln(5)
        
        # Bullets
        pdf.set_font(FONT_FAMILY, '', 10)
        for bullet in data['bullets']:
            pdf.set_x(15)
            pdf.cell(5, 5, "+", ln=0)
            pdf.multi_cell(170, 5, sanitize_text(bullet))
        pdf.ln(10)
        
        # Math Table
        if 'math_variables' in data and data['math_variables']:
            pdf.draw_math_table(data['math_variables'], calc['savings'], calc['investment'])

    output_path = "generated_roi_report.pdf"
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
