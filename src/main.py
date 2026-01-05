import os
import json
import smtplib
from email.message import EmailMessage
from openai import OpenAI
from fpdf import FPDF

# 1. Setup
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Retrieve Environment Variables
user_vertical = os.environ.get("USER_VERTICAL", "General Business")
user_spend = os.environ.get("USER_SPEND", "0")
user_email = os.environ.get("USER_EMAIL", "test@example.com")
user_name = os.environ.get("USER_NAME", "Valued Customer")

smtp_email = os.environ.get("SMTP_EMAIL")
smtp_password = os.environ.get("SMTP_PASSWORD")

print(f"Starting ROI calculation for {user_email} in {user_vertical}...")

# 2. The Logic (OpenAI)
system_prompt = f"""
You are an expert ROI analyst for Hammer. 
The user is in the {user_vertical} industry with ${user_spend}/mo spend.
Assume industry waste average is 15%.
Calculate savings and write a brief justification.
Return ONLY valid JSON: {{ "savings": "number (just the value)", "justification": "short text" }}
"""

try:
    response = client.chat.completions.create(
        model="gpt-4-turbo",  # Or gpt-3.5-turbo if you want to save cost
        response_format={ "type": "json_object" },
        messages=[{"role": "system", "content": system_prompt}]
    )
    data = json.loads(response.choices[0].message.content)
    savings = data.get('savings', 0)
    justification = data.get('justification', "Analysis complete.")
    print("AI Analysis complete.")

except Exception as e:
    print(f"Error calling OpenAI: {e}")
    # Fallback data if AI fails
    savings = 100
    justification = "Manual fallback: AI service unavailable."

# 3. Generate PDF
pdf_filename = "Hammer_ROI_Report.pdf"
pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=16)
pdf.cell(200, 10, txt="Hammer ROI Analysis", ln=1, align='C')
pdf.ln(10)
pdf.set_font("Arial", size=12)
pdf.cell(200, 10, txt=f"Prepared for: {user_name}", ln=1)
pdf.cell(200, 10, txt=f"Estimated Monthly Savings: ${savings}", ln=1)
pdf.ln(5)
pdf.multi_cell(0, 10, txt=f"Analysis:\n{justification}")
pdf.output(pdf_filename)
print("PDF generated.")

# 4. Email Delivery (SMTP via Zoho)
msg = EmailMessage()
msg['Subject'] = 'Your Hammer ROI Report'
msg['From'] = smtp_email
msg['To'] = user_email
msg.set_content(f"Hello {user_name},\n\nPlease find your ROI report attached.\n\nBest,\nThe Hammer Team")

# Attach PDF
with open(pdf_filename, 'rb') as f:
    file_data = f.read()
    file_name = f.name
    msg.add_attachment(file_data, maintype='application', subtype='pdf', filename=file_name)

try:
    # Zoho SMTP Settings (works for free accounts)
    # Server: smtp.zoho.com, Port: 465, SSL
    with smtplib.SMTP_SSL('smtp.zoho.com', 465) as smtp:
        smtp.login(smtp_email, smtp_password)
        smtp.send_message(msg)
    print(f"Email sent successfully to {user_email}")
except Exception as e:
    print(f"Failed to send email: {e}")
