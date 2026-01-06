import os
import json
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from tavily import TavilyClient

# --- CONFIGURATION ---
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# 1. THE RESEARCHER (Tavily)
def research_company(company_url, company_name):
    print(f"🕵️ Searching web for {company_name} ({company_url})...")
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    
    # We ask Tavily to find specific data points
    query = f"""
    Find the following for '{company_name}':
    1. Primary Industry/Vertical.
    2. Estimated Annual Revenue.
    3. Recent public technical failures, outages, or customer service complaints (last 2 years).
    4. Contact Center Technology Stack (e.g., Genesys, Avaya, Cisco, AWS Connect).
    """
    context = tavily.search(query=query, search_depth="advanced")
    return context['results']

# 2. THE SYNTHESIZER (LangChain)
def generate_roi_data(research_data, user_spend, playbook):
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Senior Solutions Consultant for Hammer. You map client risks to Hammer solutions."),
        ("user", """
        Based on this research: {research_data}
        And this internal Playbook: {playbook}
        And User Spend: ${user_spend}
        
        1. Identify the client's Vertical.
        2. Select the matching 'avg_downtime_cost_per_min' from the Playbook.
        3. Calculate 'Estimated Risk Exposure' (Cost * 60 mins * 12 months * 0.01 probability).
        4. Generate a persuasive Executive Summary linking their specific news/stack to Hammer solutions.
        
        Return JSON: {{ "vertical": "X", "stack": "Y", "risk_cost": 0.00, "summary": "Text" }}
        """)
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "research_data": research_data, 
        "playbook": json.dumps(playbook),
        "user_spend": user_spend
    })
    
    return json.loads(response.content)

# 3. MAIN EXECUTION FLOW
def main():
    # Load Inputs (now including URL)
    company_name = os.environ.get("USER_COMPANY_NAME")
    company_url = os.environ.get("USER_URL") 
    monthly_spend = os.environ.get("USER_SPEND", "5000") # Fallback if unknown
    
    # Load Playbook
    with open('src/hammer_playbook.json', 'r') as f:
        playbook = json.load(f)

    # A. Execute Research
    raw_research = research_company(company_url, company_name)
    
    # B. Synthesize Data
    roi_analysis = generate_roi_data(raw_research, monthly_spend, playbook)
    
    # C. Generate PDF (Updated to include Research findings)
    create_pdf(roi_analysis, company_name)
    
    # D. Send Email
    send_email(roi_analysis)

# ... (PDF and Email functions remain similar to V1.0 but use new variables)
