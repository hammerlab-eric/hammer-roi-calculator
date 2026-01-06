import os
import io
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

# --- AI & RESEARCH HELPERS ---
def get_ai_context(client_name, industry, user_project_type):
    insights = []
    project_type = user_project_type

    # 1. Tavily Research
    if TAVILY_API_KEY:
        try:
            tavily = TavilyClient(api_key=TAVILY_API_KEY)
            query = f"Top 3 strategic challenges for {client_name} in {industry} contact centers 2025"
            response = tavily.search(query=query, search_depth="basic", max_results=3)
            insights = [result['content'][:150] + "..." for result in response['results']]
        except Exception:
            insights = [f"Increasing operational efficiency in {industry}", "Reducing customer churn", "Migrating legacy systems to cloud"]
    else:
        insights = [f"Standard {industry} efficiency drivers", "Cost reduction initiatives", "Customer Experience (CX) optimization"]

    # 2. OpenAI Deduction
    if not project_type and OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            prompt = f"Based on the company '{client_name}' in the '{industry}' sector, what is the most likely IT focus area: 'Migration', 'DevOps', 'Operations', or 'CX'? Reply with just the one word."
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            project_type = completion.choices[0].message.content.strip()
        except Exception:
            project_type = "Operations"
    elif not project_type:
        project_type = "Operations"

    return insights, project_type

# --- PRO CHART GENERATION ---
def create_payback_chart(one_time_cost, recurring_cost):
    """Generates a clean, professional cumulative cash flow chart."""
    plt.style.use('seaborn-v0_8-whitegrid') # Cleaner look
    fig, ax = plt.subplots(figsize=(7, 3.5))
    
    months = list(range(13))
    # Logic: Start negative, gain savings monthly
    start_val = -1 * abs(float(one_time_cost or 50000))
    # Assume 2.5x ROI factor for the curve
    monthly_gain = (recurring_cost * 2.5) / 12 if recurring_cost > 0 else 5000
    
    cash_flow = []
    current = start_val
    for m in months:
        cash_flow.append(current)
        current += monthly_gain

    # Plot Line
    ax.plot(months, cash_flow, color='#2563EB', linewidth=3, marker='o', markersize=6)
    
    # Plot Zero Line
    ax.axhline(0, color='#64748B', linewidth=1.5, linestyle='--')
    
    # Styling
    ax.set_title("Cumulative Cash Flow (Year 1)", fontsize=12, fontweight='bold', pad=15, color='#0F172A')
    ax.set_xlabel("Months Post-Deployment", fontsize=9, color='#475569')
    ax.set_ylabel("Net Value ($)", fontsize=9, color='#475569')
    
    # Format Y-axis as Currency
    fmt = '${x:,.0f}'
    tick = mtick.StrMethodFormatter(fmt)
    ax.yaxis.set_major_formatter(tick)
    
    # Remove top/right spines for modern look
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
        # Professional Header Bar
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(0, 0, 210, 20, 'F') # Top bar
        
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
        self.cell(0, 8, title, ln=True, align='L')
        # Underline
        self.set_draw_color(*COLOR_ACCENT)
        self.set_line_width(0.5)
        self.line(10, self.get_y()+2, 200, self.get_y()+2)
        self.ln(10)

    def card_box(self, label, value, subtext, x, y, w, h):
        """Draws a shaded metric card"""
        self.set_xy(x, y)
        self.set_fill_color(248, 250, 252) # Very light slate
        self.set_draw_color(226, 232, 240) # Light border
        self.rect(x, y, w, h, 'DF')
        
        # Value (Big)
        self.set_xy(x, y + 5)
        self.set_font(FONT_FAMILY, 'B', 14)
        self.set_text_color(*COLOR_ACCENT)
        self.cell(w, 10, value, align='C', ln=1)
        
        # Label (Small)
        self.set_xy(x, y + 16)
        self.set_font(FONT_FAMILY, 'B', 9)
        self.set_text_color(*COLOR_TEXT)
        self.cell(w, 5, label, align='C', ln=1)
        
        # Subtext (Tiny)
        self.set_xy(x, y + 22)
        self.set_font(FONT_FAMILY, '', 7)
        self.set_text_color(100, 116, 139)
        self.cell(w, 5, subtext, align='C')

    def section_text(self, text, style=''):
        self.set_font(FONT_FAMILY, style, 10)
        self.set_text_color(*COLOR_TEXT)
        self.multi_cell(0, 5, text)
        self.ln(2)

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html', products=PRODUCT_DATA.keys())

@app.route('/generate', methods=['POST'])
def generate_pdf():
    # 0. Security Check
    user_code = request.form.get('access_code')
    if user_code != ACCESS_CODE:
        return "Invalid Access Code", 403

    # 1. Gather Inputs
    client_name = request.form.get('client_name')
    industry = request.form.get('industry')
    input_project_type = request.form.get('project_type')
    selected_products = request.form.getlist('products')
    
    try:
        one_time_cost = float(request.form.get('one_time_cost', 0))
        recurring_cost = float(request.form.get('recurring_cost', 0))
    except ValueError:
        one_time_cost = 0
        recurring_cost = 0

    # 2. Context
    insights, project_type = get_ai_context(client_name, industry, input_project_type)
    
    # 3. PDF Init
    pdf = ProReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- PAGE 1: EXECUTIVE SNAPSHOT ---
    pdf.add_page()
    
    # Title Block
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 22)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(0, 10, f"Strategic ROI Analysis for {client_name}", ln=True, align='L')
    
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(*COLOR_TEXT)
    pdf.cell(0, 8, f"Sector: {industry} | Initiative: {project_type}", ln=True, align='L')
    pdf.ln(10)
    
    # Math (Mocked)
    savings = (recurring_cost * 2.5) + (one_time_cost * 1.5)
    roi_percent = ((savings - (one_time_cost + recurring_cost)) / (one_time_cost + recurring_cost)) * 100 if (one_time_cost + recurring_cost) > 0 else 0
    
    # Scorecards Row
    y_start = pdf.get_y()
    card_w = 60
    card_h = 30
    gap = 5
    
    pdf.card_box("TOTAL PROJECTED SAVINGS", f"${savings:,.0f}", "Year 1 & Year 3 Combined", 10, y_start, card_w, card_h)
    pdf.card_box("PAYBACK PERIOD", "6.5 Months", "Break-even Point", 10 + card_w + gap, y_start, card_w, card_h)
    
    roi_text = f"{roi_percent:.0f}%" if one_time_cost > 0 else "N/A"
    pdf.card_box("RETURN ON INVESTMENT", roi_text, "Net Profit / Cost", 10 + (card_w + gap)*2, y_start, card_w, card_h)
    
    pdf.set_y(y_start + card_h + 15)
    
    # Chart Area
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, "Financial Projection (Year 1)", ln=True)
    chart_img = create_payback_chart(one_time_cost, recurring_cost)
    pdf.image(chart_img, x=10, w=180)

    # --- PAGE 2: BUSINESS DRIVERS ---
    pdf.add_page()
    pdf.chapter_title("1. The Cost of Inaction")
    
    pdf.section_text(f"In the current landscape of the {industry} sector, organizations face increasing pressure to modernize. Based on your focus on {project_type}, maintaining the status quo presents specific risks:")
    pdf.ln(5)
    
    # Styled Insights List
    for insight in insights:
        pdf.set_fill_color(*COLOR_LIGHT)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(5) # Indent
        pdf.cell(4, 4, ">", ln=0) # Bullet
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6, insight)
        pdf.ln(2)

    pdf.ln(5)
    pdf.set_fill_color(254, 242, 242) # Light Red for Risk Box
    pdf.set_draw_color(220, 38, 38) # Red Border
    pdf.rect(10, pdf.get_y(), 190, 25, 'DF')
    pdf.set_xy(15, pdf.get_y() + 5)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(185, 28, 28) # Dark Red Text
    pdf.cell(0, 6, "Operational Risk Alert:", ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(180, 5, "Manual processes currently consume an estimated 40% of engineering bandwidth, creating a hidden 'Technical Debt' tax on every new release.")
    pdf.set_text_color(*COLOR_TEXT) # Reset

    # --- PAGE 3: HARD ROI ---
    pdf.add_page()
    pdf.chapter_title("2. Direct Financial Impact")
    
    for prod in selected_products:
        if prod in PRODUCT_DATA:
            data = PRODUCT_DATA[prod]
            # Product Header
            pdf.set_fill_color(240, 248, 255) # Light Blue Row
            pdf.rect(10, pdf.get_y(), 190, 8, 'F')
            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 8, f"  {prod}", ln=True)
            
            # Tagline
            pdf.set_font('Helvetica', 'I', 10)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 6, f"  Strategy: {data.get('tagline', 'Optimization')}", ln=True)
            pdf.set_text_color(*COLOR_TEXT)
            
            # Hard Savings Bullets
            pdf.ln(2)
            pdf.set_font('Helvetica', '', 10)
            for point in data['hard_roi']:
                pdf.cell(5)
                pdf.cell(5, 5, "+", ln=0) # Icon
                pdf.multi_cell(0, 5, point)
            pdf.ln(5)

    # --- PAGE 4: INVESTMENT ---
    pdf.add_page()
    pdf.chapter_title("3. Investment & Returns")
    
    pdf.section_text("The following table outlines the estimated investment required to achieve the projected ROI. These figures are based on the inputs provided.")
    pdf.ln(5)
    
    # Professional Table
    col_width = 95
    row_height = 10
    
    # Header Row
    pdf.set_fill_color(*COLOR_PRIMARY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(col_width, row_height, " Cost Category", 1, 0, 'L', 1)
    pdf.cell(col_width, row_height, " Estimated Amount ($)", 1, 1, 'R', 1)
    
    # Rows
    pdf.set_text_color(*COLOR_TEXT)
    pdf.set_font('Helvetica', '', 11)
    
    # Row 1 (Striped)
    pdf.set_fill_color(241, 245, 249)
    pdf.cell(col_width, row_height, " One-Time Implementation & Training", 1, 0, 'L', 1)
    pdf.cell(col_width, row_height, f" {one_time_cost:,.2f}", 1, 1, 'R', 1)
    
    # Row 2 (White)
    pdf.cell(col_width, row_height, " Annual Subscription (Recurring)", 1, 0, 'L', 0)
    pdf.cell(col_width, row_height, f" {recurring_cost:,.2f}", 1, 1, 'R', 0)
    
    pdf.ln(20)
    
    # Disclaimer
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "DISCLAIMER: BUDGETARY ESTIMATES ONLY", ln=True, align='C')
    pdf.set_font('Helvetica', '', 8)
    pdf.multi_cell(0, 4, "The figures presented in this report are for simulation and modeling purposes only. They do not constitute a binding offer, quote, or contract. Please refer to the official Order Form for final pricing, terms, and conditions.", align='C')

    # Output
    output_path = "generated_roi_report.pdf"
    pdf.output(output_path)
    
    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
