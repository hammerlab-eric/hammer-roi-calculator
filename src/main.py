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
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

user_vertical = os.environ.get("USER_VERTICAL", "General Business")
user_spend = os.environ.get("USER_SPEND", "0")
# Default to your own email if the form didn't provide one, for safety in testing
user_email = os.environ.get("USER_EMAIL", os.environ.get("SMTP_EMAIL"))
user_name = os.environ.get("USER_NAME", "Valued Customer")

smtp_email = os.environ.get("SMTP_EMAIL")
smtp_password = os.environ.get("SMTP_PASSWORD")

print(f"--- Starting Hammer ROI Engine ---")
print(f"Target: {user_name} ({user_email})")
print(f"Vertical: {user_vertical}")

# 2. AI Analysis (OpenAI)
system_prompt = f"""
You are an expert ROI analyst for Hammer. 
The user is in the {user_vertical} industry with ${user_spend}/mo spend.
Assume industry waste average is 15%.
Calculate savings and write a brief, persuasive executive summary.
Return ONLY valid JSON: {{ "savings": "number (just the value)", "justification": "short text" }}
"""

savings = 0
justification = "Manual fallback: AI service unavailable."

try:
    response = client.chat.completions.create(
        model="gpt-4-turbo", 
        response_format={ "type": "json_object" },
        messages=[{"role": "system", "content": system_prompt}]
    )
    data = json.loads(response.choices[0].message.content)
    savings = data.get('savings', 0)
    justification = data.get('justification', "Analysis complete.")
    print("AI Analysis successful.")
except Exception as e:
    print(f"Error calling OpenAI: {e}")

# 3. Generate PDF Report
pdf_filename = "Hammer_ROI_Report.pdf"
try:
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", 'B', size=20)
    pdf.cell(0, 15, txt="Hammer ROI Analysis", ln=1, align='C')
    pdf.ln(10)
    
    # Details
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Prepared for: {user_name}", ln=1)
    pdf.cell(0, 10, txt=f"Industry Vertical: {user_vertical}", ln=1)
    pdf.ln(5)
    
    # The Big Number
    pdf.set_font("Arial", 'B', size=16)
    pdf.set_text_color(0, 100, 0) # Dark Green
    pdf.cell(0, 10, txt=f"Estimated Monthly Savings: ${savings:,.2f}", ln=1)
    pdf.set_text_color(0, 0, 0) # Reset to black
    pdf.ln(5)
    
    # Narrative
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 7, txt=f"Executive Summary:\n{justification}")
    
    pdf.output(pdf_filename)
    print(f"PDF generated: {pdf_filename}")

except Exception as e:
    print(f"Error generating PDF: {e}")
    exit(1) # Fail the action if PDF fails

# 4. Send Email via Zoho SMTP
try:
    msg = EmailMessage()
    msg['Subject'] = f'Hammer ROI Report for {user_name}'
    msg['From'] = smtp_email
    msg['To'] = user_email
    
    # Email Body
    msg.set_content(f"""
    Hello {user_name},

    Thank you for using the Hammer ROI Calculator. 
    Based on your vertical ({user_vertical}), we have identified potential efficiency gains.

    Please find your detailed Executive Summary attached.

    Best regards,
    The Hammer Team
    """)

    # Attach PDF
    with open(pdf_filename, 'rb') as f:
        file_data = f.read()
        file_name = f.name
        msg.add_attachment(file_data, maintype='application', subtype='pdf', filename=file_name)

    # Send
    print(f"Connecting to {SMTP_SERVER}...")
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.login(smtp_email, smtp_password)
        smtp.send_message(msg)
    
    print(f"✅ Email sent successfully to {user_email}")

except Exception as e:
    print(f"❌ Failed to send email: {e}")
    # We do NOT exit(1) here because we still want the artifact to upload if email fails
