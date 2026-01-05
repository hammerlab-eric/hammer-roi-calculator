import os
import json
import smtplib
from email.message import EmailMessage
from openai import OpenAI
from fpdf import FPDF

# --- CONFIGURATION ---
SMTP_SERVER = "smtp.zoho.com"
SMTP_PORT = 465

# 1. Setup & Environment Variables
api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# Debug: Check if key exists (Don't print the whole key!)
if api_key:
    print(f"✅ OpenAI API Key loaded (starts with {api_key[:8]}...)")
else:
    print("❌ ERROR: OpenAI API Key is MISSING.")

user_vertical = os.environ.get("USER_VERTICAL", "General Business")
user_spend = os.environ.get("USER_SPEND", "0")

# Email Handling
smtp_email = os.environ.get("SMTP_EMAIL") 
smtp_password = os.environ.get("SMTP_PASSWORD")

user_email = os.environ.get("USER_EMAIL", smtp_email)
cc_email = os.environ.get("CC_EMAIL", "") 
user_name = os.environ.get("USER_NAME", "Valued Customer")

print(f"--- Starting Hammer ROI Engine ---")
print(f"Target: {user_name}")

# 2. AI Analysis
system_prompt = f"""
You are an expert ROI analyst for Hammer. 
The user is in the {user_vertical} industry with ${user_spend}/mo spend.
Assume industry waste average is 15%.
Calculate savings and write a brief, persuasive executive summary.
Return ONLY valid JSON with this format: {{ "savings": 123.45, "justification": "text here" }}
"""

savings = 0
justification = "Manual fallback: AI service unavailable."

try:
    print("Attempting to call OpenAI (gpt-4o)...")
    # We use gpt-4o as it is the current flagship. 
    # If this fails with 404, your account might only support gpt-3.5-turbo
    response = client.chat.completions.create(
        model="gpt-4o", 
        response_format={ "type": "json_object" },
        messages=[{"role": "system", "content": system_prompt}]
    )
    
    raw_content = response.choices[0].message.content
    print(f"AI Raw Response: {raw_content}") # DEBUG: Print what AI actually said
    
    data = json.loads(raw_content)
    savings = data.get('savings', 0)
    justification = data.get('justification', "Analysis complete.")
    print("✅ AI Analysis successful.")

except Exception as e:
    print(f"❌ Error calling OpenAI: {e}")
    # OPTIONAL: Uncomment this if you want to try gpt-3.5 as a backup
    # print("Attempting fallback to gpt-3.5-turbo...")
    # ... (repeat call with gpt-3.5-turbo) ...

# 3. Generate PDF
pdf_filename = "Hammer_ROI_Report.pdf"
try:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', size=20)
    pdf.cell(0, 15, txt="Hammer ROI Analysis", ln=1, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Prepared for: {user_name}", ln=1)
    pdf.cell(0, 10, txt=f"Industry Vertical: {user_vertical}", ln=1)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', size=16)
    pdf.set_text_color(0, 100, 0)
    pdf.cell(0, 10, txt=f"Estimated Monthly Savings: ${savings:,.2f}", ln=1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 7, txt=f"Executive Summary:\n{justification}")
    pdf.output(pdf_filename)
    print(f"PDF generated: {pdf_filename}")

except Exception as e:
    print(f"Error generating PDF: {e}")
    exit(1)

# 4. Send Email via Zoho SMTP
try:
    msg = EmailMessage()
    msg['Subject'] = f'Hammer ROI Report for {user_name}'
    msg['From'] = smtp_email 
    msg['To'] = user_email
    
    if cc_email:
        msg['Cc'] = cc_email
    
    msg.set_content(f"""
    Hello {user_name},

    Thank you for using the Hammer ROI Calculator. 
    
    We have analyzed your monthly spend of ${user_spend}.
    Based on benchmarks for the {user_vertical} industry, we identified efficiency opportunities.

    Please find your detailed Executive Summary attached.

    Best regards,
    The Hammer Team
    """)

    with open(pdf_filename, 'rb') as f:
        file_data = f.read()
        file_name = f.name
        msg.add_attachment(file_data, maintype='application', subtype='pdf', filename=file_name)

    print(f"Connecting to {SMTP_SERVER}...")
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.login(smtp_email, smtp_password)
        recipients = [user_email]
        if cc_email:
            recipients.append(cc_email)
        smtp.send_message(msg) 
    
    print(f"✅ Email sent successfully.")

except Exception as e:
    print(f"❌ Failed to send email: {e}")
