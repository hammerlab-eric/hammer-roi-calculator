import os
import sys
import traceback
import json
import smtplib
from email.message import EmailMessage
from fpdf import FPDF

# --- SAFETY NET WRAPPER ---
try:
    # --- IMPORTS & SETUP ---
    try:
        from langchain_openai import ChatOpenAI
        from langchain.prompts import ChatPromptTemplate
        from tavily import TavilyClient
        print("✅ Libraries imported successfully.")
    except ImportError as e:
        raise ImportError(f"Missing Library: {e}. Check requirements.txt.")

    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    SMTP_SERVER = "smtp.zoho.com"
    SMTP_PORT = 465
    SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

    # --- 1. RESEARCH AGENT ---
    def research_company(company_url, company_name):
        print(f"\n🕵️ STEP 1: Researching {company_name}...")
        if not TAVILY_API_KEY:
            return {}
        
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        query = f"Research '{company_name}' ({company_url}). Find: 1. Recent cloud migration news (Genesys, AWS, Azure). 2. Hiring for 'SRE', 'DevOps', or 'Contact Center Engineer'. 3. Estimated agent count or employee size."
        context = tavily.search(query=query, search_depth="basic") 
        return context.get('results', [])

    # --- 2. THE LOGIC CORE (The ROI Algorithms) ---
    def calculate_hammer_math(agent_count, scenario_type, playbook):
        print(f"\n🧮 STEP 2a: Running Calculations for {scenario_type}...")
        metrics = playbook['product_metrics']
        defaults = playbook['defaults']
        
        results = {
            "total_annual_savings": 0,
            "breakdown": {}
        }

        # --- A. SRE / OPERATIONS LOGIC (Hammer Edge + Ativa + VoiceWatch) ---
        if scenario_type == "operations" or scenario_type == "hybrid":
            
            # 1. Hammer Edge
            total_tickets = agent_count * defaults['tickets_per_agent_monthly']
            endpoint_tickets = total_tickets * metrics['hammer_edge']['endpoint_issue_rate']
            edge_savings = endpoint_tickets * metrics['hammer_edge']['tier1_ticket_cost'] * 12
            results['breakdown']['Hammer Edge'] = {
                "value": edge_savings,
                "narrative": f"Deflecting {int(endpoint_tickets*12):,} endpoint tickets/year (Tier 1 Support).",
                "source": metrics['hammer_edge']['source_doc']
            }

            # 2. Hammer Ativa
            war_room_savings = 12 * (metrics['hammer_ativa']['avg_war_room_staff'] * metrics['hammer_ativa']['sre_hourly_rate'] * metrics['hammer_ativa']['mtti_reduction_hours'])
            ativa_total = war_room_savings + metrics['hammer_ativa']['sla_credit_recovery_annual']
            results['breakdown']['Hammer Ativa'] = {
                "value": ativa_total,
                "narrative": "Reducing 'Mean Time to Innocence' and recovering Vendor SLA credits.",
                "source": metrics['hammer_ativa']['source_doc']
            }

            # 3. Hammer VoiceWatch
            tfn_labor_hours = (metrics['hammer_voicewatch']['tfn_count_estimate'] * metrics['hammer_voicewatch']['manual_test_time_mins_per_tfn'] * 52) / 60
            vw_savings = tfn_labor_hours * metrics['hammer_qa']['manual_test_cost_per_hour']
            results['breakdown']['Hammer VoiceWatch'] = {
                "value": vw_savings,
                "narrative": "Automating manual 'sweeps' of Toll-Free Numbers.",
                "source": metrics['hammer_voicewatch']['source_doc']
            }

        # --- B. MIGRATION / PROJECT LOGIC (Hammer Performance + QA) ---
        if scenario_type == "migration" or scenario_type == "hybrid":
            
            # 4. Hammer Performance
            perf_savings = metrics['hammer_performance']['avg_rollback_cost']
            results['breakdown']['Hammer Performance'] = {
                "value": perf_savings,
                "narrative": "Risk Avoidance: Preventing 'Day 1' Rollback & Brand Damage.",
                "source": metrics['hammer_performance']['source_doc']
            }

            # 5. Hammer QA
            manual_cost = metrics['hammer_qa']['hours_per_regression_cycle'] * metrics['hammer_qa']['manual_test_cost_per_hour'] * metrics['hammer_qa']['cycles_per_year']
            results['breakdown']['Hammer QA'] = {
                "value": manual_cost,
                "narrative": "Accelerating CI/CD by automating manual regression cycles.",
                "source": metrics['hammer_qa']['source_doc']
            }

        # Sum Totals
        results['total_annual_savings'] = sum(item['value'] for item in results['breakdown'].values())
        return results

    # --- 3. SYNTHESIS AGENT (Decision Making) ---
    def synthesize_report(research_data, user_spend, playbook):
        print("\n🧠 STEP 2b: Synthesizing Narrative...")
        
        llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, api_key=OPENAI_API_KEY)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Senior SRE Architect for Hammer."),
            ("user", """
            DATA:
            Research: {research_data}
            Playbook Scenarios: {playbook_scenarios}
            User Spend: ${user_spend}

            TASK:
            1. Analyze the research. Does this look like a 'Migration' (Cloud/Transformation keywords) or 'Operations' (Steady State)?
            2. Estimate Agent Count based on company size (Default to 750 if unknown).
            3. Generate an Executive Summary focusing on the identified scenario.

            OUTPUT JSON:
            {{
                "detected_scenario": "migration OR operations OR hybrid",
                "estimated_agent_count": 750,
                "executive_summary": "3 sentences.",
                "tech_stack_notes": "Mention specific found tech (e.g. Genesys, Avaya)."
            }}
            """)
        ])
        
        chain = prompt | llm
        res = chain.invoke({
            "research_data": str(research_data), 
            "playbook_scenarios": json.dumps(playbook['scenarios']), 
            "user_spend": str(user_spend)
        })
        
        ai_data = json.loads(res.content.replace('```json', '').replace('```', '').strip())
        
        # Run the Math based on AI's decision
        math_results = calculate_hammer_math(
            ai_data.get('estimated_agent_count', 750), 
            ai_data.get('detected_scenario', 'operations'),
            playbook
        )
        
        return {**ai_data, **math_results}

    # --- 4. PDF GENERATOR (With Citations) ---
    def create_pdf(data, company_name, filename="Hammer_ROI_Report.pdf"):
        print("\n📄 STEP 3: Generating V1.2 Report...")
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("Arial", 'B', size=20)
        pdf.cell(0, 15, txt=f"Hammer Reliability Analysis", ln=1, align='C')
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, txt=f"Prepared for: {company_name}", ln=1, align='C')
        pdf.ln(5)

        # Executive Summary
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', size=12)
        pdf.cell(0, 10, txt="1. Strategic Executive Summary", ln=1, fill=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 7, txt=data.get('executive_summary', ''))
        pdf.ln(5)

        # Tech Stack Note
        if data.get('tech_stack_notes'):
            pdf.set_font("Arial", 'I', size=10)
            pdf.cell(0, 8, txt=f"Context: {data.get('tech_stack_notes')}", ln=1)
            pdf.ln(5)

        # Financial Impact Section
        pdf.set_font("Arial", 'B', size=12)
        pdf.cell(0, 10, txt="2. Projected Financial Impact", ln=1, fill=True)
        pdf.ln(5)

        # Total Big Number
        pdf.set_font("Arial", 'B', size=16)
        pdf.set_text_color(0, 100, 0) # Green
        pdf.cell(0, 10, txt=f"Total Estimated Value: ${data['total_annual_savings']:,.2f} / Year", ln=1, align='C')
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

        # Detailed Breakdown Table
        pdf.set_font("Arial", 'B', size=11)
        pdf.cell(60, 10, txt="Hammer Solution", border=1)
        pdf.cell(40, 10, txt="Est. Savings", border=1, align='R')
        pdf.cell(90, 10, txt="Logic & Citation", border=1)
        pdf.ln()

        pdf.set_font("Arial", size=10)
        for product, details in data['breakdown'].items():
            if details['value'] > 0:
                # Calculate height for Multi-Cell logic
                # We need to print Narrative + Source in the 3rd column
                
                pdf.cell(60, 16, txt=product, border=1)
                pdf.cell(40, 16, txt=f"${details['value']:,.0f}", border=1, align='R')
                
                # Save x,y position
                x = pdf.get_x()
                y = pdf.get_y()
                
                # Print Narrative
                pdf.multi_cell(90, 8, txt=details['narrative'], border='LTR')
                
                # Move to bottom half of the cell for Source
                pdf.set_xy(x, y + 8)
                pdf.set_font("Arial", 'I', size=7)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(90, 8, txt=f"Source: {details.get('source', 'Hammer Internal')}", border='LBR', align='R')
                
                # Reset Font
                pdf.set_font("Arial", size=10)
                pdf.set_text_color(0, 0, 0)
                pdf.ln()

        pdf.ln(10)
        
        # Disclaimer
        pdf.set_font("Arial", size=8)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, txt="Disclaimer: These estimates are based on public benchmarks and standard industry assumptions provided by Hammer. Actual savings may vary based on specific environment configurations.")

        pdf.output(filename)
        print(f"✅ PDF Saved: {filename}")

    # --- MAIN EXECUTION FLOW ---
    print("--- Starting Hammer ROI V1.2.1 (Citations) ---")
    
    # Inputs
    company_name = os.environ.get("USER_NAME", "Valued Client")
    company_url = os.environ.get("USER_URL", "")
    user_email = os.environ.get("USER_EMAIL")
    raw_spend = os.environ.get("USER_SPEND", "0")
    monthly_spend = raw_spend if raw_spend and raw_spend.strip() else "0"

    # Load Playbook
    try:
        with open('src/hammer_playbook.json', 'r') as f:
            playbook = json.load(f)
    except FileNotFoundError:
        print("❌ CRITICAL: hammer_playbook.json missing.")
        exit(1)

    # Execute
    research = research_company(company_url, company_name)
    final_data = synthesize_report(research, monthly_spend, playbook)
    create_pdf(final_data, company_name)

    # Email (Standard)
    if os.environ.get("SMTP_EMAIL"):
        try:
            print("\n📧 STEP 4: Sending Email...")
            msg = EmailMessage()
            msg['Subject'] = f'Hammer Reliability Analysis: {company_name}'
            msg['From'] = SMTP_EMAIL
            msg['To'] = user_email
            msg.set_content(f"Hello,\n\nPlease find the attached Reliability Analysis for {company_name}.\n\nThis report includes analysis for Hammer Edge, Ativa, and Performance Assurance.\n\nGenerated by Hammer Intelligent Consultant.")
            
            with open("Hammer_ROI_Report.pdf", 'rb') as f:
                msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename="Hammer_ROI_Report.pdf")

            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
                smtp.send_message(msg)
            print("✅ Email sent successfully.")
        except Exception as e:
            print(f"❌ Email Failed: {e}")

    print("✅ Logic Finished Successfully.")

# --- ERROR HANDLING ---
except Exception as e:
    print(f"\n❌ CRITICAL SYSTEM ERROR: {e}")
    traceback.print_exc()
    # (Error PDF Code Omitted for brevity)
