import os
import io
from flask import Flask, render_template, request, send_file
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib
from tavily import TavilyClient
from openai import OpenAI
from knowledge_base import PRODUCT_DATA

# Set non-GUI backend for Matplotlib
matplotlib.use('Agg')

app = Flask(__name__)

# --- CONFIGURATION ---
# Get API Keys from Environment Variables (Set these in Render Dashboard)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ACCESS_CODE = os.getenv("ACCESS_CODE", "Hammer2025!") # Default password if not set

# --- AI & RESEARCH HELPERS ---
def get_ai_context(client_name, industry, user_project_type):
    """
    1. Uses Tavily to get recent news/challenges for the industry.
    2. Uses OpenAI to deduce the 'Project Type' if the user left it blank.
    """
    insights = []
    project_type = user_project_type

    # 1. Tavily Research
    if TAVILY_API_KEY:
        try:
            tavily = TavilyClient(api_key=TAVILY_API_KEY)
            query = f"Top 3 strategic challenges for {client_name} in {industry} contact centers 2025"
            response = tavily.search(query=query, search_depth="basic", max_results=3)
            insights = [result['content'][:150] + "..." for result in response['results']]
        except Exception as e:
            print(f"Tavily Error: {e}")
            insights = [f"Increasing operational efficiency in {industry}", "Reducing customer churn", "Migrating legacy systems to cloud"]
    else:
        insights = [f"Standard {industry} efficiency drivers", "Cost reduction initiatives", "Customer Experience (CX) optimization"]

    # 2. OpenAI Deduction (Only if Project Type is blank)
    if not project_type and OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            prompt = f"Based on the company '{client_name}' in the '{industry}' sector, what is the most likely IT focus area: 'Migration', 'DevOps', 'Operations', or 'CX'? Reply with just the one word."
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            project_type = completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI Error: {e}")
            project_type = "Operations" # Fallback
    elif not project_type:
        project_type = "Operations" # Fallback if no API key and no input

    return insights, project_type

# --- CHART GENERATION ---
def create_payback_chart(one_time_cost, recurring_cost):
    """Generates the Executive Summary Cumulative Cash Flow chart."""
    plt.figure(figsize=(6, 3))
    months = list(range(13))
    
    # Simple Mock Math: Assume savings cover costs by month 7
    # Start at negative (One-time cost)
    start_val = -1 * abs(float(one_time_cost or 50000))
    # Monthly gain (Savings - Monthly Subscription cost)
    monthly_gain = (abs(float(start_val)) * 2) / 12 
    
    cash_flow = []
    current = start_val
    for m in months:
        cash_flow.append(current)
        current += monthly_gain

    plt.plot(months, cash_flow, color='#2563eb', linewidth=3, marker='o')
    plt.axhline(0, color='black', linewidth=1, linestyle='--')
    plt.title("Cumulative Cash Flow (Year 1)", fontsize=10, fontweight='bold')
    plt.xlabel("Months", fontsize=8)
    plt.ylabel("Net Value ($)", fontsize=8)
    plt.grid(True, linestyle=':', alpha=0.6)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buf.seek(0)
    return buf

# --- PDF GENERATOR ---
class ROIReportPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'CONFIDENTIAL - ROI ANALYSIS', align='R', ln=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 51, 102) 
        self.cell(0, 10, title, ln=True, align='L')
        self.set_draw_color(0, 51, 102)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(10)

    def chapter_body(self, text):
        self.set_font('Helvetica', '', 11)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 6, text)
        self.ln()

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
    
    # Pricing Inputs
    try:
        one_time_cost = float(request.form.get('one_time_cost', 0))
        recurring_cost = float(request.form.get('recurring_cost', 0))
    except ValueError:
        one_time_cost = 0
        recurring_cost = 0

    # 2. Get Context (AI + Tavily)
    insights, project_type = get_ai_context(client_name, industry, input_project_type)
    
    # 3. Initialize PDF
    pdf = ROIReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- PAGE 1: Executive Snapshot ---
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 24)
    pdf.cell(0, 20, f"Strategic ROI Analysis for {client_name}", ln=True, align='C')
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 10, f"Prepared for the {industry} Sector | Focus: {project_type}", ln=True, align='C')
    pdf.ln(10)
    
    # Mock Calculations based on Pricing
    savings = (recurring_cost * 2.5) + (one_time_cost * 1.5) # Fake logic for demo
    roi_percent = ((savings - (one_time_cost + recurring_cost)) / (one_time_cost + recurring_cost)) * 100 if (one_time_cost + recurring_cost) > 0 else 0
    
    # Scorecards
    y_start = pdf.get_y()
    
    # Savings Box
    pdf.set_fill_color(240, 248, 255)
    pdf.rect(10, y_start, 60, 30, 'DF')
    pdf.set_xy(10, y_start + 5)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(60, 10, f"${savings:,.0f}", align='C', ln=True)
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(60, 5, "Proj. 3-Year Savings", align='C')
    
    # Payback Box
    pdf.set_xy(75, y_start) 
    pdf.rect(75, y_start, 60, 30, 'DF')
    pdf.set_xy(75, y_start + 5)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(60, 10, "6-8 Months", align='C', ln=True)
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(60, 5, "Est. Payback Period", align='C')

    # ROI Box (Only show if pricing was entered)
    pdf.set_xy(140, y_start)
    pdf.rect(140, y_start, 60, 30, 'DF')
    pdf.set_xy(140, y_start + 5)
    pdf.set_font('Helvetica', 'B', 14)
    if one_time_cost > 0:
        pdf.cell(60, 10, f"{roi_percent:.0f}%", align='C', ln=True)
    else:
        pdf.cell(60, 10, "N/A", align='C', ln=True)
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(60, 5, "ROI Percentage", align='C')
    
    pdf.set_xy(10, y_start + 40)
    
    # Insert Payback Chart
    chart_img = create_payback_chart(one_time_cost, recurring_cost)
    pdf.image(chart_img, x=25, w=160)

    # --- PAGE 2: The Before State ---
    pdf.add_page()
    pdf.chapter_title("2. The 'Before' State: Cost of Inaction")
    
    pdf.chapter_body(f"Industry Context for {industry}:")
    pdf.set_font('Helvetica', 'I', 10)
    for insight in insights:
        pdf.cell(0, 8, f"- {insight}", ln=True)
    pdf.ln(5)

    # --- PAGE 3: Hard ROI ---
    pdf.add_page()
    pdf.chapter_title("3. Hard ROI: Direct Financial Impact")
    
    pdf.set_font('Helvetica', '', 10)
    for prod in selected_products:
        if prod in PRODUCT_DATA:
            data = PRODUCT_DATA[prod]
            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 8, f"{prod} Impact:", ln=True)
            pdf.set_font('Helvetica', '', 10)
            for point in data['hard_roi']:
                pdf.cell(10) 
                pdf.cell(0, 6, f"- {point}", ln=True)
            pdf.ln(3)

    # --- PAGE 4: Soft ROI ---
    pdf.add_page()
    pdf.chapter_title("4. Soft ROI: Productivity & Intangibles")
    
    for prod in selected_products:
        if prod in PRODUCT_DATA:
            data = PRODUCT_DATA[prod]
            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 8, f"{prod} Efficiency Gains:", ln=True)
            pdf.set_font('Helvetica', '', 10)
            for point in data['soft_roi']:
                pdf.cell(10) 
                pdf.cell(0, 6, f"- {point}", ln=True)
            pdf.ln(3)

    # --- PAGE 5: Investment ---
    pdf.add_page()
    pdf.chapter_title("5. Investment Overview")
    
    pdf.chapter_body("The following investment estimates were used to calculate the ROI scenarios.")
    pdf.ln(5)
    
    # Investment Table
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(100, 10, "Cost Category", 1, 0, 'L', 1)
    pdf.cell(50, 10, "Estimated Amount", 1, 1, 'R', 1)
    
    pdf.cell(100, 10, "One-Time Implementation & Training", 1, 0, 'L')
    pdf.cell(50, 10, f"${one_time_cost:,.2f}", 1, 1, 'R')
    
    pdf.cell(100, 10, "Annual Subscription (Recurring)", 1, 0, 'L')
    pdf.cell(50, 10, f"${recurring_cost:,.2f}", 1, 1, 'R')
    
    pdf.ln(20)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 10, "BUDGETARY ESTIMATE ONLY", align='C', ln=True)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 6, "These figures are for ROI modeling purposes only. Please refer to the official Quote document for binding pricing, terms, and conditions.", align='C')

    # Output
    output_path = "generated_roi_report.pdf"
    pdf.output(output_path)
    
    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    # Use PORT env variable for Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
