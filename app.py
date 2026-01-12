import os
import io
import json
import re
import logging
from flask import Flask, render_template, request, send_file
from fpdf import FPDF
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from tavily import TavilyClient
import google.generativeai as genai

# --- KNOWLEDGE BASE IMPORT (Ensure knowledge_base.py exists) ---
try:
    from knowledge_base import PRODUCT_DATA
except ImportError:
    # Fallback if file missing
    PRODUCT_DATA = {}

# Set non-GUI backend for Matplotlib
matplotlib.use('Agg')

app = Flask(__name__)

# --- CONFIGURATION ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ACCESS_CODE = os.getenv("ACCESS_CODE", "Hammer2025!")

# Configure Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- STYLING CONSTANTS ---
COLOR_PRIMARY = (15, 23, 42)    # Navy
COLOR_ACCENT = (37, 99, 235)    # Blue
COLOR_TEXT = (51, 65, 85)       # Slate
FONT_FAMILY = 'Helvetica'

# --- 1. ROBUST PARSING ENGINE (The Fix for "Probability" Bug) ---
def extract_currency_value(text_value):
    """
    Forensic Cleaner: Extracts the actual float value from a currency string.
    Handles '$105,000', '$105k', '105,000.00', and returns 105000.0
    Ignores probability text like '25%' unless it is the only number.
    """
    if not text_value:
        return 0.0
    
    # Convert to string if it's not
    clean_text = str(text_value).strip()
    
    # Remove currency symbols and commas
    clean_text = clean_text.replace('$', '').replace(',', '')
    
    # Handle "k/m" suffixes (e.g. "105k")
    multiplier = 1.0
    if clean_text.lower().endswith('k'):
        multiplier = 1000.0
        clean_text = clean_text[:-1]
    elif clean_text.lower().endswith('m'):
        multiplier = 1000000.0
        clean_text = clean_text[:-1]

    try:
        # Regex to find standard float/integer patterns
        # We look for the largest number in the string to avoid picking up "25%" probability
        matches = re.findall(r"[-+]?\d*\.\d+|\d+", clean_text)
        if matches:
            # Convert all matches to floats
            values = [float(m) for m in matches]
            # Heuristic: The currency value is usually the largest number in the "Impact" string
            return max(values) * multiplier
        return 0.0
    except Exception as e:
        print(f"Parsing Error on value '{text_value}': {e}")
        return 0.0

def sanitize_text(text):
    """Sanitizes text for PDF generation (Latin-1 safe)."""
    if not isinstance(text, str): return str(text)
    replacements = {
        '\u2013': '-', '\u2014': '--', '\u2018': "'", '\u2019': "'", 
        '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u00a0': ' ', '\u2022': '*'
    }
    for char, rep in replacements.items(): text = text.replace(char, rep)
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. THE SCOUT & BENCHMARK ENGINE (v1.6 Logic) ---
def get_tavily_context(client_name, client_url, industry):
    """Agent 2: The Researcher. Extracts Revenue & News."""
    if not TAVILY_API_KEY: 
        return "Standard industry challenges.", "Unknown"
    
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        query = f"What is the annual revenue and strategic priorities for {client_name} ({client_url}) in {industry}?"
        response = tavily.search(query=query, search_depth="basic", max_results=3)
        
        context_text = "\n".join([f"- {r['content'][:300]}..." for r in response['results']])
        
        # Simple Revenue Scout Logic
        revenue_size = "Medium" # Default
        if "billion" in context_text.lower():
            revenue_size = "Large"
        elif "million" in context_text.lower():
            revenue_size = "Medium"
        else:
            revenue_size = "Small"
            
        return context_text, revenue_size
    except:
        return "Standard industry operational pressure.", "Medium"

def get_benchmarks(industry, size):
    """
    Truth Table Injection. 
    In v1.6 full version, this comes from benchmarks.py. 
    Here we define a simplified truth table to ensure the Prompt works.
    """
    # Simplified Benchmark Map
    base_rate = 120000 if size == "Large" else 60000
    hourly_rate = 110 if size == "Large" else 75
    
    return f"""
    - Avg Cost of Critical Downtime: ${base_rate}/hour
    - Avg Developer Hourly Rate: ${hourly_rate}/hour
    - Avg Customer LTV: $1,500/year
    - Avg Production Defects/Year: {'50+' if size=='Large' else '10-20'}
    """

# --- 3. THE FORENSIC CFO AGENT (System Prompt Update) ---
def generate_forensic_analysis(client_name, industry, size, context_text, problem_statement, selected_products):
    """
    Generates the ROI analysis using the Skeptical CFO Persona.
    """
    if not GOOGLE_API_KEY:
        # Fallback for no key
        return {}

    benchmark_data_str = get_benchmarks(industry, size)
    
    product_context_str = ""
    for prod in selected_products:
        if prod in PRODUCT_DATA:
            product_context_str += f"\nPRODUCT: {prod}\nDESC: {PRODUCT_DATA[prod].get('tagline','')}\n"

    # --- THE SKEPTICAL CFO PROMPT ---
    cfo_prompt = f"""
    ROLE: You are a skeptical, conservative CFO. Your job is to approve a budget for {client_name}.
    You reject any ROI calculation that looks like "Marketing Fluff."

    CONTEXT:
    Client: {client_name} ({industry})
    Business Size: {size}
    Problem: "{problem_statement}"
    News/Context: {context_text}
    Benchmarks: {benchmark_data_str}
    Products: {product_context_str}

    STRICT CALCULATION RULES (DO NOT VIOLATE):
    1. **The "1% Rule" for Churn:** You NEVER claim that a software tool saves more than 0.5% to 1.0% of a client's total customer base unless the problem statement explicitly mentions "Catastrophic Outages."
       - BAD: "We save 4,500 customers." (Too high).
       - GOOD: "We prevent churn for the 0.5% of customers affected by VDI lag (approx. 150 customers)."

    2. **The "Delta" Principle:** Do not claim the full value of an employee. 
       - BAD: "Saved 5 FTEs = $500k." (Implies firing people).
       - GOOD: "Repurposed 15% of 5 FTEs' time to higher value tasks = $75k efficiency gain."

    3. **Downtime Reality:** Not all downtime costs the full benchmark rate.
       - Only "Total System Outages" cost the full benchmark rate.
       - "Performance Lag" or "Minor Errors" should be calculated at 10% of the benchmark rate.

    TASK:
    For each product, generate a JSON object with 3 distinct value drivers:
    1. "Efficiency" (Labor/Time Savings)
    2. "Risk" (Cost Avoidance)
    3. "Strategic" (Revenue/Churn)
    
    For each driver, provide:
    - "label": A short title (e.g. "Regression Automation")
    - "basis": The math logic text (e.g. "200 hours * $80/hr")
    - "Annual Impact": A CLEAN STRING representing the dollar value (e.g. "$16,000").
    
    Also provide a 2-sentence "impact" summary for the product.

    Output pure JSON: 
    {{ 
      "ProductName": {{ 
         "impact": "...",
         "Efficiency": {{ "label": "...", "basis": "...", "Annual Impact": "$..." }},
         "Risk": {{ "label": "...", "basis": "...", "Annual Impact": "$..." }},
         "Strategic": {{ "label": "...", "basis": "...", "Annual Impact": "$..." }}
      }} 
    }}
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-pro', generation_config={"response_mime_type": "application/json"})
        response = model.generate_content(cfo_prompt)
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini Error: {e}")
        return {}

# --- 4. CALCULATOR (Using Robust Parsing) ---
def calculate_roi_forensic(ai_data, user_costs):
    """
    Sums the 3 drivers using the extract_currency_value helper.
    """
    results = {}
    total_investment = 0
    total_savings = 0

    for prod_name, data in ai_data.items():
        # Get Investment
        costs = user_costs.get(prod_name, {'cost': 0, 'term': 12})
        monthly_cost = costs['cost']
        term_months = costs['term']
        investment = monthly_cost * term_months
        total_investment += investment

        # Calculate Savings (Forensic Summation)
        prod_savings = 0.0
        drivers = []
        
        for category in ['Efficiency', 'Risk', 'Strategic']:
            if category in data:
                raw_val = data[category].get('Annual Impact', '0')
                val = extract_currency_value(raw_val)
                prod_savings += val
                # Store for PDF
                drivers.append({
                    'category': category,
                    'label': data[category].get('label', category),
                    'basis': data[category].get('basis', ''),
                    'impact': val
                })
        
        # Annualize savings if term > 12 months for ROI calc (simplified view)
        # or keep total contract value. Here we usually do Annual Impact.
        # If term is 3 years, investment is 3x, but savings shown is Annual. 
        # Let's align to "Term Savings"
        term_years = max(term_months / 12.0, 1.0)
        term_savings = prod_savings * term_years

        results[prod_name] = {
            "investment": investment,
            "annual_savings": prod_savings,
            "term_savings": term_savings,
            "drivers": drivers,
            "impact_text": data.get('impact', '')
        }
        total_savings += term_savings

    return results, total_investment, total_savings

# --- 5. PDF ENGINE (Dynamic Table) ---
class ForensicReportPDF(FPDF):
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

    def draw_financial_table(self, drivers, annual_savings, investment):
        """Dynamic Table drawing for the 3 drivers"""
        self.set_y(self.get_y() + 5)
        
        # Table Header
        self.set_fill_color(240, 240, 240)
        self.set_font(FONT_FAMILY, 'B', 10)
        self.set_text_color(*COLOR_PRIMARY)
        
        col_1_w = 40  # Value Driver
        col_2_w = 110 # Basis of Calculation
        col_3_w = 35  # Annual Impact
        h = 8
        
        self.cell(col_1_w, h, "Value Driver", 1, 0, 'L', 1)
        self.cell(col_2_w, h, "Basis of Calculation", 1, 0, 'L', 1)
        self.cell(col_3_w, h, "Annual Impact", 1, 1, 'R', 1)
        
        # Rows
        self.set_font(FONT_FAMILY, '', 9)
        self.set_text_color(0, 0, 0)
        
        for d in drivers:
            # We use multi_cell for the Basis column to handle long text
            x_start = self.get_x()
            y_start = self.get_y()
            
            # Draw Col 1 (Label)
            self.cell(col_1_w, h*2, sanitize_text(d['label']), 1, 0, 'L')
            
            # Draw Col 2 (Basis) - Complex handling
            # We save position, write text, check height
            curr_x = self.get_x()
            curr_y = self.get_y()
            self.multi_cell(col_2_w, h, sanitize_text(d['basis']), 1, 'L')
            
            # Move back to top right of Col 2 for Col 3
            self.set_xy(curr_x + col_2_w, y_start)
            
            # Draw Col 3 (Impact)
            self.cell(col_3_w, h*2, f"${d['impact']:,.0f}", 1, 1, 'R')
            
            # Reset Y for next row (ensure we are below the multi_cell)
            self.set_y(y_start + (h*2))

        # Totals Row
        self.ln(2)
        self.set_font(FONT_FAMILY, 'B', 10)
        self.set_x(10 + col_1_w + col_2_w) # Align with Impact column
        self.cell(col_3_w, h, f"Total Benefits: ${annual_savings:,.0f}", 0, 1, 'R')
        
        self.set_x(10 + col_1_w + col_2_w)
        self.set_text_color(185, 28, 28) # Red for cost
        self.cell(col_3_w, h, f"Less Investment: (${investment:,.0f})", 0, 1, 'R')
        
        self.set_x(10 + col_1_w + col_2_w)
        self.set_text_color(22, 163, 74) # Green for Net
        net_val = annual_savings - investment
        self.cell(col_3_w, h, f"NET VALUE: ${net_val:,.0f}", 'T', 1, 'R')
        self.ln(10)

# --- CHART GENERATOR ---
def create_payback_chart(investment, annual_savings):
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(7, 3.5))
    
    months = list(range(13))
    start_val = -1 * abs(investment)
    monthly_gain = annual_savings / 12.0
    
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

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', products=PRODUCT_DATA.keys())

@app.route('/generate', methods=['POST'])
def generate_pdf():
    if request.form.get('access_code') != ACCESS_CODE: return "Invalid Access Code", 403
    
    client_name = sanitize_text(request.form.get('client_name'))
    industry = sanitize_text(request.form.get('industry'))
    problem_statement = sanitize_text(request.form.get('problem_statement'))
    client_url = request.form.get('client_url', '')
    selected_products = request.form.getlist('products')

    # Parse User Costs
    user_costs = {}
    for prod in selected_products:
        try:
            cost = float(request.form.get(f'cost_{prod}', 0))
            term_str = request.form.get(f'term_{prod}', '12')
            term = float(request.form.get(f'term_custom_{prod}', 12)) if term_str == 'other' else float(term_str)
            user_costs[prod] = {'cost': cost, 'term': term}
        except:
            user_costs[prod] = {'cost': 0, 'term': 12}

    # 1. SCOUT
    context_text, business_size = get_tavily_context(client_name, client_url, industry)
    
    # 2. FORENSIC CFO
    ai_content = generate_forensic_analysis(client_name, industry, business_size, context_text, problem_statement, selected_products)

    # 3. CALCULATE
    roi_data, total_inv, total_save = calculate_roi_forensic(ai_content, user_costs)

    # 4. PUBLISH PDF
    pdf = ForensicReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Page 1: Executive Summary
    pdf.add_page()
    pdf.ln(5)
    pdf.set_font(FONT_FAMILY, 'B', 20)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(0, 10, f"Strategic ROI Analysis: {client_name}", ln=True)
    pdf.set_font(FONT_FAMILY, '', 12)
    pdf.set_text_color(*COLOR_TEXT)
    pdf.multi_cell(0, 6, f"Focus: {problem_statement[:200]}...", align='L')
    pdf.ln(10)

    # Scorecards
    y_start = pdf.get_y()
    card_w, card_h = 60, 25
    roi_pct = ((total_save - total_inv)/total_inv)*100 if total_inv > 0 else 0
    
    pdf.card_box("PROJECTED SAVINGS", f"${total_save:,.0f}", "Total Value Created", 10, y_start, card_w, card_h)
    pdf.card_box("TOTAL INVESTMENT", f"${total_inv:,.0f}", "Software & Services", 75, y_start, card_w, card_h)
    pdf.card_box("ROI %", f"{roi_pct:.0f}%", "Return on Investment", 140, y_start, card_w, card_h)

    # Chart
    pdf.set_y(y_start + card_h + 15)
    chart_img = create_payback_chart(total_inv, total_save/3) # Chart assumes 3 year term for visualization
    pdf.image(chart_img, x=10, w=180)

    # Product Pages
    for prod in selected_products:
        if prod not in ai_content: continue
        
        calc_data = roi_data.get(prod, {})
        drivers = calc_data.get('drivers', [])
        
        pdf.add_page()
        pdf.chapter_title(f"Analysis: {prod}")

        pdf.set_font(FONT_FAMILY, 'I', 10)
        pdf.set_text_color(50,50,50)
        pdf.multi_cell(0, 5, sanitize_text(calc_data.get('impact_text', '')))
        pdf.ln(5)

        # Bullet Points (from drivers)
        pdf.set_font(FONT_FAMILY, '', 10)
        pdf.set_text_color(*COLOR_TEXT)
        for d in drivers:
            pdf.set_x(15)
            pdf.cell(5, 5, "+", ln=0)
            pdf.multi_cell(170, 5, sanitize_text(f"{d['label']}: {d['basis']}"))
        
        pdf.ln(5)
        
        # New Dynamic Table
        investment = calc_data.get('investment', 0)
        # We assume "Annual Savings" for the table view
        annual_save = calc_data.get('annual_savings', 0)
        
        pdf.draw_financial_table(drivers, annual_save, investment)

    output_path = "generated_roi_report.pdf"
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
