import os
import json
import smtplib
from email.message import EmailMessage
from fpdf import FPDF

# --- SAFE IMPORT BLOCK ---
try:
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate
    from tavily import TavilyClient
    print("✅ Libraries imported successfully.")
except ImportError as e:
    print(f"❌ CRITICAL IMPORT ERROR: {e}")
    print("Ensure requirements.txt contains: langchain-openai, tavily-python, langchain")
    exit(1)

# --- CONFIGURATION ---
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SMTP_SERVER = "smtp.zoho.com"
SMTP_PORT = 465
SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

# --- 1. THE RESEARCH AGENT (Tavily) ---
def research_company(company_url, company_name):
    print(f"\n🕵️  STEP 1: Researching {company_name}...")
    
    if not TAVILY_API_KEY:
        print("⚠️  Warning: TAVILY_API_KEY missing. Skipping live research.")
        return []

    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        query = f"""
        Research '{company_name}' ({company_url}). Find:
        1. Primary Industry/Vertical.
        2. Estimated Annual Revenue.
        3. Contact Center Technology Stack (Genesys, Avaya, Cisco, AWS).
        4. Any recent public technical failures or customer complaints.
        """
        # Using "basic" depth for speed/stability
        context = tavily.search(query=query, search_depth="basic") 
        results = context.get('results', [])
        print(f"✅ Research complete. Found {len(results)} sources.")
        return results
    except Exception as e:
        print(f"❌ Research Failed: {e}")
        return []

# --- 2. THE SYNTHESIS AGENT (LangChain) ---
def generate_roi_data(research_data, user_spend, playbook):
    print("\n🧠 STEP 2: Synthesizing Business Case...")
    
    try:
        llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, api_key=OPENAI_API_KEY)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Senior Solutions Consultant for Hammer. You map client risks to Hammer solutions using internal playbooks."),
            ("user", """
            CONTEXT DATA:
            Research Findings: {research_data}
            Internal Playbook: {playbook}
            User Monthly Spend: ${user_spend} (If 0, estimate based on revenue found in research)

            TASK:
            1. Determine the Client's Vertical (Map to Playbook keys: Retail, Finance, Healthcare, Technology, or General).
            2. Select the matching 'avg_downtime_cost_per_min'.
            3. Calculate 'Risk Exposure' = (Avg_Cost * 60 mins * 12 months * 0.01 probability).
            4. Write a 3-sentence 'Executive Summary' referencing their specific tech stack or industry risks.
            5. Select a 'Hammer Product' recommendation.

            OUTPUT JSON FORMAT (Do not include markdown ```json tags):
            {{
                "vertical": "String",
                "detected_stack": "String",
                "risk_exposure_annual": 0.00,
                "executive_summary": "String",
                "hammer_product_recommendation": "String"
            }}
            """)
        ])
        
        chain = prompt | llm
        response = chain.invoke({
            "research_data": str(research_data), 
            "playbook": json.dumps(playbook),
            "user_spend": str(user_spend)
        })
        
        # Clean response if LLM adds markdown tags
        clean_content = response.content.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_content)
        print("✅ AI Analysis successful.")
        return data

    except Exception as e:
        print(f"❌ AI Synthesis Failed: {e}")
        # FALLBACK DATA so PDF generation doesn't crash
        return {
            "vertical": "General",
            "detected_stack": "Unknown",
            "risk_exposure_annual": 50000,
            "executive_summary": "Automated analysis unavailable. Falling back to general Hammer efficiency metrics.",
            "hammer_product_recommendation": "Hammer End-to-End Monitoring"
        }

# --- 3. PDF GENERATION ---
def create_pdf(data, company_name, filename="Hammer_ROI_Report.pdf"):
    print("\n📄 STEP 3: Generating PDF...")
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("Arial", 'B', size=20)
        pdf.cell(0, 15, txt=f"Hammer ROI Business Case", ln=1, align='C')
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, txt=f"Prepared for: {company_name}", ln=1, align='C')
        pdf.ln(10)

        # 1. Business Profile
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', size=14)
        pdf.cell(0, 10, txt="1. Business Profile Analysis", ln=1, fill=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, txt=f"Detected Vertical: {data.get('vertical', 'General')}", ln=1)
        pdf.cell(0, 8, txt=f"Tech Stack: {data.get('detected_stack', 'Unknown')}", ln=1)
        pdf.ln(5)

        # 2. Risk Section
        pdf.set_font("Arial", 'B', size=14)
        pdf.cell(0, 10, txt="2. Estimated Risk Exposure", ln=1, fill=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, txt=f"Based on industry benchmarks for {data.get('vertical')}, your estimated annual exposure to downtime and efficiency loss is:")
        
        # Risk Value (Formatting protection)
        risk_val = data.get('risk_exposure_annual', 0)
        try:
            risk_str = f"${float(risk_val):,.2f}"
        except:
            risk_str = "$50,000.00 (Est)"

        pdf.set_font("Arial", 'B', size=16)
        pdf.set_text_color(200, 0, 0) # Red
        pdf.cell(0, 15, txt=f"{risk_str} / Year", ln=1)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        # 3. Solution Section
        pdf.set_font("Arial", 'B', size=14)
        pdf.cell(0, 10, txt="3. The Hammer Solution", ln=1, fill=True)
        pdf.set_font("Arial", 'B', size=11)
        pdf.cell(0, 8, txt=f"Recommended Module: {data.get('hammer_product_recommendation', 'General')}", ln=1)
        pdf.set_font("Arial", size=11)
        
        summary_text = data.get('executive_summary', 'Analysis pending.')
        # Sanitize text to prevent latin-1 codec errors in FPDF
        summary_text = summary_text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 7, txt=summary_text)
        
        pdf.output(filename)
        print(f"✅ PDF Saved: {filename}")
    except Exception as e:
        print(f"❌ PDF Generation Failed: {e}")
        # Create a dummy PDF so artifact upload doesn't fail
        pdf = FPDF()
        pdf.add_page()
        pdf.cell(0, 10, txt="Error generating report. Please contact support.", ln=1)
        pdf.output(filename)

# --- 4. MAIN EXECUTION ---
if __name__ == "__main__":
    # Load Environment Variables safely
    company_name = os.environ.get("USER_NAME", "Valued Client")
    company_url = os.environ.get("USER_URL", "")
    user_email = os.environ.get("USER_EMAIL")
    cc_email = os.environ.get("CC_EMAIL")
    
    # FIX: Handle empty string inputs for Spend
    raw_spend = os.environ.get("USER_SPEND")
    if raw_spend and raw_spend.strip():
        monthly_spend = raw_spend
    else:
        monthly_spend = "0"

    print(f"--- Starting Hammer ROI V1.2 ---")
    print(f"Target: {company_name} ({company_url})")
    print(f"Spend Input: {monthly_spend}")

    # Load Playbook
    try:
        with open('src/hammer_playbook.json', 'r') as f:
            playbook = json.load(f)
    except FileNotFoundError:
        print("❌ Error: hammer_playbook.json not found. Using empty dict.")
        playbook = {}

    # STEP 1: Research
    research_results = research_company(company_url, company_name)
    
    # STEP 2: Synthesize
    roi_data = generate_roi_data(research_results, monthly_spend, playbook)
    
    # STEP 3: Generate PDF
    create_pdf(roi_data, company_name)
    
    # STEP 4: Email
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("⚠️  SMTP Config missing. Skipping email.")
    else:
        try:
            print("\n📧 STEP 4: Sending Email...")
            msg = EmailMessage()
            msg['Subject'] = f'Hammer ROI Business Case: {company_name}'
            msg['From'] = SMTP_EMAIL
            msg['To'] = user_email
            if cc_email:
                msg['Cc'] = cc_email
            
            msg.set_content(f"Hello,\n\nPlease find the attached ROI Business Case for {company_name}.\n\nGenerated by Hammer Intelligent Consultant.\n\nNote: This is an AI-generated estimation based on public data.")
            
            with open("Hammer_ROI_Report.pdf", 'rb') as f:
                msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename="Hammer_ROI_Report.pdf")

            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
                recipients = [user_email]
                if cc_email: recipients.append(cc_email)
                smtp.send_message(msg, to_addrs=recipients)
            print("✅ Email sent successfully.")

        except Exception as e:
            print(f"❌ Email Failed: {e}")
