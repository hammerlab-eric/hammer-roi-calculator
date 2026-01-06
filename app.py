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

# Set non-GUI backend for Matplotlib
import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)

# --- CONFIGURATION ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ACCESS_CODE = os.getenv("ACCESS_CODE", "Hammer2025!") 

# --- STYLING CONSTANTS ---
COLOR_PRIMARY = (15, 23, 42)    # Navy Slate
COLOR_ACCENT = (37, 99, 235)    # Bright Blue
COLOR_TEXT = (51, 65, 85)       # Slate 700
COLOR_LIGHT = (241, 245, 249)   # Slate 100
FONT_FAMILY = 'Helvetica'

# --- TEXT SANITIZER ---
def sanitize_text(text):
    """
    Replaces incompatible Unicode characters with Latin-1 safe equivalents.
    """
    if not isinstance(text, str):
        return str(text)
    
    replacements = {
        '\u2013': '-',   # En-dash
        '\u2014': '--',  # Em-dash
        '\u2018': "'",   # Left single quote
        '\u2019': "'",   # Right single quote
        '\u201c': '"',   # Left double quote
        '\u201d': '"',   # Right double quote
        '\u2026': '...', # Ellipsis
        '\u00a0': ' ',   # Non-breaking space
        '\u2022': '*'    # Bullet point
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
        
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- AI ENGINE ---
def get_tavily_context(client_name, client_url, industry):
    if not TAVILY_API_KEY:
        return f"Standard {industry} challenges apply."

    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        query = f"What are the top strategic priorities and recent news for {client_name} ({client_url}) in {industry} 2024-2025?"
        response = tavily.search(query=query, search_depth="basic", max_results=3)
        
        context_text = ""
        for result in response['results']:
            context_text += f"- {result['content'][:200]}...\n"
        return context_text
    except Exception as e:
        print(f"Tavily Error: {e}")
        return f"Could not fetch live data. Assuming standard {industry} operational pressure."

def generate_tailored_content(client_name, industry, project_type, context_text, problem_statement, selected_products):
    if not OPENAI_API_KEY:
        return {prod: {"impact": PRODUCT_DATA[prod]['soft_roi'][0], "bullets": PRODUCT_DATA[prod]['hard_roi']} for prod in selected_products if prod in PRODUCT_DATA}

    client = OpenAI(api_key=OPENAI_API_KEY)
    
    product_context_str = ""
    for prod in selected_products:
        if prod in PRODUCT_DATA:
            p_data = PRODUCT_DATA[prod]
            product_context_str += f"\nPRODUCT: {prod}\nWHAT IT DOES: {p_data['tagline']}\nKEY SPECS: {', '.join(p_data['hard_roi'])}\n"

    system_prompt = "You are a Senior Solutions Engineer writing a business case."
    user_prompt = f"""
    CLIENT: {client_name}
    INDUSTRY: {industry}
    FOCUS: {project_type}
    
    *** CRITICAL INPUT - SPECIFIC CLIENT PAIN POINT ***:
    "{problem_statement}"

    CLIENT NEWS/CONTEXT:
    {context_text}

    OUR PRODUCTS:
    {product_context_str}

    TASK:
    For each product listed above, write a JSON object with two fields:
    1. "impact": A 2-sentence "Strategic Impact" statement. Connect the user's specific pain point (Problem Statement) and the client news to the product capability.
    2. "bullets": A list of 3 "Hard Savings" bullet points. Rewrite the product specs to sound like a direct solution to the user's Problem Statement.

    Output pure JSON format: {{ "ProductName": {{ "impact": "...", "bullets": ["...", "...", "..."] }} }}
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return {prod: {"impact": PRODUCT_DATA[prod]['soft_roi'][0], "bullets": PRODUCT_DATA[prod]['hard_roi']} for prod in selected_products if prod in PRODUCT_DATA}

# --- PRO CHART GENERATION ---
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
    ax.set_xlabel("Months Post-Deployment", fontsize=9, color='#475569')
    ax.set_ylabel("Net Value ($)", fontsize=9, color='#475569')
    
    fmt = '${x:,.0f}'
    tick = mtick.StrMethodFormatter(fmt)
    ax.yaxis.set_major_formatter(tick)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle=':', alpha=0.6)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close()
    buf.seek(0)
    return buf

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
        self.cell(0, 10, f'Page {self.page_no()} | Generated for Internal Use Only', align='C')

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

    def section_text(self, text, style=''):
        self.set_font(FONT_FAMILY, style, 10)
        self.set_text_color(*COLOR_TEXT)
        self.multi_cell(0, 5, sanitize_text(text))
        self.ln(2)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', products=PRODUCT_DATA.keys())

@app.route('/generate', methods=['POST'])
def generate_pdf():
    # 0. Security
    user_code = request.form.get('access_code')
    if user_code != ACCESS_CODE:
        return "Invalid Access Code", 403

    # 1. Inputs
    client_name = sanitize_text(request.form.get('client_name'))
    client_url = request.form.get('client_url')
    industry = sanitize_text(request.form.get('industry'))
    project_type = sanitize_text(request.form.get('project_type') or "Operational Efficiency")
    problem_statement = sanitize_text(request.form.get('problem_statement') or "General efficiency improvements")
    selected_products = request.form.getlist('products')
    
    try:
        one_time_cost = float(request.form.get('one_time_cost', 0))
        recurring_cost = float(request.form.get('recurring_cost', 0))
    except ValueError:
        one_time_cost = 0
        recurring_cost = 0

    # 2. AI Intelligence Layer
    tavily_raw = get_tavily_context(client_name, client_url, industry)
    tavily_context = sanitize_text(tavily_raw)
    
    ai_product_content = generate_tailored_content(client_name, industry, project_type, tavily_context, problem_statement, selected_products)

    # 3. PDF Construction
    pdf = ProReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # PAGE 1: EXECUTIVE
    pdf.add_page()
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 22)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(0, 10, f"Strategic ROI Analysis for {client_name}", ln=True, align='L')
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(*COLOR_TEXT)
    pdf.cell(0, 8, f"Sector: {industry} | Focus: {project_type}", ln=True, align='L')
    pdf.ln(10)
    
    savings = (recurring_cost * 2.5) + (one_time_cost * 1.5)
    roi_percent = ((savings - (one_time_cost + recurring_cost)) / (one_time_cost + recurring_cost)) * 100 if (one_time_cost + recurring_cost) > 0 else 0
    
    y_start = pdf.get_y()
    card_w = 60
    card_h = 30
    gap = 5
    pdf.card_box("PROJECTED SAVINGS", f"${savings:,.0f}", "3-Year Horizon", 10, y_start, card_w, card_h)
    pdf.card_box("PAYBACK PERIOD", "6.5 Months", "Break-even Point", 10 + card_w + gap, y_start, card_w, card_h)
    roi_text = f"{roi_percent:.0f}%" if one_time_cost > 0 else "N/A"
    pdf.card_box("RETURN ON INVESTMENT", roi_text, "Net Profit / Cost", 10 + (card_w + gap)*2, y_start, card_w, card_h)
    
    pdf.set_y(y_start + card_h + 15)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(0, 10, "Financial Projection (Year 1)", ln=True)
    chart_img = create_payback_chart(one_time_cost, recurring_cost)
    pdf.image(chart_img, x=10, w=180)

    # PAGE 2: CONTEXT & PROBLEM
    pdf.add_page()
    pdf.chapter_title("1. Strategic Context & Risks")
    
    pdf.set_fill_color(254, 242, 242)
    pdf.rect(10, pdf.get_y(), 190, 20, 'F')
    pdf.set_xy(15, pdf.get_y() + 5)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(185, 28, 28)
    pdf.cell(0, 5, "Defined Problem Statement:", ln=True)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(180, 5, problem_statement)
    pdf.ln(10)

    pdf.section_text(f"Our research into {client_name}'s current environment and the broader {industry} landscape highlights several key drivers:")
    pdf.ln(5)
    
    pdf.set_fill_color(*COLOR_LIGHT)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.set_text_color(*COLOR_TEXT)
    pdf.multi_cell(0, 6, tavily_context)
    pdf.ln(10)

    # PAGE 3: TAILORED IMPACT
    pdf.add_page()
    pdf.chapter_title("2. Solution Impact Analysis")
    
    for prod in selected_products:
        if prod in ai_product_content:
            content = ai_product_content[prod]
            
            pdf.set_fill_color(240, 248, 255)
            pdf.rect(10, pdf.get_y(), 190, 8, 'F')
            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 8, f"  {prod}", ln=True)
            
            pdf.ln(2)
            pdf.set_font('Helvetica', 'I', 10)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(0, 5, sanitize_text(content['impact']))
            pdf.ln(3)
            
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(*COLOR_TEXT)
            
            # --- FIXED BULLET SECTION ---
            for bullet in content['bullets']:
                # Save cursor position
                current_y = pdf.get_y()
                # Indent 5mm
                pdf.set_x(15) 
                # Print Bullet
                pdf.cell(5, 5, "+", ln=0)
                # Print Text with EXPLICIT WIDTH (170mm) to prevent overflow error
                pdf.multi_cell(170, 5, sanitize_text(bullet))
            # ---------------------------
            pdf.ln(5)

    # PAGE 4: INVESTMENT
    pdf.add_page()
    pdf.chapter_title("3. Investment Summary")
    pdf.section_text("Budgetary estimates for Year 1 implementation and recurring services.")
    pdf.ln(5)
    
    col_width = 95
    row_height = 10
    pdf.set_fill_color(*COLOR_PRIMARY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(col_width, row_height, " Cost Category", 1, 0, 'L', 1)
    pdf.cell(col_width, row_height, " Estimated Amount ($)", 1, 1, 'R', 1)
    
    pdf.set_text_color(*COLOR_TEXT)
    pdf.set_font('Helvetica', '', 11)
    pdf.set_fill_color(241, 245, 249)
    pdf.cell(col_width, row_height, " One-Time Implementation & Training", 1, 0, 'L', 1)
    pdf.cell(col_width, row_height, f" {one_time_cost:,.2f}", 1, 1, 'R', 1)
    pdf.cell(col_width, row_height, " Annual Subscription (Recurring)", 1, 0, 'L', 0)
    pdf.cell(col_width, row_height, f" {recurring_cost:,.2f}", 1, 1, 'R', 0)
    
    pdf.ln(20)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "DISCLAIMER: BUDGETARY ESTIMATES ONLY", ln=True, align='C')

    output_path = "generated_roi_report.pdf"
    pdf.output(output_path)
    
    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
